"""Fristen: Monatsarithmetik, Ampel, Zaehlerfaelligkeit, Werktage."""
from __future__ import annotations

import calendar
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal


def naechste_faelligkeit(durchgefuehrt_am: date, intervall_monate: int) -> date:
    """Addiert Monate; faellt der Tag nicht in den Zielmonat, gilt dessen letzter Tag."""
    if intervall_monate < 1:
        raise ValueError("fristen.intervall_ungueltig")
    gesamt = durchgefuehrt_am.year * 12 + (durchgefuehrt_am.month - 1) + intervall_monate
    jahr, monat0 = divmod(gesamt, 12)
    monat = monat0 + 1
    tag = min(durchgefuehrt_am.day, calendar.monthrange(jahr, monat)[1])
    return date(jahr, monat, tag)


def tage_bis(faellig_am: date, heute: date) -> int:
    """Tage bis zur Faelligkeit; negativ bedeutet ueberfaellig."""
    return (faellig_am - heute).days


def ampel(
    faellig_am: date, heute: date, gelb_ab_tagen: int = 30
) -> Literal["gruen", "gelb", "rot"]:
    """Rot ab dem Faelligkeitstag, gelb innerhalb der Vorlaufzeit davor, sonst gruen."""
    if gelb_ab_tagen < 0:
        raise ValueError("fristen.gelb_ungueltig")
    rest = tage_bis(faellig_am, heute)
    if rest <= 0:
        return "rot"
    if rest <= gelb_ab_tagen:
        return "gelb"
    return "gruen"


def faellig_nach_zaehler(
    stand_bei_pruefung: Decimal, stand_jetzt: Decimal, zaehler_intervall: int
) -> bool:
    """Wahr, wenn seit der Pruefung mindestens das Zaehlerintervall gelaufen ist."""
    if zaehler_intervall < 1:
        raise ValueError("fristen.zaehler_intervall_ungueltig")
    return stand_jetzt - stand_bei_pruefung >= Decimal(zaehler_intervall)


def naechste_nach_zaehler(stand_bei_pruefung: Decimal, zaehler_intervall: int) -> Decimal:
    """Zaehlerstand, bei dem die naechste Pruefung faellig wird."""
    if zaehler_intervall < 1:
        raise ValueError("fristen.zaehler_intervall_ungueltig")
    return stand_bei_pruefung + Decimal(zaehler_intervall)


def werktage_zwischen(von: date, bis: date, feiertage: Iterable[date] = ()) -> int:
    """Zaehlt Mo-Fr ohne Feiertage in (von, bis]; ist bis nicht nach von, ergibt es 0."""
    frei = frozenset(feiertage)
    anzahl = 0
    tag = von + timedelta(days=1)
    while tag <= bis:
        if tag.weekday() < 5 and tag not in frei:
            anzahl += 1
        tag += timedelta(days=1)
    return anzahl


def werktage_addieren(start: date, anzahl: int, feiertage: Iterable[date] = ()) -> date:
    """Liefert den Tag, der anzahl Werktage nach start liegt (start zaehlt nicht mit)."""
    if anzahl < 0:
        raise ValueError("fristen.anzahl_ungueltig")
    frei = frozenset(feiertage)
    tag = start
    offen = anzahl
    while offen > 0:
        tag += timedelta(days=1)
        if tag.weekday() < 5 and tag not in frei:
            offen -= 1
    return tag
