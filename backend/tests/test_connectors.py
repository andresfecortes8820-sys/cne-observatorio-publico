import asyncio
from datetime import datetime, timezone
import httpx
import pytest
from app.connectors import XConnector,TikTokConnector,MetaConnector,ConnectorError
from app.config import settings

def test_x_normalization_and_checkpoint():
    seen=[]
    def handler(r):
        seen.append(r)
        if r.url.path=='/2/users/1':return httpx.Response(200,json={'data':{'public_metrics':{'followers_count':5}}})
        return httpx.Response(200,json={'data':[{'id':'10','text':'CNE','created_at':'2026-11-12T12:00:00Z','public_metrics':{'like_count':2,'reply_count':3,'retweet_count':4,'quote_count':1}}],'meta':{'next_token':'page-two'}})
    async def run():
        c=XConnector('token',httpx.MockTransport(handler))
        try:
            b=await c.fetch('1',{},None)
            assert b.profile=={'followers':5};assert b.posts[0]['metrics']['reposts']==4
            assert not b.complete and b.cursor['pending_high']=='10' and b.cursor['next']=='page-two'
            assert 'views' not in b.posts[0]['metrics']
        finally:await c.close()
    asyncio.run(run())

@pytest.mark.parametrize('status,code',[(401,'token_expired'),(403,'insufficient_permissions'),(429,'rate_limited')])
def test_provider_errors_are_sanitized(status,code):
    async def run():
        c=XConnector('secret',httpx.MockTransport(lambda r:httpx.Response(status,json={'private':'secret'},headers={'retry-after':'120'})))
        try:
            with pytest.raises(ConnectorError) as e:await c.fetch('1',{},None)
            assert str(e.value)==code and 'secret' not in str(e.value)
            if status==429:assert e.value.retry_after==120
        finally:await c.close()
    asyncio.run(run())

def test_tiktok_scopes_and_pagination():
    def handler(r):
        if r.url.path.endswith('user/info/'):return httpx.Response(200,json={'data':{'user':{'open_id':'abc'}},'error':{'code':'ok'}})
        assert r.method=='POST';assert r.url.params['fields'].startswith('id,title')
        return httpx.Response(200,json={'data':{'videos':[{'id':'v1','create_time':1794484800,'video_description':'Hola','view_count':9,'like_count':2}],'has_more':True,'cursor':123},'error':{'code':'ok'}})
    async def run():
        c=TikTokConnector('t',httpx.MockTransport(handler))
        try:
            b=await c.fetch('abc',{},None)
            assert b.cursor=={'next':123};assert not b.complete
            assert b.posts[0]['metrics']=={'views':9,'likes':2}
            assert b.profile=={}
        finally:await c.close()
    asyncio.run(run())

def test_meta_requires_explicit_version(monkeypatch):
    monkeypatch.setattr(settings(),'meta_graph_version','')
    async def run():
        c=MetaConnector('t',httpx.MockTransport(lambda r:pytest.fail('No debe consultar una versión no validada')))
        try:
            with pytest.raises(ConnectorError,match='meta_version_validation_required'):await c.fetch('1',{},None)
        finally:await c.close()
    asyncio.run(run())

@pytest.mark.parametrize('instagram',[False,True])
def test_meta_normalizes_without_following_absolute_urls(monkeypatch,instagram):
    monkeypatch.setattr(settings(),'meta_graph_version','v99.0') # Solo contrato simulado, no versión real.
    def handler(r):
        assert r.url.host=='graph.facebook.com'
        if r.url.path.endswith('/1'):return httpx.Response(200,json={'followers_count':7})
        row={'id':'p','caption':'Hola','timestamp':'2026-11-12T12:00:00Z','media_type':'VIDEO','like_count':4,'comments_count':2} if instagram else {'id':'p','message':'Hola','created_time':'2026-11-12T12:00:00Z','shares':{'count':1},'reactions':{'summary':{'total_count':4}},'comments':{'summary':{'total_count':2}}}
        return httpx.Response(200,json={'data':[row],'paging':{'next':'https://attacker.example/?token=secret','cursors':{'after':'safe-cursor'}}})
    async def run():
        c=MetaConnector('secret',httpx.MockTransport(handler),instagram)
        try:
            b=await c.fetch('1',{},None)
            assert b.cursor=={'next':'safe-cursor'} and b.profile=={'followers':7}
            assert b.posts[0]['metrics'].get('likes' if instagram else 'reactions')==4
        finally:await c.close()
    asyncio.run(run())
