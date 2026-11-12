from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from typing import Literal
from zoneinfo import ZoneInfo
import csv
import secrets
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User, Connection, Post, Observation, AccountObservation, Alert, Monitor, Audit, SyncRun, now
from .security import current_user, admin, editor, password_hash, issue, encrypt
from .analytics import rows, summarize

@asynccontextmanager
async def lifespan(app):
    # Schema changes are applied by Alembic, never silently at application startup.
    from .db import Session
    with Session() as db:
        if not db.scalar(select(User).where(User.email == settings().admin_email)):
            db.add(User(email=settings().admin_email, password=password_hash.hash(settings().admin_password), role='admin'))
            try:db.commit()
            except IntegrityError:db.rollback() # Another API worker completed bootstrap.
    yield

app = FastAPI(title='CNE Social Intelligence', version='0.1.0', lifespan=lifespan)
from .public import router as public_router
app.include_router(public_router)
app.add_middleware(CORSMiddleware, allow_origins=[settings().frontend_origin], allow_credentials=True, allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['Content-Type','X-CSRF-Token'])

@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Frame-Options'] = 'DENY'
    return response

@app.get('/health')
def health(): return {'status':'ok'}

class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=512)

@app.post('/auth/login')
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    if request.headers.get('origin') != settings().frontend_origin:
        raise HTTPException(403, 'Origen no permitido')
    # Shared Redis limiter is mandatory; fail closed when unavailable.
    import redis
    try:
        r = redis.Redis.from_url(settings().redis_url, socket_connect_timeout=2, socket_timeout=2)
        key = 'login:' + (request.client.host if request.client else 'unknown')
        with r.pipeline() as pipe:
            count, _ = pipe.incr(key).expire(key, 300).execute()
        if count > 20:
            raise HTTPException(429, 'Demasiados intentos; espera 5 minutos')
    except redis.RedisError:
        raise HTTPException(503, 'Servicio de autenticación no disponible')
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not user.active or not password_hash.verify(body.password, user.password):
        raise HTTPException(401, 'Credenciales incorrectas')
    response.set_cookie('session', issue(user), httponly=True, secure=settings().cookie_secure, samesite='lax', max_age=28800)
    response.set_cookie('csrf', secrets.token_urlsafe(32), secure=settings().cookie_secure, samesite='lax', max_age=28800)
    db.add(Audit(user_id=user.id, action='login', target=str(user.id))); db.commit()
    return {'email':user.email, 'role':user.role}

@app.post('/auth/logout')
def logout(response: Response, user=Depends(current_user)):
    response.delete_cookie('session'); response.delete_cookie('csrf')
    return {'ok':True}

@app.get('/auth/me')
def me(user=Depends(current_user)):
    return {'email':user.email, 'role':user.role, 'demo':settings().demo_mode, 'timezone':settings().timezone}

class ConnectionInput(BaseModel):
    platform: Literal['facebook','instagram','x','tiktok']
    external_id: str = Field(min_length=1, max_length=120, pattern=r'^[a-zA-Z0-9_\-]+$')
    name: str = Field(min_length=1, max_length=180)
    category: str = Field(default='Institución', max_length=80)
    access: Literal['owned','public','unavailable'] = 'owned'
    token: str | None = Field(default=None, max_length=8192)
    scopes: list[str] = Field(default_factory=list, max_length=50)
    expires_at: datetime | None = None
    interval_minutes: int = Field(default=60, ge=5, le=10080)

def public_connection(c):
    return {k:getattr(c,k) for k in ['id','platform','external_id','name','category','access','status','scopes','expires_at','last_sync','interval_minutes','error','publish_enabled']}

class PublicationUpdate(BaseModel):
    enabled:bool

@app.patch('/connections/{id}/publication')
def publication(id:int,body:PublicationUpdate,user=Depends(admin),db:Session=Depends(get_db)):
    from .public import invalidate_public
    c=db.get(Connection,id)
    if not c:raise HTTPException(404)
    if settings().demo_mode:raise HTTPException(409,'No se publica el entorno DEMO')
    invalidate_public() # Fail closed before changing visibility if Redis is unavailable.
    c.publish_enabled=body.enabled
    db.add(Audit(user_id=user.id,action='publish_account' if body.enabled else 'withdraw_account',target=str(id)))
    db.commit()
    invalidate_public() # Invalidate snapshots produced during the transaction.
    return public_connection(c)

@app.get('/connections')
def connections(user=Depends(current_user), db: Session=Depends(get_db)):
    return [public_connection(c) for c in db.scalars(select(Connection).order_by(Connection.name))]

@app.post('/connections', status_code=201)
def create_connection(body:ConnectionInput, user=Depends(admin), db:Session=Depends(get_db)):
    data = body.model_dump(exclude={'token'})
    c = Connection(**data, encrypted_token=encrypt(body.token) if body.token and body.access != 'unavailable' else None, status='pending')
    db.add(c)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Esta cuenta ya está registrada')
    db.add(Audit(user_id=user.id, action='create_connection', target=str(c.id))); db.commit()
    return public_connection(c)

class CredentialUpdate(BaseModel):
    token: str = Field(min_length=1, max_length=8192)
    scopes: list[str] = Field(default_factory=list, max_length=50)
    expires_at: datetime | None = None

@app.patch('/connections/{id}/credentials')
def update_credentials(id:int, body:CredentialUpdate, user=Depends(admin), db:Session=Depends(get_db)):
    c = db.get(Connection,id)
    if not c: raise HTTPException(404)
    c.encrypted_token, c.scopes, c.expires_at, c.status, c.error = encrypt(body.token), body.scopes, body.expires_at, 'pending', None
    db.add(Audit(user_id=user.id,action='rotate_token',target=str(id))); db.commit()
    return public_connection(c)

@app.delete('/connections/{id}')
def disconnect(id:int, user=Depends(admin), db:Session=Depends(get_db)):
    c=db.get(Connection,id)
    if not c: raise HTTPException(404)
    c.encrypted_token, c.status, c.cursor = None, 'disabled', {}
    db.add(Audit(user_id=user.id,action='disconnect',target=str(id))); db.commit()
    return {'ok':True}

@app.post('/connections/{id}/sync', status_code=202)
def sync(id:int, user=Depends(editor), db:Session=Depends(get_db)):
    c = db.get(Connection,id)
    if not c: raise HTTPException(404)
    if not c.encrypted_token or c.status == 'disabled': raise HTTPException(409, 'Conexión pendiente de autorización')
    try:
        from .tasks import sync_connection
        task = sync_connection.delay(id)
    except Exception: raise HTTPException(503, 'Cola de sincronización no disponible')
    db.add(Audit(user_id=user.id,action='request_sync',target=str(id))); db.commit()
    return {'task_id':task.id, 'status':'queued'}

class Filters(BaseModel):
    start: date | None = None
    end: date | None = None
    platform: Literal['facebook','instagram','x','tiktok'] | None = None
    account: int | None = None
    keyword: str | None = Field(default=None,max_length=200)
    format: str | None = Field(default=None,max_length=30)
    topic: str | None = Field(default=None,max_length=100)

def filtered(f,db):
    today = datetime.now(ZoneInfo(settings().timezone)).date()
    end, start = f.end or today, f.start or today-timedelta(days=29)
    if end < start or (end-start).days>366:
        raise HTTPException(422,'Rango inválido; máximo 366 días')
    return rows(db,start,end,f.platform,f.account,f.keyword,f.format,f.topic), start,end

@app.get('/posts')
def posts(f:Filters=Depends(),user=Depends(current_user),db:Session=Depends(get_db)):
    data,a,b=filtered(f,db)
    return {'items':data,'limit':1000,'possibly_truncated':len(data)==1000}

@app.get('/dashboard')
def dashboard(f:Filters=Depends(),user=Depends(current_user),db:Session=Depends(get_db)):
    data,a,b=filtered(f,db)
    duration=(b-a).days+1
    previous=rows(db,a-timedelta(days=duration),a-timedelta(days=1),f.platform,f.account,f.keyword,f.format,f.topic)
    result=summarize(data)
    result['previous']=summarize(previous)
    result['followers']=[]
    for c in db.scalars(select(Connection)):
        if f.platform and c.platform!=f.platform or f.account and c.id!=f.account: continue
        obs=db.scalar(select(AccountObservation).where(AccountObservation.connection_id==c.id).order_by(AccountObservation.captured_at.desc(),AccountObservation.id.desc()))
        result['followers'].append({'account':c.name,'platform':c.platform,'followers':obs.metrics.get('followers') if obs else None,'captured_at':obs.captured_at if obs else None})
    result.update({'demo':settings().demo_mode,'timezone':settings().timezone,'start':a,'end':b,'possibly_truncated':len(data)==1000,'top_posts':sorted(data,key=lambda r:r['interactions'] if r['interactions'] is not None else -1,reverse=True)[:5]})
    return result

@app.get('/posts/{id}')
def post_detail(id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(Post,id)
    if not p:raise HTTPException(404)
    return {'id':p.id,'text':p.text,'url':p.url,'platform':p.platform,'sentiment':p.sentiment,'topic':p.topic,'history':[{'captured_at':o.captured_at,'metrics':o.metrics,'source':o.source} for o in db.scalars(select(Observation).where(Observation.post_id==id).order_by(Observation.captured_at).limit(500))]}

@app.get('/alerts')
def alerts(user=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':a.id,'kind':a.kind,'message':a.message,'created_at':a.created_at,'read':a.read} for a in db.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(100))]

@app.patch('/alerts/{id}/read')
def read_alert(id:int,user=Depends(editor),db:Session=Depends(get_db)):
    a=db.get(Alert,id)
    if not a:raise HTTPException(404)
    a.read=True;db.commit();return {'ok':True}

class MonitorInput(BaseModel):
    term:str=Field(min_length=2,max_length=200)
    platform:Literal['facebook','instagram','x','tiktok']

@app.get('/monitors')
def monitors(user=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':m.id,'term':m.term,'platform':m.platform,'coverage':'Solo publicaciones almacenadas; búsqueda pública remota pendiente de habilitación'} for m in db.scalars(select(Monitor))]

@app.post('/monitors',status_code=201)
def add_monitor(body:MonitorInput,user=Depends(editor),db:Session=Depends(get_db)):
    m=Monitor(**body.model_dump());db.add(m);db.flush()
    db.add(Audit(user_id=user.id,action='create_monitor',target=str(m.id)));db.commit()
    return {'id':m.id,'coverage':'local'}

@app.get('/sync-runs')
def sync_runs(user=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':r.id,'connection_id':r.connection_id,'status':r.status,'count':r.count,'message':r.message,'started_at':r.started_at} for r in db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(100))]

@app.get('/audit')
def audit(user=Depends(admin),db:Session=Depends(get_db)):
    return [{'action':a.action,'target':a.target,'created_at':a.created_at,'user_id':a.user_id} for a in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100))]

class NewUser(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=12,max_length=512)
    role:Literal['admin','analyst','viewer']='viewer'

@app.post('/users',status_code=201)
def add_user(body:NewUser,user=Depends(admin),db:Session=Depends(get_db)):
    u=User(email=body.email,password=password_hash.hash(body.password),role=body.role);db.add(u)
    try:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Usuario existente')
    db.add(Audit(user_id=user.id,action='create_user',target=str(u.id)));db.commit()
    return {'id':u.id,'email':u.email,'role':u.role}

def safe_cell(value):
    s=str(value) if value is not None else ''
    return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s

@app.get('/export/{kind}')
def export(kind:Literal['csv','xlsx','pdf'],f:Filters=Depends(),user=Depends(current_user),db:Session=Depends(get_db)):
    data,a,b=filtered(f,db)
    columns=['Plataforma','Cuenta','Fecha','Texto','Formato','Interacciones','Enlace']
    values=[[r['platform'],r['account'],r['published_at'],r['text'],r['format'],r['interactions'],r['url']] for r in data]
    if kind=='csv':
        stream=StringIO();writer=csv.writer(stream);writer.writerow(columns);writer.writerows([[safe_cell(c) for c in row] for row in values]);content=stream.getvalue().encode('utf-8-sig');mime='text/csv'
    elif kind=='xlsx':
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='Publicaciones';ws.append(columns)
        for row in values:ws.append([safe_cell(c) if isinstance(c,str) else c for c in row])
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
        stream=BytesIO();wb.save(stream);content=stream.getvalue();mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from xml.sax.saxutils import escape
        stream=BytesIO();styles=getSampleStyleSheet();summary=summarize(data)
        story=[Paragraph('Social Intelligence | CNE',styles['Title']),Paragraph(f'{a} a {b} · {settings().timezone}',styles['Normal']),Spacer(1,16),Paragraph(f'Publicaciones: {len(data)}. Interacciones observadas: {summary["interactions"] if summary["interactions"] is not None else "No disponibles"}.',styles['Normal']),Paragraph('Metodología: últimas observaciones disponibles de publicaciones del período. Hasta 1.000 registros. Interacciones definidas por plataforma; alcance y visualizaciones no se suman entre redes. Sentimiento no calculado en este MVP.',styles['Normal'])]
        for row in values:story.extend([Spacer(1,10),Paragraph(escape(f'{row[0]} · {row[1]} · {row[2]}'),styles['Heading3']),Paragraph(escape(str(row[3])),styles['Normal'])])
        SimpleDocTemplate(stream).build(story);content=stream.getvalue();mime='application/pdf'
    db.add(Audit(user_id=user.id,action='export_'+kind,target=f'{a}/{b}'));db.commit()
    return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="social-intelligence.{kind}"'})
