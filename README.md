# CNE · Observatorio público de redes sociales

## Modalidad activa: solo GitHub, sin alojamiento contratado

Por decisión del usuario, la publicación activa utiliza **GitHub Pages + GitHub Actions**. El dashboard público consume capturas JSON; Python se ejecuta en Actions. La administración privada se realiza con permisos del repositorio. Render está pausado. Las instrucciones Docker de abajo corresponden a la alternativa con backend permanente.

**[Guía de operación gratuita y acceso a datos reales](docs/GITHUB_ONLY.md).** El workflow intenta actualizar cada 15 minutos según el intervalo de cuenta y las cuotas. No ofrece tiempo real continuo. Aún no hay cuentas ni credenciales sociales configuradas; no se incluyen datos ficticios.

Dashboard ciudadano sin registro y administración privada. Identidad visual con el logo del CNE proporcionado por el usuario y la bandera de Colombia.

**Repositorio:** https://github.com/andresfecortes8820-sys/cne-observatorio-publico

## Acceso

- `/`: indicadores, publicaciones paginadas, comparación, capturas históricas y metodología sin iniciar sesión.
- `/admin`: inicio de sesión exclusivo para administradores autorizados; conexiones, tokens, cuentas, monitoreo y publicación.
- `/api/public/*`: REST de solo lectura, con caché y límites de consulta.
- `/api/docs`: contratos OpenAPI. Ninguna respuesta pública contiene tokens o scopes privados.

Las cuentas son privadas por defecto. El administrador debe habilitar expresamente aquellas cuya divulgación esté autorizada. El entorno DEMO no sirve datos en las rutas públicas. El ciudadano consulta PostgreSQL/Redis; solo los workers consultan las API sociales.

## Arranque local

Requisitos: Docker Desktop/Engine con Compose y Python 3.10+.

```powershell
python scripts/setup_env.py
docker compose up --build -d
```

Abrir http://localhost:3000 sin iniciar sesión. Administración: http://localhost:3000/admin. Usuario y contraseña iniciales: `ADMIN_EMAIL` y `ADMIN_PASSWORD` en `.env`; el script genera secretos sin imprimirlos. API de desarrollo: http://localhost:8000/docs.

```powershell
docker compose logs --tail 100 api worker scheduler
docker compose down
```

Los volúmenes conservan información. Respaldar antes de cambiar esquemas y no eliminar volúmenes con datos que deban conservarse.

## Incorporar datos reales

1. Obtener el producto, consentimiento, revisión, permisos y token oficiales del proveedor.
2. Registrar cuenta/token desde `/admin`; se cifra y no se devuelve al navegador.
3. Validar la versión Meta antes de configurar `META_GRAPH_VERSION`; su documentación no pudo verificarse completamente durante el desarrollo.
4. Sincronizar y revisar errores, fuente, captura y cobertura.
5. Habilitar publicación solo después de revisar los derechos para divulgar contenido y métricas. La autorización de captura no se presume equivalente a redistribución.

No hay credenciales reales incluidas ni métricas de relleno. Las integraciones reales siguen pendientes de permisos. Ver [credenciales](docs/CREDENTIALS.md) y [matriz](docs/CAPABILITIES.md).

## Producción y GitHub Actions

`.github/workflows/ci-deploy.yml` ejecuta pruebas, migraciones PostgreSQL, build Next.js e imágenes Docker. En main puede desplegar automáticamente por SSH al configurar el environment `production`, secretos y `DEPLOY_ENABLED=true`.

`compose.production.yaml` aloja Next.js, FastAPI, PostgreSQL, Redis, Celery y Caddy con HTTPS bajo un dominio común. Solo expone 80/443. GitHub Pages no ejecuta este backend ni la base de datos.

**[Guía de publicación, API pública y pasos pendientes](docs/PUBLIC_DEPLOYMENT.md).** Se necesita un host/proveedor conectado y dominio para entregar una URL pública operativa. No se declara la aplicación publicada por tener el código en GitHub.

## Stack y estructura

```text
frontend/app/page.tsx         Dashboard público
frontend/app/admin/page.tsx   Administración privada
frontend/app/api/             Proxy local del backend
frontend/public/             Logo original del CNE
backend/app/public.py        Lectura ciudadana, caché y límites
backend/app/main.py          Administración y autenticación
backend/app/analytics.py     Cálculos y última observación
backend/app/connectors.py    Adaptadores oficiales de lectura
backend/app/sync.py          Upsert e históricos
backend/app/tasks.py         Celery y programación
backend/migrations/          Migraciones versionadas
backend/tests/               Seguridad, API, métricas y conectores
deploy/                     Proxy HTTPS y releases
.github/workflows/           CI/CD
```

Next.js, React, TypeScript, Recharts; FastAPI; SQLAlchemy/Alembic; PostgreSQL, Redis y Celery. CSS propio responsive y modo oscuro. No se usa Tailwind/shadcn en esta versión.

## Desarrollo sin Docker

Necesitas PostgreSQL y Redis. Configura las variables de `.env.example` en el entorno o en `backend/.env`. En local usa `FRONTEND_ORIGIN=http://localhost:3000`, `COOKIE_SECURE=false` y URLs accesibles de BD/Redis.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.lock.txt
cd backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

En terminales separadas desde backend:

```powershell
..\.venv\Scripts\python -m celery -A app.tasks.celery worker --pool=solo --loglevel=warning
..\.venv\Scripts\python -m celery -A app.tasks.celery beat --loglevel=warning
```

Celery de producción debe ejecutarse en Linux. Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

`/api` usa un proxy local a `http://localhost:8000`; `API_INTERNAL_URL` cambia su destino desde el servidor. En producción Caddy dirige `/api` directamente a FastAPI. Nunca agregar tokens a `NEXT_PUBLIC_*`.

## Validación y límites

Desde backend: `python -m pytest -q`. Desde frontend: `npm run build`.

Ver [resultados reales](docs/VALIDATION.md). Las pruebas de proveedores son simuladas y no certifican acceso en vivo. El resumen público tiene límite explícito de 5.000 publicaciones; tabla paginada, 25 por página. “No disponible” no se transforma en cero.

Pendientes: OAuth interactivo, refresco automático de tokens, búsqueda remota autorizada, insights privados, clasificación/sentimiento con IA, alertas estadísticas, correo y reportes ejecutivos con gráficos. X incorpora publicaciones incrementales; refrescar sus métricas antiguas necesita un trabajo adicional. Las alertas operativas y exportadores privados CSV/XLSX/PDF sí existen.

No es todavía SaaS multitenant ni una certificación normativa. Antes de producción: prueba integral en servicios activos, carga, seguridad, retención, derechos de redistribución y revisión institucional. Ver [seguridad](docs/SECURITY.md), [arquitectura](docs/ARCHITECTURE.md) y [licencia pendiente](LICENSE.md).
