"""i0001 — die Grundlinie des Inventars: Schema, Konto `inventar_nutzer` und alle Tabellen.

Das Konto legt der **Kern** an (`rollen.modulrolle_anlegen`): es erbt `kern_nutzer`. Die Rechte am eigenen
Schema gibt das Modul selbst — und an keinem fremden (T-K-11). Die Tabellen stehen ausgeschrieben (kein
Autogenerate); `tools/migration_erzeugen.py` hat sie aus `modelle.py` geschrieben, `tests/pg` vergleicht beide.
Jede spätere Migration ist additiv (T-AP02-11): kein `drop_*`, kein verengendes `alter`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from digiassistenz_kern import rollen

revision = "i0001_grundlinie"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "inventar"
ROLLE = "inventar_nutzer"


def upgrade() -> None:
    rollen.modulrolle_anlegen(op.execute, ROLLE)
    op.execute(f"GRANT USAGE, CREATE ON SCHEMA {SCHEMA} TO {ROLLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} GRANT ALL ON TABLES TO {ROLLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} GRANT ALL ON SEQUENCES TO {ROLLE}")
    konto = op.get_bind().execute(sa.text("SELECT session_user")).scalar_one()
    rollen.dem_dienstkonto_geben(op.execute, konto, ROLLE)

    op.create_table(
        'gruppe',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('schluessel', sa.Text(), nullable=False),
        sa.Column('bezeichnung', sa.Text(), nullable=False),
        sa.Column('kuerzel', sa.String(2), nullable=False),
        sa.Column('oben_id', sa.BigInteger(), nullable=True),
        sa.Column('sortierung', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('aktiv', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('startwert', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_gruppe_mandant_id'),
        sa.ForeignKeyConstraint(['oben_id'], ['inventar.gruppe.id'], name='fk_gruppe_oben_id'),
        sa.UniqueConstraint('mandant_id', 'kuerzel', name='uq_gruppe_kuerzel'),
        sa.UniqueConstraint('mandant_id', 'schluessel', name='uq_gruppe_schluessel'),
        sa.CheckConstraint("kuerzel ~ '^[A-Z]{2}$'", name='ck_gruppe_kuerzel_form'),
        schema=SCHEMA,
    )

    op.create_table(
        'pruefart',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('schluessel', sa.Text(), nullable=False),
        sa.Column('bezeichnung', sa.Text(), nullable=False),
        sa.Column('intervall_monate', sa.Integer(), nullable=False),
        sa.Column('zaehler_intervall', sa.Integer(), nullable=True),
        sa.Column('rechtsgrund', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('durchfuehrung', sa.Text(), nullable=False),
        sa.Column('intervall_je_merkmal', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('aktiv', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('startwert', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_pruefart_mandant_id'),
        sa.UniqueConstraint('mandant_id', 'schluessel', name='uq_pruefart_schluessel'),
        sa.CheckConstraint("durchfuehrung IN ('intern', 'extern', 'beides')", name='ck_pruefart_durchfuehrung'),
        sa.CheckConstraint('intervall_monate >= 1', name='ck_pruefart_intervall'),
        schema=SCHEMA,
    )

    op.create_table(
        'zaehler',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('schluessel', sa.Text(), nullable=False),
        sa.Column('stand', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_zaehler_mandant_id'),
        sa.UniqueConstraint('mandant_id', 'schluessel', name='uq_zaehler_schluessel'),
        schema=SCHEMA,
    )

    op.create_table(
        'bauteil',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('bauteilnummer', sa.Text(), nullable=False),
        sa.Column('bezeichnung', sa.Text(), nullable=False),
        sa.Column('lieferant_id', sa.BigInteger(), nullable=True),
        sa.Column('hersteller', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('preis_zuletzt', sa.Numeric(14, 4), nullable=True),
        sa.Column('hinweis', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('aktiv', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['lieferant_id'], ['kern.lieferant.id'], name='fk_bauteil_lieferant_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_bauteil_mandant_id'),
        sa.UniqueConstraint('mandant_id', 'bauteilnummer', name='uq_bauteil_nummer'),
        schema=SCHEMA,
    )

    op.create_table(
        'einstellung',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('schluessel', sa.Text(), nullable=False),
        sa.Column('wert', sa.Text(), nullable=False),
        sa.Column('geaendert_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('geaendert_von', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['geaendert_von'], ['kern.benutzer.id'], name='fk_einstellung_geaendert_von'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_einstellung_mandant_id'),
        sa.UniqueConstraint('mandant_id', 'schluessel', name='uq_einstellung_schluessel'),
        schema=SCHEMA,
    )

    op.create_table(
        'gruppe_pruefart',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('gruppe_id', sa.BigInteger(), nullable=False),
        sa.Column('pruefart_id', sa.BigInteger(), nullable=False),
        sa.Column('intervall_monate', sa.Integer(), nullable=True),
        sa.Column('aktiv', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('startwert', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['gruppe_id'], ['inventar.gruppe.id'], name='fk_gruppe_pruefart_gruppe_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_gruppe_pruefart_mandant_id'),
        sa.ForeignKeyConstraint(['pruefart_id'], ['inventar.pruefart.id'], name='fk_gruppe_pruefart_pruefart_id'),
        sa.UniqueConstraint('gruppe_id', 'pruefart_id', name='uq_gruppe_pruefart'),
        schema=SCHEMA,
    )

    op.create_table(
        'merkmal',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('gruppe_id', sa.BigInteger(), nullable=False),
        sa.Column('schluessel', sa.Text(), nullable=False),
        sa.Column('bezeichnung', sa.Text(), nullable=False),
        sa.Column('typ', sa.Text(), nullable=False),
        sa.Column('einheit', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('auswahl', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('pflicht', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('sortierung', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('aktiv', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('startwert', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['gruppe_id'], ['inventar.gruppe.id'], name='fk_merkmal_gruppe_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_merkmal_mandant_id'),
        sa.UniqueConstraint('gruppe_id', 'schluessel', name='uq_merkmal_schluessel'),
        sa.CheckConstraint("typ IN ('text', 'zahl', 'datum', 'ja_nein', 'auswahl')", name='ck_merkmal_typ'),
        schema=SCHEMA,
    )
    op.create_index('ix_merkmal_mandant_gruppe', 'merkmal', ['mandant_id', 'gruppe_id'], schema=SCHEMA)

    op.create_table(
        'stueck',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('inventarnummer', sa.Text(), nullable=False),
        sa.Column('bezeichnung', sa.Text(), nullable=False),
        sa.Column('gruppe_id', sa.BigInteger(), nullable=False),
        sa.Column('art', sa.Text(), nullable=False),
        sa.Column('kennung_qr', sa.Text(), nullable=True),
        sa.Column('hersteller', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('typ', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('seriennummer', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('baujahr', sa.Integer(), nullable=True),
        sa.Column('lieferant_id', sa.BigInteger(), nullable=True),
        sa.Column('kaufdatum', sa.Date(), nullable=True),
        sa.Column('kaufpreis', sa.Numeric(12, 2), nullable=True),
        sa.Column('nutzungsdauer_monate', sa.Integer(), nullable=True),
        sa.Column('restwert', sa.Numeric(12, 2), nullable=True),
        sa.Column('zaehler_einheit', sa.Text(), nullable=True),
        sa.Column('miete', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('miet_von', sa.Date(), nullable=True),
        sa.Column('miet_bis', sa.Date(), nullable=True),
        sa.Column('mietkosten', sa.Numeric(12, 2), nullable=True),
        sa.Column('besonderheiten', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('foto_pfad', sa.Text(), nullable=True),
        sa.Column('foto_sha256', sa.Text(), nullable=True),
        sa.Column('buchwert_extern', sa.Numeric(12, 2), nullable=True),
        sa.Column('afa_hinweis', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'aktiv'"), nullable=False),
        sa.Column('status_seit', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status_grund', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('quelle', sa.Text(), nullable=False),
        sa.Column('angelegt_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('angelegt_von', sa.BigInteger(), nullable=True),
        sa.Column('geaendert_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('geaendert_von', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['angelegt_von'], ['kern.benutzer.id'], name='fk_stueck_angelegt_von'),
        sa.ForeignKeyConstraint(['geaendert_von'], ['kern.benutzer.id'], name='fk_stueck_geaendert_von'),
        sa.ForeignKeyConstraint(['gruppe_id'], ['inventar.gruppe.id'], name='fk_stueck_gruppe_id'),
        sa.ForeignKeyConstraint(['lieferant_id'], ['kern.lieferant.id'], name='fk_stueck_lieferant_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_stueck_mandant_id'),
        sa.UniqueConstraint('mandant_id', 'inventarnummer', name='uq_stueck_inventarnummer'),
        sa.CheckConstraint("art IN ('gross', 'klein', 'menge')", name='ck_stueck_art'),
        sa.CheckConstraint("quelle IN ('web', 'handy', 'import', 'baustelle', 'pruefung', 'werkstatt', 'system', 'testdaten')", name='ck_stueck_quelle'),
        sa.CheckConstraint("status IN ('aktiv', 'in_reparatur', 'vermisst', 'stillgelegt', 'verkauft', 'verschrottet')", name='ck_stueck_status'),
        sa.CheckConstraint("zaehler_einheit IN ('h', 'km')", name='ck_stueck_zaehler_einheit'),
        schema=SCHEMA,
    )
    op.create_index('ix_stueck_gruppe', 'stueck', ['mandant_id', 'gruppe_id'], schema=SCHEMA)
    op.create_index('ix_stueck_seriennummer', 'stueck', ['mandant_id', 'seriennummer'], schema=SCHEMA)
    op.create_index('ix_stueck_status', 'stueck', ['mandant_id', 'status'], schema=SCHEMA)
    op.create_index('uq_stueck_kennung_qr', 'stueck', ['mandant_id', 'kennung_qr'], unique=True, postgresql_where=sa.text('kennung_qr IS NOT NULL'), schema=SCHEMA)

    op.create_table(
        'beziehung',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('von_stueck_id', sa.BigInteger(), nullable=True),
        sa.Column('art', sa.Text(), nullable=False),
        sa.Column('zu_stueck_id', sa.BigInteger(), nullable=True),
        sa.Column('bauteil_id', sa.BigInteger(), nullable=True),
        sa.Column('gruppe_id', sa.BigInteger(), nullable=True),
        sa.Column('hinweis', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('gueltig_von', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('gueltig_bis', sa.Date(), nullable=True),
        sa.Column('angelegt_von', sa.BigInteger(), nullable=True),
        sa.Column('angelegt_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['angelegt_von'], ['kern.benutzer.id'], name='fk_beziehung_angelegt_von'),
        sa.ForeignKeyConstraint(['bauteil_id'], ['inventar.bauteil.id'], name='fk_beziehung_bauteil_id'),
        sa.ForeignKeyConstraint(['gruppe_id'], ['inventar.gruppe.id'], name='fk_beziehung_gruppe_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_beziehung_mandant_id'),
        sa.ForeignKeyConstraint(['von_stueck_id'], ['inventar.stueck.id'], name='fk_beziehung_von_stueck_id'),
        sa.ForeignKeyConstraint(['zu_stueck_id'], ['inventar.stueck.id'], name='fk_beziehung_zu_stueck_id'),
        sa.CheckConstraint("art IN ('gehoert_zu', 'passt_zu')", name='ck_beziehung_art'),
        sa.CheckConstraint("art <> 'gehoert_zu' OR (von_stueck_id IS NOT NULL AND zu_stueck_id IS NOT NULL AND bauteil_id IS NULL AND gruppe_id IS NULL)", name='ck_beziehung_gehoert_zu'),
        sa.CheckConstraint("art <> 'passt_zu' OR (bauteil_id IS NOT NULL AND von_stueck_id IS NULL AND num_nonnulls(zu_stueck_id, gruppe_id) = 1)", name='ck_beziehung_passt_zu'),
        schema=SCHEMA,
    )
    op.create_index('ix_beziehung_von', 'beziehung', ['mandant_id', 'von_stueck_id'], schema=SCHEMA)
    op.create_index('ix_beziehung_zu', 'beziehung', ['mandant_id', 'zu_stueck_id'], schema=SCHEMA)

    op.create_table(
        'kostensatz',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=True),
        sa.Column('gruppe_id', sa.BigInteger(), nullable=True),
        sa.Column('gueltig_ab', sa.Date(), nullable=False),
        sa.Column('kaufpreis_basis', sa.Numeric(12, 2), nullable=True),
        sa.Column('nutzungsdauer_monate', sa.Integer(), nullable=False),
        sa.Column('restwert', sa.Numeric(12, 2), nullable=True),
        sa.Column('restwert_prozent', sa.Numeric(5, 2), nullable=True),
        sa.Column('zins_prozent', sa.Numeric(5, 2), nullable=False),
        sa.Column('reparatur_prozent_jahr', sa.Numeric(5, 2), nullable=False),
        sa.Column('satz_monat', sa.Numeric(12, 2), nullable=True),
        sa.Column('satz_tag', sa.Numeric(12, 2), nullable=True),
        sa.Column('satz_woche', sa.Numeric(12, 2), nullable=True),
        sa.Column('satz_stunde', sa.Numeric(12, 2), nullable=True),
        sa.Column('quelle', sa.Text(), nullable=False),
        sa.Column('angelegt_von', sa.BigInteger(), nullable=True),
        sa.Column('angelegt_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['angelegt_von'], ['kern.benutzer.id'], name='fk_kostensatz_angelegt_von'),
        sa.ForeignKeyConstraint(['gruppe_id'], ['inventar.gruppe.id'], name='fk_kostensatz_gruppe_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_kostensatz_mandant_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_kostensatz_stueck_id'),
        sa.CheckConstraint("quelle IN ('gerechnet', 'manuell', 'bgl', 'vorschlag_box')", name='ck_kostensatz_quelle'),
        sa.CheckConstraint('num_nonnulls(stueck_id, gruppe_id) = 1', name='ck_kostensatz_ziel'),
        schema=SCHEMA,
    )
    op.create_index('uq_kostensatz_gruppe', 'kostensatz', ['mandant_id', 'gruppe_id', 'gueltig_ab'], unique=True, postgresql_where=sa.text('gruppe_id IS NOT NULL'), schema=SCHEMA)
    op.create_index('uq_kostensatz_stueck', 'kostensatz', ['mandant_id', 'stueck_id', 'gueltig_ab'], unique=True, postgresql_where=sa.text('stueck_id IS NOT NULL'), schema=SCHEMA)

    op.create_table(
        'meldung',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('kostenstelle_id', sa.BigInteger(), nullable=False),
        sa.Column('art', sa.Text(), nullable=False),
        sa.Column('beschreibung', sa.Text(), nullable=False),
        sa.Column('foto_pfad', sa.Text(), nullable=True),
        sa.Column('foto_sha256', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'offen'"), nullable=False),
        sa.Column('gemeldet_von', sa.BigInteger(), nullable=True),
        sa.Column('gemeldet_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('bearbeitet_von', sa.BigInteger(), nullable=True),
        sa.Column('erledigt_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rueckmeldung', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('grund', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('fremd_vorgang', sa.Text(), nullable=True),
        sa.Column('eintrag_schluessel', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['bearbeitet_von'], ['kern.benutzer.id'], name='fk_meldung_bearbeitet_von'),
        sa.ForeignKeyConstraint(['gemeldet_von'], ['kern.benutzer.id'], name='fk_meldung_gemeldet_von'),
        sa.ForeignKeyConstraint(['kostenstelle_id'], ['kern.kostenstelle.id'], name='fk_meldung_kostenstelle_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_meldung_mandant_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_meldung_stueck_id'),
        sa.UniqueConstraint('mandant_id', 'eintrag_schluessel', name='uq_meldung_eintrag'),
        sa.CheckConstraint("art IN ('schaden', 'reparatur', 'wartung', 'sonstiges')", name='ck_meldung_art'),
        sa.CheckConstraint("status IN ('offen', 'angenommen', 'in_arbeit', 'erledigt', 'zurueckgezogen')", name='ck_meldung_status'),
        schema=SCHEMA,
    )
    op.create_index('ix_meldung_status', 'meldung', ['mandant_id', 'status'], schema=SCHEMA)
    op.create_index('ix_meldung_stueck', 'meldung', ['stueck_id'], schema=SCHEMA)

    op.create_table(
        'pruefung',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('pruefart_id', sa.BigInteger(), nullable=False),
        sa.Column('faellig_am', sa.Date(), nullable=True),
        sa.Column('durchgefuehrt_am', sa.Date(), nullable=False),
        sa.Column('ergebnis', sa.Text(), nullable=False),
        sa.Column('durchfuehrung', sa.Text(), nullable=False),
        sa.Column('pruefer_text', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('pruefer_benutzer_id', sa.BigInteger(), nullable=True),
        sa.Column('pruefer_lieferant_id', sa.BigInteger(), nullable=True),
        sa.Column('zaehlerstand', sa.Numeric(14, 3), nullable=True),
        sa.Column('nachweis_pfad', sa.Text(), nullable=True),
        sa.Column('nachweis_sha256', sa.Text(), nullable=True),
        sa.Column('bemerkung', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('naechste_am', sa.Date(), nullable=True),
        sa.Column('quelle', sa.Text(), nullable=False),
        sa.Column('angelegt_von', sa.BigInteger(), nullable=True),
        sa.Column('angelegt_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['angelegt_von'], ['kern.benutzer.id'], name='fk_pruefung_angelegt_von'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_pruefung_mandant_id'),
        sa.ForeignKeyConstraint(['pruefart_id'], ['inventar.pruefart.id'], name='fk_pruefung_pruefart_id'),
        sa.ForeignKeyConstraint(['pruefer_benutzer_id'], ['kern.benutzer.id'], name='fk_pruefung_pruefer_benutzer_id'),
        sa.ForeignKeyConstraint(['pruefer_lieferant_id'], ['kern.lieferant.id'], name='fk_pruefung_pruefer_lieferant_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_pruefung_stueck_id'),
        sa.CheckConstraint("durchfuehrung IN ('intern', 'extern')", name='ck_pruefung_durchfuehrung'),
        sa.CheckConstraint("ergebnis IN ('bestanden', 'maengel', 'nicht_bestanden')", name='ck_pruefung_ergebnis'),
        sa.CheckConstraint("quelle IN ('web', 'handy', 'import', 'baustelle', 'pruefung', 'werkstatt', 'system', 'testdaten')", name='ck_pruefung_quelle'),
        schema=SCHEMA,
    )
    op.create_index('ix_pruefung_stueck', 'pruefung', ['stueck_id', 'pruefart_id', 'durchgefuehrt_am'], schema=SCHEMA)

    op.create_table(
        'stueck_merkmal',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('merkmal_id', sa.BigInteger(), nullable=False),
        sa.Column('wert', sa.Text(), nullable=False),
        sa.Column('wert_zahl', sa.Numeric(18, 6), nullable=True),
        sa.Column('geaendert_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('geaendert_von', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['geaendert_von'], ['kern.benutzer.id'], name='fk_stueck_merkmal_geaendert_von'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_stueck_merkmal_mandant_id'),
        sa.ForeignKeyConstraint(['merkmal_id'], ['inventar.merkmal.id'], name='fk_stueck_merkmal_merkmal_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_stueck_merkmal_stueck_id'),
        sa.UniqueConstraint('stueck_id', 'merkmal_id', name='uq_stueck_merkmal'),
        schema=SCHEMA,
    )

    op.create_table(
        'stueck_pruefart',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('pruefart_id', sa.BigInteger(), nullable=False),
        sa.Column('intervall_monate', sa.Integer(), nullable=True),
        sa.Column('aktiv', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_stueck_pruefart_mandant_id'),
        sa.ForeignKeyConstraint(['pruefart_id'], ['inventar.pruefart.id'], name='fk_stueck_pruefart_pruefart_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_stueck_pruefart_stueck_id'),
        sa.UniqueConstraint('stueck_id', 'pruefart_id', name='uq_stueck_pruefart'),
        schema=SCHEMA,
    )

    op.create_table(
        'transfer',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('menge', sa.Numeric(14, 3), nullable=False),
        sa.Column('von_kostenstelle_id', sa.BigInteger(), nullable=True),
        sa.Column('nach_kostenstelle_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('abgang_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('abgang_von', sa.BigInteger(), nullable=True),
        sa.Column('eingang_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eingang_von', sa.BigInteger(), nullable=True),
        sa.Column('beendet_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('grund', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('quelle', sa.Text(), nullable=False),
        sa.Column('eintrag_schluessel', sa.Text(), nullable=False),
        sa.Column('eingang_schluessel', sa.Text(), nullable=True),
        sa.Column('erinnert_am', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['abgang_von'], ['kern.benutzer.id'], name='fk_transfer_abgang_von'),
        sa.ForeignKeyConstraint(['eingang_von'], ['kern.benutzer.id'], name='fk_transfer_eingang_von'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_transfer_mandant_id'),
        sa.ForeignKeyConstraint(['nach_kostenstelle_id'], ['kern.kostenstelle.id'], name='fk_transfer_nach_kostenstelle_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_transfer_stueck_id'),
        sa.ForeignKeyConstraint(['von_kostenstelle_id'], ['kern.kostenstelle.id'], name='fk_transfer_von_kostenstelle_id'),
        sa.UniqueConstraint('mandant_id', 'eintrag_schluessel', name='uq_transfer_eintrag'),
        sa.CheckConstraint("quelle IN ('web', 'handy', 'import', 'baustelle', 'pruefung', 'werkstatt', 'system', 'testdaten')", name='ck_transfer_quelle'),
        sa.CheckConstraint("status IN ('angekuendigt', 'bestaetigt', 'ueberholt', 'zurueckgezogen')", name='ck_transfer_status'),
        schema=SCHEMA,
    )
    op.create_index('ix_transfer_status', 'transfer', ['mandant_id', 'status'], schema=SCHEMA)
    op.create_index('ix_transfer_stueck', 'transfer', ['stueck_id', 'status'], schema=SCHEMA)
    op.create_index('uq_transfer_eingang', 'transfer', ['mandant_id', 'eingang_schluessel'], unique=True, postgresql_where=sa.text('eingang_schluessel IS NOT NULL'), schema=SCHEMA)

    op.create_table(
        'zaehlerstand',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('stand', sa.Numeric(14, 3), nullable=False),
        sa.Column('einheit', sa.Text(), nullable=False),
        sa.Column('abgelesen_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('abgelesen_von', sa.BigInteger(), nullable=True),
        sa.Column('quelle', sa.Text(), nullable=False),
        sa.Column('kostenstelle_id', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['abgelesen_von'], ['kern.benutzer.id'], name='fk_zaehlerstand_abgelesen_von'),
        sa.ForeignKeyConstraint(['kostenstelle_id'], ['kern.kostenstelle.id'], name='fk_zaehlerstand_kostenstelle_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_zaehlerstand_mandant_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_zaehlerstand_stueck_id'),
        sa.CheckConstraint("einheit IN ('h', 'km')", name='ck_zaehlerstand_einheit'),
        sa.CheckConstraint("quelle IN ('web', 'handy', 'import', 'baustelle', 'pruefung', 'werkstatt', 'system', 'testdaten')", name='ck_zaehlerstand_quelle'),
        schema=SCHEMA,
    )
    op.create_index('ix_zaehlerstand_stueck', 'zaehlerstand', ['stueck_id', 'abgelesen_am'], schema=SCHEMA)

    op.create_table(
        'reparatur',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('meldung_id', sa.BigInteger(), nullable=True),
        sa.Column('beschreibung', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('durchfuehrung', sa.Text(), nullable=False),
        sa.Column('lieferant_id', sa.BigInteger(), nullable=True),
        sa.Column('begonnen_am', sa.Date(), nullable=True),
        sa.Column('beendet_am', sa.Date(), nullable=True),
        sa.Column('kosten', sa.Numeric(12, 2), nullable=True),
        sa.Column('kosten_quelle', sa.Text(), nullable=True),
        sa.Column('rechnung_verweis', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'offen'"), nullable=False),
        sa.Column('grund', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('arbeit', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('durchgefuehrt_von', sa.BigInteger(), nullable=True),
        sa.Column('angelegt_von', sa.BigInteger(), nullable=True),
        sa.Column('angelegt_am', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['angelegt_von'], ['kern.benutzer.id'], name='fk_reparatur_angelegt_von'),
        sa.ForeignKeyConstraint(['durchgefuehrt_von'], ['kern.benutzer.id'], name='fk_reparatur_durchgefuehrt_von'),
        sa.ForeignKeyConstraint(['lieferant_id'], ['kern.lieferant.id'], name='fk_reparatur_lieferant_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_reparatur_mandant_id'),
        sa.ForeignKeyConstraint(['meldung_id'], ['inventar.meldung.id'], name='fk_reparatur_meldung_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_reparatur_stueck_id'),
        sa.CheckConstraint("durchfuehrung IN ('intern', 'extern')", name='ck_reparatur_durchfuehrung'),
        sa.CheckConstraint("kosten_quelle IN ('geschaetzt', 'rechnung')", name='ck_reparatur_kosten_quelle'),
        sa.CheckConstraint("status IN ('offen', 'in_arbeit', 'erledigt', 'zurueckgezogen')", name='ck_reparatur_status'),
        schema=SCHEMA,
    )
    op.create_index('ix_reparatur_stueck', 'reparatur', ['stueck_id'], schema=SCHEMA)

    op.create_table(
        'standort',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column('mandant_id', sa.BigInteger(), nullable=False),
        sa.Column('stueck_id', sa.BigInteger(), nullable=False),
        sa.Column('kostenstelle_id', sa.BigInteger(), nullable=False),
        sa.Column('menge', sa.Numeric(14, 3), server_default=sa.text('1'), nullable=False),
        sa.Column('von', sa.DateTime(timezone=True), nullable=False),
        sa.Column('bis', sa.DateTime(timezone=True), nullable=True),
        sa.Column('transfer_id', sa.BigInteger(), nullable=True),
        sa.Column('quelle', sa.Text(), nullable=False),
        sa.Column('von_person', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['kostenstelle_id'], ['kern.kostenstelle.id'], name='fk_standort_kostenstelle_id'),
        sa.ForeignKeyConstraint(['mandant_id'], ['kern.mandant.id'], name='fk_standort_mandant_id'),
        sa.ForeignKeyConstraint(['stueck_id'], ['inventar.stueck.id'], name='fk_standort_stueck_id'),
        sa.ForeignKeyConstraint(['transfer_id'], ['inventar.transfer.id'], name='fk_standort_transfer_id'),
        sa.ForeignKeyConstraint(['von_person'], ['kern.benutzer.id'], name='fk_standort_von_person'),
        sa.CheckConstraint("quelle IN ('web', 'handy', 'import', 'baustelle', 'pruefung', 'werkstatt', 'system', 'testdaten')", name='ck_standort_quelle'),
        sa.CheckConstraint('bis IS NULL OR bis >= von', name='ck_standort_zeitraum'),
        schema=SCHEMA,
    )
    op.create_index('ix_standort_offen', 'standort', ['mandant_id', 'kostenstelle_id'], postgresql_where=sa.text('bis IS NULL'), schema=SCHEMA)
    op.create_index('ix_standort_stueck', 'standort', ['stueck_id', 'bis'], schema=SCHEMA)


def downgrade() -> None:
    """Nichts wird gelöscht: Schema, Tabellen und Rolle bleiben (Alembic löscht danach nur seine Zeile)."""
