# Operación gratuita solo con GitHub

Esta modalidad responde a la decisión de no contratar alojamiento. GitHub Pages publica HTML/JS/JSON. GitHub Actions ejecuta Python en servidores temporales y consulta API oficiales únicamente cuando el administrador habilita cuentas y credenciales. Pages no ejecuta FastAPI ni PostgreSQL.

## URL

La ruta de publicación prevista es `https://andresfecortes8820-sys.github.io/cne-observatorio-publico/`. Confirmar el despliegue y abrirla antes de declararla disponible. `/admin/` muestra accesos a la administración del repositorio; GitHub controla los permisos.

Render fue pausado y no se activaron planes facturables. El stack FastAPI/PostgreSQL/Redis/Celery se conserva como opción futura, pero no es el backend permanente de esta modalidad.

## Datos reales

### Perfiles de interés suministrados

Se registraron Instagram `cne_colombia`, X `cne_colombia`, TikTok `consejonacionalelectoral` y el enlace compartido de Facebook `https://www.facebook.com/share/1C5Jxh6Ux7/`. Se quitaron parámetros de seguimiento; no se extrajeron publicaciones ni cifras de las páginas web.

Están en `watchlist`, separados de `accounts`. El enlace corto de Facebook no se convierte en un identificador de página inventado; el ID oficial está pendiente. El equipo confirmó que administra las cuatro cuentas. La vista pública muestra “acceso API pendiente”, no “conectado”. El registro de perfiles no incrementa el número de cuentas con métricas disponibles. El foco vigente son comentarios y respuestas de la audiencia; ver `AUDIENCE_LISTENING.md`.

Para terceros, el acceso depende del producto aprobado: por ejemplo, TikTok Display requiere un usuario que autoriza; Research tiene elegibilidad y credenciales distintas. X documenta lectura de usuarios mediante bearer autorizado. Meta requiere verificar permisos y funciones aplicables; la documentación devolvió 429 durante la revisión. No se presume acceso universal por ser perfiles públicos.

Referencias: [X User Lookup](https://docs.x.com/x-api/users/get-user-by-username), [TikTok Display](https://developers.tiktok.com/docs/en/display-api-get-started), [TikTok Research](https://developers.tiktok.com/docs/en/research-api-get-started).

No se proporcionaron credenciales de Meta, X o TikTok. `config/public_accounts.json` empieza vacío y `data/observatory.json` no contiene publicaciones ni métricas de demostración. Publicar la interfaz no equivale a tener acceso API.

Para habilitar una cuenta:

1. Obtener consentimiento, permisos, revisión y token mediante el proveedor oficial. Las condiciones de acceso o consulta de una API pueden tener costos propios: no están incluidos por usar GitHub gratis.
2. En [Secrets de Actions](https://github.com/andresfecortes8820-sys/cne-observatorio-publico/settings/secrets/actions), registrar el secreto correspondiente. Nunca pegarlo en el código, un issue ni el chat.
3. Editar `config/public_accounts.json` con ID oficial, nombre y publicación expresamente aprobada. Esta versión admite una cuenta por plataforma para que cada token corresponda a un activo autorizado.

```json
{
  "accounts": [
    {
      "platform": "x",
      "external_id": "REEMPLAZAR_CON_ID_OFICIAL",
      "name": "REEMPLAZAR_CON_NOMBRE",
      "category": "Institución",
      "approved_for_publication": true,
      "interval_minutes": 60
    }
  ]
}
```

El ejemplo no configura una cuenta real. El ID debe obtenerse de la API autorizada; no se supone que el usuario o la URL sean un identificador válido.

| Plataforma | Secreto de GitHub |
|---|---|
| Facebook | FACEBOOK_ACCESS_TOKEN |
| Instagram | INSTAGRAM_ACCESS_TOKEN |
| X | X_ACCESS_TOKEN |
| TikTok | TIKTOK_ACCESS_TOKEN |

4. En Variables de Actions, establecer `API_SYNC_ENABLED=true` después de aprobar permisos, divulgación y cualquier costo del proveedor. Para Meta, configurar también `META_GRAPH_VERSION` con una versión vigente validada: su documentación no pudo verificarse completamente durante el desarrollo.
5. Ejecutar `Public dashboard on GitHub Pages` desde Actions y revisar el estado de las fuentes y las capturas publicadas. Un error de permisos, cuota o token no se reemplaza con cifras ficticias.

## Actualización: no es tiempo real continuo

El workflow intenta ejecutarse cada 15 minutos. Cada cuenta tiene un intervalo mínimo configurable de 15 minutos; el valor de ejemplo es 60 minutos. La ejecución de GitHub puede retrasarse y las cuotas pueden impedir consultas. La web comprueba cada minuto si existe una nueva captura; el CDN puede conservarla temporalmente. Esto no garantiza que una publicación aparezca en segundos.

No se implementan webhooks ni streams continuos en Pages. El tiempo real requiere capacidades del proveedor y una infraestructura que procese eventos de forma continua; no se promete que todas las plataformas lo ofrezcan ni que sea gratuito. [Programación de GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

El recolector limita cada cuenta a dos páginas por ejecución y una ventana de 90 días. Captura parcial se identifica como tal. Conserva hasta 2.000 publicaciones y 24 observaciones por publicación. Los contadores solo existen si el proveedor los devuelve; un campo ausente es no disponible. La configuración y la captura pública se guardan centralizadas en el repositorio, sin tokens ni base privada exportada.

Retirar una cuenta de la configuración y volver a ejecutar el workflow elimina su contenido del snapshot vigente. Los commits históricos públicos pueden conservar copias anteriores; no habilitar publicación sin evaluar previamente los derechos y la retención. No usar esta modalidad para datos cuya eliminación histórica deba garantizarse inmediatamente.

## Seguridad y costos

Los tokens solo se inyectan en el paso de Python del workflow; no se entregan al build del frontend ni al navegador. El collector serializa un esquema explícito y elimina parámetros de consulta de las URLs. No hay scraping ni evasión de restricciones. El administrador es quien tiene permisos sobre el repositorio; no existe registro de ciudadanos.

Pages y los runners estándar de Actions para repositorios públicos se usan en sus condiciones gratuitas. No se han activado planes, runners especiales ni servicios de pago. No se garantiza capacidad ilimitada; aplicar las políticas y límites de GitHub. Las API sociales pueden exigir aprobación o pago independiente.

Los workflows programados en repositorios públicos pueden deshabilitarse tras inactividad del repositorio; supervisar el estado de Actions y las marcas de captura. La fuente oficial de la disponibilidad de una métrica sigue siendo cada API, no la fecha del último build.

## Verificación local

```powershell
python scripts/collect_public.py
node --test frontend/tests/snapshot.test.mjs
node scripts/build_pages.mjs
```

El último comando excluye temporalmente el proxy dinámico, compila una exportación estática y restaura los archivos del servidor. Para reproducir el prefijo de GitHub, establecer `NEXT_PUBLIC_BASE_PATH=/cne-observatorio-publico`. El backend permanente continúa usando `npm run build` normal.
