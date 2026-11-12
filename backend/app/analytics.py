from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from .models import Post, Observation, Connection, AccountObservation
from .config import settings

def rows(db, start, end, platform=None, account=None, keyword=None, format=None, topic=None, *, published_only=False, limit=1000, offset=0):
    tz = ZoneInfo(settings().timezone)
    a = datetime.combine(start, time.min, tzinfo=tz).astimezone(timezone.utc)
    b = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    ranked = select(Observation.post_id, Observation.metrics, Observation.source, Observation.captured_at, func.row_number().over(partition_by=Observation.post_id, order_by=(Observation.captured_at.desc(),Observation.id.desc())).label('rank')).subquery()
    q = select(Post, Connection.name, ranked.c.metrics,ranked.c.source,ranked.c.captured_at).join(Connection, Connection.id == Post.connection_id).outerjoin(ranked,(ranked.c.post_id==Post.id)&(ranked.c.rank==1)).where(Post.published_at >= a, Post.published_at < b)
    if published_only:
        official=(ranked.c.source.like('https://api.x.com/%')|ranked.c.source.like('https://graph.facebook.com/%')|ranked.c.source.like('https://open.tiktokapis.com/%'))
        q=q.where(Connection.publish_enabled.is_(True),official)
    if platform: q = q.where(Post.platform == platform)
    if account: q = q.where(Post.connection_id == account)
    if keyword: q = q.where(Post.text.ilike('%' + keyword.replace('%', '\\%').replace('_', '\\_') + '%', escape='\\'))
    if format: q = q.where(Post.format == format)
    if topic: q = q.where(Post.topic == topic)
    result = []
    for post, name, observed_metrics, source, captured_at in db.execute(q.order_by(Post.published_at.desc(),Post.id.desc()).offset(offset).limit(limit)):
        m = observed_metrics or {}
        interaction_keys = ['reactions', 'comments', 'shares'] if post.platform == 'facebook' else ['likes', 'comments', 'reposts', 'quotes'] if post.platform == 'x' else ['likes', 'comments', 'shares'] if post.platform == 'tiktok' else ['likes', 'comments']
        interactions = sum(m[k] for k in interaction_keys) if all(k in m for k in interaction_keys) else None
        result.append({'id':post.id, 'platform':post.platform, 'account':name, 'account_id':post.connection_id, 'text':post.text, 'url':post.url, 'format':post.format, 'published_at':post.published_at.isoformat(), 'topic':post.topic, 'sentiment':post.sentiment, 'metrics':m, 'interactions':interactions, 'captured_at':captured_at.isoformat() if captured_at else None, 'source':source})
    return result

def summarize(items):
    daily = defaultdict(lambda: {'posts':0, 'interactions':0, 'available':False})
    platforms = defaultdict(lambda: {'posts':0, 'interactions':0, 'measured_posts':0})
    for r in items:
        day = datetime.fromisoformat(r['published_at'])
        if not day.tzinfo:
            day = day.replace(tzinfo=timezone.utc)
        key = day.astimezone(ZoneInfo(settings().timezone)).date().isoformat()
        daily[key]['posts'] += 1
        platforms[r['platform']]['posts'] += 1
        if r['interactions'] is not None:
            daily[key]['interactions'] += r['interactions']
            daily[key]['available'] = True
            platforms[r['platform']]['interactions'] += r['interactions']
            platforms[r['platform']]['measured_posts'] += 1
    measured = [r for r in items if r['interactions'] is not None]
    return {'posts':len(items), 'interactions':sum(r['interactions'] for r in measured) if measured else None, 'measured_posts':len(measured), 'included_platforms':sorted(set(r['platform'] for r in measured)), 'daily':[{'date':k, **v, 'interactions':v['interactions'] if v['available'] else None} for k,v in sorted(daily.items())], 'platforms':[{'platform':k, **v, 'interactions':v['interactions'] if v['measured_posts'] else None} for k,v in platforms.items()], 'engagement_rate':None, 'reach':None, 'impressions':None, 'views':None}
