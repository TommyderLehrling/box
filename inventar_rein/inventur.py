"""Inventur: Stichtagslauf, der Gesehenes und Erwartetes vergleicht und Vermisste vorschlaegt."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

_ZAEHLT = ("aktiv", "in_reparatur")


@dataclass(frozen=True)
class Erwartet:
    inventarnummer: str
    kostenstelle: int
    menge: int
    status: str


@dataclass(frozen=True)
class Gesehen:
    inventarnummer: str
    kostenstelle: int
    menge: int
    zeit: datetime


@dataclass(frozen=True)
class Fehlt:
    inventarnummer: str
    kostenstelle: int
    erwartet: int
    gesehen: int


@dataclass(frozen=True)
class Woanders:
    inventarnummer: str
    erwartet_auf: int
    gesehen_auf: int


@dataclass(frozen=True)
class Inventurergebnis:
    gefunden: tuple[str, ...]
    woanders: tuple[Woanders, ...]
    fehlmengen: tuple[Fehlt, ...]
    vermisst_vorschlag: tuple[str, ...]
    wieder_aufgetaucht: tuple[str, ...]
    unbekannt: tuple[str, ...]


def auswerten(
    erwartet: Iterable[Erwartet], gesehen: Iterable[Gesehen], umfang: Iterable[int]
) -> Inventurergebnis:
    """Wertet einen Stichtag aus: nur Kostenstellen im Umfang zaehlen; nicht Gesehenes wird als vermisst vorgeschlagen."""
    ks_umfang = frozenset(umfang)
    soll = list(erwartet)
    bekannt = {e.inventarnummer for e in soll}
    gesehen_je: dict[tuple[str, int], int] = defaultdict(int)
    gesehen_nr: dict[str, list[int]] = defaultdict(list)
    for g in gesehen:
        if g.kostenstelle not in ks_umfang:
            raise ValueError("inventur.gesehen_ausserhalb_umfang")
        if g.menge < 1:
            raise ValueError("inventur.menge_ungueltig")
        gesehen_je[(g.inventarnummer, g.kostenstelle)] += g.menge
        gesehen_nr[g.inventarnummer].append(g.kostenstelle)
    gefunden: set[str] = set()
    woanders: list[Woanders] = []
    fehlmengen: list[Fehlt] = []
    vermisst: set[str] = set()
    zurueck: set[str] = set()
    zeilen_je: dict[str, list[Erwartet]] = defaultdict(list)
    for e in soll:
        zeilen_je[e.inventarnummer].append(e)
    for nummer, zeilen in zeilen_je.items():
        im_umfang = [e for e in zeilen if e.kostenstelle in ks_umfang]
        if not im_umfang:
            continue
        if all(e.status == "vermisst" for e in im_umfang):
            if gesehen_nr.get(nummer):
                zurueck.add(nummer)
            continue
        if not all(e.status in _ZAEHLT for e in im_umfang):
            continue  # Endzustaende sind nicht Teil der Inventur
        erwartete_orte = {e.kostenstelle for e in zeilen}
        komplett_fehlend = True
        for e in im_umfang:
            gesehen_hier = gesehen_je.get((nummer, e.kostenstelle), 0)
            if gesehen_hier >= e.menge:
                gefunden.add(nummer)
                komplett_fehlend = False
            elif gesehen_hier > 0:
                fehlmengen.append(Fehlt(nummer, e.kostenstelle, e.menge, gesehen_hier))
                komplett_fehlend = False
            else:
                anderswo = [k for k in gesehen_nr.get(nummer, []) if k not in erwartete_orte]
                if anderswo:
                    woanders.append(Woanders(nummer, e.kostenstelle, anderswo[0]))
                    komplett_fehlend = False
                else:
                    fehlmengen.append(Fehlt(nummer, e.kostenstelle, e.menge, 0))
        if komplett_fehlend:
            vermisst.add(nummer)
    unbekannt = sorted(n for n in gesehen_nr if n not in bekannt)
    return Inventurergebnis(
        tuple(sorted(gefunden)), tuple(sorted(woanders, key=lambda w: (w.inventarnummer, w.erwartet_auf))),
        tuple(sorted(fehlmengen, key=lambda f: (f.inventarnummer, f.kostenstelle))),
        tuple(sorted(vermisst)), tuple(sorted(zurueck)), tuple(unbekannt))
