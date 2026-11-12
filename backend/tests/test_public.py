from datetime import datetime,timezone
import json
import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import event
from app.main import app
from app.db import engine
from app.models import Connection,Post,Observation,AccountObservation,User
from app.security import encrypt,issue,password_hash
from app.config import settings

class Cache:
    def __init__(self):self.data={};self.calls=0
    def get(self,k):return self.data.get(k)
    def setex(self,k,ttl,v):self.data[k]=v
    def incr(self,k):self.data[k]=int(self.data.get(k,0))+1;return self.data[k]
    def pipeline(self):return Pipeline(self)
class Pipeline:
    def __init__(self,cache):self.cache=cache
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def incr(self,k):return self
    def expire(self,*a):return self
    def execute(self):self.cache.calls+=1;return [self.cache.calls,True]

@pytest.fixture
def cache(monkeypatch):
    c=Cache();monkeypatch.setattr('app.public.redis_client',lambda:c);return c

def insert(db,published=True,synthetic=False):
    c=Connection(platform='x',external_id=str(db.query(Connection).count()+1),name='Cuenta visible' if published else 'Cuenta interna',publish_enabled=published,encrypted_token=encrypt('NEVER_PUBLIC_TOKEN'),scopes=['secret_scope'],error='INTERNAL_ERROR',last_sync=datetime(2026,11,12,12,tzinfo=timezone.utc))
    db.add(c);db.flush()
    for i in range(3):
        p=Post(connection_id=c.id,platform='x',external_id=f'{c.external_id}-{i}',text='Contenido oficial' if published else 'CONTENIDO_INTERNO',url='https://x.com/i/status/1',format='text',published_at=datetime(2026,11,12,12,tzinfo=timezone.utc));db.add(p);db.flush()
        db.add(Observation(post_id=p.id,source='synthetic-demo' if synthetic else 'https://api.x.com/2/users/1/tweets',metrics={'likes':3,'comments':2,'reposts':1,'quotes':0,'private_metric':999}))
    db.add(AccountObservation(connection_id=c.id,source='https://api.x.com/2/users/1',metrics={'followers':10}))
    db.commit();return c

def test_public_without_session_and_no_internal_data(db,cache):
    insert(db);insert(db,False)
    with TestClient(app) as c:
        r=c.get('/public/dashboard?start=2026-11-12&end=2026-11-12')
        assert r.status_code==200 and r.json()['posts']==3
        assert r.json()['interactions']==18
        for secret in ['NEVER_PUBLIC_TOKEN','CONTENIDO_INTERNO','secret_scope','INTERNAL_ERROR','encrypted_token','private_metric']:
            assert secret not in r.text
        assert c.get('/connections').status_code==401
        assert c.get('/audit').status_code==401
        assert c.post('/connections',json={}).status_code==401

def test_only_explicit_publication_is_visible(db,cache):
    private=insert(db,False)
    with TestClient(app) as c:
        r=c.get('/public/dashboard?start=2026-11-12&end=2026-11-12')
        assert r.json()['posts']==0 and r.json()['interactions'] is None
        assert c.get('/public/accounts').json()['items']==[]
        assert c.get('/public/posts/1').status_code==404

def test_pagination_stable_without_duplicates(db,cache):
    insert(db)
    with TestClient(app) as c:
        prefix='/public/posts?start=2026-11-12&end=2026-11-12&page_size=2'
        first=c.get(prefix+'&page=1').json();second=c.get(prefix+'&page=2').json()
        assert first['has_more'] and not second['has_more']
        assert set(p['id'] for p in first['items']).isdisjoint(p['id'] for p in second['items'])
        assert c.get(prefix+'&page_size=1000').status_code==422
        assert c.get('/public/posts?page=201').status_code==422

def test_cache_does_not_queue_requests(db,cache,monkeypatch):
    insert(db)
    def never(*a,**k):pytest.fail('Un visitante no debe consultar el proveedor')
    monkeypatch.setattr('app.connectors.XConnector.fetch',never)
    with TestClient(app) as c:
        url='/public/dashboard?start=2026-11-12&end=2026-11-12'
        assert c.get(url).headers['x-data-cache']=='MISS'
        assert c.get(url).headers['x-data-cache']=='HIT'

def test_withdrawal_invalidates_cached_visibility(client,db,cache):
    c=insert(db)
    url='/public/dashboard?start=2026-11-12&end=2026-11-12'
    assert client.get(url).json()['posts']==3
    assert client.get('/public/posts/1').status_code==200
    assert client.patch(f'/connections/{c.id}/publication',json={'enabled':False}).status_code==200
    assert client.get(url).json()['posts']==0
    assert client.get('/public/posts/1').status_code==404

def test_rate_limit_and_redis_failure(cache,monkeypatch):
    monkeypatch.setattr(settings(),'public_requests_per_minute',1)
    with TestClient(app) as c:
        assert c.get('/public/accounts').status_code==200
        assert c.get('/public/accounts').status_code==429
        def down():raise redis.ConnectionError('SECRET')
        monkeypatch.setattr('app.public.redis_client',down)
        r=c.get('/public/accounts');assert r.status_code==503 and 'SECRET' not in r.text

def test_demo_is_not_public(db,cache,monkeypatch):
    insert(db,synthetic=True)
    with TestClient(app) as c:
        assert c.get('/public/dashboard?start=2026-11-12&end=2026-11-12').json()['posts']==0
        monkeypatch.setattr(settings(),'demo_mode',True)
        assert c.get('/public/accounts').status_code==404

def test_public_history_has_source_capture_and_metric_whitelist(db,cache):
    insert(db)
    with TestClient(app) as c:
        r=c.get('/public/posts/1');assert r.status_code==200
        h=r.json()['history'][0]
        assert h['source']=='https://api.x.com/2/users/1/tweets'
        assert h['captured_at'].endswith('+00:00')
        assert 'private_metric' not in h['metrics']

def test_public_query_count_does_not_grow_per_post(db,cache):
    insert(db)
    queries=[]
    def count(conn,cursor,statement,*args):queries.append(statement)
    with TestClient(app) as c:
        event.listen(engine,'before_cursor_execute',count)
        try:r=c.get('/public/dashboard?start=2026-11-12&end=2026-11-12')
        finally:event.remove(engine,'before_cursor_execute',count)
        assert r.status_code==200 and len(queries)<=4

def test_analyst_cannot_modify_monitoring(client,db,cache):
    u=User(email='analyst@test.local',role='analyst',password=password_hash.hash('long-password-123'));db.add(u);db.commit()
    client.cookies.set('session',issue(u))
    assert client.post('/monitors',json={'term':'CNE','platform':'x'}).status_code==403
