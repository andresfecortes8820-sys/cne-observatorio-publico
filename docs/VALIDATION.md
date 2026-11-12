# Validación de la entrega

## Revisión GitHub Pages

- 41 pruebas Python aprobadas, incluidas aprobación explícita, ausencia de credenciales, saneamiento de métricas/URLs, retirada de cuentas y cuotas del recolector.
- 5 pruebas Node aprobadas: zona horaria Bogotá, métricas desconocidas, filtros, paginación e históricos.
- Exportación estática de `/` y `/admin/` compilada correctamente.
- PostCSS fijado en 8.5.32; `npm audit` no reportó vulnerabilidades tras la actualización.
- GitHub Pages habilitado con GitHub Actions. Render pausado por la decisión de no usar servicios facturables.
- Sin credenciales de redes sociales: no se declara validación de captura en vivo ni actualización continua en tiempo real.

## Revisión de acceso público

**CI remoto confirmado:** [Validate and deploy #1](https://github.com/andresfecortes8820-sys/cne-observatorio-publico/actions/runs/43294014462), commit `d85b6cfe92c4f1197f78b473fe3555036e6af064`. Backend y frontend finalizaron en success: migraciones reversibles PostgreSQL, suite de pruebas, compilación Next.js, construcción de ambas imágenes Docker y validación de Compose. El job de despliegue quedó skipped porque `DEPLOY_ENABLED` y la infraestructura no están configurados. Esto valida construcción y pruebas; no demuestra una aplicación publicada ni una sincronización en vivo.

- **35 pruebas aprobadas** en Windows/Python 3.13, incluidas lectura anónima, separación de cuentas privadas, ausencia de tokens/scopes, retiro con invalidación de caché, historial, límites de consulta, paginación estable y consultas SQL acotadas.
- Compilación de producción Next.js aprobada para `/`, `/admin` y proxy de servidor `/api/[...path]`.
- Migraciones 001/002: subida, reversión y nueva subida comprobadas en SQLite.
- Verificación en navegador: dashboard ciudadano sin sesión, filtro de plataforma, logo CNE/paleta colombiana, estado vacío explícito, enlace a administración con login y regreso sin registro.
- La vista local se revisó con SQLite vacío y una caché de prueba en memoria. No se sembraron publicaciones ni métricas. No equivale a validación de Redis/PostgreSQL/worker en producción.
- El workflow de GitHub prepara pruebas contra PostgreSQL y builds Docker. Su ejecución remota debe confirmarse por separado; no se presume correcta solo por existir el archivo.
- Sin credenciales sociales reales, sin infraestructura aprovisionada y sin prueba de carga. URL de aplicación pendiente. El repositorio nuevo es público.

Las notas históricas del MVP que aparecen debajo se conservan como contexto; esta revisión es la validación vigente.

Entorno: Windows, Python 3.13.3, Node 22.16.0. Fecha de trabajo: 12 de noviembre de 2026.

| Comprobación | Resultado |
|---|---|
| Backend `pytest -q` | **25 pruebas aprobadas** |
| Next.js `npm run build` | **Aprobado**, compilación, TypeScript y generación de página |
| Alembic upgrade → downgrade → upgrade | **Aprobado en SQLite** |
| Vista local en navegador | Pantalla de inicio de sesión visible y revisada |
| REST | Cubierto con TestClient; sesión y limitador con Redis simulado |
| Exportaciones CSV/XLSX/PDF | Respuestas verificadas en pruebas de API |
| Conectores | X, TikTok y variantes Meta probados con transporte HTTP simulado |
| PostgreSQL / Redis / Celery en Compose | **No ejecutado**: Docker no está instalado en este equipo |
| Proveedores sociales en vivo | **No ejecutado**: no se suministraron credenciales ni autorizaciones |
| Dashboard autenticado en navegador, móvil y todos los flujos | **Pendiente de prueba integral con servicios activos** |
| Evaluación jurídica, pentest y carga | **Pendientes** |

La suite prueba restricciones de roles, CSRF/origen, sesión y logout, cifrado y no exposición de tokens, límite de rango, identidad de cuenta, paginación, permisos insuficientes, expiración, cuotas, normalización, deduplicación, históricos, última captura y cambio de día America/Bogota. El caso de límite de día detectó un problema de conversión de zona horaria que se corrigió antes del resultado final.

Una advertencia de deprecación proviene del uso de httpx por Starlette TestClient; no afecta estas pruebas. Las versiones instaladas se conservan en `backend/requirements.lock.txt` y `frontend/package-lock.json`.

La primera compilación falló al crear el directorio standalone por permisos de Windows; la compilación posterior con acceso autorizado terminó correctamente. El bucle asíncrono de Windows requirió ejecución fuera del sandbox para crear sus sockets internos. Las API sociales permanecieron simuladas durante esas pruebas.

No se declara esta entrega lista para producción. Ver los límites del MVP en el README y la matriz de capacidades antes de operar con datos reales.

