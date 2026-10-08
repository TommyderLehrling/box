"""Prueffaelle fuer werkstatt (W1-W11)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal as D

import pytest

from inventar_rein.werkstatt import (
    kosten_belegen,
    meldung_weiter,
    neue_meldung,
    neue_reparatur,
    reparatur_abschliessen,
    reparatur_beginnen,
    reparatur_zurueckziehen,
    reparaturkosten,
    status_folge,
)

JETZT = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)
SPAETER = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)


def test_W1_neue_meldung():
    m = neue_meldung("schaden", " Hydraulikschlauch undicht ", "paul", JETZT)
    assert (m.status, m.art, m.beschreibung, m.gemeldet_von) == ("offen", "schaden", "Hydraulikschlauch undicht", "paul")
    for art, text, person in (("kaputt", "x", "p"), ("schaden", " ", "p"), ("schaden", "x", " ")):
        with pytest.raises(ValueError):
            neue_meldung(art, text, person, JETZT)
    with pytest.raises(ValueError, match="zeit_naiv"):
        neue_meldung("schaden", "x", "p", datetime(2026, 10, 8))


def test_W2_meldung_ablauf_bis_erledigt():
    m = neue_meldung("reparatur", "Motor stottert", "paul", JETZT)
    m = meldung_weiter(m, "angenommen", "werner", JETZT)
    assert (m.status, m.bearbeitet_von) == ("angenommen", "werner")
    m = meldung_weiter(m, "in_arbeit", "werner", JETZT)
    m = meldung_weiter(m, "erledigt", "werner", SPAETER, rueckmeldung="Zuendkerze getauscht")
    assert (m.status, m.erledigt_am, m.rueckmeldung) == ("erledigt", SPAETER, "Zuendkerze getauscht")


def test_W3_erledigt_braucht_rueckmeldung_zurueckziehen_braucht_grund():
    m = meldung_weiter(neue_meldung("wartung", "Oelwechsel", "paul", JETZT), "angenommen", "werner", JETZT)
    with pytest.raises(ValueError, match="rueckmeldung_fehlt"):
        meldung_weiter(m, "erledigt", "werner", SPAETER)
    with pytest.raises(ValueError, match="grund_fehlt"):
        meldung_weiter(m, "zurueckgezogen", "paul", SPAETER)
    assert meldung_weiter(m, "zurueckgezogen", "paul", SPAETER, grund="doppelt gemeldet").grund == "doppelt gemeldet"


def test_W4_unzulaessige_meldungswechsel_und_endzustaende():
    m = neue_meldung("schaden", "x", "paul", JETZT)
    with pytest.raises(ValueError, match="wechsel_nicht_erlaubt"):
        meldung_weiter(m, "erledigt", "werner", JETZT, rueckmeldung="ok")  # erst annehmen
    with pytest.raises(ValueError, match="status_unbekannt"):
        meldung_weiter(m, "fertig", "werner", JETZT)
    fertig = meldung_weiter(meldung_weiter(m, "angenommen", "w", JETZT), "erledigt", "w", JETZT, rueckmeldung="ok")
    for neu in ("offen", "angenommen", "in_arbeit", "zurueckgezogen"):
        with pytest.raises(ValueError, match="wechsel_nicht_erlaubt"):
            meldung_weiter(fertig, neu, "w", JETZT, grund="g")


def test_W5_reparatur_ablauf():
    r = neue_reparatur("intern")
    assert r.status == "offen"
    r = reparatur_beginnen(r, date(2026, 10, 8), D("350"))
    assert (r.status, r.begonnen_am, r.kosten, r.kosten_quelle) == ("in_arbeit", date(2026, 10, 8), D("350"), "geschaetzt")
    r = reparatur_abschliessen(r, date(2026, 10, 10), D("412.50"), "geschaetzt")
    assert (r.status, r.beendet_am, r.kosten) == ("erledigt", date(2026, 10, 10), D("412.50"))


def test_W6_beleg_ersetzt_schaetzung_nur_nach_abschluss():
    r = reparatur_abschliessen(reparatur_beginnen(neue_reparatur("extern"), date(2026, 10, 1)), date(2026, 10, 2), D("500"))
    belegt = kosten_belegen(r, D("487.30"))
    assert (belegt.kosten, belegt.kosten_quelle) == (D("487.30"), "beleg")
    with pytest.raises(ValueError, match="wechsel_nicht_erlaubt"):
        kosten_belegen(neue_reparatur("intern"), D("1"))


def test_W7_reparatur_pruefungen():
    r = neue_reparatur("intern")
    with pytest.raises(ValueError):
        neue_reparatur("fremd")
    with pytest.raises(ValueError, match="wechsel_nicht_erlaubt"):
        reparatur_abschliessen(r, date(2026, 10, 8), D("1"))
    laufend = reparatur_beginnen(r, date(2026, 10, 8))
    assert laufend.kosten is None and laufend.kosten_quelle is None
    with pytest.raises(ValueError, match="ende_vor_beginn"):
        reparatur_abschliessen(laufend, date(2026, 10, 7), D("1"))
    with pytest.raises(ValueError, match="kosten_ungueltig"):
        reparatur_abschliessen(laufend, date(2026, 10, 9), D("-1"))
    with pytest.raises(ValueError, match="kostenquelle_unbekannt"):
        reparatur_abschliessen(laufend, date(2026, 10, 9), D("1"), "raten")
    with pytest.raises(ValueError, match="kosten_ungueltig"):
        reparatur_beginnen(r, date(2026, 10, 8), D("-5"))
    with pytest.raises(ValueError, match="wechsel_nicht_erlaubt"):
        reparatur_beginnen(laufend, date(2026, 10, 9))


def test_W8_reparatur_zurueckziehen_mit_grund():
    r = neue_reparatur("intern")
    with pytest.raises(ValueError, match="grund_fehlt"):
        reparatur_zurueckziehen(r, " ")
    z = reparatur_zurueckziehen(reparatur_beginnen(r, date(2026, 10, 8)), "Schaden war keiner")
    assert (z.status, z.grund) == ("zurueckgezogen", "Schaden war keiner")
    fertig = reparatur_abschliessen(reparatur_beginnen(r, date(2026, 10, 8)), date(2026, 10, 8), D("0"))
    with pytest.raises(ValueError, match="wechsel_nicht_erlaubt"):
        reparatur_zurueckziehen(fertig, "zu spaet")


def test_W9_status_folge_fuer_das_stueck():
    assert status_folge("aktiv", 1) == "in_reparatur"
    assert status_folge("in_reparatur", 1) is None  # noch eine laeuft
    assert status_folge("in_reparatur", 0) == "aktiv"
    assert status_folge("aktiv", 0) is None
    assert status_folge("vermisst", 2) is None and status_folge("stillgelegt", 0) is None
    with pytest.raises(ValueError, match="anzahl_ungueltig"):
        status_folge("aktiv", -1)


def test_W10_reparaturkosten_getrennt_nach_quelle():
    def erledigt(kosten: str, quelle: str):
        r = reparatur_beginnen(neue_reparatur("extern"), date(2026, 1, 1))
        return reparatur_abschliessen(r, date(2026, 1, 2), D(kosten), quelle)
    laufend = reparatur_beginnen(neue_reparatur("intern"), date(2026, 1, 1), D("999"))
    liste = [erledigt("100.005", "beleg"), erledigt("50", "geschaetzt"), erledigt("20.50", "beleg"), laufend,
             reparatur_zurueckziehen(neue_reparatur("intern"), "x")]
    assert reparaturkosten(liste) == (D("120.51"), D("50.00"))
    assert reparaturkosten([]) == (D("0.00"), D("0.00"))


def test_W11_eingabe_bleibt_unveraendert():
    m = neue_meldung("schaden", "x", "paul", JETZT)
    meldung_weiter(m, "angenommen", "w", JETZT)
    assert m.status == "offen"
