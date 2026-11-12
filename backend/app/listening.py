"""Read-only audience text adapters. Separate from post interaction counters."""
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
import re
from .connectors import OfficialConnector,ConnectorError,iso
from .config import settings

@dataclass
class OpinionBatch:
    items:list
    source:str
    has_more:bool=False

class XListening(OfficialConnector):
    origin='https://api.x.com'
    async def read(self,account,parent,handle=None):
        if not str(parent['external_id']).isdigit():raise ConnectorError('invalid_post_id')
        since=max(iso(parent['published_at']),datetime.now(timezone.utc)-timedelta(days=6,hours=23))
        result=await self.request('GET','/2/tweets/search/recent',params={'query':f'conversation_id:{parent["external_id"]} is:reply','start_time':since.isoformat().replace('+00:00','Z'),'max_results':100,'tweet.fields':'created_at,public_metrics,author_id,conversation_id'})
        rows=[]
        for r in result.get('data',[]):
            if not r.get('author_id') or r['author_id']==str(account):continue
            rows.append({'external_id':r['id'],'text':r['text'],'published_at':iso(r['created_at']),'url':f'https://x.com/i/status/{r["id"]}','kind':'reply','parent_external_id':parent['external_id']})
        return OpinionBatch(rows,self.origin+'/2/tweets/search/recent',bool(result.get('meta',{}).get('next_token')))

class MetaListening(OfficialConnector):
    origin='https://graph.facebook.com'
    def __init__(self,token,transport=None,instagram=False):
        super().__init__(token,transport);self.instagram=instagram
    async def read(self,account,parent,handle=None):
        version=settings().meta_graph_version
        if not re.fullmatch(r'v\d+\.\d+',version):raise ConnectorError('meta_version_validation_required')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',str(parent['external_id'])):raise ConnectorError('invalid_post_id')
        fields='id,text,timestamp,from,hidden' if self.instagram else 'id,message,created_time,from,is_hidden'
        path=f'/{version}/{parent["external_id"]}/comments'
        result=await self.request('GET',path,params={'fields':fields,'limit':100})
        rows=[]
        for r in result.get('data',[]):
            if r.get('hidden' if self.instagram else 'is_hidden') is not False:continue
            author=r.get('from',{}).get('id')
            if not author or str(author)==str(account):continue
            text=r.get('text' if self.instagram else 'message','')
            if not text.strip():continue
            rows.append({'external_id':r['id'],'text':text,'published_at':iso(r['timestamp' if self.instagram else 'created_time']),'url':parent['url'],'kind':'comment','parent_external_id':parent['external_id']})
        return OpinionBatch(rows,self.origin+path,bool(result.get('paging',{}).get('next')))

def listening_connector(platform,token,transport=None):
    if platform=='x':return XListening(token,transport)
    if platform in ('facebook','instagram'):return MetaListening(token,transport,platform=='instagram')
    # Display API does not provide the text of comments. Business Accounts access
    # requires a separately approved product/contract; do not invent an endpoint.
    raise ConnectorError('tiktok_comments_access_required')
