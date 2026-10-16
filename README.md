# Plata Clara · Finanzas personales

App web para registrar movimientos, manejar cuentas, tarjetas de crédito y créditos
(con cálculo de intereses y proyección de pago) y planear metas de ahorro.

## Stack
| Capa | Tecnología |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2 |
| Base de datos | PostgreSQL 16 |
| Auth | JWT + bcrypt |
| Migraciones | Alembic |
| Informes | ReportLab (PDF) · openpyxl (Excel) |
| Infra | Docker Compose · nginx |

## Arrancar

**Con Docker (recomendado)**
```powershell
copy .env.example .env      # edita las claves
docker compose up --build
```
- App: http://localhost:5173
- API + documentación Swagger: http://localhost:8000/docs

**Sin Docker (desarrollo)**
```powershell
# Backend (usa SQLite por defecto; crea las tablas solo, por migraciones)
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Frontend (en otra terminal)
cd frontend
npm install
$env:API_URL = "http://localhost:8000"; npm run dev
```

## Migraciones de la base de datos
El esquema se versiona con Alembic y **se aplica solo al arrancar la API**. Cuando cambies un modelo:
```powershell
cd backend
.\.venv\Scripts\alembic.exe revision --autogenerate -m "describe el cambio"   # genera la migración
.\.venv\Scripts\alembic.exe upgrade head                                       # la aplica (la API también lo hace)
```
Revisa siempre el archivo generado en `backend/alembic/versions/`. Una prueba (`tests/test_migrations.py`) **falla si un
modelo cambia sin su migración**, así el esquema real y el del código no se separan.

Una base de desarrollo creada antes de las migraciones se rechaza con un mensaje claro: bórrala (`backend/dev.db`).

## Estructura
```
backend/app/
  models.py          tablas                       migrate.py   aplica Alembic al arrancar
  schemas.py         validación de entrada/salida clock.py     «hoy» en la zona horaria del usuario
  services/          finance (matemática), queries, ledger, recurring, notifications, assistant, rules, importer,
                     exporter, report (PDF), loans, tags, uploads, account, ratelimit
  routers/           auth, account, core (cuentas/movimientos/transferencias), exports, reports, budgets, recurring,
                     notifications, assistant, tags, rules, imports, attachments, loans, debts, savings, simulator
backend/alembic/     migraciones
frontend/src/pages/  Resumen, Cuentas y movimientos, Importar extracto, Quién me debe, Presupuestos, Deudas, Ahorro,
                     Asistente, Simulador, Ajustes
```

## Cómo se calculan los intereses
- Tasa **EA** (efectiva anual, la que publican los bancos): `mensual = (1+EA)^(1/12) − 1`
- **MV** ya es mensual; **NA** se divide entre 12.
- Cuota de crédito (sistema francés): `P·r / (1 − (1+r)^−n)`
- Tarjeta: se simula mes a mes `interés = saldo·r`, `capital = pago − interés`;
  si el pago no cubre el interés, avisa que la deuda nunca se salda.
- Ahorro: aporte mensual para llegar a la meta considerando el rendimiento.

## Cuentas y entidades
- Catálogo de entidades colombianas en `backend/app/institutions.py`: bancos, billeteras y neobancos
  (Nequi, Daviplata, Nu, Lulo…), inversión y pensiones (Hapi, Trii, Tyba, Skandia, Protección…),
  y pagos/cripto. Para agregar una, basta una línea en esa lista.
- Los logos salen del favicon de cada entidad (servicio gratuito de Google); si no carga, se muestra un monograma.
- Si la entidad no está en la lista, se elige «Otra entidad o app» y se escribe el nombre.
- Tipos de cuenta: ahorros, corriente, billetera digital, inversión, tarjeta de crédito y efectivo.
- **Tarjeta de crédito:** al crearla se crea su deuda (tasa, cupo, pago mensual). Un gasto en la tarjeta sube la
  deuda, un ingreso/abono la baja, y la proyección con intereses sale en «Deudas y tarjetas».

## Funciones
- **Presupuestos:** tope mensual por categoría de gasto, con barra de avance y navegación por mes.
- **Recurrentes:** arriendo, suscripciones, nómina (semanal, quincenal o mensual). Se registran solos al entrar a la app
  y, si pasaron días sin entrar, se ponen al día. Es idempotente.
- **Notificaciones:** campana con avisos de presupuesto al 80 % y 100 %, pago de tarjeta/crédito en los próximos 3 días
  (requiere el «día de pago»), metas por vencer y recurrentes registrados. Cada aviso sale una sola vez. Opcionalmente
  también como aviso del navegador.
- **Asistente:** reglas explicables sobre tus datos: tasa de ahorro, categorías que se dispararon frente al mes pasado,
  presupuestos, deuda más cara y cuánto ahorras con un abono extra, fondo de emergencia (meses cubiertos) y viabilidad de metas.
- **Ahorro:** aportes y retiros con historial, edición de la meta y proyección con gráfica.
- **Transferencias:** entre tus cuentas (por ejemplo, pagar la tarjeta desde el banco). No cuentan como ingreso ni gasto.
- **Categorías propias:** crear y borrar (los movimientos quedan sin categoría).

### Movimientos avanzados
- **Importar extractos (CSV y Excel .xlsx):** sube el archivo del banco y revisa una vista previa antes de guardar.
  Entiende extractos colombianos: separador `;` o `,`, tildes (UTF-8 o Windows-1252), líneas de resumen antes del
  encabezado, montos como `$ 1.234.567,89`, `(50.000)` o `50.000-`, fechas día/mes/año y columnas de débito y crédito
  separadas. Si no reconoce las columnas, te deja indicarlas. Para tarjetas existe la opción «invertir» (las compras
  vienen positivas). Máx. 2.000 filas y 5 MB por archivo.
  - **Duplicados:** cada fila lleva una huella; reimportar el mismo extracto marca «Ya importado» y no duplica nada.
    Si coincide con un movimiento que anotaste a mano (misma cuenta, fecha, monto y tipo) lo marca «Posible duplicado».
- **Categorización automática:** aprende de lo que categorizas (sin IA): si pones «Éxito» en Mercado, la próxima vez lo
  sugiere. Ignora tildes y mayúsculas, no sugiere cuando hay dudas entre dos categorías y respeta si es ingreso o gasto.
  Puedes forzar reglas manuales, que mandan sobre lo aprendido.
- **Buscar y filtrar:** por texto (nota o categoría), fechas, monto mínimo y máximo, cuenta, categoría, tipo y etiqueta,
  con carga paginada.
- **Editar movimientos:** el saldo de la cuenta y la deuda de la tarjeta se recalculan solos.
- **Etiquetas:** agrupa movimientos de distintas categorías en un proyecto («viaje-cartagena») y mira cuánto va gastado.
- **Recibos:** adjunta foto (JPG, PNG, WEBP) o PDF a un movimiento (máx. 5 por movimiento, 5 MB c/u). En el celular
  abre la cámara.
- **Quién me debe:** préstamos sin intereses en ambos sentidos, con abonos y avisos de vencimiento. Si eliges una
  cuenta, el dinero entra o sale de ella, pero **prestar o cobrar no cuenta como gasto ni ingreso del mes**.
- **Dividir una cuenta:** pagaste entre varios; solo tu parte es gasto (y entra a tu presupuesto), lo demás queda como
  «te deben». Partes iguales (los centavos sobrantes te tocan a ti) o montos distintos.

### Informes, exportación y tu cuenta
- **Informe mensual en PDF** (pantalla Resumen): resumen del mes, comparación con el mes anterior, gasto por categoría
  contra tu presupuesto, mayores gastos, cuentas y patrimonio, y préstamos pendientes.
- **Exportar a Excel y CSV** (botones en el historial): respeta los filtros que tengas aplicados. El CSV usa `;`, coma
  decimal y UTF-8 con BOM para abrirse bien en Excel en español, y se puede volver a importar. Un texto que empiece con
  `=`, `+`, `-` o `@` se neutraliza para que Excel no lo ejecute como fórmula.
- **Ajustes:** cambiar contraseña (cierra las otras sesiones), descargar todos tus datos en JSON y borrar tu cuenta con
  todo lo que contiene (incluidos los recibos del disco).
- **Zona horaria:** «hoy» y «este mes» se calculan en `TIMEZONE` (por defecto `America/Bogota`), no en la hora del
  servidor, que en Docker es UTC. Sin esto, después de las 7 p. m. la app creería que ya es el día siguiente.

## Seguridad
- **Límite de intentos:** 5 fallos de inicio de sesión por IP y correo (30 por IP) en 15 minutos bloquean con un 429; un
  correo inexistente se bloquea igual que uno real, y la contraseña correcta tampoco entra mientras dura el bloqueo.
  Máx. 10 registros por hora y por IP. El limitador vive en memoria: sirve para una sola instancia de la API.
- **Sin credenciales en el repositorio:** `.env` está en `.gitignore`; solo se sube `.env.example` con valores de ejemplo.
  Un escaneo con gitleaks (`.github/workflows/secrets.yml`) revisa toda la historia en cada push.
- Con `ENVIRONMENT=production` la API **no arranca** si `SECRET_KEY` es la de desarrollo o tiene menos de 32 caracteres.
  `docker-compose.yml` exige las variables del `.env` (falla con un mensaje claro si falta alguna).
- Contraseñas con bcrypt, sesiones JWT, y cada consulta filtra por el usuario dueño: nadie ve ni toca datos ajenos
  (las pruebas lo verifican para cada recurso).
- **Archivos subidos:** el tipo se verifica por los bytes del archivo (no por lo que declara el navegador), se limita
  el tamaño, se guardan con un nombre generado (nunca el del usuario, así no hay manipulación de rutas) y solo se
  descargan con sesión del dueño. Los Excel se leen con `defusedxml` y límite de filas.

## Pruebas y CI
```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q     # 184 pruebas
```
Las pruebas corren sobre SQLite en memoria **con llaves foráneas activadas** (como PostgreSQL), una carpeta de archivos
nueva en cada prueba, y verifican que las migraciones coincidan con los modelos. GitHub Actions corre en cada push:
- `ci.yml`: pruebas del backend, build del frontend y **construcción de las imágenes de Docker** de producción.
- `secrets.yml`: escaneo de secretos (gitleaks) sobre toda la historia.

> **Nota:** las pruebas usan SQLite; el despliegue usa PostgreSQL. Las consultas son estándar SQLAlchemy, pero conviene
> probar los flujos principales contra PostgreSQL (`docker compose up`) antes de guardar datos reales.

## Despliegue en tu propio servidor
```powershell
# .env: ENVIRONMENT=production, SECRET_KEY de 32+ caracteres aleatorios, contraseña de la base, TIMEZONE
docker compose -f docker-compose.prod.yml up -d --build
```
Solo queda expuesta la web (nginx, puerto 80 o `WEB_PORT`); la API y la base viven en la red interna de Docker. nginx
añade cabeceras de seguridad (CSP, X-Frame-Options, nosniff…) y reenvía `/api` a la API **sobrescribiendo**
`X-Forwarded-For` con la IP real, para que el límite de intentos no se pueda esquivar con una IP inventada.
**Pon HTTPS delante** (Caddy, Cloudflare o un balanceador) antes de usarla fuera de tu casa: sin HTTPS la contraseña y la
sesión viajan sin cifrar. Si el proxy HTTPS es un servicio de nube compartido, la «IP real» que ve nginx será la del
proxy y el límite de intentos se aplicaría en conjunto; en ese caso conviene ajustar `nginx.conf`.

## Pendiente / siguientes pasos
- Probar el despliegue de producción en un servidor real (las imágenes se construyen en el CI, pero el flujo completo
  con HTTPS no se ha ejecutado)
- Pruebas de interfaz de punta a punta (Playwright)
- Adjuntos y límite de intentos para varias réplicas (hoy en memoria / disco local)
