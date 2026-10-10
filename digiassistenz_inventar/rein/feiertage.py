"""Gesetzliche Feiertage je Bundesland (rein, ohne Datenbank).

Feste Tage und bewegliche Tage nach Ostern (Gauss/Meeus, gregorianisch). Nur Tage, die im ganzen Land gelten; Tage, die nur
in Teilen eines Landes gelten (Mariae Himmelfahrt in Bayern, Fronleichnam in Teilen von Sachsen und Thueringen, Augsburger
Friedensfest), zaehlen nicht. Einzelne Jahre mit Sondertagen (8. Mai in Berlin 2020 und 2025) sind nicht hinterlegt; solche
Tage tragen die Betriebe als eigene Tage ein.
"""
from __future__ import annotations

from datetime import date, timedelta

LAENDER = ("BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH")

_DREIKOENIG = ("BW", "BY", "ST")
_FRAUENTAG = ("BE", "MV")
_FRONLEICHNAM = ("BW", "BY", "HE", "NW", "RP", "SL")
_MARIAE_HIMMELFAHRT = ("SL",)
_WELTKINDERTAG = ("TH",)
_REFORMATIONSTAG = ("BB", "HB", "HH", "MV", "NI", "SN", "ST", "SH", "TH")
_ALLERHEILIGEN = ("BW", "BY", "NW", "RP", "SL")
_BUSS_UND_BETTAG = ("SN",)


def ostern(jahr: int) -> date:
    """Ostersonntag (anonymer gregorianischer Algorithmus)."""
    a, b, c = jahr % 19, jahr // 100, jahr % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    w = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * w) // 451
    monat, tag = divmod(h + w - 7 * m + 114, 31)
    return date(jahr, monat, tag + 1)


def buss_und_bettag(jahr: int) -> date:
    """Der Mittwoch vor dem 23. November."""
    tag = date(jahr, 11, 22)
    while tag.weekday() != 2:
        tag -= timedelta(days=1)
    return tag


def feiertage_benannt(jahr: int, bundesland: str) -> dict[date, str]:
    """Feiertage des Jahres im Bundesland: Tag -> Textschluessel des Namens. Leeres Bundesland: keine Feiertage."""
    land = bundesland.strip().upper()
    if not land:
        return {}
    if land not in LAENDER:
        raise ValueError("feiertage.land_unbekannt")
    o = ostern(jahr)
    tage: dict[date, str] = {
        date(jahr, 1, 1): "neujahr",
        o - timedelta(days=2): "karfreitag",
        o + timedelta(days=1): "ostermontag",
        date(jahr, 5, 1): "tag_der_arbeit",
        o + timedelta(days=39): "christi_himmelfahrt",
        o + timedelta(days=50): "pfingstmontag",
        date(jahr, 10, 3): "tag_der_einheit",
        date(jahr, 12, 25): "weihnachtstag_1",
        date(jahr, 12, 26): "weihnachtstag_2",
    }
    if land in _DREIKOENIG:
        tage[date(jahr, 1, 6)] = "heilige_drei_koenige"
    if land in _FRAUENTAG:
        tage[date(jahr, 3, 8)] = "frauentag"
    if land in _FRONLEICHNAM:
        tage[o + timedelta(days=60)] = "fronleichnam"
    if land in _MARIAE_HIMMELFAHRT:
        tage[date(jahr, 8, 15)] = "mariae_himmelfahrt"
    if land in _WELTKINDERTAG:
        tage[date(jahr, 9, 20)] = "weltkindertag"
    if land in _REFORMATIONSTAG:
        tage[date(jahr, 10, 31)] = "reformationstag"
    if land in _ALLERHEILIGEN:
        tage[date(jahr, 11, 1)] = "allerheiligen"
    if land in _BUSS_UND_BETTAG:
        tage[buss_und_bettag(jahr)] = "buss_und_bettag"
    return dict(sorted(tage.items()))


def feiertage(jahr: int, bundesland: str) -> set[date]:
    """Die Feiertage des Jahres im Bundesland (leer = keine)."""
    return set(feiertage_benannt(jahr, bundesland))


def feiertage_zwischen(von: date, bis: date, bundesland: str) -> set[date]:
    """Feiertage im Zeitraum [von, bis] ueber die betroffenen Jahre."""
    if bis < von:
        return set()
    erg: set[date] = set()
    for jahr in range(von.year, bis.year + 1):
        erg |= {t for t in feiertage(jahr, bundesland) if von <= t <= bis}
    return erg
