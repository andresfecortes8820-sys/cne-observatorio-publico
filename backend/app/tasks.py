import asyncio
from datetime import datetime, timedelta
from celery import Celery
from sqlalchemy import select
from .config import settings
from .db import Session
from .models import Connection, SyncRun, now
from .sync import synchronize, aware

celery = Celery('social', broker=settings().redis_url, backend=settings().redis_url)
celery.conf.update(timezone=settings().timezone, beat_schedule={'due-connections': {'task':'app.tasks.dispatch', 'schedule':60.0}}, task_serializer='json', accept_content=['json'])

@celery.task(name='app.tasks.sync_connection', soft_time_limit=90, time_limit=120)
def sync_connection(connection_id):
    # Redis lease guards dispatch/manual retries; SQL row lock protects persistent state.
    import redis
    r = redis.Redis.from_url(settings().redis_url)
    with r.lock(f'sync:{connection_id}', timeout=150, blocking_timeout=1):
        return asyncio.run(synchronize(connection_id))

@celery.task(name='app.tasks.dispatch')
def dispatch():
    with Session() as db:
        for c in db.scalars(select(Connection).where(Connection.status != 'disabled', Connection.encrypted_token.is_not(None))):
            retry_at = (c.cursor or {}).get('retry_at')
            if retry_at and datetime.fromisoformat(retry_at) > now():
                continue
            last = db.scalar(select(SyncRun).where(SyncRun.connection_id == c.id).order_by(SyncRun.started_at.desc()))
            interval = 1 if last and last.status == 'partial' else c.interval_minutes
            if not last or aware(last.started_at) + timedelta(minutes=interval) <= now():
                sync_connection.delay(c.id)
