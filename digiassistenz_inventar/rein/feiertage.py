"""Gesetzliche Feiertage einer Region (rein, ohne Datenbank) — ein dünner Umschlag um das Paket `holidays`.

Die Region steht im Kern am Mandanten (`mandant.feiertagsregion`) und wird gelesen wie `fristen.feiertage()` der Belege:
`<Land>[-<Teil>]`. `DE` allein heißt die bundesweiten Feiertage, `DE-NI` Niedersachsen, ein anderes Land seine Tage; leer heißt keine Feiertage.
Land und Teil werden getrennt gelesen und so an das Paket gegeben, nie in ein eigenes Kürzel umgerechnet.

Das Paket ist auf `holidays==0.60` festgelegt (wie bei den Belegen); bei AP-K2 wandert nur dieser Umschlag in den Kern.
Regionale Feiertage, die nur in Teilen eines Landes gelten, trägt der Betrieb als eigene Tage ein.
"""
from __future__ import annotations

import warnings
from datetime import date

with warnings.catch_warnings():
    # `holidays` 0.x warnt beim Import vor der Version 1.0; wir haben die Version festgelegt (`==0.60`), wie es die Warnung empfiehlt
    warnings.filterwarnings("ignore", message=r"(?s).*future version incompatibility.*", category=Warning)
    import holidays

#: Die 16 Bundesländer als Teil hinter `DE-` (für die Prüffälle und die Anzeige)
LAENDER = ("BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH")


def region_teilen(region: str) -> tuple[str, str]:
    """`DE-NI` → (`DE`, `NI`); `DE` → (`DE`, ``); leer → (``, ``). Land und Teil großgeschrieben."""
    land, _, teil = (region or "").strip().upper().partition("-")
    return land.strip(), teil.strip()


def _paket(land: str, teil: str, jahre: list[int]) -> holidays.HolidayBase:
    try:
        return holidays.country_holidays(land, subdiv=teil or None, years=jahre, language="de")
    except NotImplementedError as ursache:
        raise ValueError("feiertage.region_unbekannt") from ursache
    except Exception:  # noqa: BLE001 - die Sprache gibt es für dieses Land nicht: Namen in der Landessprache des Pakets
        try:
            return holidays.country_holidays(land, subdiv=teil or None, years=jahre)
        except NotImplementedError as ursache:
            raise ValueError("feiertage.region_unbekannt") from ursache


def feiertage_benannt(jahr: int, region: str) -> dict[date, str]:
    """Feiertage des Jahres in der Region: Tag → Name (aus dem Paket). Leere Region: keine Feiertage."""
    land, teil = region_teilen(region)
    if not land:
        return {}
    gefunden = _paket(land, teil, [jahr])
    return {tag: str(name) for tag, name in sorted(gefunden.items())}


def feiertage(jahr: int, region: str) -> set[date]:
    """Die Feiertage des Jahres in der Region (leer = keine)."""
    return set(feiertage_benannt(jahr, region))


def feiertage_zwischen(von: date, bis: date, region: str) -> set[date]:
    """Feiertage im Zeitraum [von, bis] über die betroffenen Jahre."""
    if bis < von:
        return set()
    land, teil = region_teilen(region)
    if not land:
        return set()
    gefunden = _paket(land, teil, list(range(von.year, bis.year + 1)))
    return {tag for tag in gefunden if von <= tag <= bis}
