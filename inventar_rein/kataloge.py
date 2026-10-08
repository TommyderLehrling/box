"""Startkataloge (Gruppen, Merkmale, Pruefarten) als Daten, mit Lader und Pruefung."""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
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
        )
        for e in _lies_liste(pfad)
    ]


def _doppelte(werte: list[str]) -> list[str]:
    """Liefert die mehrfach vorkommenden Werte in Reihenfolge des ersten Auftretens."""
    zaehler = Counter(werte)
    return [w for w in dict.fromkeys(werte) if zaehler[w] > 1]


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
    fehler += [f"pruefart.schluessel_doppelt:{s}" for s in _doppelte([p.schluessel for p in pruefarten])]
    return fehler
