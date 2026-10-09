"""Pruefungen: Zuordnung, Faelligkeit nach Datum und Zaehler, Ampel, Faellig-Liste."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Literal

from .fristen import ampel as datum_ampel
from .fristen import naechste_faelligkeit, tage_bis
from .kataloge import Pruefart

Ergebnis = Literal["bestanden", "maengel", "nicht_bestanden"]
Ampel = Literal["gruen", "unbekannt", "gelb", "rot"]
_RANG = MappingProxyType({"gruen": 0, "unbekannt": 1, "gelb": 2, "rot": 3})
_ERGEBNISSE = ("bestanden", "maengel", "nicht_bestanden")


@dataclass(frozen=True)
class Zuordnung:
    pruefart: str
    intervall_monate: int
    zaehler_intervall: int | None


@dataclass(frozen=True)
class Ueberschreibung:
    """Einstellung je Stueck: Intervall aendern oder die Pruefart abschalten."""

    pruefart: str
    intervall_monate: int | None = None
    aktiv: bool = True


@dataclass(frozen=True)
class Eintrag:
    pruefart: str
    durchgefuehrt_am: date
    ergebnis: Ergebnis
    zaehlerstand: Decimal | None = None


@dataclass(frozen=True)
class Pruefstand:
    pruefart: str
    faellig_am: date | None
    tage: int | None  # negativ = ueberfaellig
    faellig_bei_zaehler: Decimal | None
    zaehler_rest: Decimal | None  # negativ = ueberschritten
    ampel: Ampel
    grund: Literal["datum", "zaehler", "nicht_bestanden", "nie_geprueft"]


@dataclass(frozen=True)
class Eintragsfolge:
    naechste_am: date
    naechste_bei_zaehler: Decimal | None


def _intervall_je_merkmal(p: Pruefart, merkmale: Mapping[str, str]) -> int | None:
    """Kuerzestes Intervall, das ein Merkmalswert des Stuecks vorgibt; ohne Treffer None."""
    treffer = [monate[merkmale[name]] for name, monate in p.intervall_je_merkmal.items()
               if name in merkmale and merkmale[name] in monate]
    return min(treffer) if treffer else None


def zuordnungen_fuer(
    gruppe: str, pruefarten: Iterable[Pruefart], ueberschreibungen: Iterable[Ueberschreibung] = (),
    merkmale: Mapping[str, str] | None = None,
) -> list[Zuordnung]:
    """Pruefarten der Gruppe, je Stueck angepasst; Reihenfolge der Intervalle: Stueck-Ueberschreibung, Merkmal, Katalog."""
    ueber = {u.pruefart: u for u in ueberschreibungen}
    ergebnis = []
    for p in pruefarten:
        if gruppe not in p.gruppen:
            continue
        u = ueber.get(p.schluessel)
        if u is not None and not u.aktiv:
            continue
        if u is not None and u.intervall_monate is not None:
            intervall = u.intervall_monate
        else:
            intervall = _intervall_je_merkmal(p, merkmale or {}) or p.intervall_monate
        if intervall < 1:
            raise ValueError("pruefung.intervall_ungueltig")
        ergebnis.append(Zuordnung(p.schluessel, intervall, p.zaehler_intervall))
    return ergebnis


def eintragen(
    zuordnung: Zuordnung, durchgefuehrt_am: date, ergebnis: str, heute: date, zaehlerstand: Decimal | None = None
) -> Eintragsfolge:
    """Prueft einen neuen Eintrag und liefert die naechste Faelligkeit (bei nicht bestanden: sofort)."""
    if ergebnis not in _ERGEBNISSE:
        raise ValueError("pruefung.ergebnis_unbekannt")
    if durchgefuehrt_am > heute:
        raise ValueError("pruefung.datum_in_zukunft")
    if zaehlerstand is not None and zaehlerstand < 0:
        raise ValueError("pruefung.zaehlerstand_ungueltig")
    if zuordnung.zaehler_intervall is not None and zaehlerstand is None:
        raise ValueError("pruefung.zaehlerstand_fehlt")
    if ergebnis == "nicht_bestanden":
        return Eintragsfolge(durchgefuehrt_am, zaehlerstand)
    nach_zaehler = None
    if zuordnung.zaehler_intervall is not None and zaehlerstand is not None:
        nach_zaehler = zaehlerstand + Decimal(zuordnung.zaehler_intervall)
    return Eintragsfolge(naechste_faelligkeit(durchgefuehrt_am, zuordnung.intervall_monate), nach_zaehler)


def pruefstand(
    zuordnung: Zuordnung, letzte: Eintrag | None, heute: date, zaehler_jetzt: Decimal | None = None,
    gelb_ab_tagen: int = 30, gelb_zaehler_anteil: Decimal = Decimal("0.10"),
) -> Pruefstand:
    """Stand einer Pruefart: Faelligkeit nach Datum und Zaehler, schlechtere Ampel gilt; ohne Pruefung: unbekannt."""
    if letzte is None:
        return Pruefstand(zuordnung.pruefart, None, None, None, None, "unbekannt", "nie_geprueft")
    if letzte.pruefart != zuordnung.pruefart:
        raise ValueError("pruefung.pruefart_passt_nicht")
    if letzte.ergebnis == "nicht_bestanden":
        return Pruefstand(zuordnung.pruefart, letzte.durchgefuehrt_am, tage_bis(letzte.durchgefuehrt_am, heute),
                          None, None, "rot", "nicht_bestanden")
    faellig = naechste_faelligkeit(letzte.durchgefuehrt_am, zuordnung.intervall_monate)
    farbe_datum = datum_ampel(faellig, heute, gelb_ab_tagen)
    ziel = rest = None
    farbe_zaehler: Ampel = "gruen"
    if zuordnung.zaehler_intervall is not None and letzte.zaehlerstand is not None:
        ziel = letzte.zaehlerstand + Decimal(zuordnung.zaehler_intervall)
        if zaehler_jetzt is not None:
            rest = ziel - zaehler_jetzt
            if rest <= 0:
                farbe_zaehler = "rot"
            elif rest <= Decimal(zuordnung.zaehler_intervall) * gelb_zaehler_anteil:
                farbe_zaehler = "gelb"
    if _RANG[farbe_zaehler] > _RANG[farbe_datum]:
        return Pruefstand(zuordnung.pruefart, faellig, tage_bis(faellig, heute), ziel, rest, farbe_zaehler, "zaehler")
    return Pruefstand(zuordnung.pruefart, faellig, tage_bis(faellig, heute), ziel, rest, farbe_datum, "datum")


def gesamt_ampel(staende: Iterable[Pruefstand]) -> Ampel:
    """Schlechteste Ampel aller Pruefarten eines Stuecks (rot, gelb, unbekannt, gruen; ohne Pruefart: gruen)."""
    schlechteste: Ampel = "gruen"
    for s in staende:
        if _RANG[s.ampel] > _RANG[schlechteste]:
            schlechteste = s.ampel
    return schlechteste


def faellig_liste(
    staende: Iterable[tuple[str, Pruefstand]], nur: tuple[Ampel, ...] = ("rot", "gelb")
) -> list[tuple[str, Pruefstand]]:
    """Faellig-Liste: erst rot, dann gelb; innerhalb nach Faelligkeit, dann Nummer und Pruefart.

    Stuecke ohne Nachweis (unbekannt) stehen nicht hier, sondern in ohne_nachweis.
    """
    gefiltert = [(n, s) for n, s in staende if s.ampel in nur]
    return sorted(gefiltert, key=lambda x: (-_RANG[x[1].ampel], x[1].faellig_am or date.max, x[0], x[1].pruefart))


def ohne_nachweis(staende: Iterable[tuple[str, Pruefstand]]) -> list[tuple[str, Pruefstand]]:
    """Eigener Block der Faellig-Liste: Stuecke und Pruefarten ohne jede eingetragene Pruefung."""
    return sorted(((n, s) for n, s in staende if s.ampel == "unbekannt"), key=lambda x: (x[0], x[1].pruefart))
