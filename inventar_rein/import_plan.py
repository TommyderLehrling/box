"""Idempotenter Import: vergleicht geprueft gelesene Zeilen mit dem Bestand und plant, was neu ist."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .import_vorlage import ImportZeile
from .nummernformat import normalisiere

# Standort-Angaben (Kostenstelle, Menge) vergleicht der Plan nicht: sie aendern sich durch Transfers.
VERGLEICHSFELDER = ("bezeichnung", "gruppe", "art", "hersteller", "typ", "seriennummer", "baujahr", "kaufdatum",
                    "kaufpreis", "lieferant", "besonderheiten", "merkmale")


@dataclass(frozen=True)
class Abweichung:
    inventarnummer: str
    felder: tuple[str, ...]


@dataclass(frozen=True)
class BerichtZeile:
    gruppe: str
    art: str
    neu: int
    unveraendert: int
    abweichend: int


@dataclass(frozen=True)
class Plan:
    neu: tuple[ImportZeile, ...]
    unveraendert: tuple[str, ...]
    abweichend: tuple[Abweichung, ...]
    bericht: tuple[BerichtZeile, ...]


def plane(zeilen: Iterable[ImportZeile], vorhanden: Mapping[str, ImportZeile]) -> Plan:
    """Teilt die Zeilen in neu, unveraendert und abweichend (Bestand bleibt unberuehrt); zweiter Lauf legt nichts neu an."""
    bestand = {normalisiere(k): v for k, v in vorhanden.items()}
    liste = list(zeilen)
    nummern = [normalisiere(z.inventarnummer) for z in liste]
    if len(set(nummern)) != len(nummern):
        raise ValueError("import_plan.nummer_doppelt")
    neu: list[ImportZeile] = []
    gleich: list[str] = []
    anders: list[Abweichung] = []
    zaehler: Counter[tuple[str, str, str]] = Counter()
    for nummer, z in zip(nummern, liste):
        alt = bestand.get(nummer)
        if alt is None:
            neu.append(z)
            zaehler[(z.gruppe, z.art, "neu")] += 1
            continue
        felder = tuple(f for f in VERGLEICHSFELDER if getattr(alt, f) != getattr(z, f))
        if felder:
            anders.append(Abweichung(nummer, felder))
            zaehler[(z.gruppe, z.art, "abweichend")] += 1
        else:
            gleich.append(nummer)
            zaehler[(z.gruppe, z.art, "unveraendert")] += 1
    schluessel = sorted({(g, a) for g, a, _ in zaehler})
    bericht = tuple(BerichtZeile(g, a, zaehler[(g, a, "neu")], zaehler[(g, a, "unveraendert")],
                                 zaehler[(g, a, "abweichend")]) for g, a in schluessel)
    return Plan(tuple(neu), tuple(gleich), tuple(anders), bericht)
