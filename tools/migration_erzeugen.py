"""Schreibt `migrationen/versions/i0001_grundlinie.py` aus den Modellen — einmalig, danach von Hand gepflegt.

Aufruf: python tools/migration_erzeugen.py > ausgabe.py   (der Kopf der Datei kommt aus KOPF unten)
Die Kette ist Handarbeit im Sinne des Auftrags: explizit `op.create_table`, kein Autogenerate zur Laufzeit.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from digiassistenz_inventar import modelle


def typ(t: sa.types.TypeEngine) -> str:
    if isinstance(t, postgresql.JSONB):
        return "postgresql.JSONB()"
    if isinstance(t, sa.Numeric):
        return f"sa.Numeric({t.precision}, {t.scale})"
    if isinstance(t, sa.DateTime):
        return "sa.DateTime(timezone=True)"
    if isinstance(t, sa.String) and t.length:
        return f"sa.String({t.length})"
    return f"sa.{type(t).__name__}()"


def spalte(c: sa.Column) -> str:
    teile = [repr(c.name), typ(c.type)]
    if c.identity is not None:
        teile.append("sa.Identity()")
    if c.server_default is not None and c.identity is None:
        teile.append(f"server_default=sa.text({str(c.server_default.arg)!r})")
    if c.primary_key:
        teile.append("primary_key=True")
    teile.append(f"nullable={c.nullable}")
    return f"        sa.Column({', '.join(teile)}),"


def tabelle(t: sa.Table) -> str:
    zeilen = [f"    op.create_table(", f"        {t.name!r},"]
    zeilen += [spalte(c) for c in t.columns]
    for fk in sorted((f for c in t.columns for f in c.foreign_keys), key=lambda f: f.parent.name):
        ziel = fk.target_fullname if isinstance(fk.target_fullname, str) else str(fk.column)
        zeilen.append(f"        sa.ForeignKeyConstraint([{fk.parent.name!r}], [{ziel!r}], name={fk.name!r}),")
    for u in sorted((c for c in t.constraints if isinstance(c, sa.UniqueConstraint)), key=lambda c: c.name):
        spalten = ", ".join(repr(c.name) for c in u.columns)
        zeilen.append(f"        sa.UniqueConstraint({spalten}, name={u.name!r}),")
    for ck in sorted((c for c in t.constraints if isinstance(c, sa.CheckConstraint)), key=lambda c: c.name):
        zeilen.append(f"        sa.CheckConstraint({str(ck.sqltext)!r}, name={ck.name!r}),")
    zeilen.append("        schema=SCHEMA,")
    zeilen.append("    )")
    for ix in sorted(t.indexes, key=lambda i: i.name):
        spalten = ", ".join(repr(c.name) for c in ix.columns)
        zusatz = ""
        if ix.unique:
            zusatz += ", unique=True"
        where = ix.dialect_options["postgresql"]["where"]
        if where is not None:
            zusatz += f", postgresql_where=sa.text({str(where)!r})"
        zeilen.append(f"    op.create_index({ix.name!r}, {t.name!r}, [{spalten}]{zusatz}, schema=SCHEMA)")
    return "\n".join(zeilen)


def main() -> None:
    ts = [t for t in modelle.Basis.metadata.sorted_tables if t.schema == modelle.SCHEMA]
    print("\n\n".join(tabelle(t) for t in ts))
    print()
    print("TABELLEN = (" + ", ".join(repr(t.name) for t in ts) + ",)")


if __name__ == "__main__":
    main()
