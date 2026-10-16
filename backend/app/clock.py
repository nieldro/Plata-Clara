"""«Hoy» en la zona horaria del usuario, no en la del servidor.

Un servidor en Docker trabaja en UTC: después de las 7 p. m. en Colombia ya sería «mañana» y las recurrentes,
los avisos, los presupuestos del mes y los informes se adelantarían un día. Por eso todo el código pide la fecha aquí.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings


def _utcnow() -> datetime:  # punto de reemplazo para las pruebas
    return datetime.now(timezone.utc)


def now() -> datetime:
    return _utcnow().astimezone(ZoneInfo(settings.timezone))


def today() -> date:
    return now().date()
