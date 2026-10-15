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
| Infra | Docker Compose |

## Arrancar
```powershell
copy .env.example .env      # edita las claves
docker compose up --build
```
- App: http://localhost:5173
- API + documentación Swagger: http://localhost:8000/docs

## Estructura
```
backend/app/
  models.py          tablas
  schemas.py         validación de entrada/salida
  services/finance.py  matemática financiera (tasas, cuotas, amortización, ahorro)
  services/          finance, queries, ledger, recurring, notifications, assistant
  routers/           auth, core (cuentas/movimientos/transferencias), budgets, recurring,
                     notifications, assistant, debts, savings, simulator
frontend/src/pages/  Resumen, Cuentas y movimientos, Presupuestos, Deudas, Ahorro, Asistente, Simulador
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

## Pruebas y CI
```powershell
cd backend; python -m pytest -q     # 43 pruebas de API y de la matemática financiera
```
GitHub Actions (`.github/workflows/ci.yml`) corre las pruebas del backend y el build del frontend en cada push.

## Pendiente / siguientes pasos
- Migraciones con Alembic: hoy se usa `create_all`; al cambiar columnas las bases existentes no se actualizan solas
  (en desarrollo, borrar `dev.db`)
- Importar extractos CSV, exportar a Excel/PDF
- Build de producción (nginx sirviendo el frontend)
