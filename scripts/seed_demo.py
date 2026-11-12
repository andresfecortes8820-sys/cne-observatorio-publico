"""Synthetic, offline-only fixtures. Requires DEMO_MODE and a dedicated database."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from datetime import timedelta
from sqlalchemy import select
from app.config import settings
from app.db import Session
from app.models import Connection,Post,Observation,AccountObservation,now

if not settings().demo_mode or 'demo' not in settings().database_url.lower():
    raise SystemExit('Requiere DEMO_MODE=true y una base dedicada cuyo nombre incluya demo.')
with Session() as db:
    if db.scalar(select(Connection).limit(1)):
        raise SystemExit('La base no está vacía; no se mezclan datos.')
    for i,platform in enumerate(['facebook','instagram','x','tiktok']):
        c=Connection(platform=platform,external_id='demo_'+platform,name='DEMO · Institución ficticia',access='unavailable',status='disabled')
        db.add(c);db.flush()
        db.add(AccountObservation(connection_id=c.id,source='synthetic-demo',metrics={'followers':1000*(i+1)}))
        for day in range(14):
            p=Post(connection_id=c.id,platform=platform,external_id=f'demo_{platform}_{day}',text=f'DEMO · Ejemplo sintético de participación ciudadana {day+1}',url='',format='video' if platform=='tiktok' else 'text',published_at=now()-timedelta(days=day))
            db.add(p);db.flush()
            m={'likes':10+day,'comments':day+1,'shares':3,'reactions':12+day,'reposts':2,'quotes':1}
            db.add(Observation(post_id=p.id,source='synthetic-demo',metrics=m))
    db.commit()
print('Datos sintéticos creados exclusivamente en la base DEMO.')
