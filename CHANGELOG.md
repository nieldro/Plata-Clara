# Cambios

Resumen por día de lo que fue cambiando en Plata Clara. El detalle está en el historial de commits.

## 22 de octubre de 2026 · Pulido
**Rendimiento**
- Cada pantalla se descarga solo cuando se abre, y React, las animaciones y las gráficas van en archivos propios que el
  navegador guarda en caché (antes todo viajaba en un solo archivo de ~817 KB).
- La API comprime con gzip las respuestas grandes.
- Índice compuesto usuario + fecha en movimientos (migración `0005`).

**Robustez y seguridad**
- Los errores imprevistos responden un JSON genérico, quedan registrados completos en el servidor y no filtran detalles.
- En producción no se publican `/docs`, `/redoc` ni `/openapi.json`; en desarrollo `/docs` ahora describe la API.
- Las peticiones colgadas se cortan a los 30 s (120 s al subir archivos) con un mensaje claro.
- `SECURITY.md` con la vía privada para reportar vulnerabilidades y Dependabot para las dependencias.
- TypeScript detecta código sin usar.

**Experiencia**
- Lista de primeros pasos en el Resumen; esqueletos de carga en sus tarjetas.
- Fechas legibles (Hoy, Ayer, 22 de oct) y atajo `/` para ir a la búsqueda del historial.
- Se respeta «reducir movimiento» del sistema; enlace para saltar el menú y región principal para lectores de pantalla.
- En el teléfono las tablas anchas se deslizan de lado.
- Portada con las ocho funciones principales.

## 21 de octubre de 2026 · Organizar y entender
Acciones en lote, vistas guardadas, presupuestos sugeridos, renombrar y fusionar categorías y etiquetas, recurrentes
detectados, preferencias de avisos, cerrar sesión en otros dispositivos, resumen semanal, gastos inusuales, fecha para
quedar libre de deudas y modo privacidad.

## 20 de octubre de 2026 · Planear
Próximos pagos, proyección del efectivo día a día, patrimonio en el tiempo, estrategias de deuda (avalancha y bola de
nieve), gasto por comercio, registro rápido en lenguaje natural, aviso de duplicados, «Mi año», presupuesto por día y
app instalable (PWA).

## 19 de octubre de 2026 · Calidad
Lint con ruff, `/health/ready`, edición de cuentas, límites de intentos y cabeceras de seguridad, mensajes de error
claros, pantalla de recuperación, accesibilidad básica y pruebas del frontend con vitest.

## 16 de octubre de 2026 · Cuenta e informes
Migraciones con Alembic, límite de intentos de inicio de sesión, cambio de contraseña, descarga de datos, borrado de
cuenta, exportar a Excel y CSV, informe mensual en PDF, zona horaria correcta y despliegue de producción con nginx.

## 13 al 15 de octubre de 2026 · Base
Cuentas y tarjetas con el catálogo de entidades colombianas, cálculo de intereses, deudas, metas de ahorro, movimientos
con transferencias, presupuestos, recurrentes, notificaciones, asistente, importación de extractos, reglas de
categorización, etiquetas, recibos y préstamos entre personas.
