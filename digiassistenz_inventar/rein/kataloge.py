"""Startkataloge (Gruppen, Merkmale, Pruefarten) als Daten, mit Lader und Pruefung."""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collections.abc import Iterable
from typing import Any, Literal

_DATEN = Path(__file__).resolve().parent / "daten"
_SCHLUESSEL = re.compile(r"[a-z][a-z0-9_]*")
_KUERZEL = re.compile(r"[A-Z]{2}")
_TYPEN = ("text", "zahl", "datum", "ja_nein", "auswahl")
_DURCHFUEHRUNG = ("intern", "extern", "beides")


@dataclass(frozen=True)
class Gruppe:
    schluessel: str
    bezeichnung: str
    kuerzel: str
    oben: str | None
    sortierung: int


@dataclass(frozen=True)
class Merkmal:
    gruppe: str
    schluessel: str
    bezeichnung: str
    typ: Literal["text", "zahl", "datum", "ja_nein", "auswahl"]
    einheit: str
    auswahl: tuple[str, ...]
    pflicht: bool
    sortierung: int


@dataclass(frozen=True)
class Pruefart:
    schluessel: str
    bezeichnung: str
    intervall_monate: int
    zaehler_intervall: int | None
    rechtsgrund: str
    durchfuehrung: Literal["intern", "extern", "beides"]
    gruppen: tuple[str, ...]
    # Intervall je Merkmalswert, z. B. {"fahrzeugklasse": {"pkw": 24, "lkw_ueber_3_5": 12}}; Stueck-Ueberschreibung geht vor
    intervall_je_merkmal: dict[str, dict[str, int]] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class Bauteil:
    bauteilnummer: str
    bezeichnung: str
    hersteller: str
    lieferant: str
    preis_zuletzt: Decimal | None
    hinweis: str
    passt_zu_gruppen: tuple[str, ...]
    passt_zu_stuecke: tuple[str, ...]


def _lies_liste(pfad: Path) -> list[dict[str, Any]]:
    """Liest eine JSON-Datei, die eine Liste von Objekten enthaelt."""
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as fehler:
        raise ValueError(f"kataloge.datei_unlesbar:{pfad.name}") from fehler
    if not isinstance(roh, list) or not all(isinstance(e, dict) for e in roh):
        raise ValueError(f"kataloge.datei_form:{pfad.name}")
    return roh


def _feld(eintrag: dict[str, Any], name: str, art: type, datei: str, vorgabe: Any = ...) -> Any:
    """Holt ein Feld mit Typpruefung; fehlt es und gibt es keine Vorgabe, ValueError."""
    if name not in eintrag:
        if vorgabe is ...:
            raise ValueError(f"kataloge.feld_fehlt:{datei}:{name}")
        return vorgabe
    wert = eintrag[name]
    if wert is None and vorgabe is None:
        return None
    if not isinstance(wert, art) or (art is int and isinstance(wert, bool)):
        raise ValueError(f"kataloge.feld_typ:{datei}:{name}")
    return wert


def _texte(eintrag: dict[str, Any], name: str, datei: str) -> tuple[str, ...]:
    """Holt eine Liste von Zeichenketten als Tupel; fehlt sie, ist sie leer."""
    liste = _feld(eintrag, name, list, datei, [])
    if not all(isinstance(t, str) for t in liste):
        raise ValueError(f"kataloge.feld_typ:{datei}:{name}")
    return tuple(liste)


def lade_gruppen(pfad: Path | None = None) -> list[Gruppe]:
    """Liest die Gruppen aus gruppen.json (Reihenfolge wie in der Datei)."""
    pfad = pfad or _DATEN / "gruppen.json"
    d = pfad.name
    return [
        Gruppe(
            schluessel=_feld(e, "schluessel", str, d),
            bezeichnung=_feld(e, "bezeichnung", str, d),
            kuerzel=_feld(e, "kuerzel", str, d),
            oben=_feld(e, "oben", str, d, None),
            sortierung=_feld(e, "sortierung", int, d),
        )
        for e in _lies_liste(pfad)
    ]


def lade_merkmale(pfad: Path | None = None) -> list[Merkmal]:
    """Liest die Merkmale aus merkmale.json (Reihenfolge wie in der Datei)."""
    pfad = pfad or _DATEN / "merkmale.json"
    d = pfad.name
    return [
        Merkmal(
            gruppe=_feld(e, "gruppe", str, d),
            schluessel=_feld(e, "schluessel", str, d),
            bezeichnung=_feld(e, "bezeichnung", str, d),
            typ=_feld(e, "typ", str, d),
            einheit=_feld(e, "einheit", str, d, ""),
            auswahl=_texte(e, "auswahl", d),
            pflicht=_feld(e, "pflicht", bool, d, False),
            sortierung=_feld(e, "sortierung", int, d),
        )
        for e in _lies_liste(pfad)
    ]


def _je_merkmal(eintrag: dict[str, Any], datei: str) -> dict[str, dict[str, int]]:
    """Holt intervall_je_merkmal (Merkmal -> Wert -> Monate); fehlt es, ist es leer."""
    roh = _feld(eintrag, "intervall_je_merkmal", dict, datei, {})
    ergebnis: dict[str, dict[str, int]] = {}
    for merkmal, werte in roh.items():
        if not isinstance(werte, dict) or not all(
            isinstance(w, str) and isinstance(m, int) and not isinstance(m, bool) for w, m in werte.items()
        ):
            raise ValueError(f"kataloge.feld_typ:{datei}:intervall_je_merkmal")
        ergebnis[merkmal] = dict(werte)
    return ergebnis


def lade_pruefarten(pfad: Path | None = None) -> list[Pruefart]:
    """Liest die Pruefarten aus pruefarten.json (Reihenfolge wie in der Datei)."""
    pfad = pfad or _DATEN / "pruefarten.json"
    d = pfad.name
    return [
        Pruefart(
            schluessel=_feld(e, "schluessel", str, d),
            bezeichnung=_feld(e, "bezeichnung", str, d),
            intervall_monate=_feld(e, "intervall_monate", int, d),
            zaehler_intervall=_feld(e, "zaehler_intervall", int, d, None),
            rechtsgrund=_feld(e, "rechtsgrund", str, d),
            durchfuehrung=_feld(e, "durchfuehrung", str, d),
            gruppen=_texte(e, "gruppen", d),
            intervall_je_merkmal=_je_merkmal(e, d),
        )
        for e in _lies_liste(pfad)
    ]


def gruppe_pruefart(pruefarten: Iterable[Pruefart]) -> tuple[tuple[str, str], ...]:
    """Startwert der Zuordnung Gruppe -> Pruefart (Gruppe, Pruefart) in Reihenfolge des Katalogs."""
    return tuple((g, p.schluessel) for p in pruefarten for g in p.gruppen)


def lade_bauteile(pfad: Path | None = None) -> list[Bauteil]:
    """Liest den Bauteilkatalog aus bauteile.json (Startkatalog ist leer: nur die Form)."""
    pfad = pfad or _DATEN / "bauteile.json"
    d = pfad.name
    ergebnis = []
    for e in _lies_liste(pfad):
        preis = _feld(e, "preis_zuletzt", str, d, None)
        try:
            betrag = None if preis is None else Decimal(preis)
        except InvalidOperation as fehler:
            raise ValueError(f"kataloge.feld_typ:{d}:preis_zuletzt") from fehler
        ergebnis.append(Bauteil(
            bauteilnummer=_feld(e, "bauteilnummer", str, d),
            bezeichnung=_feld(e, "bezeichnung", str, d),
            hersteller=_feld(e, "hersteller", str, d, ""),
            lieferant=_feld(e, "lieferant", str, d, ""),
            preis_zuletzt=betrag,
            hinweis=_feld(e, "hinweis", str, d, ""),
            passt_zu_gruppen=_texte(e, "passt_zu_gruppen", d),
            passt_zu_stuecke=_texte(e, "passt_zu_stuecke", d),
        ))
    return ergebnis


def passende_bauteile(bauteile: Iterable[Bauteil], gruppe: str, inventarnummer: str) -> list[Bauteil]:
    """Liefert die Bauteile, die zur Gruppe oder genau zu diesem Stueck passen."""
    return [b for b in bauteile if gruppe in b.passt_zu_gruppen or inventarnummer in b.passt_zu_stuecke]


def pruefe_bauteile(bauteile: list[Bauteil], gruppen: list[Gruppe]) -> list[str]:
    """Liefert Fehlerschluessel zum Bauteilkatalog; leere Liste bedeutet in Ordnung."""
    fehler: list[str] = []
    gruppen_schluessel = {g.schluessel for g in gruppen}
    for b in bauteile:
        if not b.bauteilnummer.strip():
            fehler.append("bauteil.nummer_leer")
        if not b.bezeichnung.strip():
            fehler.append(f"bauteil.bezeichnung_leer:{b.bauteilnummer}")
        if b.preis_zuletzt is not None and b.preis_zuletzt < 0:
            fehler.append(f"bauteil.preis_negativ:{b.bauteilnummer}")
        if not b.passt_zu_gruppen and not b.passt_zu_stuecke:
            fehler.append(f"bauteil.passt_zu_nichts:{b.bauteilnummer}")
        fehler += [f"bauteil.gruppe_unbekannt:{b.bauteilnummer}:{g}" for g in b.passt_zu_gruppen
                   if g not in gruppen_schluessel]
    fehler += [f"bauteil.nummer_doppelt:{n}" for n in _doppelte([b.bauteilnummer for b in bauteile])]
    return fehler


def _doppelte(werte: list[str]) -> list[str]:
    """Liefert die mehrfach vorkommenden Werte in Reihenfolge des ersten Auftretens."""
    zaehler = Counter(werte)
    return [w for w in dict.fromkeys(werte) if zaehler[w] > 1]


def _pruefe_je_merkmal(p: Pruefart, merkmale: list[Merkmal]) -> list[str]:
    """Das Merkmal muss eine Auswahl in einer Gruppe der Pruefart sein, jeder Wert aus der Auswahl, Monate ab 1."""
    fehler: list[str] = []
    for name, werte in p.intervall_je_merkmal.items():
        passend = [m for m in merkmale if m.schluessel == name and m.gruppe in p.gruppen and m.typ == "auswahl"]
        if not passend:
            fehler.append(f"pruefart.merkmal_unbekannt:{p.schluessel}:{name}")
            continue
        erlaubt = {w for m in passend for w in m.auswahl}
        fehler += [f"pruefart.merkmal_wert_unbekannt:{p.schluessel}:{name}:{w}" for w in werte if w not in erlaubt]
        if any(monate < 1 for monate in werte.values()):
            fehler.append(f"pruefart.intervall_je_merkmal_ungueltig:{p.schluessel}:{name}")
    return fehler


def pruefe_kataloge(
    gruppen: list[Gruppe], merkmale: list[Merkmal], pruefarten: list[Pruefart]
) -> list[str]:
    """Liefert Fehlerschluessel der drei Kataloge; leere Liste bedeutet in Ordnung."""
    fehler: list[str] = []
    gruppen_schluessel = {g.schluessel for g in gruppen}

    for g in gruppen:
        if not _SCHLUESSEL.fullmatch(g.schluessel):
            fehler.append(f"gruppe.schluessel_ungueltig:{g.schluessel}")
        if not g.bezeichnung.strip():
            fehler.append(f"gruppe.bezeichnung_leer:{g.schluessel}")
        if not _KUERZEL.fullmatch(g.kuerzel):
            fehler.append(f"gruppe.kuerzel_ungueltig:{g.schluessel}:{g.kuerzel}")
        if g.oben is not None and g.oben not in gruppen_schluessel:
            fehler.append(f"gruppe.oben_unbekannt:{g.schluessel}:{g.oben}")
    fehler += [f"gruppe.schluessel_doppelt:{s}" for s in _doppelte([g.schluessel for g in gruppen])]
    fehler += [f"gruppe.kuerzel_doppelt:{k}" for k in _doppelte([g.kuerzel for g in gruppen])]

    for m in merkmale:
        if not _SCHLUESSEL.fullmatch(m.schluessel):
            fehler.append(f"merkmal.schluessel_ungueltig:{m.schluessel}")
        if m.gruppe not in gruppen_schluessel:
            fehler.append(f"merkmal.gruppe_unbekannt:{m.schluessel}:{m.gruppe}")
        if m.typ not in _TYPEN:
            fehler.append(f"merkmal.typ_unbekannt:{m.schluessel}:{m.typ}")
        elif m.typ == "auswahl" and not m.auswahl:
            fehler.append(f"merkmal.auswahl_leer:{m.schluessel}")
        elif m.typ != "auswahl" and m.auswahl:
            fehler.append(f"merkmal.auswahl_unerwartet:{m.schluessel}")
        if _doppelte(list(m.auswahl)):
            fehler.append(f"merkmal.auswahl_doppelt:{m.schluessel}")
    fehler += [f"merkmal.schluessel_doppelt:{s}" for s in _doppelte([m.schluessel for m in merkmale])]

    for p in pruefarten:
        if not _SCHLUESSEL.fullmatch(p.schluessel):
            fehler.append(f"pruefart.schluessel_ungueltig:{p.schluessel}")
        if p.intervall_monate < 1:
            fehler.append(f"pruefart.intervall_ungueltig:{p.schluessel}")
        if p.zaehler_intervall is not None and p.zaehler_intervall < 1:
            fehler.append(f"pruefart.zaehler_intervall_ungueltig:{p.schluessel}")
        if p.durchfuehrung not in _DURCHFUEHRUNG:
            fehler.append(f"pruefart.durchfuehrung_unbekannt:{p.schluessel}:{p.durchfuehrung}")
        fehler += [
            f"pruefart.gruppe_unbekannt:{p.schluessel}:{g}"
            for g in p.gruppen
            if g not in gruppen_schluessel
        ]
        fehler += _pruefe_je_merkmal(p, merkmale)
    fehler += [f"pruefart.schluessel_doppelt:{s}" for s in _doppelte([p.schluessel for p in pruefarten])]
    return fehler
