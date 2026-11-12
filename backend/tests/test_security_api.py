from fastapi.testclient import TestClient
from app.main import app,safe_cell
from app.models import User,Connection
from app.security import issue,encrypt,decrypt,password_hash

def test_unauthenticated_is_blocked():
    with TestClient(app) as c:assert c.get('/dashboard').status_code==401

def test_empty_dashboard_has_no_fake_metrics(client):
    r=client.get('/dashboard');assert r.status_code==200
    assert r.json()['posts']==0 and r.json()['interactions'] is None
    assert r.json()['followers']==[] and r.json()['reach'] is None

def test_tokens_encrypted_and_never_returned(client,db):
    r=client.post('/connections',json={'platform':'x','external_id':'123','name':'Prueba','token':'secret-access-token'})
    assert r.status_code==201
    assert 'secret-access-token' not in r.text and 'encrypted_token' not in r.text
    c=db.query(Connection).one();assert c.encrypted_token!='secret-access-token'
    assert decrypt(c.encrypted_token)=='secret-access-token'
    assert 'secret-access-token' not in client.get('/connections').text

def test_duplicate_connection_returns_conflict(client):
    body={'platform':'x','external_id':'1','name':'Prueba'}
    assert client.post('/connections',json=body).status_code==201
    assert client.post('/connections',json=body).status_code==409

def test_csrf_and_origin(client):
    client.headers['x-csrf-token']='bad'
    assert client.post('/monitors',json={'term':'CNE','platform':'x'}).status_code==403
    client.headers['x-csrf-token']='test-csrf';client.headers['origin']='https://attacker.example'
    assert client.post('/monitors',json={'term':'CNE','platform':'x'}).status_code==403

def test_viewer_cannot_write(client,db):
    u=User(email='viewer@test.local',role='viewer',password=password_hash.hash('test-password-123'));db.add(u);db.commit()
    client.cookies.set('session',issue(u))
    assert client.post('/connections',json={'platform':'x','external_id':'1','name':'Prueba'}).status_code==403
    assert client.get('/audit').status_code==403

def test_invalid_id_and_range(client):
    assert client.post('/connections',json={'platform':'x','external_id':'../me','name':'Prueba'}).status_code==422
    assert client.get('/dashboard?start=2026-11-12&end=2026-10-01').status_code==422
    assert client.get('/dashboard?start=2020-01-01&end=2026-01-01').status_code==422

def test_disconnect_removes_token(client,db):
    c=Connection(platform='x',external_id='1',name='A',encrypted_token=encrypt('token'));db.add(c);db.commit()
    assert client.delete('/connections/'+str(c.id)).status_code==200
    db.refresh(c);assert c.encrypted_token is None and c.status=='disabled'

def test_missing_credentials_cannot_sync(client):
    r=client.post('/connections',json={'platform':'x','external_id':'1','name':'A'})
    assert client.post(f'/connections/{r.json()["id"]}/sync').status_code==409

def test_exports_and_formula_injection(client):
    for kind,mime in [('csv','text/csv'),('xlsx','application/vnd.openxmlformats'),('pdf','application/pdf')]:
        r=client.get('/export/'+kind);assert r.status_code==200 and mime in r.headers['content-type']
    for value in ['=HYPERLINK("x")',' +1','@SUM(A1)','\t=1']:
        assert safe_cell(value).startswith("'")

def test_openapi(client):
    r=client.get('/openapi.json');assert r.status_code==200
    assert '/connections/{id}/sync' in r.json()['paths']

def test_login_sets_http_only_cookie_and_real_session(monkeypatch):
    class Pipeline:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def incr(self,*args):return self
        def expire(self,*args):return self
        def execute(self):return [1,True]
    class Redis:
        def pipeline(self):return Pipeline()
    monkeypatch.setattr('redis.Redis.from_url',lambda *a,**k:Redis())
    with TestClient(app) as c:
        c.headers['origin']='http://localhost:3000'
        assert c.post('/auth/login',json={'email':'admin@test.local','password':'bad'}).status_code==401
        r=c.post('/auth/login',json={'email':'admin@test.local','password':'test-admin-password-1234'})
        assert r.status_code==200 and 'HttpOnly' in r.headers.get_list('set-cookie')[0]
        assert c.get('/auth/me').json()['role']=='admin'
        c.headers['x-csrf-token']=c.cookies['csrf']
        assert c.post('/auth/logout').status_code==200
        assert c.get('/auth/me').status_code==401

def test_login_fails_closed_without_limiter(monkeypatch):
    import redis
    def broken(*args,**kwargs):raise redis.ConnectionError('not available')
    monkeypatch.setattr('redis.Redis.from_url',broken)
    with TestClient(app) as c:
        r=c.post('/auth/login',headers={'origin':'http://localhost:3000'},json={'email':'admin@test.local','password':'test-admin-password-1234'})
        assert r.status_code==503
