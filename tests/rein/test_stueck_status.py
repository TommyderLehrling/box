"""Prueffaelle fuer stueck_status (S1-S8)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from digiassistenz_inventar.rein.stueck_status import ALLE, ENDZUSTAENDE, buchbar, hinweis, im_bestand, ist_endzustand, wechsle

JETZT = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)


def test_S1_sechs_status_und_drei_endzustaende():
    assert set(ALLE) == {"aktiv", "in_reparatur", "vermisst", "stillgelegt", "verkauft", "verschrottet"}
    assert set(ENDZUSTAENDE) == {"stillgelegt", "verkauft", "verschrottet"}
    assert [ist_endzustand(s) for s in ALLE] == [False, False, False, True, True, True]


def test_S2_buchbar_und_im_bestand():
    assert [buchbar(s) for s in ALLE] == [True, True, True, False, False, False]  # in Reparatur und vermisst bleiben buchbar
    assert [im_bestand(s) for s in ALLE] == [buchbar(s) for s in ALLE]
    with pytest.raises(ValueError, match="unbekannt"):
        buchbar("kaputt")


def test_S3_hinweise_nur_fuer_reparatur_und_vermisst():
    assert hinweis("aktiv") == "" and hinweis("verkauft") == ""
    assert hinweis("in_reparatur") == "stueck_status.hinweis_in_reparatur"
    assert hinweis("vermisst") == "stueck_status.hinweis_vermisst"


def test_S4_aktiv_und_reparatur_ohne_grund():
    w = wechsle("aktiv", "in_reparatur", "", "werner", JETZT)
    assert (w.von, w.nach, w.grund, w.protokoll) == ("aktiv", "in_reparatur", "", "stueck_status.in_reparatur")
    assert wechsle("in_reparatur", "aktiv", "", "werner", JETZT).nach == "aktiv"


def test_S5_vermisst_und_endzustaende_brauchen_einen_grund():
    for neu in ("vermisst", "stillgelegt", "verkauft", "verschrottet"):
        with pytest.raises(ValueError, match="grund_fehlt"):
            wechsle("aktiv", neu, "  ", "werner", JETZT)
        assert wechsle("aktiv", neu, " Inventur ", "werner", JETZT).grund == "Inventur"


def test_S6_rueckkehr_aus_endzustand_nur_mit_grund():
    with pytest.raises(ValueError, match="grund_fehlt"):
        wechsle("stillgelegt", "aktiv", "", "werner", JETZT)
    assert wechsle("stillgelegt", "aktiv", "Irrtum", "werner", JETZT).nach == "aktiv"
    assert wechsle("vermisst", "aktiv", "", "werner", JETZT).nach == "aktiv"  # wieder aufgetaucht: kein Grund noetig
    assert wechsle("vermisst", "verschrottet", "nie gefunden", "werner", JETZT).nach == "verschrottet"


def test_S7_unzulaessige_wechsel():
    with pytest.raises(ValueError, match="unveraendert"):
        wechsle("aktiv", "aktiv", "", "werner", JETZT)
    with pytest.raises(ValueError, match="wechsel_nicht_erlaubt"):
        wechsle("verkauft", "verschrottet", "x", "werner", JETZT)
    assert wechsle("stillgelegt", "verkauft", "verkauft an Dritte", "werner", JETZT).nach == "verkauft"


def test_S8_eingabe_wird_geprueft():
    with pytest.raises(ValueError, match="zeit_naiv"):
        wechsle("aktiv", "vermisst", "x", "werner", datetime(2026, 10, 8))
    with pytest.raises(ValueError, match="person_fehlt"):
        wechsle("aktiv", "vermisst", "x", " ", JETZT)
    with pytest.raises(ValueError, match="unbekannt"):
        wechsle("aktiv", "gestohlen", "x", "werner", JETZT)
