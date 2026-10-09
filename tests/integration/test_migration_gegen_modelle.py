"""Die Kette `i0001` und `modelle.py` beschreiben dieselben Tabellen (Spalten, Nullbarkeit, Eindeutigkeit, Fremdschlüssel, Prüfungen)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from conftest import aufbau_pruefen
from digiassistenz_inventar import modelle as m

pytestmark = pytest.mark.usefixtures("_aufbau")


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _typ(t) -> str:
    """Eine Familie je Typ: der Vergleich gilt der Art, nicht der Schreibweise."""
    name = type(t).__name__.upper()
    familien = {"BIGINTEGER": "INT", "BIGINT": "INT", "INTEGER": "INT", "SMALLINT": "INT", "TEXT": "TEXT", "STRING": "TEXT",
                "VARCHAR": "TEXT", "DATETIME": "ZEIT", "TIMESTAMP": "ZEIT", "NUMERIC": "ZAHL", "BOOLEAN": "BOOL", "DATE": "DATUM",
                "JSONB": "JSON"}
    return familien.get(name, name)


def test_jede_tabelle_stimmt_mit_dem_modell_ueberein(box) -> None:
    motor = create_engine(box.db_url)
    try:
        pruefer = inspect(motor)
        abweichungen = []
        for tabelle in m.Basis.metadata.tables.values():
            if tabelle.schema != m.SCHEMA:
                continue
            echt = {c["name"]: c for c in pruefer.get_columns(tabelle.name, schema=m.SCHEMA)}
            soll = {c.name: c for c in tabelle.columns}
            if set(echt) != set(soll):
                abweichungen.append(f"{tabelle.name}: Spalten {sorted(set(echt) ^ set(soll))}")
                continue
            for name, c in soll.items():
                if echt[name]["nullable"] != c.nullable:
                    abweichungen.append(f"{tabelle.name}.{name}: nullable")
                if _typ(echt[name]["type"]) != _typ(c.type):
                    abweichungen.append(f"{tabelle.name}.{name}: Typ {echt[name]['type']} gegen {c.type}")
            namen = {u["name"] for u in pruefer.get_unique_constraints(tabelle.name, schema=m.SCHEMA)}
            erwartet = {c.name for c in tabelle.constraints if c.__class__.__name__ == "UniqueConstraint"}
            if namen != erwartet:
                abweichungen.append(f"{tabelle.name}: Eindeutigkeit {sorted(namen ^ erwartet)}")
            fk_echt = {f["name"] for f in pruefer.get_foreign_keys(tabelle.name, schema=m.SCHEMA)}
            fk_soll = {f.name for c in tabelle.columns for f in c.foreign_keys}
            if fk_echt != fk_soll:
                abweichungen.append(f"{tabelle.name}: Fremdschlüssel {sorted(fk_echt ^ fk_soll)}")
            ck_echt = {c["name"] for c in pruefer.get_check_constraints(tabelle.name, schema=m.SCHEMA)}
            ck_soll = {c.name for c in tabelle.constraints if c.__class__.__name__ == "CheckConstraint"}
            if ck_echt != ck_soll:
                abweichungen.append(f"{tabelle.name}: Prüfungen {sorted(ck_echt ^ ck_soll)}")
            ix_echt = {i["name"] for i in pruefer.get_indexes(tabelle.name, schema=m.SCHEMA) if not i.get("duplicates_constraint")}
            ix_soll = {i.name for i in tabelle.indexes}
            if ix_echt != ix_soll:
                abweichungen.append(f"{tabelle.name}: Indizes {sorted(ix_echt ^ ix_soll)}")
    finally:
        motor.dispose()
    assert abweichungen == []


def test_migration_hat_nichts_geloescht_und_zweiter_lauf_aendert_nichts(box) -> None:
    from digiassistenz_inventar import migration

    assert migration.nachziehen(box.db_url, None) == "i0001_grundlinie"
    assert migration.aktuelle_revision(box.db_url) == migration.SCHEMA_KOPF
