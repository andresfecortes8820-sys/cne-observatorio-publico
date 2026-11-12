"""Generate local secrets once, without displaying them in logs."""
from pathlib import Path
import base64
import secrets

root=Path(__file__).resolve().parents[1]
target=root/'.env'
if target.exists():
    raise SystemExit('.env ya existe; se conserva sin cambios.')
password=secrets.token_urlsafe(24)
text=(root/'.env.example').read_text(encoding='utf-8')
text=text.replace('JWT_SECRET=\n','JWT_SECRET='+secrets.token_urlsafe(48)+'\n').replace('TOKEN_KEY=\n','TOKEN_KEY='+base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()+'\n').replace('ADMIN_PASSWORD=\n','ADMIN_PASSWORD='+secrets.token_urlsafe(18)+'\n').replace('POSTGRES_PASSWORD=\n','POSTGRES_PASSWORD='+password+'\n').replace('CHANGE_ME',password)
target.write_text(text,encoding='utf-8')
print('Archivo .env creado. Consulta ADMIN_PASSWORD localmente; no lo publiques.')
