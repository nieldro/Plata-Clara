# Política de seguridad

Plata Clara maneja información financiera personal, así que los reportes de seguridad se toman en serio.

## Cómo reportar una vulnerabilidad

**No abras un issue público** con los detalles. Usa el reporte privado de GitHub:
*Security → Report a vulnerability* en <https://github.com/nieldro/Plata-Clara/security/advisories/new>.

Incluye, si puedes: qué viste, los pasos para reproducirlo y qué impacto crees que tiene. Se responde lo antes posible
y se avisa cuando esté corregido.

## Qué está cubierto

- Acceso a datos de otro usuario, o saltarse el inicio de sesión.
- Evadir el límite de intentos de inicio de sesión.
- Subida de archivos maliciosos (extractos, recibos) o lectura de rutas del servidor.
- Filtración de credenciales o claves por la API, los registros o el repositorio.

## Lo que ya hace el proyecto

El detalle está en la sección *Seguridad* del [README](README.md): contraseñas con bcrypt, sesiones JWT que se invalidan
al cambiar la contraseña, límite de intentos, cabeceras de seguridad, verificación de archivos por sus bytes,
escaneo de secretos con gitleaks en cada push y actualización semanal de dependencias con Dependabot.

## Si publicas tu propia instancia

- Usa `ENVIRONMENT=production` y una `SECRET_KEY` aleatoria de 32+ caracteres (la API no arranca con una débil).
- Pon HTTPS delante de nginx; sin él la contraseña y la sesión viajan sin cifrar.
- Nunca subas tu archivo `.env`: está en `.gitignore`, y solo se versiona `.env.example`.
- Si una credencial llegó a subirse al repositorio, **rótala**: borrarla del historial no basta.
