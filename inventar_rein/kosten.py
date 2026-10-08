"""Kalkulatorische Kostenrechnung (Logik der Baugeraeteliste); keine steuerliche AfA."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .fristen import naechste_faelligkeit, werktage_zwischen
from .transfer import Standort

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class Kostenparameter:
    kaufpreis: Decimal
    restwert: Decimal
    nutzungsdauer_monate: int
    zins_prozent: Decimal
    reparatur_prozent_jahr: Decimal
    tage_je_monat: Decimal = Decimal("30")


@dataclass(frozen=True)
class Kostensatz:
    abschreibung_monat: Decimal
    zins_monat: Decimal
    reparatur_monat: Decimal
    satz_monat: Decimal
    satz_tag: Decimal
    satz_woche: Decimal


@dataclass(frozen=True)
class Vorhaltung:
    kostenstelle: int
    tage: int
    betrag: Decimal


def _runde(x: Decimal) -> Decimal:
    """Rundet kaufmaennisch auf zwei Stellen."""
    return x.quantize(_CENT, rounding=ROUND_HALF_UP)


def _pruefe(p: Kostenparameter) -> None:
    if p.kaufpreis < 0 or p.restwert < 0 or p.restwert > p.kaufpreis:
        raise ValueError("kosten.preis_ungueltig")
    if p.nutzungsdauer_monate < 1:
        raise ValueError("kosten.nutzungsdauer_ungueltig")
    if p.zins_prozent < 0 or p.reparatur_prozent_jahr < 0:
        raise ValueError("kosten.prozent_ungueltig")
    if p.tage_je_monat <= 0:
        raise ValueError("kosten.tage_je_monat_ungueltig")


def _roh(p: Kostenparameter) -> tuple[Decimal, Decimal, Decimal]:
    """Abschreibung, Zins und Reparatur je Monat, ungerundet."""
    _pruefe(p)
    abschreibung = (p.kaufpreis - p.restwert) / p.nutzungsdauer_monate
    zins = p.kaufpreis / 2 * p.zins_prozent / 100 / 12
    reparatur = p.kaufpreis * p.reparatur_prozent_jahr / 100 / 12
    return abschreibung, zins, reparatur


def kostensatz(p: Kostenparameter) -> Kostensatz:
    """Berechnet die Saetze je Monat, Tag und Woche; gerundet wird erst am Ende jeder Groesse."""
    abschreibung, zins, reparatur = _roh(p)
    monat = abschreibung + zins + reparatur
    tag = monat / p.tage_je_monat
    return Kostensatz(_runde(abschreibung), _runde(zins), _runde(reparatur),
                      _runde(monat), _runde(tag), _runde(tag * 7))


def vorhaltung(
    standorte: Iterable[Standort], von: date, bis: date, satz_tag: Decimal, mit_menge: bool = False,
    werktage: bool = False, feiertage: Iterable[date] = (),
) -> tuple[Vorhaltung, ...]:
    """Tage (Kalender- oder Werktage) und Betrag je Kostenstelle in [von, bis]; Eingangstag zaehlt zum Ziel, Abgangstag nicht zur Quelle."""
    if bis < von:
        raise ValueError("kosten.zeitraum_ungueltig")
    frei = frozenset(feiertage)
    tage: dict[int, int] = {}
    betrag: dict[int, Decimal] = {}
    for s in standorte:
        anfang = max(s.von.date(), von)
        ende = bis if s.bis is None else min(s.bis.date() - timedelta(days=1), bis)
        if werktage:
            anzahl = werktage_zwischen(anfang - timedelta(days=1), ende, frei) if ende >= anfang else 0
        else:
            anzahl = (ende - anfang).days + 1
        if anzahl <= 0:
            continue
        tage[s.kostenstelle] = tage.get(s.kostenstelle, 0) + anzahl
        faktor = s.menge if mit_menge else 1
        betrag[s.kostenstelle] = betrag.get(s.kostenstelle, Decimal(0)) + satz_tag * anzahl * faktor
    return tuple(Vorhaltung(ks, tage[ks], _runde(betrag[ks])) for ks in sorted(tage))


def gesamtkosten(kaufpreis: Decimal, reparaturen: Iterable[Decimal]) -> Decimal:
    """Kaufpreis plus alle Reparaturkosten."""
    return _runde(kaufpreis + sum(reparaturen, Decimal(0)))


def _volle_monate(kaufdatum: date, stichtag: date, grenze: int) -> int:
    """Volle Monate seit dem Kauf (Monatsende-Regel wie bei den Fristen), hoechstens grenze."""
    if stichtag < kaufdatum:
        return 0
    n = min(grenze, (stichtag.year - kaufdatum.year) * 12 + stichtag.month - kaufdatum.month)
    while n > 0 and naechste_faelligkeit(kaufdatum, n) > stichtag:
        n -= 1
    return n


def kalkulatorisch_bis(p: Kostenparameter, kaufdatum: date, heute: date) -> Decimal:
    """Volle Monate seit Kauf mal Monatssatz, hoechstens die Nutzungsdauer."""
    abschreibung, zins, reparatur = _roh(p)
    n = _volle_monate(kaufdatum, heute, p.nutzungsdauer_monate)
    return _runde((abschreibung + zins + reparatur) * n)


def miete_vs_eigen(
    mietkosten: Decimal, satz_tag_eigen: Decimal, tage: int
) -> tuple[Decimal, Decimal, Decimal]:
    """Liefert (Miete, Eigen, Differenz = Miete - Eigen)."""
    if tage < 0:
        raise ValueError("kosten.tage_ungueltig")
    miete = _runde(mietkosten)
    eigen = _runde(satz_tag_eigen * tage)
    return miete, eigen, miete - eigen


def restbuchwert_kalk(p: Kostenparameter, kaufdatum: date, stichtag: date) -> Decimal:
    """Linearer kalkulatorischer Restwert, nie unter dem Restwert."""
    abschreibung, _, _ = _roh(p)
    n = _volle_monate(kaufdatum, stichtag, p.nutzungsdauer_monate)
    return _runde(max(p.restwert, p.kaufpreis - abschreibung * n))
