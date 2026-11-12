import asyncio,importlib.util,json
from datetime import datetime,timezone
from pathlib import Path
from app.connectors import Batch,ConnectorError

file=Path(__file__).resolve().parents[2]/'scripts/collect_public.py'
spec=importlib.util.spec_from_file_location('collect_public',file)
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
CONFIG={'accounts':[{'platform':'x','external_id':'1','name':'UNIT TEST ACCOUNT','approved_for_publication':True,'interval_minutes':15}]}

def test_missing_tokens_never_call_provider(monkeypatch):
    monkeypatch.delenv('X_ACCESS_TOKEN',raising=False)
    def fail(*a):raise AssertionError('No provider call without credentials')
    result=asyncio.run(collector.collect(CONFIG,{},True,fail))
    assert result['posts']==[]
    assert next(s for s in result['sources'] if s['platform']=='x')['status']=='missing_credentials'

def test_explicit_approval_required():
    assert collector.approved_accounts({'accounts':[{'platform':'x','external_id':'1'}]})==[]

def test_only_public_numeric_fields_are_published():
    account=collector.approved_accounts(CONFIG)[0]
    row={'id':'10','text':'TEST ONLY','url':'https://x.com/i/status/10?access_token=PRIVATE','published_at':datetime.now(timezone.utc),'format':'text','metrics':{'likes':1,'comments':2,'reposts':3,'quotes':4,'access_token':'PRIVATE','private_metric':999}}
    result=collector.merge_post(row,account,'https://api.x.com/2/users/1/tweets?access_token=PRIVATE')
    assert result['interactions']==10 and len(result['history'])==1
    assert 'PRIVATE' not in json.dumps(result)
    assert 'private_metric' not in result['metrics']

def test_collect_normalizes_and_saves_real_capture_contract(monkeypatch):
    monkeypatch.setenv('X_ACCESS_TOKEN','TEST_SECRET_NEVER_PUBLISHED')
    class Adapter:
        async def fetch(self,*args):
            return Batch({'followers':9},[{'id':'10','text':'UNIT TEST','url':'https://x.com/i/status/10','published_at':datetime.now(timezone.utc),'format':'text','metrics':{'likes':1,'comments':2,'reposts':3,'quotes':4}}],{},True,'https://api.x.com/2/users/1/tweets')
        async def close(self):pass
    result=asyncio.run(collector.collect(CONFIG,{},True,lambda *a:Adapter()))
    assert len(result['posts'])==1 and result['accounts'][0]['followers']==9
    assert result['accounts'][0]['source']=='https://api.x.com/2/users/1'
    assert 'TEST_SECRET_NEVER_PUBLISHED' not in json.dumps(result)

def test_withdrawn_accounts_are_removed_from_snapshot():
    previous={'accounts':[{'id':1}],'posts':[{'id':2,'account_id':1}]}
    result=asyncio.run(collector.collect({'accounts':[]},previous,False))
    assert not result['accounts'] and not result['posts']

def test_provider_failures_are_sanitized_and_respect_cooldown(monkeypatch):
    monkeypatch.setenv('X_ACCESS_TOKEN','SECRET')
    class Adapter:
        async def fetch(self,*args):raise ConnectorError('rate_limited',3600)
        async def close(self):pass
    result=asyncio.run(collector.collect(CONFIG,{},True,lambda *a:Adapter()))
    status=next(s for s in result['sources'] if s['platform']=='x')
    assert status['status']=='rate_limited' and 'retry_at' in status
    def never(*a):raise AssertionError('Cooldown should prevent another request')
    asyncio.run(collector.collect(CONFIG,result,True,never))

def test_public_profile_is_not_converted_into_api_authorization():
    config={'accounts':[],'watchlist':[{'platform':'x','name':'TEST TARGET','handle':'example','profile_url':'https://x.com/example?s=tracking'}]}
    result=asyncio.run(collector.collect(config,{},False))
    assert result['accounts']==[] and result['posts']==[]
    assert result['watchlist'][0]['profile_url']=='https://x.com/example'
    assert next(s for s in result['sources'] if s['platform']=='x')['status']=='api_access_pending'

def test_watchlist_rejects_non_official_hosts():
    import pytest
    with pytest.raises(ValueError):collector.public_watchlist({'watchlist':[{'platform':'x','profile_url':'https://attacker.example/x'}]})

def test_team_ownership_does_not_create_comment_authorization():
    config={'accounts':[],'watchlist':[{'platform':'x','profile_url':'https://x.com/example','ownership':'team_managed'}]}
    result=asyncio.run(collector.collect(config,{},False))
    assert result['watchlist'][0]['access_mode']=='owned_pending_authorization'
    opinions=asyncio.run(collector.collect_opinions(config,result,{}))
    assert opinions['opinions']==[] and len(opinions['opinion_sources'])==4

def test_opinion_collection_requires_separate_enable_flag(monkeypatch):
    monkeypatch.delenv('LISTENING_SYNC_ENABLED',raising=False)
    def never(*a):raise AssertionError('No API call without explicit enable')
    result=asyncio.run(collector.collect_opinions(CONFIG,{'posts':[]},{},never))
    assert result['opinions']==[]
    assert next(s for s in result['opinion_sources'] if s['platform']=='x')['status']=='not_enabled'
