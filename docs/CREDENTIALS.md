# Configuración de credenciales oficiales

No pegues secretos en el código, Git ni capturas. Este MVP admite tokens emitidos por los mecanismos oficiales del proveedor y los almacena cifrados. La pantalla de alta envía el token una sola vez al backend; ninguna lectura lo devuelve. El wizard OAuth interactivo todavía no está implementado.

1. Registra la aplicación en el portal oficial y solicita el producto y los permisos mínimos.
2. Obtén el consentimiento del titular, la revisión y el token por el flujo oficial correspondiente; conserva sus expiraciones.
3. En Configuración, selecciona red, identificador oficial, nombre, acceso, token, scopes concedidos y frecuencia. No uses un nombre de usuario donde se requiere un ID.
4. Solicita Sincronizar. El estado pasa de pendiente a conectado solo después de una consulta satisfactoria. Una cuenta pública sin acceso sigue registrada sin cifras.
5. Verifica errores operativos, fecha y fuente de las observaciones antes de utilizar indicadores.

## Meta

Portal: https://developers.facebook.com/apps/. Usar la variante de Instagram con Facebook Login y cuenta profesional vinculada cuando sea aplicable; no mezclar sus permisos con Instagram Login.

Selecciona una versión Graph soportada y configura `META_GRAPH_VERSION`. La documentación oficial no pudo consultarse completamente por restricciones de acceso durante el desarrollo: estos adaptadores y permisos requieren validación antes de activarse con activos reales. No se fija una versión inventada ni se anuncian insights como soportados.

Facebook: ID de página y token apropiado para la página; revisar `pages_show_list`, `pages_read_engagement` y permisos adicionales si aplican. Instagram: ID de cuenta profesional, `instagram_basic`, `pages_read_engagement` y permisos aplicables del flujo. `read_insights` / `instagram_manage_insights` no habilitan por sí solos métricas en este MVP. No conectar cuentas personales ni asumir acceso a páginas ajenas.

## X

Portal: https://console.x.com/. El adaptador acepta un bearer autorizado con acceso a los endpoints de lectura. Usa ID numérico de usuario. Se consultan perfil y timeline; la búsqueda reciente no está implementada. Comprueba nivel de acceso, créditos, términos y límites en tu cuenta. No se fijan precios en el código.

## TikTok

Portal: https://developers.tiktok.com/. Habilita Login Kit y Display API y solicita `user.info.basic` y `video.list`. Usa el `open_id` del usuario que autorizó el token. El adaptador comprueba la identidad antes de listar videos. No usa Research API ni convierte Login Kit en un buscador público.

El conector mínimo no solicita `user.info.stats`; por ello los seguidores TikTok permanecen no disponibles. Expansiones futuras deben comprobar los scopes antes de pedir campos adicionales. Registra la expiración mediante REST. El refresco automático sigue pendiente.

## Rotación y expiración

La ruta `PATCH /connections/{id}/credentials` acepta `token`, `scopes` y `expires_at` (ISO 8601 con zona horaria). Solo admin, con sesión, origen permitido y CSRF. El administrador debe programar rotación mientras no exista refresco automático. Desconectar elimina el token local; para revocar acceso al proveedor, revócalo también en su portal oficial.

## Producción

HTTPS, `COOKIE_SECURE=true`, secretos externos, `FRONTEND_ORIGIN` exacto, `NEXT_PUBLIC_API_URL` correcto durante el build, PostgreSQL y Redis privados, revisión de permisos y pruebas con activos de prueba. No publicar esta instancia de desarrollo como servicio abierto.
