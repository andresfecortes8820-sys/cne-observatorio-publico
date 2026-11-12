# Seguridad, privacidad y operación

## Actualización: consulta pública

`/public/*` permite lectura anónima solo de cuentas habilitadas por un administrador. Administración, sincronización, credenciales, auditoría y monitoreo mantienen autenticación. Las modificaciones requieren rol admin; analyst/viewer no pueden cambiar parámetros. No existe autorregistro público. Caché, cuotas y el esquema explícito se describen en `PUBLIC_DEPLOYMENT.md`.

La autorización de lectura API no basta para redistribuir datos. La migración deja todas las conexiones privadas. Retirar publicación invalida snapshots de caché. No se guardan respuestas públicas en caché del navegador. Los datos ya descargados por visitantes no pueden retirarse de sus equipos.

Implementado: hashes Argon2, cookies HttpOnly/SameSite, validación CSRF/origen para mutaciones autenticadas, JWT con expiración, roles, cifrado Fernet, entrada tipada, consultas ORM parametrizadas, tokens excluidos de respuestas, errores de proveedor saneados, auditoría y protección de fórmulas en exportaciones. El login usa limitador compartido Redis y falla cerrado si Redis no está disponible. No confía en `X-Forwarded-For` de clientes.

Los usuarios de esta instalación pertenecen a una sola institución; no es todavía un SaaS multitenant. Los roles controlan funciones, no aislamiento por organización o cuenta. No exponer a varias organizaciones hasta implementar tenant_id y pruebas de aislamiento. Las sesiones no tienen revocación individual inmediata: desactivar el usuario bloquea su siguiente solicitud; logout borra la cookie del navegador. MFA, recuperación de contraseña, SSO y administración visual de usuarios pendientes.

La clave Fernet debe estar en un gestor de secretos, separada de respaldos de BD. Rotarla requiere recifrar los tokens existentes; no sustituirla sin migración. Proteger `.env` con permisos del sistema operativo. Se recomienda TLS, proxy con límites de solicitud, CSP adaptada a Next.js, monitoreo, análisis de dependencias y registro externo de auditoría antes de producción. Los logs no incluyen deliberadamente respuestas crudas de los proveedores.

PostgreSQL requiere respaldos cifrados y restauraciones probadas. Redis solo accesible desde la red de aplicación. Compose es una base de desarrollo, no un despliegue cloud endurecido. Un solo scheduler evita encolado redundante. Las alertas operativas pueden repetirse en fallos recurrentes: supresión y política de retención pendientes.

## Tratamiento de datos

Antes de operar, el responsable debe definir finalidad y base aplicable, avisos/autorizaciones cuando correspondan, retención, acceso, derechos de titulares, procedimientos de eliminación y gestión de incidentes. La información pública sigue requiriendo evaluación de su tratamiento. Este proyecto no constituye certificación de cumplimiento de la Ley 1581 de 2012 ni asesoría jurídica. La evaluación legal institucional y las políticas vigentes de los proveedores deben completarse antes de incorporar datos personales reales.

No hay scraping, enriquecimiento de identidad ni inferencia de preferencias políticas por persona. Sentimiento está en `indeterminado`; no se asignan etiquetas inventadas. Una futura estimación automatizada debe conservar modelo, versión, confianza, revisión humana y límites metodológicos.
