"""Read-only official adapters. Never follow server-provided absolute pagination URLs."""
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import re
import httpx
from .config import settings

class ConnectorError(Exception):
    def __init__(self, code, retry_after=0):
        self.code, self.retry_after = code, retry_after
        super().__init__(code)

@dataclass
class Batch:
    profile: dict
    posts: list
    cursor: dict
    complete: bool
    source: str

def iso(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def metrics(data, mapping):
    return {target: data[source] for source, target in mapping.items() if source in data and isinstance(data[source], (int, float)) and data[source] >= 0}

class OfficialConnector:
    origin = ''
    def __init__(self, token, transport=None):
        self.client = httpx.AsyncClient(base_url=self.origin, headers={'Authorization': f'Bearer {token}'}, timeout=25, follow_redirects=False, transport=transport)

    async def close(self):
        await self.client.aclose()

    async def request(self, method, path, **kwargs):
        for attempt in range(3):
            try:
                response = await self.client.request(method, path, **kwargs)
            except httpx.RequestError:
                if attempt == 2:
                    raise ConnectorError('network_error')
                await asyncio.sleep(2 ** attempt)
                continue
            if response.status_code == 429:
                raw = response.headers.get('retry-after', '60')
                raise ConnectorError('rate_limited', int(raw) if raw.isdigit() else 60)
            if response.status_code in (401, 403):
                raise ConnectorError('token_expired' if response.status_code == 401 else 'insufficient_permissions')
            if response.status_code >= 500 and attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            if response.status_code >= 300:
                raise ConnectorError(f'provider_http_{response.status_code}')
            try:
                data = response.json()
            except ValueError:
                raise ConnectorError('invalid_provider_response')
            if data.get('error') and (not isinstance(data['error'], dict) or data['error'].get('code') not in ('ok', None)):
                error = data['error']
                code = error.get('code') if isinstance(error, dict) else None
                raise ConnectorError({190: 'token_expired', 10: 'insufficient_permissions', 200: 'insufficient_permissions', 'access_token_invalid': 'token_expired', 'scope_not_authorized': 'insufficient_permissions'}.get(code, 'provider_error'))
            if data.get('errors'):
                raise ConnectorError('partial_provider_response')
            return data
        raise ConnectorError('provider_unavailable')

class XConnector(OfficialConnector):
    origin = 'https://api.x.com'
    async def fetch(self, account, state, since):
        profile = (await self.request('GET', f'/2/users/{account}', params={'user.fields': 'public_metrics,name,username'})).get('data', {})
        p = {'max_results': 100, 'tweet.fields': 'created_at,public_metrics,attachments', 'expansions': 'attachments.media_keys', 'media.fields': 'type'}
        if state.get('next'):
            p['pagination_token'] = state['next']
        if state.get('since_id'):
            p['since_id'] = state['since_id']
        elif since:
            p['start_time'] = since.isoformat().replace('+00:00', 'Z')
        data = await self.request('GET', f'/2/users/{account}/tweets', params=p)
        media = {m['media_key']: m['type'] for m in data.get('includes', {}).get('media', [])}
        posts = []
        for row in data.get('data', []):
            formats = [media.get(k, 'unknown') for k in row.get('attachments', {}).get('media_keys', [])]
            posts.append({'id': row['id'], 'text': row['text'], 'published_at': iso(row['created_at']), 'url': f'https://x.com/i/status/{row["id"]}', 'format': 'video' if 'video' in formats else 'image' if formats else 'text', 'metrics': metrics(row.get('public_metrics', {}), {'like_count':'likes', 'reply_count':'comments', 'retweet_count':'reposts', 'quote_count':'quotes', 'impression_count':'impressions'})})
        meta = data.get('meta', {})
        high = max([int(r['id']) for r in data.get('data', [])] + [int(state.get('pending_high', state.get('since_id', '0')))])
        next_token = meta.get('next_token')
        cursor = {'since_id': state.get('since_id'), 'pending_high': str(high), 'next': next_token} if next_token else {'since_id': str(high)}
        return Batch(metrics(profile.get('public_metrics', {}), {'followers_count':'followers'}), posts, cursor, not next_token, f'{self.origin}/2/users/{account}/tweets')

class TikTokConnector(OfficialConnector):
    origin = 'https://open.tiktokapis.com'
    async def fetch(self, account, state, since):
        user = await self.request('GET', '/v2/user/info/', params={'fields':'open_id,display_name'})
        if user.get('data', {}).get('user', {}).get('open_id') != account:
            raise ConnectorError('account_token_mismatch')
        body = {'max_count': 20}
        if state.get('next'):
            body['cursor'] = state['next']
        result = await self.request('POST', '/v2/video/list/', params={'fields':'id,title,video_description,create_time,share_url,view_count,like_count,comment_count,share_count'}, json=body)
        data = result.get('data', {})
        posts = [{'id':r['id'], 'text':r.get('video_description', r.get('title', '')), 'published_at':iso(r['create_time']), 'url':r.get('share_url', ''), 'format':'video', 'metrics':metrics(r, {'view_count':'views', 'like_count':'likes', 'comment_count':'comments', 'share_count':'shares'})} for r in data.get('videos', [])]
        # Re-scan a bounded first page on next cycle to refresh recent counters.
        older = bool(posts and since and min(r['published_at'] for r in posts) <= since)
        more = data.get('has_more', False) and not older
        return Batch({}, posts, {'next':data.get('cursor')} if more else {}, not more, f'{self.origin}/v2/video/list/')

class MetaConnector(OfficialConnector):
    origin = 'https://graph.facebook.com'
    def __init__(self, token, transport=None, instagram=False):
        super().__init__(token, transport)
        self.instagram = instagram

    async def fetch(self, account, state, since):
        version = settings().meta_graph_version
        if not re.fullmatch(r'v\d+\.\d+', version):
            raise ConnectorError('meta_version_validation_required')
        root = f'/{version}/{account}'
        fields = 'id,username,followers_count' if self.instagram else 'id,name,followers_count'
        profile = await self.request('GET', root, params={'fields': fields})
        fields = 'id,caption,media_type,timestamp,permalink,like_count,comments_count' if self.instagram else 'id,message,created_time,permalink_url,shares,comments.limit(0).summary(true),reactions.limit(0).summary(true)'
        params = {'fields': fields, 'limit': 50}
        if state.get('next'):
            params['after'] = state['next']
        if since and not self.instagram:
            params['since'] = int(since.timestamp())
        endpoint = root + ('/media' if self.instagram else '/posts')
        data = await self.request('GET', endpoint, params=params)
        posts = []
        for r in data.get('data', []):
            m = metrics(r, {'like_count':'likes', 'comments_count':'comments'}) if self.instagram else {k:v for k,v in {'shares':r.get('shares', {}).get('count'), 'comments':r.get('comments', {}).get('summary', {}).get('total_count'), 'reactions':r.get('reactions', {}).get('summary', {}).get('total_count')}.items() if v is not None}
            posts.append({'id':r['id'], 'text':r.get('caption', r.get('message', '')), 'published_at':iso(r.get('timestamp', r.get('created_time'))), 'url':r.get('permalink', r.get('permalink_url', '')), 'format':r.get('media_type', 'unknown').lower(), 'metrics':m})
        paging = data.get('paging', {})
        more = bool(paging.get('next'))
        after = paging.get('cursors', {}).get('after')
        if more and not after:
            raise ConnectorError('unsupported_pagination')
        if self.instagram and posts and since and min(p['published_at'] for p in posts) <= since:
            more = False
        return Batch(metrics(profile, {'followers_count':'followers'}), posts, {'next':after} if more else {}, not more, self.origin + endpoint)

def connector(platform, token, transport=None):
    if platform == 'x': return XConnector(token, transport)
    if platform == 'tiktok': return TikTokConnector(token, transport)
    if platform in ('facebook', 'instagram'): return MetaConnector(token, transport, platform == 'instagram')
    raise ConnectorError('unsupported_platform')
