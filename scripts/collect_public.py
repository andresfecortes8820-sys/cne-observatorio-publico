"""Official API collection inside GitHub Actions; publish only explicitly approved data.

No credentials, raw provider responses or private database files are serialized.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from hashlib import sha256
from urllib.parse import urlsplit,urlunsplit
import asyncio,json,math,os,secrets,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
# Unused application secrets are ephemeral; no application server is started here.
os.environ.setdefault('JWT_SECRET',secrets.token_urlsafe(48))
os.environ.setdefault('ADMIN_PASSWORD',secrets.token_urlsafe(32))
os.environ.setdefault('TOKEN_KEY',__import__('base64').urlsafe_b64encode(secrets.token_bytes(32)).decode())
from app.connectors import connector,ConnectorError

PLATFORMS={'facebook':('FACEBOOK_ACCESS_TOKEN','graph.facebook.com'),'instagram':('INSTAGRAM_ACCESS_TOKEN','graph.facebook.com'),'x':('X_ACCESS_TOKEN','api.x.com'),'tiktok':('TIKTOK_ACCESS_TOKEN','open.tiktokapis.com')}
COUNTERS={'likes','reactions','comments','shares','reposts','quotes','views'}
INTERACTIONS={'facebook':['reactions','comments','shares'],'instagram':['likes','comments'],'x':['likes','comments','reposts','quotes'],'tiktok':['likes','comments','shares']}
MAX_POSTS=2000

def identity(value):return int(sha256(value.encode()).hexdigest()[:12],16)
def stamp():return datetime.now(timezone.utc).isoformat()
def counters(raw):return {k:v for k,v in raw.items() if k in COUNTERS and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0}
def public_source(value,platform):
    u=urlsplit(value)
    if u.scheme!='https' or u.hostname!=PLATFORMS[platform][1] or u.username or u.password:raise ValueError('unexpected_source')
    return urlunsplit(('https',u.hostname,u.path,'',''))
def original_url(value,platform):
    u=urlsplit(value)
    domains={'facebook':{'facebook.com','www.facebook.com'},'instagram':{'instagram.com','www.instagram.com'},'x':{'x.com','www.x.com'},'tiktok':{'tiktok.com','www.tiktok.com','m.tiktok.com'}}
    return urlunsplit(('https',u.hostname,u.path,'','')) if u.scheme=='https' and u.hostname in domains[platform] and not u.username and not u.password else ''

def merge_post(row,account,batch_source,old=None,captured=None):
    platform=account['platform'];m=counters(row['metrics']);captured=captured or stamp()
    source=public_source(batch_source,platform)
    required=INTERACTIONS[platform]
    total=sum(m[k] for k in required) if all(k in m for k in required) else None
    history=list((old or {}).get('history',[]))
    history.append({'captured_at':captured,'metrics':m,'source':source})
    return {'id':identity(platform+':'+row['id']),'external_id':row['id'],'account_id':account['id'],'account':account['account'],'platform':platform,'text':row['text'][:10000],'format':row['format'][:30],'url':original_url(row['url'],platform),'published_at':row['published_at'].astimezone(timezone.utc).isoformat(),'captured_at':captured,'source':source,'metrics':m,'interactions':total,'sentiment':'indeterminado','topic':None,'history':history[-24:]}

def approved_accounts(config):
    result=[];seen=set()
    for c in config.get('accounts',[]):
        if c.get('approved_for_publication') is not True:continue
        platform=c.get('platform');external=str(c.get('external_id',''))
        if platform not in PLATFORMS or not external or len(external)>120 or not all(x.isalnum() or x in '_-' for x in external):raise ValueError('invalid_account_config')
        if platform in seen:raise ValueError('Este modo admite una cuenta por plataforma; cada una usa su secreto oficial independiente')
        seen.add(platform)
        interval=int(c.get('interval_minutes',60))
        if not 15<=interval<=1440:raise ValueError('Intervalo permitido: 15 a 1440 minutos')
        result.append({'id':identity(platform+':'+external),'external_id':external,'account':str(c.get('name',external))[:180],'name':str(c.get('name',external))[:180],'platform':platform,'category':str(c.get('category','Institución'))[:80],'interval_minutes':interval})
    return result

def public_watchlist(config):
    result=[];seen=set()
    for item in config.get('watchlist',[]):
        platform=item.get('platform')
        if platform not in PLATFORMS:raise ValueError('invalid_watchlist_platform')
        url=original_url(str(item.get('profile_url','')),platform)
        if not url:raise ValueError('invalid_watchlist_url')
        if (platform,url) in seen:continue
        seen.add((platform,url))
        result.append({'platform':platform,'name':str(item.get('name',platform))[:180],'handle':str(item['handle'])[:120] if item.get('handle') else None,'profile_url':url,'access_mode':'public_interest','api_status':'api_access_pending','verification':'provided_by_user'})
    return result[:200]

async def collect(config,previous,enabled=None,make_connector=connector):
    now=datetime.now(timezone.utc);captured=now.isoformat();since=now-timedelta(days=90)
    approved=approved_accounts(config);ids={c['id'] for c in approved};watchlist=public_watchlist(config)
    existing={p['id']:p for p in previous.get('posts',[]) if p['account_id'] in ids and datetime.fromisoformat(p['published_at'])>=since}
    old_accounts={a['id']:a for a in previous.get('accounts',[])}
    old_sources={s['platform']:s for s in previous.get('sources',[])}
    sources=[];accounts=[];limited=False
    enabled=os.getenv('API_SYNC_ENABLED','').lower()=='true' if enabled is None else enabled
    for account in approved:
        p=account['platform'];token=os.getenv(PLATFORMS[p][0]);old=old_accounts.get(account['id'],{})
        public={k:account[k] for k in ['id','account','name','platform','category']}
        public.update({k:old.get(k) for k in ['followers','captured_at','source','last_update']})
        status={'platform':p,'last_attempt':captured,'status':'not_enabled'}
        if not token:status['status']='missing_credentials'
        elif enabled:
            prior=old_sources.get(p,{})
            attempt=prior.get('last_attempt')
            retry_at=prior.get('retry_at')
            if retry_at and datetime.fromisoformat(retry_at)>now or attempt and datetime.fromisoformat(attempt)+timedelta(minutes=account['interval_minutes'])>now:
                sources.append(prior);accounts.append(public);continue
            adapter=make_connector(p,token)
            try:
                state={};complete=False
                for page in range(2): # Strict per-run quota bound: max two pages/account.
                    batch=await adapter.fetch(account['external_id'],state,since)
                    public_source(batch.source,p)
                    for row in batch.posts:
                        if row['published_at']<since:continue
                        key=identity(p+':'+row['id'])
                        existing[key]=merge_post(row,account,batch.source,existing.get(key),captured)
                    followers=batch.profile.get('followers')
                    if isinstance(followers,(int,float)) and not isinstance(followers,bool) and math.isfinite(followers) and followers>=0:
                        profile_source=public_source(batch.source,p)
                        for ending in ['/tweets','/posts','/media']:
                            if profile_source.endswith(ending):profile_source=profile_source[:-len(ending)]
                        public.update(followers=followers,captured_at=captured,source=profile_source)
                    state=batch.cursor;complete=batch.complete
                    if complete:break
                status['status']='available' if complete else 'partial'
                limited|=not complete
                public['last_update']=captured
            except ConnectorError as e:
                status['status']=e.code
                if e.retry_after:status['retry_at']=(now+timedelta(seconds=e.retry_after)).isoformat()
            except Exception:status['status']='collection_error'
            finally:await adapter.close()
        sources.append(status);accounts.append(public)
    for platform in PLATFORMS:
        if platform not in {c['platform'] for c in approved}:sources.append({'platform':platform,'status':'api_access_pending' if any(w['platform']==platform for w in watchlist) else 'not_configured','last_attempt':captured})
    data=sorted(existing.values(),key=lambda p:(p['published_at'],p['id']),reverse=True)
    return {'version':1,'generated_at':captured,'accounts':accounts,'watchlist':watchlist,'posts':data[:MAX_POSTS],'sources':sources,'truncated':limited or len(data)>MAX_POSTS}

def main():
    config=json.loads((ROOT/'config/public_accounts.json').read_text(encoding='utf-8'))
    target=ROOT/'data/observatory.json'
    previous=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    result=asyncio.run(collect(config,previous))
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('Captura pública procesada: '+str(len(result['posts']))+' publicaciones. No se imprimen credenciales.')

if __name__=='__main__':main()
