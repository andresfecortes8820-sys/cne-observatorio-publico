import asyncio,json
from datetime import datetime,timezone
import httpx,pytest
from app.listening import XListening,MetaListening,listening_connector
from app.connectors import ConnectorError
from app.config import settings

def test_x_reads_received_replies_without_own_posts_or_author_profiles():
    def handler(r):
        assert r.url.path=='/2/tweets/search/recent'
        assert r.url.params['query']=='conversation_id:10 is:reply'
        return httpx.Response(200,json={'data':[{'id':'11','text':'UNIT TEST CITIZEN COMMENT','author_id':'2','created_at':'2026-11-12T12:00:00Z'},{'id':'12','text':'OWN RESPONSE','author_id':'1','created_at':'2026-11-12T12:00:00Z'}],'meta':{'next_token':'more'}})
    async def run():
        c=XListening('secret',httpx.MockTransport(handler))
        try:
            batch=await c.read('1',{'external_id':'10','published_at':datetime.now(timezone.utc).isoformat()})
            assert len(batch.items)==1 and batch.items[0]['kind']=='reply'
            assert 'author_id' not in batch.items[0] and batch.has_more
        finally:await c.close()
    asyncio.run(run())

@pytest.mark.parametrize('instagram',[False,True])
def test_meta_excludes_hidden_unknown_visibility_and_self_comments(monkeypatch,instagram):
    monkeypatch.setattr(settings(),'meta_graph_version','v99.0')
    def handler(r):
        assert r.url.host=='graph.facebook.com' and r.url.path=='/v99.0/10/comments'
        text='text' if instagram else 'message';time='timestamp' if instagram else 'created_time';hidden='hidden' if instagram else 'is_hidden'
        rows=[{'id':'11',text:'PUBLIC TEST',time:'2026-11-12T12:00:00Z',hidden:False,'from':{'id':'2','name':'DO NOT STORE'}},{'id':'12',text:'HIDDEN TEST',time:'2026-11-12T12:00:00Z',hidden:True,'from':{'id':'3'}},{'id':'13',text:'OWN',time:'2026-11-12T12:00:00Z',hidden:False,'from':{'id':'1'}},{'id':'14',text:'UNKNOWN VISIBILITY',time:'2026-11-12T12:00:00Z','from':{'id':'4'}}]
        return httpx.Response(200,json={'data':rows})
    async def run():
        c=MetaListening('secret',httpx.MockTransport(handler),instagram)
        try:
            batch=await c.read('1',{'external_id':'10','url':'https://www.instagram.com/p/test/'})
            assert len(batch.items)==1 and batch.items[0]['text']=='PUBLIC TEST'
            assert 'DO NOT STORE' not in json.dumps(batch.items,default=str)
        finally:await c.close()
    asyncio.run(run())

def test_display_token_does_not_grant_tiktok_comment_text():
    with pytest.raises(ConnectorError,match='tiktok_comments_access_required'):listening_connector('tiktok','token')
