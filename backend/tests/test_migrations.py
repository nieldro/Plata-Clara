"""Las migraciones y los modelos deben decir lo mismo: si cambias un modelo, crea su migración."""
import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.db import Base
from app.migrate import alembic_config, run_migrations


def url_for(tmp_path, name="m.db"):
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def test_migrations_build_exactly_what_the_models_describe(tmp_path):
    url = url_for(tmp_path)
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    engine.dispose()
    assert diff == [], (
        "Los modelos cambiaron sin migración. Genera una con:\n"
        "  alembic revision --autogenerate -m \"describe el cambio\"\nDiferencias: " + repr(diff)
    )


def test_upgrade_then_downgrade_leaves_no_tables(tmp_path):
    url = url_for(tmp_path)
    cfg = alembic_config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    tables = {r[0] for r in sqlite3.connect(tmp_path / "m.db").execute("select name from sqlite_master where type='table'")}
    assert tables <= {"alembic_version"}


def test_run_migrations_is_idempotent(tmp_path):
    url = url_for(tmp_path)
    run_migrations(url)
    run_migrations(url)  # la segunda vez no hace nada ni falla
    rows = sqlite3.connect(tmp_path / "m.db").execute("select version_num from alembic_version").fetchall()
    assert len(rows) == 1


def test_database_created_without_migrations_is_rejected_with_clear_message(tmp_path):
    url = url_for(tmp_path, "legacy.db")
    engine = create_engine(url)
    Base.metadata.create_all(engine)  # como se hacía antes
    engine.dispose()
    with pytest.raises(RuntimeError, match="antes de usar migraciones"):
        run_migrations(url)
