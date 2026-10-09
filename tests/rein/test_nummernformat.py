"""Prueffaelle fuer nummernformat (N1-N12)."""
from __future__ import annotations

import pytest

from digiassistenz_inventar.rein.nummernformat import (
    Muster,
    entspricht,
    naechste,
    normalisiere,
    pruefe_muster,
    zaehler_schluessel,
)


def test_N1_beispiel_nur_nummer():
    nummer, stand = naechste(Muster("{nr:5}"), {}, 2026, None)
    assert nummer == "00001"
    assert stand == {"": 1}


def test_N2_beispiel_mit_jahr():
    assert naechste(Muster("G-{jahr}-{nr:4}"), {}, 2026, None)[0] == "G-2026-0001"


def test_N3_beispiel_mit_gruppe():
    nummer, stand = naechste(Muster("{gruppe}-{nr:5}"), {"BM": 16}, 2026, "BM")
    assert nummer == "BM-00017"
    assert stand == {"BM": 17}


def test_N4_beispiel_nr_ohne_praefix_und_jahr2():
    assert naechste(Muster("{jahr2}/{gruppe}/{nr:3}"), {}, 2026, "FZ")[0] == "26/FZ/001"
    assert naechste(Muster("{nr:5}"), {"": 41}, 2026, None)[0] == "00042"


def test_N5_ueberlauf_wird_laenger():
    nummer, stand = naechste(Muster("{nr:3}"), {"": 999}, 2026, None)
    assert nummer == "1000"
    assert stand == {"": 1000}
    assert entspricht(Muster("{nr:3}"), "1000")


def test_N6_zaehler_schluessel_alle_vier_formen():
    assert zaehler_schluessel(Muster("{nr:5}"), 2026, "BM") == ""
    assert zaehler_schluessel(Muster("{jahr}-{nr:4}"), 2026, "BM") == "2026"
    assert zaehler_schluessel(Muster("{jahr2}-{nr:4}"), 2026, None) == "2026"
    assert zaehler_schluessel(Muster("{gruppe}-{nr:5}"), 2026, "BM") == "BM"
    assert zaehler_schluessel(Muster("{jahr}/{gruppe}/{nr:5}"), 2026, "BM") == "2026/BM"


def test_N7_zaehler_laufen_getrennt_und_eingabe_bleibt_unberuehrt():
    muster = Muster("{gruppe}-{jahr2}-{nr:3}")
    start: dict[str, int] = {}
    a, s1 = naechste(muster, start, 2026, "BM")
    b, s2 = naechste(muster, s1, 2026, "FZ")
    c, s3 = naechste(muster, s2, 2026, "BM")
    d, s4 = naechste(muster, s3, 2027, "BM")
    assert (a, b, c, d) == ("BM-26-001", "FZ-26-001", "BM-26-002", "BM-27-001")
    assert start == {} and s1 == {"2026/BM": 1}
    assert s4 == {"2026/BM": 2, "2026/FZ": 1, "2027/BM": 1}


def test_N8_gruppe_im_muster_ohne_gruppe_ist_fehler():
    with pytest.raises(ValueError, match="nummernformat.gruppe_fehlt"):
        naechste(Muster("{gruppe}-{nr:5}"), {}, 2026, None)
    with pytest.raises(ValueError, match="nummernformat.gruppe_ungueltig"):
        naechste(Muster("{gruppe}-{nr:5}"), {}, 2026, "bm")
    with pytest.raises(ValueError, match="nummernformat.jahr_ungueltig"):
        naechste(Muster("{jahr}-{nr:5}"), {}, 26, None)
    with pytest.raises(ValueError, match="nummernformat.zaehler_ungueltig"):
        naechste(Muster("{nr:5}"), {"": -1}, 2026, None)


def test_N9_pruefe_muster_meldet_fehler():
    assert pruefe_muster("{gruppe}-{nr:5}") == []
    assert pruefe_muster("G-{jahr}-{nr:4}") == []
    assert "muster.nr_fehlt" in pruefe_muster("G-{jahr}")
    assert "muster.nr_fehlt" in pruefe_muster("")
    assert "muster.nr_doppelt" in pruefe_muster("{nr:3}-{nr:3}")
    assert "muster.platzhalter_unbekannt:monat" in pruefe_muster("{monat}-{nr:3}")
    assert "muster.nr_breite_fehlt" in pruefe_muster("{nr}")
    assert "muster.nr_breite_ungueltig" in pruefe_muster("{nr:0}")
    assert "muster.nr_breite_ungueltig" in pruefe_muster("{nr:05}")
    assert "muster.nr_breite_ungueltig" in pruefe_muster("{nr:13}")
    assert "muster.klammer_unpaarig" in pruefe_muster("{nr:3}}")
    with pytest.raises(ValueError):
        naechste(Muster("{monat}-{nr:3}"), {}, 2026, None)


def test_N10_entspricht_passende_und_falsche_nummern():
    muster = Muster("{gruppe}-{nr:5}")
    assert entspricht(muster, "BM-00017")
    assert not entspricht(muster, "BM-0017")  # falsche Breite (zu kurz)
    assert not entspricht(muster, "BM-000017")  # fuehrende Null bei Ueberbreite
    assert entspricht(muster, "BM-100000")
    assert not entspricht(muster, "bm-00017")
    assert not entspricht(muster, "BMX-00017")
    assert not entspricht(muster, " BM-00017")
    jahr = Muster("G-{jahr}-{nr:4}")
    assert entspricht(jahr, "G-2026-0001")
    assert not entspricht(jahr, "G-26-0001")
    assert not entspricht(jahr, "G-2026-0001x")
    assert entspricht(Muster("{jahr2}/{nr:3}"), "26/001")
    assert not entspricht(Muster("A.{nr:2}"), "AX01")  # Punkt ist Text, kein Joker


def test_N11_normalisiere():
    assert normalisiere(" bm-00017 ") == "BM-00017"
    assert normalisiere("bm   00017") == "BM 00017"
    assert normalisiere("\tg ä -1\n") == "G Ä -1"
    assert normalisiere("straße") == "STRAßE"
    assert normalisiere("   ") == ""


def test_N12_normalisiert_passt_dann_zum_muster():
    muster = Muster("{gruppe}-{nr:5}")
    assert entspricht(muster, normalisiere(" bm-00017 "))
