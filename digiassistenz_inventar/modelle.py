"""Tabellen des Moduls — Schema `inventar` (Spec v0.2 Abschnitt 7, Auftrag 03 Abschnitt 6).

Jede Tabelle trägt `mandant_id`; Fremdschlüssel gehen nur ins eigene Schema oder nach `kern` (T-K-14).
Nichts wird gelöscht: Verlauf über `bis`, `beendet_am`, `aktiv`, `gueltig_bis`. Die Kette `i0001` legt
dieselben Tabellen an (`migrationen/versions/i0001_grundlinie.py`); der Prüffall `tests/pg` vergleicht beide.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from digiassistenz_kern import (
    BETRAG,
    EINZELPREIS,
    FALSCH,
    FK_BENUTZER,
    FK_KOSTENSTELLE,
    FK_LIEFERANT,
    FK_MANDANT,
    JETZT,
    MENGE,
    PROZENT,
    WAHR,
    ZEITPUNKT,
    aufzaehlung,
    id_spalte,
    modul_metadata,
)

SCHEMA = "inventar"

ART = ("gross", "klein", "menge")
STATUS = ("aktiv", "in_reparatur", "vermisst", "stillgelegt", "verkauft", "verschrottet")
QUELLE = ("web", "handy", "import", "baustelle", "pruefung", "werkstatt", "system", "testdaten")
MERKMAL_TYP = ("text", "zahl", "datum", "ja_nein", "auswahl")
BEZIEHUNG_ART = ("gehoert_zu", "passt_zu")
TRANSFER_STATUS = ("angekuendigt", "bestaetigt", "ueberholt", "zurueckgezogen")
DURCHFUEHRUNG = ("intern", "extern", "beides")
PRUEF_DURCHFUEHRUNG = ("intern", "extern")
ERGEBNIS = ("bestanden", "maengel", "nicht_bestanden")
MELDUNG_ART = ("schaden", "reparatur", "wartung", "sonstiges")
MELDUNG_STATUS = ("offen", "angenommen", "in_arbeit", "erledigt", "zurueckgezogen")
REPARATUR_STATUS = ("offen", "in_arbeit", "erledigt", "zurueckgezogen")
KOSTEN_QUELLE = ("geschaetzt", "rechnung")
ZAEHLER_EINHEIT = ("h", "km")
SATZ_QUELLE = ("gerechnet", "manuell", "bgl", "vorschlag_box")

FK_GRUPPE = f"{SCHEMA}.gruppe.id"
FK_MERKMAL = f"{SCHEMA}.merkmal.id"
FK_STUECK = f"{SCHEMA}.stueck.id"
FK_BAUTEIL = f"{SCHEMA}.bauteil.id"
FK_TRANSFER = f"{SCHEMA}.transfer.id"
FK_PRUEFART = f"{SCHEMA}.pruefart.id"
FK_MELDUNG = f"{SCHEMA}.meldung.id"


class Basis(DeclarativeBase):
    """Die Registratur des Moduls: eigenes Schema als Vorgabe, Kern-Tabellen gespiegelt (nur Beschreibung)."""

    metadata = modul_metadata(SCHEMA)


def _mandant(tabelle: str) -> Mapped[int]:
    return mapped_column(BigInteger, ForeignKey(FK_MANDANT, name=f"fk_{tabelle}_mandant_id"), nullable=False)


def _fk(ziel: str, tabelle: str, spalte: str, *, null: bool = False) -> Mapped[Any]:
    return mapped_column(BigInteger, ForeignKey(ziel, name=f"fk_{tabelle}_{spalte}"), nullable=null)


def _benutzer(tabelle: str, spalte: str) -> Mapped[int | None]:
    return _fk(FK_BENUTZER, tabelle, spalte, null=True)


def _am() -> Mapped[dt.datetime]:
    return mapped_column(ZEITPUNKT, nullable=False, server_default=JETZT)


def _leer() -> Mapped[str]:
    return mapped_column(Text, nullable=False, server_default=text("''"))


def _text() -> Mapped[str]:
    return mapped_column(Text, nullable=False)


def _zeit() -> Mapped[dt.datetime | None]:
    return mapped_column(ZEITPUNKT, nullable=True)


def _ja() -> Mapped[bool]:
    return mapped_column(Boolean, nullable=False, server_default=WAHR)


def _nein() -> Mapped[bool]:
    return mapped_column(Boolean, nullable=False, server_default=FALSCH)


class Gruppe(Basis):
    __tablename__ = "gruppe"
    __table_args__ = (
        UniqueConstraint("mandant_id", "schluessel", name="uq_gruppe_schluessel"),
        UniqueConstraint("mandant_id", "kuerzel", name="uq_gruppe_kuerzel"),
        CheckConstraint("kuerzel ~ '^[A-Z]{2}$'", name="ck_gruppe_kuerzel_form"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("gruppe")
    schluessel: Mapped[str] = _text()
    bezeichnung: Mapped[str] = _text()
    kuerzel: Mapped[str] = mapped_column(String(2), nullable=False)
    oben_id: Mapped[int | None] = _fk(FK_GRUPPE, "gruppe", "oben_id", null=True)
    sortierung: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    aktiv: Mapped[bool] = _ja()
    startwert: Mapped[bool] = _nein()


class Merkmal(Basis):
    __tablename__ = "merkmal"
    __table_args__ = (
        UniqueConstraint("gruppe_id", "schluessel", name="uq_merkmal_schluessel"),
        aufzaehlung("typ", MERKMAL_TYP, "merkmal"),
        Index("ix_merkmal_mandant_gruppe", "mandant_id", "gruppe_id"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("merkmal")
    gruppe_id: Mapped[int] = _fk(FK_GRUPPE, "merkmal", "gruppe_id")
    schluessel: Mapped[str] = _text()
    bezeichnung: Mapped[str] = _text()
    typ: Mapped[str] = _text()
    einheit: Mapped[str] = _leer()
    auswahl: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    pflicht: Mapped[bool] = _nein()
    sortierung: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    aktiv: Mapped[bool] = _ja()
    startwert: Mapped[bool] = _nein()


class Stueck(Basis):
    __tablename__ = "stueck"
    __table_args__ = (
        UniqueConstraint("mandant_id", "inventarnummer", name="uq_stueck_inventarnummer"),
        aufzaehlung("art", ART, "stueck"),
        aufzaehlung("status", STATUS, "stueck"),
        aufzaehlung("quelle", QUELLE, "stueck"),
        aufzaehlung("zaehler_einheit", ZAEHLER_EINHEIT, "stueck"),
        Index("ix_stueck_seriennummer", "mandant_id", "seriennummer"),
        Index("ix_stueck_gruppe", "mandant_id", "gruppe_id"),
        Index("ix_stueck_status", "mandant_id", "status"),
        Index("uq_stueck_kennung_qr", "mandant_id", "kennung_qr", unique=True,
              postgresql_where=text("kennung_qr IS NOT NULL")),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("stueck")
    inventarnummer: Mapped[str] = _text()
    bezeichnung: Mapped[str] = _text()
    gruppe_id: Mapped[int] = _fk(FK_GRUPPE, "stueck", "gruppe_id")
    art: Mapped[str] = _text()
    kennung_qr: Mapped[str | None] = mapped_column(Text)
    hersteller: Mapped[str] = _leer()
    typ: Mapped[str] = _leer()
    seriennummer: Mapped[str] = _leer()
    baujahr: Mapped[int | None] = mapped_column(Integer)
    lieferant_id: Mapped[int | None] = _fk(FK_LIEFERANT, "stueck", "lieferant_id", null=True)
    kaufdatum: Mapped[dt.date | None] = mapped_column(Date)
    kaufpreis: Mapped[Decimal | None] = mapped_column(BETRAG)
    nutzungsdauer_monate: Mapped[int | None] = mapped_column(Integer)
    restwert: Mapped[Decimal | None] = mapped_column(BETRAG)
    zaehler_einheit: Mapped[str | None] = mapped_column(Text)
    miete: Mapped[bool] = _nein()
    miet_von: Mapped[dt.date | None] = mapped_column(Date)
    miet_bis: Mapped[dt.date | None] = mapped_column(Date)
    mietkosten: Mapped[Decimal | None] = mapped_column(BETRAG)
    besonderheiten: Mapped[str] = _leer()
    foto_pfad: Mapped[str | None] = mapped_column(Text)
    foto_sha256: Mapped[str | None] = mapped_column(Text)
    buchwert_extern: Mapped[Decimal | None] = mapped_column(BETRAG)
    afa_hinweis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'aktiv'"))
    status_seit: Mapped[dt.datetime] = _am()
    status_grund: Mapped[str] = _leer()
    quelle: Mapped[str] = _text()
    angelegt_am: Mapped[dt.datetime] = _am()
    angelegt_von: Mapped[int | None] = _benutzer("stueck", "angelegt_von")
    geaendert_am: Mapped[dt.datetime | None] = _zeit()
    geaendert_von: Mapped[int | None] = _benutzer("stueck", "geaendert_von")


class StueckMerkmal(Basis):
    __tablename__ = "stueck_merkmal"
    __table_args__ = (UniqueConstraint("stueck_id", "merkmal_id", name="uq_stueck_merkmal"),)
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("stueck_merkmal")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "stueck_merkmal", "stueck_id")
    merkmal_id: Mapped[int] = _fk(FK_MERKMAL, "stueck_merkmal", "merkmal_id")
    wert: Mapped[str] = _text()
    wert_zahl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    geaendert_am: Mapped[dt.datetime] = _am()
    geaendert_von: Mapped[int | None] = _benutzer("stueck_merkmal", "geaendert_von")


class Bauteil(Basis):
    __tablename__ = "bauteil"
    __table_args__ = (UniqueConstraint("mandant_id", "bauteilnummer", name="uq_bauteil_nummer"),)
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("bauteil")
    bauteilnummer: Mapped[str] = _text()
    bezeichnung: Mapped[str] = _text()
    lieferant_id: Mapped[int | None] = _fk(FK_LIEFERANT, "bauteil", "lieferant_id", null=True)
    hersteller: Mapped[str] = _leer()
    preis_zuletzt: Mapped[Decimal | None] = mapped_column(EINZELPREIS)
    hinweis: Mapped[str] = _leer()
    aktiv: Mapped[bool] = _ja()


class Beziehung(Basis):
    """Zubehör (`gehoert_zu`: von → zu, beides Stücke) oder Passung (`passt_zu`: Bauteil → Stück oder Gruppe)."""

    __tablename__ = "beziehung"
    __table_args__ = (
        aufzaehlung("art", BEZIEHUNG_ART, "beziehung"),
        CheckConstraint(
            "art <> 'gehoert_zu' OR (von_stueck_id IS NOT NULL AND zu_stueck_id IS NOT NULL"
            " AND bauteil_id IS NULL AND gruppe_id IS NULL)", name="ck_beziehung_gehoert_zu"),
        CheckConstraint(
            "art <> 'passt_zu' OR (bauteil_id IS NOT NULL AND von_stueck_id IS NULL"
            " AND num_nonnulls(zu_stueck_id, gruppe_id) = 1)", name="ck_beziehung_passt_zu"),
        Index("ix_beziehung_von", "mandant_id", "von_stueck_id"),
        Index("ix_beziehung_zu", "mandant_id", "zu_stueck_id"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("beziehung")
    von_stueck_id: Mapped[int | None] = _fk(FK_STUECK, "beziehung", "von_stueck_id", null=True)
    art: Mapped[str] = _text()
    zu_stueck_id: Mapped[int | None] = _fk(FK_STUECK, "beziehung", "zu_stueck_id", null=True)
    bauteil_id: Mapped[int | None] = _fk(FK_BAUTEIL, "beziehung", "bauteil_id", null=True)
    gruppe_id: Mapped[int | None] = _fk(FK_GRUPPE, "beziehung", "gruppe_id", null=True)
    hinweis: Mapped[str] = _leer()
    gueltig_von: Mapped[dt.date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    gueltig_bis: Mapped[dt.date | None] = mapped_column(Date)
    angelegt_von: Mapped[int | None] = _benutzer("beziehung", "angelegt_von")
    angelegt_am: Mapped[dt.datetime] = _am()


class Transfer(Basis):
    __tablename__ = "transfer"
    __table_args__ = (
        UniqueConstraint("mandant_id", "eintrag_schluessel", name="uq_transfer_eintrag"),
        aufzaehlung("status", TRANSFER_STATUS, "transfer"),
        aufzaehlung("quelle", QUELLE, "transfer"),
        Index("uq_transfer_eingang", "mandant_id", "eingang_schluessel", unique=True,
              postgresql_where=text("eingang_schluessel IS NOT NULL")),
        Index("ix_transfer_status", "mandant_id", "status"),
        Index("ix_transfer_stueck", "stueck_id", "status"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("transfer")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "transfer", "stueck_id")
    menge: Mapped[Decimal] = mapped_column(MENGE, nullable=False)
    von_kostenstelle_id: Mapped[int | None] = _fk(FK_KOSTENSTELLE, "transfer", "von_kostenstelle_id", null=True)
    nach_kostenstelle_id: Mapped[int] = _fk(FK_KOSTENSTELLE, "transfer", "nach_kostenstelle_id")
    status: Mapped[str] = _text()
    abgang_am: Mapped[dt.datetime | None] = _zeit()
    abgang_von: Mapped[int | None] = _benutzer("transfer", "abgang_von")
    eingang_am: Mapped[dt.datetime | None] = _zeit()
    eingang_von: Mapped[int | None] = _benutzer("transfer", "eingang_von")
    beendet_am: Mapped[dt.datetime | None] = _zeit()
    grund: Mapped[str] = _leer()
    quelle: Mapped[str] = _text()
    eintrag_schluessel: Mapped[str] = _text()
    eingang_schluessel: Mapped[str | None] = mapped_column(Text)
    erinnert_am: Mapped[dt.datetime | None] = _zeit()


class Standort(Basis):
    __tablename__ = "standort"
    __table_args__ = (
        aufzaehlung("quelle", QUELLE, "standort"),
        CheckConstraint("bis IS NULL OR bis >= von", name="ck_standort_zeitraum"),
        Index("ix_standort_stueck", "stueck_id", "bis"),
        Index("ix_standort_offen", "mandant_id", "kostenstelle_id", postgresql_where=text("bis IS NULL")),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("standort")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "standort", "stueck_id")
    kostenstelle_id: Mapped[int] = _fk(FK_KOSTENSTELLE, "standort", "kostenstelle_id")
    menge: Mapped[Decimal] = mapped_column(MENGE, nullable=False, server_default=text("1"))
    von: Mapped[dt.datetime] = mapped_column(ZEITPUNKT, nullable=False)
    bis: Mapped[dt.datetime | None] = _zeit()
    transfer_id: Mapped[int | None] = _fk(FK_TRANSFER, "standort", "transfer_id", null=True)
    quelle: Mapped[str] = _text()
    von_person: Mapped[int | None] = _benutzer("standort", "von_person")


class Pruefart(Basis):
    __tablename__ = "pruefart"
    __table_args__ = (
        UniqueConstraint("mandant_id", "schluessel", name="uq_pruefart_schluessel"),
        aufzaehlung("durchfuehrung", DURCHFUEHRUNG, "pruefart"),
        CheckConstraint("intervall_monate >= 1", name="ck_pruefart_intervall"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("pruefart")
    schluessel: Mapped[str] = _text()
    bezeichnung: Mapped[str] = _text()
    intervall_monate: Mapped[int] = mapped_column(Integer, nullable=False)
    zaehler_intervall: Mapped[int | None] = mapped_column(Integer)
    rechtsgrund: Mapped[str] = _leer()
    durchfuehrung: Mapped[str] = _text()
    intervall_je_merkmal: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    aktiv: Mapped[bool] = _ja()
    startwert: Mapped[bool] = _nein()


class GruppePruefart(Basis):
    __tablename__ = "gruppe_pruefart"
    __table_args__ = (UniqueConstraint("gruppe_id", "pruefart_id", name="uq_gruppe_pruefart"),)
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("gruppe_pruefart")
    gruppe_id: Mapped[int] = _fk(FK_GRUPPE, "gruppe_pruefart", "gruppe_id")
    pruefart_id: Mapped[int] = _fk(FK_PRUEFART, "gruppe_pruefart", "pruefart_id")
    intervall_monate: Mapped[int | None] = mapped_column(Integer)
    aktiv: Mapped[bool] = _ja()
    startwert: Mapped[bool] = _nein()


class StueckPruefart(Basis):
    __tablename__ = "stueck_pruefart"
    __table_args__ = (UniqueConstraint("stueck_id", "pruefart_id", name="uq_stueck_pruefart"),)
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("stueck_pruefart")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "stueck_pruefart", "stueck_id")
    pruefart_id: Mapped[int] = _fk(FK_PRUEFART, "stueck_pruefart", "pruefart_id")
    intervall_monate: Mapped[int | None] = mapped_column(Integer)
    aktiv: Mapped[bool] = _ja()


class Pruefung(Basis):
    __tablename__ = "pruefung"
    __table_args__ = (
        aufzaehlung("ergebnis", ERGEBNIS, "pruefung"),
        aufzaehlung("durchfuehrung", PRUEF_DURCHFUEHRUNG, "pruefung"),
        aufzaehlung("quelle", QUELLE, "pruefung"),
        Index("ix_pruefung_stueck", "stueck_id", "pruefart_id", "durchgefuehrt_am"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("pruefung")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "pruefung", "stueck_id")
    pruefart_id: Mapped[int] = _fk(FK_PRUEFART, "pruefung", "pruefart_id")
    faellig_am: Mapped[dt.date | None] = mapped_column(Date)
    durchgefuehrt_am: Mapped[dt.date] = mapped_column(Date, nullable=False)
    ergebnis: Mapped[str] = _text()
    durchfuehrung: Mapped[str] = _text()
    pruefer_text: Mapped[str] = _leer()
    pruefer_benutzer_id: Mapped[int | None] = _benutzer("pruefung", "pruefer_benutzer_id")
    pruefer_lieferant_id: Mapped[int | None] = _fk(FK_LIEFERANT, "pruefung", "pruefer_lieferant_id", null=True)
    zaehlerstand: Mapped[Decimal | None] = mapped_column(MENGE)
    nachweis_pfad: Mapped[str | None] = mapped_column(Text)
    nachweis_sha256: Mapped[str | None] = mapped_column(Text)
    bemerkung: Mapped[str] = _leer()
    naechste_am: Mapped[dt.date | None] = mapped_column(Date)
    quelle: Mapped[str] = _text()
    angelegt_von: Mapped[int | None] = _benutzer("pruefung", "angelegt_von")
    angelegt_am: Mapped[dt.datetime] = _am()


class Meldung(Basis):
    __tablename__ = "meldung"
    __table_args__ = (
        UniqueConstraint("mandant_id", "eintrag_schluessel", name="uq_meldung_eintrag"),
        aufzaehlung("art", MELDUNG_ART, "meldung"),
        aufzaehlung("status", MELDUNG_STATUS, "meldung"),
        Index("ix_meldung_status", "mandant_id", "status"),
        Index("ix_meldung_stueck", "stueck_id"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("meldung")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "meldung", "stueck_id")
    kostenstelle_id: Mapped[int] = _fk(FK_KOSTENSTELLE, "meldung", "kostenstelle_id")
    art: Mapped[str] = _text()
    beschreibung: Mapped[str] = _text()
    foto_pfad: Mapped[str | None] = mapped_column(Text)
    foto_sha256: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'offen'"))
    gemeldet_von: Mapped[int | None] = _benutzer("meldung", "gemeldet_von")
    gemeldet_am: Mapped[dt.datetime] = _am()
    bearbeitet_von: Mapped[int | None] = _benutzer("meldung", "bearbeitet_von")
    erledigt_am: Mapped[dt.datetime | None] = _zeit()
    rueckmeldung: Mapped[str] = _leer()
    grund: Mapped[str] = _leer()
    fremd_vorgang: Mapped[str | None] = mapped_column(Text)
    eintrag_schluessel: Mapped[str] = _text()


class Reparatur(Basis):
    __tablename__ = "reparatur"
    __table_args__ = (
        aufzaehlung("durchfuehrung", PRUEF_DURCHFUEHRUNG, "reparatur"),
        aufzaehlung("kosten_quelle", KOSTEN_QUELLE, "reparatur"),
        aufzaehlung("status", REPARATUR_STATUS, "reparatur"),
        Index("ix_reparatur_stueck", "stueck_id"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("reparatur")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "reparatur", "stueck_id")
    meldung_id: Mapped[int | None] = _fk(FK_MELDUNG, "reparatur", "meldung_id", null=True)
    beschreibung: Mapped[str] = _leer()
    durchfuehrung: Mapped[str] = _text()
    lieferant_id: Mapped[int | None] = _fk(FK_LIEFERANT, "reparatur", "lieferant_id", null=True)
    begonnen_am: Mapped[dt.date | None] = mapped_column(Date)
    beendet_am: Mapped[dt.date | None] = mapped_column(Date)
    kosten: Mapped[Decimal | None] = mapped_column(BETRAG)
    kosten_quelle: Mapped[str | None] = mapped_column(Text)
    rechnung_verweis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'offen'"))
    grund: Mapped[str] = _leer()
    angelegt_von: Mapped[int | None] = _benutzer("reparatur", "angelegt_von")
    angelegt_am: Mapped[dt.datetime] = _am()


class Zaehlerstand(Basis):
    __tablename__ = "zaehlerstand"
    __table_args__ = (
        aufzaehlung("einheit", ZAEHLER_EINHEIT, "zaehlerstand"),
        aufzaehlung("quelle", QUELLE, "zaehlerstand"),
        Index("ix_zaehlerstand_stueck", "stueck_id", "abgelesen_am"),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("zaehlerstand")
    stueck_id: Mapped[int] = _fk(FK_STUECK, "zaehlerstand", "stueck_id")
    stand: Mapped[Decimal] = mapped_column(MENGE, nullable=False)
    einheit: Mapped[str] = _text()
    abgelesen_am: Mapped[dt.datetime] = mapped_column(ZEITPUNKT, nullable=False)
    abgelesen_von: Mapped[int | None] = _benutzer("zaehlerstand", "abgelesen_von")
    quelle: Mapped[str] = _text()
    kostenstelle_id: Mapped[int | None] = _fk(FK_KOSTENSTELLE, "zaehlerstand", "kostenstelle_id", null=True)


class Kostensatz(Basis):
    """Parameter je Gruppe oder Stück (Stück vor Gruppe). Die gerechneten Sätze kommen mit G5."""

    __tablename__ = "kostensatz"
    __table_args__ = (
        aufzaehlung("quelle", SATZ_QUELLE, "kostensatz"),
        CheckConstraint("num_nonnulls(stueck_id, gruppe_id) = 1", name="ck_kostensatz_ziel"),
        Index("uq_kostensatz_gruppe", "mandant_id", "gruppe_id", "gueltig_ab", unique=True,
              postgresql_where=text("gruppe_id IS NOT NULL")),
        Index("uq_kostensatz_stueck", "mandant_id", "stueck_id", "gueltig_ab", unique=True,
              postgresql_where=text("stueck_id IS NOT NULL")),
    )
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("kostensatz")
    stueck_id: Mapped[int | None] = _fk(FK_STUECK, "kostensatz", "stueck_id", null=True)
    gruppe_id: Mapped[int | None] = _fk(FK_GRUPPE, "kostensatz", "gruppe_id", null=True)
    gueltig_ab: Mapped[dt.date] = mapped_column(Date, nullable=False)
    kaufpreis_basis: Mapped[Decimal | None] = mapped_column(BETRAG)
    nutzungsdauer_monate: Mapped[int] = mapped_column(Integer, nullable=False)
    restwert: Mapped[Decimal | None] = mapped_column(BETRAG)
    restwert_prozent: Mapped[Decimal | None] = mapped_column(PROZENT)
    zins_prozent: Mapped[Decimal] = mapped_column(PROZENT, nullable=False)
    reparatur_prozent_jahr: Mapped[Decimal] = mapped_column(PROZENT, nullable=False)
    satz_monat: Mapped[Decimal | None] = mapped_column(BETRAG)
    satz_tag: Mapped[Decimal | None] = mapped_column(BETRAG)
    satz_woche: Mapped[Decimal | None] = mapped_column(BETRAG)
    satz_stunde: Mapped[Decimal | None] = mapped_column(BETRAG)
    quelle: Mapped[str] = _text()
    angelegt_von: Mapped[int | None] = _benutzer("kostensatz", "angelegt_von")
    angelegt_am: Mapped[dt.datetime] = _am()


class Einstellung(Basis):
    __tablename__ = "einstellung"
    __table_args__ = (UniqueConstraint("mandant_id", "schluessel", name="uq_einstellung_schluessel"),)
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("einstellung")
    schluessel: Mapped[str] = _text()
    wert: Mapped[str] = _text()
    geaendert_am: Mapped[dt.datetime] = _am()
    geaendert_von: Mapped[int | None] = _benutzer("einstellung", "geaendert_von")


class Zaehler(Basis):
    """Nummernzähler je Mandant und Schlüssel — vergeben unter `SELECT … FOR UPDATE`."""

    __tablename__ = "zaehler"
    __table_args__ = (UniqueConstraint("mandant_id", "schluessel", name="uq_zaehler_schluessel"),)
    id: Mapped[int] = id_spalte()
    mandant_id: Mapped[int] = _mandant("zaehler")
    schluessel: Mapped[str] = _text()
    stand: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


TABELLEN = tuple(t.name for t in Basis.metadata.sorted_tables if t.schema == SCHEMA)

__all__ = [
    "Basis", "Bauteil", "Beziehung", "Einstellung", "Gruppe", "GruppePruefart", "Kostensatz", "Meldung", "Merkmal",
    "Pruefart", "Pruefung", "Reparatur", "SCHEMA", "Standort", "Stueck", "StueckMerkmal", "StueckPruefart",
    "TABELLEN", "Transfer", "Zaehler", "Zaehlerstand",
]
