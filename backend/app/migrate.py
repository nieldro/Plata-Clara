"""Aplica las migraciones de Alembic al arrancar la API."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from .config import settings

ROOT = Path(__file__).resolve().parents[1]  # carpeta backend/


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    if url:
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def _is_legacy(url: str) -> bool:
    """¿Tablas creadas antes de usar migraciones (hay `users` pero no `alembic_version`)?"""
    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    return "users" in names and "alembic_version" not in names


def run_migrations(url: str | None = None) -> None:
    url = url or settings.database_url
    if _is_legacy(url):
        raise RuntimeError(
            "Esta base de datos se creó antes de usar migraciones. En desarrollo, bórrala y vuelve a arrancar "
            "(p. ej. borrar backend/dev.db). Si ya tiene el esquema actual y quieres conservar los datos: "
            "`alembic stamp head`."
        )
    command.upgrade(alembic_config(url), "head")
