"""Werkstatt: Statusautomaten fuer Meldung und Reparatur, Folge fuer den Stueckstatus, Reparaturkosten."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType
from typing import Literal

MeldungStatus = Literal["offen", "angenommen", "in_arbeit", "erledigt", "zurueckgezogen"]
ReparaturStatus = Literal["offen", "in_arbeit", "erledigt", "zurueckgezogen"]
#: Vorsilbe des Statusgrundes, wenn die Automatik `in_reparatur` gesetzt hat (`reparatur:<id>`)
GRUND_PRAEFIX = "reparatur:"
MELDUNG_ARTEN = ("schaden", "reparatur", "wartung", "sonstiges")
_MELDUNG_WEG = MappingProxyType({
    "offen": ("angenommen", "zurueckgezogen"),
    "angenommen": ("in_arbeit", "erledigt", "zurueckgezogen"),
    "in_arbeit": ("erledigt", "zurueckgezogen"),
    "erledigt": (),
    "zurueckgezogen": (),
})
_REPARATUR_WEG = MappingProxyType({
    "offen": ("in_arbeit", "zurueckgezogen"),
    "in_arbeit": ("erledigt", "zurueckgezogen"),
    "erledigt": (),
    "zurueckgezogen": (),
})


@dataclass(frozen=True)
class Meldung:
    art: str
    status: MeldungStatus
    beschreibung: str
    gemeldet_von: str
    gemeldet_am: datetime
    bearbeitet_von: str | None = None
    erledigt_am: datetime | None = None
    rueckmeldung: str = ""
    grund: str = ""


@dataclass(frozen=True)
class Reparatur:
    status: ReparaturStatus
    durchfuehrung: Literal["intern", "extern"]
    begonnen_am: date | None = None
    beendet_am: date | None = None
    kosten: Decimal | None = None
    kosten_quelle: Literal["geschaetzt", "rechnung"] | None = None
    grund: str = ""
    lieferant_id: int | None = None
    arbeit: str = ""
    durchgefuehrt_von: str | None = None


def _zeit(zeit: datetime) -> None:
    if zeit.tzinfo is None or zeit.utcoffset() is None:
        raise ValueError("werkstatt.zeit_naiv")


def neue_meldung(art: str, beschreibung: str, person: str, zeit: datetime) -> Meldung:
    """Legt eine offene Meldung an (Art aus Katalog, Beschreibung Pflicht)."""
    _zeit(zeit)
    if art not in MELDUNG_ARTEN:
        raise ValueError("meldung.art_unbekannt")
    if not beschreibung.strip() or not person.strip():
        raise ValueError("meldung.angaben_fehlen")
    return Meldung(art, "offen", beschreibung.strip(), person, zeit)


def meldung_weiter(
    m: Meldung, neu: str, person: str, zeit: datetime, rueckmeldung: str = "", grund: str = ""
) -> Meldung:
    """Schaltet die Meldung weiter; erledigt braucht eine Rueckmeldung, zurueckziehen einen Grund."""
    _zeit(zeit)
    if neu not in _MELDUNG_WEG:
        raise ValueError("meldung.status_unbekannt")
    if neu not in _MELDUNG_WEG[m.status]:
        raise ValueError("meldung.wechsel_nicht_erlaubt")
    if not person.strip():
        raise ValueError("meldung.angaben_fehlen")
    if neu == "erledigt" and not rueckmeldung.strip():
        raise ValueError("meldung.rueckmeldung_fehlt")
    if neu == "zurueckgezogen" and not grund.strip():
        raise ValueError("meldung.grund_fehlt")
    return replace(
        m, status=neu, bearbeitet_von=person if neu in ("angenommen", "in_arbeit", "erledigt") else m.bearbeitet_von,  # type: ignore[arg-type]
        erledigt_am=zeit if neu == "erledigt" else m.erledigt_am,
        rueckmeldung=rueckmeldung.strip() or m.rueckmeldung, grund=grund.strip() or m.grund)


def neue_reparatur(durchfuehrung: str, lieferant_id: int | None = None) -> Reparatur:
    """Legt eine offene Reparatur an (intern oder extern); beim Anlegen ist alles freiwillig."""
    if durchfuehrung not in ("intern", "extern"):
        raise ValueError("reparatur.durchfuehrung_unbekannt")
    return Reparatur("offen", durchfuehrung, lieferant_id=lieferant_id)  # type: ignore[arg-type]


def reparatur_beginnen(r: Reparatur, am: date, geschaetzte_kosten: Decimal | None = None) -> Reparatur:
    """Beginnt die Reparatur; geschaetzte Kosten sind optional."""
    if r.status != "offen":
        raise ValueError("reparatur.wechsel_nicht_erlaubt")
    if geschaetzte_kosten is not None and geschaetzte_kosten < 0:
        raise ValueError("reparatur.kosten_ungueltig")
    return replace(r, status="in_arbeit", begonnen_am=am, kosten=geschaetzte_kosten,
                   kosten_quelle="geschaetzt" if geschaetzte_kosten is not None else None)


def reparatur_abschliessen(
    r: Reparatur, am: date, kosten: Decimal | None, quelle: str = "geschaetzt", *, arbeit: str = "",
    lieferant_id: int | None = None, durchgefuehrt_von: str | None = None,
) -> Reparatur:
    """Schliesst die Reparatur ab; beim Abschliessen ist Pflicht: wann, was, und wer (extern: die Firma, intern: die Person).

    Quelle Rechnung ueberschreibt eine Schaetzung. Ohne Kosten (`None`: wer abschliesst, darf sie nicht eintragen)
    bleibt eine frueher geschaetzte Angabe stehen.
    """
    if r.status != "in_arbeit" or r.begonnen_am is None:
        raise ValueError("reparatur.wechsel_nicht_erlaubt")
    if am < r.begonnen_am:
        raise ValueError("reparatur.ende_vor_beginn")
    if not arbeit.strip():
        raise ValueError("reparatur.arbeit_fehlt")
    firma = lieferant_id if lieferant_id is not None else r.lieferant_id
    if r.durchfuehrung == "extern" and firma is None:
        raise ValueError("reparatur.lieferant_fehlt")
    person = (durchgefuehrt_von or "").strip() or None
    if r.durchfuehrung == "intern" and person is None:
        raise ValueError("reparatur.durchgefuehrt_von_fehlt")
    fertig = replace(r, status="erledigt", beendet_am=am, arbeit=arbeit.strip(), lieferant_id=firma,
                     durchgefuehrt_von=person if r.durchfuehrung == "intern" else None)
    if kosten is None:
        return fertig
    if kosten < 0:
        raise ValueError("reparatur.kosten_ungueltig")
    if quelle not in ("geschaetzt", "rechnung"):
        raise ValueError("reparatur.kostenquelle_unbekannt")
    return replace(fertig, kosten=kosten, kosten_quelle=quelle)  # type: ignore[arg-type]


def kosten_aus_rechnung(r: Reparatur, kosten: Decimal) -> Reparatur:
    """Ersetzt eine Schaetzung nachtraeglich durch den Betrag aus der Rechnung (nur erledigte Reparaturen)."""
    if r.status != "erledigt":
        raise ValueError("reparatur.wechsel_nicht_erlaubt")
    if kosten < 0:
        raise ValueError("reparatur.kosten_ungueltig")
    return replace(r, kosten=kosten, kosten_quelle="rechnung")


def reparatur_zurueckziehen(r: Reparatur, grund: str) -> Reparatur:
    """Zieht eine offene oder laufende Reparatur mit Grund zurueck."""
    if "zurueckgezogen" not in _REPARATUR_WEG[r.status]:
        raise ValueError("reparatur.wechsel_nicht_erlaubt")
    if not grund.strip():
        raise ValueError("reparatur.grund_fehlt")
    return replace(r, status="zurueckgezogen", grund=grund.strip())


def status_folge(stueck_status: str, laufende_reparaturen: int, status_grund: str = "") -> str | None:
    """Zielstatus des Stuecks nach einer Aenderung: in_reparatur, solange eine Reparatur laeuft.

    Hand bleibt Hand: zurueck auf aktiv geht es nur, wenn die Automatik `in_reparatur` gesetzt hat (Statusgrund beginnt mit
    `reparatur:`); ein von Hand gesetzter Status bleibt, bis die Werkstatt ihn von Hand aufhebt.
    """
    if laufende_reparaturen < 0:
        raise ValueError("reparatur.anzahl_ungueltig")
    if stueck_status == "aktiv" and laufende_reparaturen > 0:
        return "in_reparatur"
    if stueck_status == "in_reparatur" and laufende_reparaturen == 0 and status_grund.startswith(GRUND_PRAEFIX):
        return "aktiv"
    return None


def reparaturkosten(reparaturen: Iterable[Reparatur]) -> tuple[Decimal, Decimal]:
    """Liefert (Summe aus Belegen, Summe aus Schaetzungen) aller erledigten Reparaturen."""
    echt = geschaetzt = Decimal(0)
    for r in reparaturen:
        if r.status != "erledigt" or r.kosten is None:
            continue
        if r.kosten_quelle == "rechnung":
            echt += r.kosten
        else:
            geschaetzt += r.kosten
    cent = Decimal("0.01")
    return echt.quantize(cent, rounding=ROUND_HALF_UP), geschaetzt.quantize(cent, rounding=ROUND_HALF_UP)
