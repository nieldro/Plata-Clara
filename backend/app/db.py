from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def make_sqlite_unicode_aware(engine_) -> None:
    """lower() de SQLite ignora las letras con tilde (É no pasa a é); PostgreSQL sí las convierte.
    Se reemplaza para que la búsqueda se comporte igual en desarrollo (SQLite) y en producción."""
    if engine_.dialect.name != "sqlite":
        return

    @event.listens_for(engine_, "connect")
    def _on_connect(dbapi_conn, _record):
        dbapi_conn.create_function("lower", 1, lambda s: s.lower() if isinstance(s, str) else s, deterministic=True)


make_sqlite_unicode_aware(engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
