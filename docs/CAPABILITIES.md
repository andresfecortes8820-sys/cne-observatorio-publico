# Matriz de capacidades y restricciones

Revisión documental: 12 de noviembre de 2026. “Documentado” significa que se pudo leer la referencia oficial; no significa que la aplicación tenga autorización. Todas las integraciones reales están **pendientes de validación con credenciales**. No hay precios fijos garantizados. Revisar políticas y consola de cada proveedor antes de cada puesta en producción.

| Plataforma / operación o métrica | API / endpoint | Cuenta / permisos | Acceso y costo | Restricciones y estado |
|---|---|---|---|---|
| Facebook: identificación, nombre, seguidores | Graph `GET /{page-id}?fields=id,name,followers_count` | Página; token y permisos aplicables a Page | Revisión/activos; costos no verificados | Adaptador preparado; documentación Meta bloqueada; **pendiente de validación**, versión explícita requerida |
| Facebook: publicaciones, fecha, texto, enlace | Graph `GET /{page-id}/posts` | Página autorizada; revisar `pages_read_engagement` | Acceso según app/activo | Campos y acceso por versión pendientes de validación |
| Facebook: reacciones, número de comentarios, compartidos | Mismo endpoint, `reactions.summary`, `comments.summary`, `shares` | Permisos de lectura aplicables | Cuotas de app/negocio pendientes de verificar | Conteos solo cuando presentes; no descarga textos de comentarios |
| Facebook: descripción, video, alcance, impresiones | No implementado | Revisar `read_insights` y permisos por activo | Según producto y versión | **Pendiente**; sin endpoint ni métricas inventados; campos cambian por versión |
| Facebook: terceros y búsqueda de palabras clave | No implementado | Funciones/revisión específicas cuando existan | Elegibilidad por producto | No se presupone búsqueda global ni acceso a páginas públicas |
| Instagram: perfil, seguidores | Graph con Facebook Login, `GET /{ig-user-id}` | Profesional vinculado según flujo; revisar `instagram_basic`, `pages_read_engagement` | Revisión y permisos por activo; costo no verificado | Documentación no accesible; **pendiente de validación** |
| Instagram: medios, fechas, caption, enlaces y formato | Graph `GET /{ig-user-id}/media` | Cuenta profesional autorizada | Según acceso de app | Imágenes/videos/carruseles normalizados; Reels no se clasifican por campo específico en este MVP |
| Instagram: likes y comentarios | Mismo endpoint, campos `like_count,comments_count` | Lectura concedida al activo | Según permisos y restricciones del contenido | Ausentes permanecen desconocidos |
| Instagram: vistas, alcance, impresiones, audiencia histórica privada | No implementado | Revisar `instagram_manage_insights`; métricas/versiones a confirmar | Revisión y propiedad | No se mapea una métrica eliminada a cero |
| Instagram: Business Discovery / hashtags | No implementado | Producto y permisos específicos | Según aprobación | No confundir con acceso a cualquier cuenta personal |
| X: perfil y seguidores | X v2 `GET /2/users/{id}`, `user.fields=public_metrics` | Usuario accesible; bearer de app o usuario con acceso autorizado | Créditos y permisos de consola; tarifa por endpoint | [Perfil oficial](https://docs.x.com/x-api/users/get-user-by-id); documentado, sin prueba live |
| X: texto, fecha, enlace, formato | X v2 `GET /2/users/{id}/tweets`, expansiones de medios | Timeline accesible | Acceso/consumo contratado | [Timeline oficial](https://docs.x.com/x-api/users/get-posts); paginación y `since_id`; no garantiza archivo completo |
| X: likes, respuestas, reposts y citas | `public_metrics` del timeline | Según disponibilidad por post | Misma operación de lectura | No se suman likes a reacciones de Facebook como si fueran la misma definición |
| X: impresiones | `public_metrics.impression_count` si el proveedor lo devuelve | Según acceso/visibilidad | Según producto | Se conserva por publicación cuando presente; no se ofrece agregado transversal |
| X: búsqueda reciente, menciones, video y datos privados | No implementado | Requiere permisos/entitlements por endpoint | Créditos y elegibilidad | Pendiente; no se anuncia cobertura total |
| TikTok: perfil básico | Display `GET /v2/user/info/` | Usuario que autorizó; `user.info.basic` | App/producto aprobado; costo no establecido en la referencia | [Referencia oficial](https://developers.tiktok.com/docs/en/tiktok-api-v2-get-user-info); valida `open_id` |
| TikTok: seguidores/audiencia | Campo `follower_count` requiere `user.info.stats` | Usuario autorizado y scope aprobado | Según aprobación | **No implementado**; Login Kit no concede estas métricas por sí solo |
| TikTok: videos, fecha, texto, URL | Display `POST /v2/video/list/` | Usuario autorizado; `video.list` | Producto habilitado | [Referencia oficial](https://developers.tiktok.com/docs/en/tiktok-api-v2-video-list); hasta 20 por página, cursor y `has_more` |
| TikTok: vistas, likes, comentarios y compartidos | Campos de video de Display API | Scope de lectura y disponibilidad | Misma consulta | Guardados solo si presentes; vistas no se suman a impresiones de otras redes |
| TikTok: terceros y búsquedas públicas | Research API, sin implementación de endpoint en MVP | Proyecto de investigación aprobado y credenciales independientes | Elegibilidad específica; costo no confirmado | [Acceso Research](https://developers.tiktok.com/docs/en/research-api-get-started); no sustituible por token de Display |

## Cuotas y costos

X publica [límites por endpoint](https://docs.x.com/x-api/fundamentals/rate-limits) y [consumo por créditos](https://docs.x.com/x-api/getting-started/pricing). El precio efectivo debe consultarse en la consola; no se codifica una cifra ni un supuesto plan universal. Este MVP reconoce HTTP 429 y reintenta después de cooldown, pero no interpreta todavía todos los encabezados de reinicio específicos de X.

TikTok documenta una ventana móvil de un minuto con límite predeterminado de 600 solicitudes para cada uno de `user/info`, `video/query` y `video/list`; la aprobación puede modificarlo. El conector opera muy por debajo con frecuencia mínima de cinco minutos y paginación acotada. Ver [límites oficiales](https://developers.tiktok.com/docs/en/tiktok-api-v2-rate-limit).

Meta: no se pudo verificar la documentación por error de acceso/429. Se intentaron las referencias oficiales [Page posts](https://developers.facebook.com/docs/graph-api/reference/page/posts/) e [Instagram con Facebook Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/). Los contratos están marcados pendientes y requieren validación manual en la versión soportada antes de su uso real. El adaptador se niega a consultar sin `META_GRAPH_VERSION`.

## Metodología de métricas

- Facebook: interacciones = reacciones + comentarios + compartidos.
- Instagram: likes + comentarios.
- X: likes + respuestas + reposts + citas.
- TikTok: likes + comentarios + compartidos.

Solo se calcula ese total si todos sus componentes están presentes. Son definiciones diferentes y el agregado indica cobertura por plataforma/publicación. No son usuarios únicos ni deduplicación de personas. El cero existe únicamente cuando la API devuelve cero. Seguidores: última captura por cuenta, sin extrapolación. Crecimiento, engagement y deltas de interacción por período requieren baseline temporal comparable y todavía no se calculan. Los filtros seleccionan fechas de publicación, no fechas de ocurrencia de cada interacción.
