# Escucha: lo que la gente escribe sobre el CNE

El equipo confirmó que administra Instagram `cne_colombia`, X `cne_colombia`, Facebook mediante el enlace compartido y TikTok `consejonacionalelectoral`. El objetivo principal es leer comentarios y respuestas de la audiencia, no solamente indicadores de publicaciones del CNE. La vista inicial de GitHub Pages pasa a “Lo que opina la gente”.

## Implementado

- Modelo de opiniones separado de publicaciones y contadores.
- Adaptador X para respuestas públicas en conversaciones de publicaciones del CNE mediante búsqueda reciente.
- Adaptadores Meta de comentarios, preparados y sujetos a validación del contrato en la versión elegida.
- Excluir respuestas del titular cuando se identifica al autor; no publicar comentarios ocultos o de visibilidad desconocida de Meta.
- Guardar texto, fecha, fuente, contexto y captura; no guardar nombres ni perfiles de quienes comentan.
- Filtros, lista de textos recibidos y conteo de palabras por comentario (descriptivo, no afinidad política).
- Sentimiento `indeterminado`: no se calculan porcentajes ni etiquetas inventadas. Análisis con modelo de IA pendiente.

Las menciones globales, respuestas anidadas completas y búsquedas de toda la conversación pública aún no están implementadas. No se afirma cobertura de todas las opiniones del país. Las publicaciones de la institución no se contabilizan como opiniones ciudadanas.

## Acceso requerido

| Red | Texto de la audiencia | Estado |
|---|---|---|
| Facebook | Comentarios en publicaciones autorizadas; revisar `pages_read_user_content` y dependencias de la app | Preparado; documentación Meta bloqueada con 429, exige validación en activo de prueba |
| Instagram | Comentarios de medios profesionales; permisos del flujo Facebook Login usado, incluido el de comentarios aplicable | Preparado; requiere autorización y validación |
| X | `GET /2/tweets/search/recent` con búsqueda por conversación; últimos 7 días y acceso efectivo al endpoint | Contrato documentado y probado con transporte simulado; sin credenciales reales |
| TikTok | Display API no basta para texto de comentarios. Accounts API for Business contempla comentarios de videos propios bajo producto/permisos específicos | Pendiente; no se reutiliza un token Display como autorización para otro producto |

Fuentes oficiales: [búsqueda reciente de X](https://docs.x.com/x-api/posts/search-recent-posts), [comentarios de Instagram](https://developers.facebook.com/docs/instagram-platform/comment-moderation/), [comentarios Graph](https://developers.facebook.com/docs/graph-api/reference/object/comments/), [TikTok Accounts API](https://business-api.tiktok.com/gateway/docs/index?doc_id=1737565048641538&language=ENGLISH). La API de comentarios de anuncios de TikTok no se confunde con comentarios orgánicos de videos propios.

## Activación segura en GitHub

1. Tener la app/API oficial de cada red con los permisos de lectura correspondientes. Confirmar los identificadores oficiales: un username o enlace no se convierte en ID arbitrario.
2. Guardar los tokens en Secrets de GitHub, nunca en el chat ni en archivos públicos.
3. Registrar las cuentas autorizadas en `accounts` con `approved_for_publication=true`, tras revisar la divulgación de comentarios. `watchlist` identifica perfiles, pero no concede permisos API.
4. Habilitar `API_SYNC_ENABLED` para publicaciones de contexto y `LISTENING_SYNC_ENABLED` para textos recibidos. Para Meta, activar `META_COMMENTS_VALIDATED` solo después de verificar el contrato en su versión soportada y revisar los campos de visibilidad.
5. Ejecutar el workflow y verificar textos reales, fuentes, fechas y cobertura. Si faltan permisos o datos, el tablero lo dice.

El recolector de escucha revisa hasta dos publicaciones recientes por cuenta y una página de textos por publicación, respetando el intervalo configurado y el cooldown de cuotas. Retiene como máximo 5.000 opiniones de los últimos 90 días. X reciente no recupera automáticamente todos los comentarios anteriores a su ventana. Este muestreo no es un censo ni una encuesta representativa.

No se han recibido tokens ni permisos de API. En esta entrega los textos reales todavía no están disponibles, pese a que las cuentas sean administradas por el equipo. La actualización es periódica en GitHub Actions; no es tiempo real continuo.

## Retención y privacidad

Solo contenido público autorizado. Sin mensajes privados, segmentación por persona ni inferencias de afiliación política individual. Antes de publicar comentarios, el responsable institucional debe revisar finalidad, retención y derechos de divulgación. El historial público de Git conserva versiones anteriores; no usar ese almacenamiento para datos cuya retirada histórica deba garantizarse de inmediato.
