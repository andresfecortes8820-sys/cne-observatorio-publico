from datetime import timedelta, timezone
from sqlalchemy import select
from .db import Session
from .models import Connection, Post, Observation, AccountObservation, SyncRun, Alert, now
from .connectors import connector, ConnectorError
from .security import decrypt

def aware(d):
    return d.replace(tzinfo=timezone.utc) if d and not d.tzinfo else d

async def synchronize(connection_id, transport=None):
    with Session() as db:
        # Row lock prevents concurrent workers from overwriting cursor checkpoints.
        c = db.scalar(select(Connection).where(Connection.id == connection_id).with_for_update())
        if not c or not c.encrypted_token or c.status == 'disabled':
            return {'status':'unavailable'}
        run = SyncRun(connection_id=c.id)
        db.add(run)
        adapter = None
        try:
            if c.expires_at and aware(c.expires_at) <= now():
                raise ConnectorError('token_expired')
            adapter = connector(c.platform, decrypt(c.encrypted_token), transport)
            since = aware(c.last_sync) - timedelta(days=3) if c.last_sync else now() - timedelta(days=90)
            batch = await adapter.fetch(c.external_id, c.cursor or {}, since)
            for row in batch.posts:
                post = db.scalar(select(Post).where(Post.platform == c.platform, Post.external_id == row['id']))
                if not post:
                    post = Post(connection_id=c.id, platform=c.platform, external_id=row['id'], text=row['text'], url=row['url'], format=row['format'], published_at=row['published_at'])
                    db.add(post)
                    db.flush()
                else:
                    post.text, post.url = row['text'], row['url']
                db.add(Observation(post_id=post.id, source=batch.source, metrics=row['metrics']))
            if batch.profile:
                db.add(AccountObservation(connection_id=c.id, source=batch.source, metrics=batch.profile))
            c.cursor = batch.cursor
            # Advance watermark only after every page has been consumed.
            if batch.complete:
                c.last_sync = now()
            c.status, c.error = 'connected', None
            run.status, run.count = ('success' if batch.complete else 'partial'), len(batch.posts)
        except ConnectorError as e:
            c.status, c.error, run.status = 'error', e.code, 'error'
            run.message = e.code
            # Store cooldown without provider bodies or tokens.
            if e.retry_after:
                state = dict(c.cursor or {})
                state['retry_at'] = (now() + timedelta(seconds=e.retry_after)).isoformat()
                c.cursor = state
            db.add(Alert(connection_id=c.id, kind=e.code, message=f'{c.name}: {e.code}'))
        except Exception:
            db.rollback()
            c = db.get(Connection, connection_id)
            c.status, c.error = 'error', 'internal_sync_error'
            run = SyncRun(connection_id=c.id, status='error', message='internal_sync_error')
            db.add(run)
            db.add(Alert(connection_id=c.id, kind='sync_error', message=f'{c.name}: error interno de sincronización'))
        finally:
            if adapter:
                await adapter.close()
        run.finished_at = now()
        db.commit()
        return {'status':run.status, 'count':run.count, 'message':run.message}
