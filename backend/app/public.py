"""Anonymous read-only API. Never imports a connector or queues provider requests."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import time
from typing import Literal
from urllib.parse import urlsplit,urlunsplit
from zoneinfo import ZoneInfo
import redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Connection,Post,Observation,AccountObservation
from .analytics import rows,summarize

router=APIRouter(prefix='/public',tags=['Consulta ciudadana'])
HOSTS={'facebook':'graph.facebook.com','instagram':'graph.facebook.com','x':'api.x.com','tiktok':'open.tiktokapis.com'}
LIMIT=5000
METRICS={'likes','reactions','comments','shares','reposts','quotes','views'}
METHODOLOGY='Se seleccionan publicaciones por fecha en America/Bogota y se usa su última captura. Las interacciones conservan la definición de cada red; no representan personas únicas ni actividad ocurrida ese día. Ausencia de métrica significa no disponible. No hay cobertura completa de la conversación pública.'

def redis_client():
    return redis.Redis.from_url(settings().redis_url,decode_responses=True,socket_connect_timeout=2,socket_timeout=2)

def public_context(request:Request):
    if settings().demo_mode:
        raise HTTPException(404,'El entorno DEMO no publica información ciudadana')
    try:
        r=redis_client()
        # Trust only ASGI client address. Production proxy overwrites the forwarding chain.
        identity=sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()[:24]
        key=f'public:rate:{identity}:{int(time.time())//60}'
        with r.pipeline() as pipe:
            count,_=pipe.incr(key).expire(key,65).execute()
        if count>settings().public_requests_per_minute:
            raise HTTPException(429,'Límite de consultas; reintenta en un minuto',headers={'Retry-After':'60'})
        revision=r.get('public:revision') or '0'
        return r,str(revision)
    except redis.RedisError:
        raise HTTPException(503,'Consulta pública temporalmente no disponible')

def cache_result(context,request,response,build):
    r,revision=context
    # Canonicalize query order, never include cookies or user data.
    identity=request.url.path+'?'+str(sorted(request.query_params.multi_items()))
    key='public:v2:'+revision+':'+sha256(identity.encode()).hexdigest()
    try:
        cached=r.get(key)
        if cached:
            response.headers['X-Data-Cache']='HIT'
            return json.loads(cached)
        result=jsonable_encoder(build())
        r.setex(key,settings().public_cache_seconds,json.dumps(result,ensure_ascii=False))
        response.headers['X-Data-Cache']='MISS'
        # Browser caching remains disabled so withdrawal takes effect on the next request.
        return result
    except redis.RedisError:
        raise HTTPException(503,'Consulta pública temporalmente no disponible')

def invalidate_public():
    try:redis_client().incr('public:revision')
    except redis.RedisError:raise HTTPException(503,'Caché no disponible; no se puede cambiar la publicación')

def source_url(source,platform):
    if not source:return None
    try:
        p=urlsplit(source)
        if p.scheme!='https' or p.hostname!=HOSTS.get(platform) or p.username or p.password:return None
        return urlunsplit(('https',p.hostname,p.path,'',''))
    except ValueError:return None

def utc_iso(value):
    if value is None:return None
    if not value.tzinfo:value=value.replace(tzinfo=timezone.utc)
    return value.isoformat()

def clean_post(p):
    # Explicit public schema; never serialize ORM connections or provider bodies.
    out={k:p[k] for k in ['id','platform','account','account_id','text','url','format','published_at','topic','sentiment','interactions','captured_at']}
    out['source']=source_url(p.get('source'),p['platform'])
    out['published_at']=utc_iso(datetime.fromisoformat(out['published_at']))
    out['captured_at']=utc_iso(datetime.fromisoformat(out['captured_at'])) if out['captured_at'] else None
    out['metrics']={k:v for k,v in p['metrics'].items() if k in METRICS and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0}
    return out

class PublicFilters(BaseModel):
    start:date|None=None
    end:date|None=None
    platform:Literal['facebook','instagram','x','tiktok']|None=None
    account:int|None=Field(default=None,ge=1)
    keyword:str|None=Field(default=None,max_length=100)
    format:str|None=Field(default=None,max_length=30)
    topic:str|None=Field(default=None,max_length=100)

def dates(f):
    today=datetime.now(ZoneInfo(settings().timezone)).date()
    a,b=f.start or today-timedelta(days=29),f.end or today
    if b<a or (b-a).days>366:raise HTTPException(422,'Rango inválido; máximo 366 días')
    return a,b

def public_rows(db,f,limit,offset=0,start=None,end=None):
    a,b=dates(f)
    return rows(db,start or a,end or b,f.platform,f.account,f.keyword,f.format,f.topic,published_only=True,limit=limit,offset=offset)

def account_data(db,f=None):
    ranked=select(AccountObservation.connection_id,AccountObservation.captured_at,AccountObservation.metrics,AccountObservation.source,func.row_number().over(partition_by=AccountObservation.connection_id,order_by=(AccountObservation.captured_at.desc(),AccountObservation.id.desc())).label('rank')).subquery()
    q=select(Connection,ranked.c.captured_at,ranked.c.metrics,ranked.c.source).outerjoin(ranked,(ranked.c.connection_id==Connection.id)&(ranked.c.rank==1)).where(Connection.publish_enabled.is_(True))
    if f and f.platform:q=q.where(Connection.platform==f.platform)
    if f and f.account:q=q.where(Connection.id==f.account)
    accounts=[]
    for c,captured,m,source in db.execute(q.order_by(Connection.name).limit(200)):
        legitimate=source_url(source,c.platform)
        accounts.append({'id':c.id,'account':c.name,'name':c.name,'platform':c.platform,'category':c.category,'last_update':utc_iso(c.last_sync),'captured_at':utc_iso(captured) if legitimate else None,'followers':m.get('followers') if m and legitimate else None,'source':legitimate})
    return accounts

@router.get('/accounts')
def accounts(request:Request,response:Response,context=Depends(public_context),db:Session=Depends(get_db)):
    return cache_result(context,request,response,lambda:{'items':account_data(db),'limit':200})

@router.get('/dashboard')
def dashboard(request:Request,response:Response,f:PublicFilters=Depends(),context=Depends(public_context),db:Session=Depends(get_db)):
    a,b=dates(f)
    def build():
        raw=public_rows(db,f,LIMIT+1)
        truncated=len(raw)>LIMIT
        data=[clean_post(p) for p in raw[:LIMIT]]
        duration=(b-a).days+1
        prev_raw=public_rows(db,f,LIMIT+1,start=a-timedelta(days=duration),end=a-timedelta(days=1))
        result=summarize(data)
        previous=summarize([clean_post(p) for p in prev_raw[:LIMIT]])
        ac=account_data(db,f)
        captures=[p['captured_at'] for p in data if p['captured_at']]
        result.update({'previous':previous,'followers':ac,'top_posts':sorted(data,key=lambda p:p['interactions'] if p['interactions'] is not None else -1,reverse=True)[:5], 'possibly_truncated':truncated,'previous_truncated':len(prev_raw)>LIMIT,'limit':LIMIT,'start':a,'end':b,'timezone':settings().timezone,'last_capture':max(captures) if captures else None,'generated_at':datetime.now(timezone.utc),'cache_seconds':settings().public_cache_seconds,'methodology':METHODOLOGY,'coverage':{'published_accounts':len(ac),'platforms_with_data':sorted({p['platform'] for p in data}),'measured_posts':result['measured_posts'],'observed_posts':len(data),'complete':not truncated,'status':'partial' if truncated else 'available' if data else 'no_authorized_data'},'demo':False})
        return result
    return cache_result(context,request,response,build)

@router.get('/posts')
def posts(request:Request,response:Response,f:PublicFilters=Depends(),page:int=Query(default=1,ge=1,le=200),page_size:int=Query(default=25,ge=1,le=100),context=Depends(public_context),db:Session=Depends(get_db)):
    dates(f)
    def build():
        data=public_rows(db,f,page_size+1,(page-1)*page_size)
        return {'items':[clean_post(p) for p in data[:page_size]],'page':page,'page_size':page_size,'has_more':len(data)>page_size,'methodology':METHODOLOGY}
    return cache_result(context,request,response,build)

@router.get('/posts/{id}')
def detail(id:int,request:Request,response:Response,page:int=Query(default=1,ge=1,le=200),context=Depends(public_context),db:Session=Depends(get_db)):
    # Recheck publication before cache lookup, including for a previously cached detail.
    p=db.scalar(select(Post).join(Connection).where(Post.id==id,Connection.publish_enabled.is_(True)))
    if not p:raise HTTPException(404,'Publicación no disponible')
    def build():
        observations=list(db.scalars(select(Observation).where(Observation.post_id==id).order_by(Observation.captured_at.desc(),Observation.id.desc()).offset((page-1)*50).limit(51)))
        history=[{'captured_at':utc_iso(o.captured_at),'source':source_url(o.source,p.platform),'metrics':{k:v for k,v in o.metrics.items() if k in METRICS and isinstance(v,(int,float)) and math.isfinite(v) and v>=0}} for o in observations[:50] if source_url(o.source,p.platform)]
        if not history:raise HTTPException(404,'Sin observaciones oficiales publicables')
        return {'id':p.id,'platform':p.platform,'text':p.text,'url':p.url,'sentiment':p.sentiment,'topic':p.topic,'history':history,'page':page,'has_more':len(observations)>50,'methodology':METHODOLOGY}
    return cache_result(context,request,response,build)
