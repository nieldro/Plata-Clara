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

## Pruebas del cálculo financiero
```powershell
docker compose exec backend pytest
```

## Estructura
```
backend/app/
  models.py          tablas
  schemas.py         validación de entrada/salida
  services/finance.py  matemática financiera (tasas, cuotas, amortización, ahorro)
  routers/           auth, core (cuentas/movimientos), debts, savings, simulator
frontend/src/pages/  Resumen, Movimientos, Deudas, Ahorro, Simulador
```

## Cómo se calculan los intereses
- Tasa **EA** (efectiva anual, la que publican los bancos): `mensual = (1+EA)^(1/12) − 1`
- **MV** ya es mensual; **NA** se divide entre 12.
- Cuota de crédito (sistema francés): `P·r / (1 − (1+r)^−n)`
- Tarjeta: se simula mes a mes `interés = saldo·r`, `capital = pago − interés`;
  si el pago no cubre el interés, avisa que la deuda nunca se salda.
- Ahorro: aporte mensual para llegar a la meta considerando el rendimiento.

## Pendiente / siguientes pasos
- Migraciones con Alembic (hoy usa `create_all`)
- Pruebas de API con base de datos de prueba
- Gráficas (recharts), presupuestos por categoría, gastos recurrentes
- Importar extractos CSV, exportar a Excel/PDF
- Build de producción (nginx sirviendo el frontend) y CI con GitHub Actions
