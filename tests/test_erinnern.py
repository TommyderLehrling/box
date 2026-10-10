"""Der Modulprozess `erinnern` ohne Datenbank: Schleife, Fehlertoleranz, Beenden — Uhr und Schlaf sind eingehängt."""

from __future__ import annotations

import datetime as dt
import signal

from digiassistenz_inventar import erinnern
from digiassistenz_inventar.dienstlogik import erinnerungen
from digiassistenz_inventar.erinnern import Takt

UHR = dt.datetime(2026, 10, 10, 6, 0, tzinfo=dt.timezone.utc)


class Halter:
    """`anhalten()` sagt nach n Abfragen ja."""

    def __init__(self, n: int) -> None:
        self.rest = n

    def __call__(self) -> bool:
        self.rest -= 1
        return self.rest < 0


def test_die_schleife_ruft_den_lauf_je_takt_und_zaehlt_die_tageslaeufe():
    gerufen, geschlafen = [], []
    ergebnisse = iter([Takt(None, False), Takt(erinnerungen.Tageslauf(2, 1), True), Takt(None, False)])

    def lauf(jetzt):
        gerufen.append(jetzt)
        return next(ergebnisse)

    # derselbe Tag: nach dem erledigten Tag wird nicht mehr nachgesehen
    n = erinnern.laufen(lambda: len(gerufen) >= 2, uhr=lambda: UHR, schlafen=geschlafen.append, lauf=lauf, takt=3.0, schritt=1.0)
    assert n == 1 and len(gerufen) == 2 and all(g == UHR for g in gerufen)
    assert set(geschlafen) == {1.0}, "geschlafen wird in kurzen Schritten, nicht am Stück"


def test_ist_der_tag_erledigt_schaut_die_schleife_bis_zum_naechsten_datum_nicht_mehr_nach():
    zeiten = [UHR, UHR + dt.timedelta(hours=1), UHR + dt.timedelta(days=1), UHR + dt.timedelta(days=1, hours=1)]
    uhrstand = {"n": 0}
    gerufen = []

    def uhr():
        i = min(uhrstand["n"], len(zeiten) - 1)
        uhrstand["n"] += 1
        return zeiten[i]

    def lauf(jetzt):
        gerufen.append(jetzt)
        return Takt(erinnerungen.Tageslauf(0, 0), True)

    n = erinnern.laufen(lambda: uhrstand["n"] >= 4, uhr=uhr, schlafen=lambda _: None, lauf=lauf, takt=1.0, schritt=1.0)
    assert [g.date() for g in gerufen] == [UHR.date(), (UHR + dt.timedelta(days=1)).date()] and n == 2


def test_ein_fehler_im_lauf_beendet_den_prozess_nicht(caplog):
    zaehler = {"n": 0}

    def lauf(_):
        zaehler["n"] += 1
        if zaehler["n"] == 1:
            raise RuntimeError("Datenbank weg")
        return Takt(erinnerungen.Tageslauf(0, 0), True)

    n = erinnern.laufen(Halter(20), uhr=lambda: UHR, schlafen=lambda _: None, lauf=lauf, takt=2.0, schritt=1.0)
    assert n == 1 and zaehler["n"] == 2, "nach dem Fehler beim nächsten Takt noch einmal, danach ist der Tag erledigt"
    assert "inventar.erinnern_fehler" in caplog.text


def test_sigterm_beendet_die_schleife_sauber():
    alt = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGINT)}
    try:
        halt = erinnern._signale()
        assert halt() is False
        signal.raise_signal(signal.SIGTERM)
        assert halt() is True
        n = erinnern.laufen(halt, uhr=lambda: UHR, schlafen=lambda _: None, lauf=lambda _: Takt(None, False))
        assert n == 0
    finally:
        for nummer, handler in alt.items():
            signal.signal(nummer, handler)


def test_der_kern_startet_den_prozess_ueber_die_modulbeschreibung():
    from digiassistenz_inventar.modul import BESCHREIBUNG

    assert BESCHREIBUNG.prozesse == ("digiassistenz_inventar.erinnern",)
    assert callable(erinnern.main)
