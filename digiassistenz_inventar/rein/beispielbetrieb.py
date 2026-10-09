"""Beispielbetrieb: 50 handverlesene Stuecke mit Geschichte (deterministisch, aus daten/beispielbetrieb.json)."""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from openpyxl import Workbook

from .import_vorlage import BLATT, SPALTEN, ImportZeile
from .kataloge import Merkmal, Pruefart
from .pruefung import Eintrag, Pruefstand, pruefstand, zuordnungen_fuer
from .transfer import Standort, Zustand, abgang_buchen, scan_ist_hier, zubehoer_folgt
from .werkstatt import Meldung, Reparatur, meldung_weiter, neue_meldung, neue_reparatur, reparatur_beginnen

_DATEI = Path(__file__).resolve().parent / "daten" / "beispielbetrieb.json"


@dataclass(frozen=True)
class Kostenstelle:
    nummer: int
    bezeichnung: str


@dataclass(frozen=True)
class Person:
    kennung: str
    rolle: str
    kostenstellen: tuple[int, ...]


@dataclass(frozen=True)
class Miete:
    von: date
    bis: date
    lieferant: str
    kosten: Decimal | None = None  # Mietkosten fuer den ganzen Zeitraum


@dataclass(frozen=True)
class BeispielStueck:
    zeile: ImportZeile
    status: str
    status_grund: str
    miete: Miete | None
    pruefarten: tuple[str, ...]
    fall: str  # welcher Fall dieses Stueck zeigt (Klartext fuer die README-Tabelle)


@dataclass(frozen=True)
class Buchung:
    art: Literal["abgang", "scan"]
    stueck: str
    person: str
    zeit: datetime
    quelle: str
    schluessel: str
    von: int | None = None
    nach: int | None = None
    ks: int | None = None
    menge: int | None = None


@dataclass(frozen=True)
class Beispielbetrieb:
    heute: date
    angelegt_am: datetime
    kostenstellen: tuple[Kostenstelle, ...]
    personen: tuple[Person, ...]
    stuecke: tuple[BeispielStueck, ...]
    zubehoer: tuple[tuple[str, str], ...]  # (Zubehoer, Hauptstueck)
    buchungen: tuple[Buchung, ...]
    pruefungen: tuple[tuple[str, Eintrag], ...]
    zaehlerstaende: tuple[tuple[str, Decimal, date, str], ...]  # (Nummer, Stand, abgelesen_am, Quelle)
    meldungen: tuple[tuple[str, Meldung], ...]
    reparaturen: tuple[tuple[str, Reparatur], ...]


def _datum(wert: str) -> date:
    return date.fromisoformat(wert)


def _zeit(wert: str) -> datetime:
    zeit = datetime.fromisoformat(wert)
    if zeit.tzinfo is None:
        raise ValueError("beispielbetrieb.zeit_naiv")
    return zeit


def _bauen_meldung(roh: dict[str, Any]) -> tuple[str, Meldung]:
    m = neue_meldung(roh["art"], roh["beschreibung"], roh["person"], _zeit(roh["am"]))
    for schritt in roh["weg"]:
        m = meldung_weiter(m, schritt["status"], schritt["person"], _zeit(schritt["am"]))
    return roh["stueck"], m


def _bauen_reparatur(roh: dict[str, Any]) -> tuple[str, Reparatur]:
    kosten = Decimal(roh["geschaetzte_kosten"]) if roh.get("geschaetzte_kosten") else None
    r = reparatur_beginnen(neue_reparatur(roh["durchfuehrung"]), _datum(roh["begonnen_am"]), kosten)
    return roh["stueck"], r


def lade_beispielbetrieb(pfad: Path | None = None) -> Beispielbetrieb:
    """Liest und prueft den Beispielbetrieb; Fehler als ValueError mit Schluessel beispielbetrieb.*."""
    try:
        roh = json.loads((pfad or _DATEI).read_text(encoding="utf-8"))
    except (OSError, ValueError) as fehler:
        raise ValueError("beispielbetrieb.datei_unlesbar") from fehler
    stuecke = []
    for i, s in enumerate(roh["stuecke"], start=2):
        zeile = ImportZeile(
            i, s["inventarnummer"], s["bezeichnung"], s["gruppe"], s["art"], s["hersteller"], s["typ"],
            s["seriennummer"], s["baujahr"], _datum(s["kaufdatum"]), Decimal(s["kaufpreis"]), s["lieferant"],
            s["kostenstelle"], s["menge"], s["besonderheiten"], dict(s["merkmale"]))
        miete = None if not s["miete"] else Miete(_datum(s["miete"]["von"]), _datum(s["miete"]["bis"]), s["miete"]["lieferant"],
                                                    Decimal(s["miete"]["kosten"]) if s["miete"].get("kosten") else None)
        stuecke.append(BeispielStueck(zeile, s["status"], s["status_grund"], miete, tuple(s["pruefarten"]), s["fall"]))
    nummern = [s.zeile.inventarnummer for s in stuecke]
    if len(set(nummern)) != len(nummern):
        raise ValueError("beispielbetrieb.nummer_doppelt")
    bekannt = set(nummern)
    kostenstellen = tuple(Kostenstelle(k["nummer"], k["bezeichnung"]) for k in roh["kostenstellen"])
    erlaubt = {k.nummer for k in kostenstellen}
    if any(s.zeile.kostenstelle not in erlaubt for s in stuecke):
        raise ValueError("beispielbetrieb.kostenstelle_unbekannt")
    zubehoer = tuple((z["stueck"], z["gehoert_zu"]) for z in roh["zubehoer"])
    if any(a not in bekannt or b not in bekannt for a, b in zubehoer):
        raise ValueError("beispielbetrieb.zubehoer_unbekannt")
    buchungen = tuple(Buchung(
        b["art"], b["stueck"], b["person"], _zeit(b["zeit"]), b["quelle"], b["schluessel"],
        b.get("von"), b.get("nach"), b.get("ks"), b.get("menge")) for b in roh["transfers"])
    pruefungen = tuple((p["stueck"], Eintrag(
        p["pruefart"], _datum(p["durchgefuehrt_am"]), p["ergebnis"],
        Decimal(p["zaehlerstand"]) if p["zaehlerstand"] else None)) for p in roh["pruefungen"])
    zaehler = tuple((z["stueck"], Decimal(z["stand"]), _datum(z["am"]), z["quelle"]) for z in roh["zaehlerstaende"])
    return Beispielbetrieb(
        _datum(roh["heute"]), _zeit(roh["angelegt_am"]), kostenstellen,
        tuple(Person(p["kennung"], p["rolle"], tuple(p["kostenstellen"])) for p in roh["personen"]),
        tuple(stuecke), zubehoer, buchungen, pruefungen, zaehler,
        tuple(_bauen_meldung(m) for m in roh["meldungen"]), tuple(_bauen_reparatur(r) for r in roh["reparaturen"]))


def zustaende(b: Beispielbetrieb) -> dict[str, Zustand]:
    """Standorte und Transfers je Stueck: Startstandort, danach alle Buchungen der Reihe nach (Zubehoer folgt)."""
    z: dict[str, Zustand] = {
        s.zeile.inventarnummer: Zustand((Standort(
            s.zeile.inventarnummer, s.zeile.kostenstelle, s.zeile.menge, b.angelegt_am, None, None, "import",
            "import"),), ()) for s in b.stuecke}
    folgt: dict[str, list[str]] = {}
    for zub, haupt in b.zubehoer:
        folgt.setdefault(haupt, []).append(zub)
    for x in b.buchungen:
        if x.art == "abgang":
            assert x.von is not None and x.nach is not None and x.menge is not None
            erg = abgang_buchen(z[x.stueck], x.stueck, x.von, x.nach, x.menge, x.person, x.zeit, x.quelle,  # type: ignore[arg-type]
                                x.schluessel)
        else:
            assert x.ks is not None
            erg = scan_ist_hier(z[x.stueck], x.stueck, x.ks, x.person, x.zeit, x.quelle, x.schluessel, x.menge)  # type: ignore[arg-type]
        z[x.stueck] = erg.zustand
        for zub, folge in zubehoer_folgt(erg, folgt.get(x.stueck, []), z, x.zeit).items():
            z[zub] = folge.zustand
    return z


def pruefstaende(b: Beispielbetrieb, katalog: Iterable[Pruefart]) -> dict[str, tuple[Pruefstand, ...]]:
    """Pruefstand je Stueck und zugeordneter Pruefart zum Stichtag (nie geprueft: unbekannt)."""
    katalog = list(katalog)
    letzte: dict[tuple[str, str], Eintrag] = {}
    for nummer, e in sorted(b.pruefungen, key=lambda x: x[1].durchgefuehrt_am):
        letzte[(nummer, e.pruefart)] = e
    zaehler: dict[str, tuple[Decimal, date]] = {}
    for nummer, stand, am, _ in sorted(b.zaehlerstaende, key=lambda x: x[2]):
        zaehler[nummer] = (stand, am)
    ergebnis: dict[str, tuple[Pruefstand, ...]] = {}
    for s in b.stuecke:
        nummer = s.zeile.inventarnummer
        arten = [p for p in katalog if p.schluessel in s.pruefarten]
        staende = []
        for zu in zuordnungen_fuer(s.zeile.gruppe, arten):
            jetzt = zaehler.get(nummer, (None, None))[0] if zu.zaehler_intervall is not None else None
            staende.append(pruefstand(zu, letzte.get((nummer, zu.pruefart)), b.heute, jetzt))
        ergebnis[nummer] = tuple(staende)
    return ergebnis


def schreibe_importdatei(b: Beispielbetrieb, pfad: Path, merkmale: Iterable[Merkmal]) -> None:
    """Schreibt die Stuecke im Format der Import-Vorlage (ohne Beispielzeilen) fuer den eigenen Import-Prueflauf."""
    schluessel = sorted({m.schluessel for m in merkmale} & {k for s in b.stuecke for k in s.zeile.merkmale})
    wb = Workbook()
    ws = wb.active
    ws.title = BLATT
    ws.append(list(SPALTEN) + [f"m:{k}" for k in schluessel])
    for s in b.stuecke:
        z = s.zeile
        ws.append([z.inventarnummer, z.bezeichnung, z.gruppe, z.art, z.hersteller, z.typ, z.seriennummer, z.baujahr,
                   z.kaufdatum, float(z.kaufpreis) if z.kaufpreis is not None else None, z.lieferant, z.kostenstelle,
                   z.menge, z.besonderheiten] + [z.merkmale.get(k) for k in schluessel])
    wb.save(pfad)
