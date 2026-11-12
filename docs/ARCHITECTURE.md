# Arquitectura y contratos

## Arquitectura pública vigente

La revisión pública separa `/` (ciudadanía), `/admin` (administradores) y `/public/*` (lectura anónima validada y cacheada). `connections.publish_enabled` requiere habilitación expresa. Ver `PUBLIC_DEPLOYMENT.md` para proxy, límites, aislamiento y CI/CD; esta revisión prevalece sobre las notas del MVP inicial. El rol analyst queda sin facultades de modificación.

```text
frontend/app/           Next.js, componentes y estilos
backend/app/main.py    REST y controles de acceso
backend/app/models.py  Esquema SQLAlchemy
backend/app/security.py Sesión, CSRF, roles y cifrado
backend/app/connectors.py Adaptadores oficiales de solo lectura
backend/app/sync.py    Normalización, upsert y observaciones
backend/app/tasks.py   Celery worker + beat
backend/app/analytics.py Filtros y cálculos
backend/migrations/   Alembic
backend/tests/        API, seguridad, conectores y métricas
scripts/              Preparación de secretos y demo
docs/                 Matriz, operación y validación
```

Flujo: navegador → FastAPI → PostgreSQL. La API encola trabajos en Redis; Celery consulta proveedores con tokens descifrados en memoria, guarda observaciones y checkpoints en la misma transacción. Beat consulta vencimientos cada minuto. La frecuencia es configurable por conexión; no se promete tiempo real.

## Entidades

`users`: hash Argon2, rol, estado. `connections`: cuenta/plataforma, categoría, tipo de acceso, scopes declarados, token cifrado, expiración, estado, frecuencia y cursor. `posts`: identificador único por plataforma, fecha, texto, formato, vínculo, tema y sentimiento. `post_observations` / `account_observations`: métricas como objetos JSON, fuente y fecha UTC. Ausencia de clave significa no disponible, nunca cero implícito.

`sync_runs`: ejecución y resultado. `monitors`: términos de seguimiento local. `alerts`: incidencias operativas. `audit_logs`: acciones sin secretos. Roles, plataformas y permisos son catálogos de código del MVP, no tablas independientes. Resultados de búsquedas remotas, clasificaciones/versiones de modelos, reglas de alertas y campañas se añadirán en las fases avanzadas.

## REST

La especificación exacta se genera en `/openapi.json`.

| Ruta | Acceso | Función |
|---|---|---|
| POST /auth/login | público con limitador | Sesión de 8 horas |
| GET /auth/me; POST /auth/logout | autenticado | Sesión |
| GET /connections | autenticado | Estado, sin tokens |
| POST /connections | admin | Alta de cuenta/token autorizado |
| PATCH /connections/{id}/credentials | admin | Rotación manual |
| DELETE /connections/{id} | admin | Borra token y deshabilita; conserva histórico |
| POST /connections/{id}/sync | analyst/admin | Encola consulta |
| GET /dashboard; GET /posts | autenticado | Filtros y analítica |
| GET /posts/{id} | autenticado | Histórico de publicación |
| GET /alerts; PATCH /alerts/{id}/read | lectura / analyst | Incidencias |
| GET/POST /monitors | lectura / analyst | Seguimiento local |
| GET /export/{csv,xlsx,pdf} | autenticado | Hasta 1.000 publicaciones |
| GET /sync-runs | autenticado | Historial operativo |
| GET /audit; POST /users | admin | Auditoría y usuarios |

Filtros: `start`, `end` (fechas inclusivas en zona configurada), `platform`, `account`, `keyword`, `format`, `topic`. El límite de rango es 366 días. Intervalos de comparación tienen igual número de días. La interfaz usa America/Bogota; el backend permite `TIMEZONE`, pero cambiarla exige adaptar también el selector de fechas del frontend en esta versión.

## Integraciones

Cada adaptador devuelve `Batch(profile, posts, cursor, complete, source)`. El checkpoint solo avanza el watermark temporal cuando termina la paginación. Las URLs absolutas de paginación nunca se siguen: se extrae solo el cursor para conservar el host oficial. Errores de proveedor se traducen a códigos sin persistir cuerpos que puedan contener secretos. Respuestas parciales de X se rechazan para no declarar una captura completa.

Bloqueo distribuido Redis y bloqueo de fila PostgreSQL evitan escrituras concurrentes. SQLite es únicamente para pruebas; no sustituye las garantías de concurrencia de PostgreSQL. Una página por trabajo limita consumo. En respuestas parciales se reanuda cada minuto. Reintentos HTTP acotados: 3 intentos para red/5xx. Cuotas se reintentan después de `Retry-After`; sin ese encabezado, tras 60 segundos. No se implementa aún un planificador adaptativo basado en los encabezados específicos de cada proveedor.

## Siguientes fases

1. Completar OAuth Authorization Code + PKCE/estado, descubrimiento de activos, rotación y revocación.
2. Validar conectores con credenciales reales y permisos por activo; añadir insights probados por versión y consulta de capacidades.
3. Refresco de publicaciones históricas de X; comparaciones por observaciones al cierre de cada período.
4. Búsqueda pública X según acceso, productos de investigación sujetos a aprobación, clasificación y sentimiento versionados con nivel de confianza.
5. Reglas estadísticas con mínimo histórico y supresión de duplicados; correo mediante cola de salida.
6. Informes con gráficos, campañas, paginación y exportaciones asíncronas, recuperación de cuenta, MFA, SSO y auditoría externa.
