import asyncio
from datetime import date,datetime,timezone
import httpx
from app.models import Connection,Post,Observation,SyncRun,AccountObservation
from app.security import encrypt
from app.sync import synchronize
from app.analytics import rows,summarize

def test_sync_deduplicates_and_keeps_history(db):
    c=Connection(platform='x',external_id='1',name='A',encrypted_token=encrypt('token'));db.add(c);db.commit()
    def handler(r):
        if r.url.path.endswith('/1'):return httpx.Response(200,json={'data':{'public_metrics':{'followers_count':10}}})
        return httpx.Response(200,json={'data':[{'id':'20','text':'Elecciones','created_at':'2026-11-12T12:00:00Z','public_metrics':{'like_count':2,'reply_count':1,'retweet_count':3,'quote_count':0}}],'meta':{}})
    for _ in range(2):assert asyncio.run(synchronize(c.id,httpx.MockTransport(handler)))['status']=='success'
    db.expire_all()
    assert db.query(Post).count()==1 and db.query(Observation).count()==2
    assert db.query(SyncRun).count()==2 and db.query(AccountObservation).count()==2
    result=rows(db,date(2026,11,12),date(2026,11,12))
    assert result[0]['interactions']==6
    assert summarize(result)['interactions']==6

def test_partial_page_does_not_advance_watermark(db):
    c=Connection(platform='x',external_id='1',name='A',encrypted_token=encrypt('token'));db.add(c);db.commit()
    def handler(r):
        return httpx.Response(200,json={'data':{'public_metrics':{}}} if r.url.path.endswith('/1') else {'data':[],'meta':{'next_token':'next'}})
    assert asyncio.run(synchronize(c.id,httpx.MockTransport(handler)))['status']=='partial'
    db.refresh(c);assert c.last_sync is None and c.cursor['next']=='next'

def test_bogota_day_boundary_and_missing_metrics(db):
    c=Connection(platform='x',external_id='1',name='A');db.add(c);db.flush()
    for id,time in [('a','2026-11-12T04:59:59+00:00'),('b','2026-11-12T05:00:00+00:00')]:
        p=Post(connection_id=c.id,platform='x',external_id=id,text='CNE',url='',format='text',published_at=datetime.fromisoformat(time));db.add(p)
    db.commit()
    data=rows(db,date(2026,11,12),date(2026,11,12));assert len(data)==1 and data[0]['interactions'] is None
    s=summarize(data);assert s['interactions'] is None and s['daily'][0]['date']=='2026-11-12'

def test_latest_observation_wins_and_filters(db):
    c=Connection(platform='instagram',external_id='1',name='A');db.add(c);db.flush()
    p=Post(connection_id=c.id,platform='instagram',external_id='1',text='CNE elecciones',url='',format='image',published_at=datetime(2026,11,12,12,tzinfo=timezone.utc));db.add(p);db.flush()
    db.add_all([Observation(post_id=p.id,source='official',metrics={'likes':2,'comments':1}),Observation(post_id=p.id,source='official',metrics={'likes':5,'comments':2})]);db.commit()
    data=rows(db,date(2026,11,12),date(2026,11,12),'instagram',c.id,'elecciones','image');assert data[0]['interactions']==7
    assert rows(db,date(2026,11,12),date(2026,11,12),'x')==[]
