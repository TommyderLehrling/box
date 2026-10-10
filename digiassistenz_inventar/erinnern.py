"""Modulprozess `python -m digiassistenz_inventar.erinnern` — vom Kern neben dem Webserver gestartet und überwacht.

Der Prozess läuft dauerhaft und arbeitet **einmal täglich** (Einstellung `erinnern_um`, Ortszeit, Standard 06:00): überfällige
Transfers und fällige Prüfungen werden als Mail eingereiht (siehe `dienstlogik.erinnerungen.tageslauf`). Sonst schläft er in
kurzen Schritten, damit ein SIGTERM sauber beendet. Uhr und Schlaf sind einhängbar, damit die Prüffälle nicht warten müssen.
Ein Fehler im Lauf beendet den Prozess nicht (fällt er, fällt der Container): er steht im Log, der nächste Takt versucht es neu.
"""

from __future__ import annotations

import datetime as dt
import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass
from contextlib import AbstractContextManager
from typing import Any

from digiassistenz_kern import hochlauf, zeit
from digiassistenz_kern.sitzung import einzelmandant

from .dienstlogik import erinnerungen, katalog
from .rein import zeitplan

_log = logging.getLogger(__name__)

#: Wie oft die Uhr gegen die Einstellung geprüft wird (Sekunden) und in welchen Schritten geschlafen wird
TAKT = 300.0
SCHRITT = 1.0

SitzungsFabrik = Callable[[str], AbstractContextManager[Any]]


@dataclass(frozen=True)
class Takt:
    """Ergebnis einer Prüfung: lief der Tageslauf jetzt, und ist für diesen Tag nichts mehr zu tun?"""

    lauf: erinnerungen.Tageslauf | None
    erledigt: bool


def tick(jetzt: dt.datetime, sitzung_oeffnen: SitzungsFabrik = einzelmandant) -> Takt:
    """Eine Prüfung: ist der Lauf des Tages dran, wird er gefahren (und committet, wenn die Sitzung endet)."""
    with sitzung_oeffnen("inventar.erinnern") as sitzung:
        mid = sitzung.kontext.mandant_id
        um = zeitplan.uhrzeit_oder_standard(katalog.einstellung(sitzung.db, mid, erinnerungen.EINSTELLUNG_UM, zeitplan.STANDARD_UHRZEIT))
        letzter = zeitplan.tag_lesen(katalog.einstellung(sitzung.db, mid, erinnerungen.EINSTELLUNG_LETZTER))
        if letzter == jetzt.date():
            return Takt(None, True)
        if not zeitplan.ist_dran(jetzt, um, letzter):
            return Takt(None, False)
        return Takt(erinnerungen.tageslauf(sitzung.db, mid, jetzt.date()), True)


def laufen(
    anhalten: Callable[[], bool], uhr: Callable[[], dt.datetime] = zeit.jetzt_ortszeit, schlafen: Callable[[float], None] = time.sleep,
    lauf: Callable[[dt.datetime], Takt] = tick, takt: float = TAKT, schritt: float = SCHRITT,
) -> int:
    """Die Schleife bis `anhalten()`; liefert die Zahl der gefahrenen Tagesläufe. `lauf` ist die Prüfung je Takt (hier einhängbar).

    Ist der Tag erledigt, wird bis zum nächsten Datum nicht mehr in die Datenbank geschaut.
    """
    laeufe = 0
    erledigt_am: dt.date | None = None
    while not anhalten():
        jetzt = uhr()
        if erledigt_am != jetzt.date():
            try:
                ergebnis = lauf(jetzt)
            except Exception:  # der Prozess darf nicht fallen; der nächste Takt versucht es noch einmal
                _log.exception("inventar.erinnern_fehler")
            else:
                if ergebnis.erledigt:
                    erledigt_am = jetzt.date()
                if ergebnis.lauf is not None:
                    laeufe += 1
                    _log.info("inventar.erinnern_lauf transfers=%s pruefungen=%s", ergebnis.lauf.transfers, ergebnis.lauf.pruefungen)
        gewartet = 0.0
        while gewartet < takt and not anhalten():
            schlafen(schritt)
            gewartet += schritt
    return laeufe


def _signale() -> Callable[[], bool]:
    halt = {"ja": False}

    def beenden(_nummer: int, _rahmen: object) -> None:
        halt["ja"] = True

    for nummer in (signal.SIGTERM, signal.SIGINT):
        signal.signal(nummer, beenden)
    return lambda: halt["ja"]


def main() -> int:
    hochlauf.hochlaufen(leise=True)
    _log.info("inventar.erinnern_start")
    laufen(_signale())
    _log.info("inventar.erinnern_ende")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
