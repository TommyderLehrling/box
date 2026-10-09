"""Die Kette des Inventars — Versionstabelle `inventar.alembic_version` (Muster: Attrappe, L8).

Kern zuerst (`env.py` bricht sonst ab), dann `i0001`. Jede spätere Migration ist additiv.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from digiassistenz_kern import migration as kern_migration

MIGRATIONSORDNER = Path(__file__).with_name("migrationen")
SCHEMA = "inventar"
SCHEMA_KOPF = "i0001_grundlinie"
SCHEMA_FASSUNGEN = {"i0001_grundlinie": 1}


def schema_version(revision: str | None) -> int | None:
    return None if revision is None else SCHEMA_FASSUNGEN.get(revision)


def _konfig(db_url: str) -> Config:
    konfig = Config()
    konfig.set_main_option("script_location", str(MIGRATIONSORDNER))
    konfig.set_main_option("sqlalchemy.url", db_url)
    return konfig


def hochziehen(db_url: str, ziel: str = "head") -> None:
    command.upgrade(_konfig(db_url), ziel)


def herabziehen(db_url: str, ziel: str = "base") -> None:
    command.downgrade(_konfig(db_url), ziel)


def aktuelle_revision(db_url: str) -> str | None:
    motor = create_engine(db_url)
    try:
        with motor.connect() as verbindung:
            return MigrationContext.configure(
                verbindung,
                opts={"version_table": "alembic_version", "version_table_schema": SCHEMA},
            ).get_current_revision()
    finally:
        motor.dispose()


def nachziehen(db_url: str, abzug_ordner: Path | None) -> str | None:
    """Wie jede Kette: Stand prüfen, Abzug, Migration."""
    vorher = aktuelle_revision(db_url)
    if vorher == SCHEMA_KOPF:
        return vorher
    if abzug_ordner is not None:
        kern_migration.abzug_erstellen(db_url, abzug_ordner, marke=vorher or "inventar_leer")
    hochziehen(db_url)
    return aktuelle_revision(db_url)
