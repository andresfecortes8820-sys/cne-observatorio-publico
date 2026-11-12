# Publicación en internet y estado verificable

## Decisión vigente: solo GitHub

Se eligió GitHub Pages + Actions para evitar contratar alojamiento. Ver `GITHUB_ONLY.md` para la arquitectura activa, sus límites y configuración de datos reales. Render está pausado. La documentación de servidor Linux de abajo se conserva como alternativa futura y no describe un servicio contratado.

## Repositorio principal

Proyecto nuevo: https://github.com/andresfecortes8820-sys/cne-observatorio-publico. El proyecto previo `CNE` no se modifica. El código se organiza desde la raíz de este repositorio; `.github/workflows/ci-deploy.yml` debe permanecer en la raíz, no dentro de una subcarpeta.

El logo original está en `frontend/public/logo-cne.jpeg`. La interfaz utiliza amarillo, azul y rojo de Colombia. `LICENSE.md` mantiene la licencia pendiente de decisión; publicar un repositorio no equivale todavía a conceder una licencia de código abierto.

## Arquitectura pública

```text
Ciudadano sin registro
       │ HTTPS
       ▼
Caddy / dominio público
  ├── / y /admin → Next.js
  └── /api/* → FastAPI
                     ├── /public/* → Redis + PostgreSQL (solo cuentas publicadas)
                     ├── login → sesión de administrador
                     └── operaciones privadas → rol admin + CSRF + origen

Celery Beat → Redis → Worker → API oficiales → PostgreSQL
```

El navegador no recibe tokens sociales ni llama a Meta, X o TikTok. Las páginas públicas tampoco encolan sincronizaciones. La base centralizada es la misma para todos los visitantes. La API devuelve una lista explícita de campos públicos; no serializa conexiones, scopes, tokens, errores internos ni auditorías.

Todas las cuentas migradas o nuevas comienzan con `publish_enabled=false`. El administrador debe habilitar su publicación expresamente después de revisar los derechos para divulgar contenido y métricas. La autorización para recopilar no se presume equivalente a autorización para redistribuir. Una cuenta retirada desaparece de las consultas públicas y se invalida la caché. El entorno DEMO no expone rutas públicas.

## Rutas públicas

| Ruta bajo `/api` | Uso |
|---|---|
| GET /public/accounts | Catálogo aprobado, fuente y fecha de captura, máximo 200 cuentas |
| GET /public/dashboard | Indicadores, tendencias por fecha de publicación, comparación, cobertura y metodología |
| GET /public/posts | Lista estable paginada, `page=1..200`, `page_size=1..100`, valor por defecto 25 |
| GET /public/posts/{id} | Histórico de observaciones, 50 por página, fuente y captura |

Las fechas de los filtros son inclusivas en America/Bogota. Rango máximo 366 días; palabra clave de hasta 100 caracteres. El resumen usa hasta 5.000 publicaciones por período, avisa si está acotado e impide interpretar esa muestra como universo total. La interfaz no anuncia la variación porcentual del resumen cuando no existe una base comparable completa.

La tabla usa paginación y exporta CSV de la página actual. XLSX/PDF completos siguen reservados al panel privado. No se ofrece una exportación pública ilimitada que pueda agotar recursos. Las observaciones conservan métricas disponibles; no hay sentimiento estimado ni alcance inventado.

## Caché y protección contra abuso

Redis almacena respuestas 60 segundos. `PUBLIC_CACHE_SECONDS` y `PUBLIC_REQUESTS_PER_MINUTE` son configurables. Límite inicial: 120 solicitudes públicas por IP/minuto, respuestas 429 con Retry-After. Redis caído implica respuesta 503; nunca información inventada ni acceso sin limitador. Redis usa `noeviction` para no perder locks/trabajos silenciosamente: monitorear memoria y aumentar capacidad según carga.

Las consultas de publicación usan una ventana SQL para seleccionar la última observación, evitando una consulta adicional por publicación. La migración 002 agrega índices para conexión/fecha y selección de observaciones. La prueba de consulta pública verifica un número acotado de consultas SQL.

La identidad de IP procede del proxy de confianza. En producción, únicamente Caddy expone puertos. Uvicorn acepta encabezados reenviados desde la red interna; no se debe publicar el puerto de la API ni colocar un proxy que conserve encabezados de IP arbitrarios del cliente. En desarrollo, el proxy Next.js elimina los encabezados reenviados y el limitador puede compartir la IP local de ese proxy; esto es deliberadamente conservador.

## Opción de producción preparada: servidor Linux con Docker

GitHub Pages no ejecuta FastAPI, PostgreSQL, Redis o Celery. La configuración entregada usa `compose.production.yaml`, un host Linux con Docker Compose y Caddy con HTTPS. No se han contratado servicios ni generado facturas.

Pasos pendientes para activar esta opción:

1. Proveer un servidor Linux con capacidad adecuada, disco persistente, Docker Engine y Compose. Crear un usuario de despliegue y directorio `/opt/cne`; proteger su acceso SSH.
2. Elegir un dominio/subdominio y dirigir sus registros A/AAAA al servidor. Permitir 80/443; restringir SSH a administradores. No abrir PostgreSQL, Redis ni FastAPI al exterior.
3. En el servidor, clonar el repositorio y ejecutar `python3 scripts/setup_env.py`. Guardar `.env` en `/opt/cne/.env`, accesible solo por el usuario de despliegue. Configurar `PUBLIC_DOMAIN`, `FRONTEND_ORIGIN=https://dominio`, `COOKIE_SECURE=true`, `PRODUCTION=true`, `DEMO_MODE=false`. Las URLs de BD y Redis deben usar `db` y `redis` de la red interna.
4. Instalar `deploy/deploy-release.sh` como `/opt/cne/deploy-release.sh`. El usuario de despliegue necesita poder manejar Docker; ese acceso es administrativo sobre el host y debe limitarse.
5. Lanzar la primera instancia con `docker compose -p cne -f compose.production.yaml up --build -d`. La migración se ejecuta antes de la API. Usar el mismo nombre de proyecto `cne` en despliegues futuros para conservar volúmenes.
6. Verificar `https://dominio/`, `https://dominio/api/public/accounts` y `https://dominio/admin`. La primera debe abrir sin sesión. Las rutas privadas deben responder 401/403 para usuarios no autorizados.
7. Configurar respaldos cifrados de PostgreSQL, restauración probada, monitorización de disco/Redis, actualización de imágenes y procedimientos de retiro de datos. La configuración no constituye todavía certificación de alta disponibilidad ni prueba de carga.

Caddy administra certificados y redirección a HTTPS cuando el dominio y los puertos están correctamente configurados. Fuentes: [HTTPS automático](https://caddyserver.com/docs/automatic-https) y [proxy inverso](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

## GitHub Actions

Cada push a main o pull request ejecuta:

- Migraciones y pruebas del backend contra PostgreSQL 17 real en el runner.
- Compilación Next.js, construcción de imágenes Docker y validación de Compose.
- En main, despliegue SSH solamente cuando `DEPLOY_ENABLED=true` y existe el environment `production` con los secretos requeridos.

Crear en GitHub:

| Tipo | Nombre | Valor |
|---|---|---|
| Secret de production | DEPLOY_HOST | Host/IP del servidor |
| Secret de production | DEPLOY_USER | Usuario SSH de despliegue |
| Secret de production | DEPLOY_SSH_KEY | Clave privada dedicada |
| Secret de production | DEPLOY_KNOWN_HOSTS | Clave pública del servidor, verificada fuera de banda |
| Variable | DEPLOY_ENABLED | `true` después del primer despliegue verificado |
| Variable | PUBLIC_URL | URL HTTPS sin barra final |

El workflow transfiere el commit validado con `git archive`, construye en el servidor, aplica migraciones y comprueba la web y la API pública. No desactiva verificación SSH. Conserva releases y volúmenes. Antes de una migración incompatible se necesita respaldo y un plan de reversión; el script no revierte automáticamente la base de datos. Los secrets de API sociales permanecen en el servidor, no en el repositorio ni en Actions.

Configurar la protección de `main`, checks obligatorios y revisiones según la política institucional. [Documentación oficial de environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments).

## Alojamiento gestionado nuevo

Se identificó Render como proveedor compatible y se abrió su opción de conexión. No está confirmado su acceso ni se han creado servicios. La conexión debe completarse antes de aprovisionar. No se activa un plan facturable sin conocer el presupuesto autorizado.

Una alternativa gestionada necesita servicio Node para Next.js, servicio Python para FastAPI, PostgreSQL persistente, Redis, worker y scheduler. Debe mantener las cookies y el origen bajo un dominio común o proxy correctamente configurado. No copiar el stack de Compose en GitHub Pages ni suponer que un hosting estático ejecuta trabajos Python.

Si se elige Render, revisar sus [tipos de servicios y Blueprints](https://render.com/docs/blueprint-spec) y [despliegues después de CI](https://render.com/docs/deploys). No hay un Blueprint activado: hace falta elegir planes, presupuesto, región y provisión de los servicios.

## Datos reales y URL

No se proporcionaron tokens de Meta/X/TikTok ni una base con capturas reales autorizadas. Por eso la vista muestra estados vacíos o indisponibilidad del servicio, sin relleno numérico. Para poblarla: iniciar sesión como admin, registrar una cuenta/token oficial, validar permisos y expiración, ejecutar sincronización, comprobar observaciones y habilitar publicación.

La URL del repositorio es real. La URL pública de la aplicación queda pendiente de infraestructura/proveedor conectado y configuración de dominio. La documentación no inventa una URL ni declara un despliegue no realizado.
