"""Der Modulprozess `erinnern` ohne Datenbank: Schleife, Fehlertoleranz, Beenden — Uhr und Schlaf sind eingehängt."""

from __future__ import annotations

import datetime as dt
import signal

from digiassistenz_inventar import erinnern
from digiassistenz_inventar.dienstlogik import erinnerungen
from digiassistenz_inventar.erinnern import Merker, Takt

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


class _Sitzung:
    """Eine Sitzung, die nichts kann außer gezählt zu werden (kein Zugriff auf die Datenbank)."""

    class kontext:
        mandant_id = 1

    db = object()


class _Fabrik:
    def __init__(self) -> None:
        self.geoeffnet = 0

    def __call__(self, _zweck: str):
        from contextlib import nullcontext

        self.geoeffnet += 1
        return nullcontext(_Sitzung())


def _einstellungen(monkeypatch, um: str, letzter: str = "") -> list[str]:
    gelesen: list[str] = []

    def lesen(_db, _mid, schluessel, standard=""):
        gelesen.append(schluessel)
        return {"erinnern_um": um, "erinnern_letzter_lauf": letzter}.get(schluessel, standard)

    monkeypatch.setattr(erinnern.katalog, "einstellung", lesen)
    monkeypatch.setattr(erinnern.erinnerungen, "tageslauf", lambda *_a, **_k: erinnerungen.Tageslauf(0, 0))
    return gelesen


def test_nachts_oeffnet_der_prozess_hoechstens_einmal_je_stunde_eine_sitzung(monkeypatch):
    """Kern-Regel: ein Prozess, der wartet, öffnet keine Sitzung — 00:00 bis 05:55 im Takt von 5 Minuten, Uhrzeit 06:00."""
    _einstellungen(monkeypatch, "06:00")
    fabrik, merker = _Fabrik(), Merker()
    nacht = dt.datetime(2026, 10, 10, 0, 0, tzinfo=dt.timezone.utc)
    for n in range(72):  # 00:00 … 05:55
        takt = erinnern.tick(nacht + dt.timedelta(minutes=5 * n), fabrik, merker)
        assert takt == Takt(None, False)
    assert fabrik.geoeffnet == 6, "ein Lesen je Stunde (vorher 72)"
    lauf = erinnern.tick(nacht + dt.timedelta(hours=6), fabrik, merker)
    assert lauf.erledigt and lauf.lauf is not None and fabrik.geoeffnet == 7


def test_eine_geaenderte_uhrzeit_gilt_spaetestens_nach_einer_stunde(monkeypatch):
    _einstellungen(monkeypatch, "06:00")
    fabrik, merker = _Fabrik(), Merker()
    start = dt.datetime(2026, 10, 10, 1, 0, tzinfo=dt.timezone.utc)
    erinnern.tick(start, fabrik, merker)
    assert merker.um == dt.time(6, 0)
    _einstellungen(monkeypatch, "03:00")
    assert erinnern.tick(start + dt.timedelta(minutes=30), fabrik, merker) == Takt(None, False) and fabrik.geoeffnet == 1
    spaeter = erinnern.tick(start + dt.timedelta(hours=2), fabrik, merker)  # 03:00 erreicht, die neue Uhrzeit wird gelesen
    assert merker.um == dt.time(3, 0) and spaeter.lauf is not None


def test_ohne_merker_wird_jedes_mal_gelesen(monkeypatch):
    _einstellungen(monkeypatch, "06:00")
    fabrik = _Fabrik()
    for n in range(3):
        erinnern.tick(dt.datetime(2026, 10, 10, 1, n, tzinfo=dt.timezone.utc), fabrik)
    assert fabrik.geoeffnet == 3


def test_die_schleife_nutzt_standardmaessig_den_merker(monkeypatch):
    _einstellungen(monkeypatch, "06:00")
    fabrik = _Fabrik()
    monkeypatch.setattr(erinnern.tick, "__defaults__", (fabrik, None))  # die Fabrik, die `laufen` über `tick` erreicht
    stand = {"n": 0}

    def uhr():
        stand["n"] += 1
        return dt.datetime(2026, 10, 10, 1, 0, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=5 * (stand["n"] - 1))

    n = erinnern.laufen(lambda: stand["n"] >= 13, uhr=uhr, schlafen=lambda _: None, takt=0.0, schritt=1.0)  # 01:00 bis 02:00
    assert n == 0 and fabrik.geoeffnet == 2, "zweimal gelesen (01:00 und 02:00), dazwischen nur die Uhr"


def test_der_prozess_schreibt_auch_auf_den_bildschirm(monkeypatch):
    """stdout ist das Log des Containers: `hochlaufen(leise=False)`."""
    aufrufe: list[dict] = []
    monkeypatch.setattr(erinnern.hochlauf, "hochlaufen", lambda *a, **k: aufrufe.append(k))
    monkeypatch.setattr(erinnern, "laufen", lambda _anhalten: 0)
    alt = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGINT)}
    try:
        assert erinnern.main() == 0
    finally:
        for nummer, handler in alt.items():
            signal.signal(nummer, handler)
    assert aufrufe == [{"leise": False}]
