"""Alembic-Umgebung des Inventars — Kern zuerst, eigene Versionstabelle `inventar.alembic_version`."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

SCHEMA = "inventar"
konfiguration = context.config


def online() -> None:
    abschnitt = konfiguration.get_section(konfiguration.config_ini_section) or {}
    abschnitt["sqlalchemy.url"] = konfiguration.get_main_option("sqlalchemy.url")
    motor = engine_from_config(abschnitt, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with motor.connect() as verbindung:
        if verbindung.exec_driver_sql("SELECT to_regclass('kern.alembic_version')").scalar() is None:
            raise RuntimeError("i0001.kern_zuerst")
        verbindung.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        verbindung.commit()
        context.configure(
            connection=verbindung,
            target_metadata=None,
            version_table="alembic_version",
            version_table_schema=SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


online()
