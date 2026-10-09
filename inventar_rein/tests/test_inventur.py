"""Prueffaelle fuer inventur (V1-V7)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from inventar_rein.inventur import Erwartet, Fehlt, Gesehen, Woanders, auswerten

T = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)


def e(nr: str, ks: int, menge: int = 1, status: str = "aktiv") -> Erwartet:
    return Erwartet(nr, ks, menge, status)


def g(nr: str, ks: int, menge: int = 1) -> Gesehen:
    return Gesehen(nr, ks, menge, T)


def test_V1_gefunden_und_nicht_gesehen_wird_als_vermisst_vorgeschlagen():
    erg = auswerten([e("A", 100), e("B", 100), e("C", 100)], [g("A", 100), g("B", 100)], [100])
    assert erg.gefunden == ("A", "B") and erg.vermisst_vorschlag == ("C",)
    assert erg.fehlmengen == (Fehlt("C", 100, 1, 0),)


def test_V2_gesehen_auf_anderer_kostenstelle_ist_nicht_vermisst():
    erg = auswerten([e("A", 100)], [g("A", 200)], [100, 200])
    assert erg.woanders == (Woanders("A", 100, 200),) and erg.vermisst_vorschlag == () and erg.gefunden == ()


def test_V3_nur_der_umfang_zaehlt():
    erg = auswerten([e("A", 100), e("B", 200)], [g("A", 100)], [100])
    assert erg.gefunden == ("A",) and erg.vermisst_vorschlag == ()  # B liegt auf 200, das nicht inventarisiert wurde
    with pytest.raises(ValueError, match="gesehen_ausserhalb_umfang"):
        auswerten([e("A", 100)], [g("A", 300)], [100])


def test_V4_mengenartikel_fehlmenge_ist_kein_vermisst():
    erg = auswerten([e("S", 100, 40)], [g("S", 100, 25), g("S", 100, 5)], [100])
    assert erg.fehlmengen == (Fehlt("S", 100, 40, 30),) and erg.vermisst_vorschlag == () and erg.gefunden == ()
    voll = auswerten([e("S", 100, 40)], [g("S", 100, 40)], [100])
    assert voll.gefunden == ("S",) and voll.fehlmengen == ()
    mehr = auswerten([e("S", 100, 40)], [g("S", 100, 45)], [100])
    assert mehr.gefunden == ("S",)


def test_V5_mengenartikel_auf_zwei_kostenstellen():
    erg = auswerten([e("S", 100, 30), e("S", 200, 10)], [g("S", 100, 30)], [100, 200])
    assert erg.gefunden == ("S",) and erg.fehlmengen == (Fehlt("S", 200, 10, 0),) and erg.vermisst_vorschlag == ()


def test_V6_vermisste_endzustaende_und_unbekannte():
    erwartet = [e("V", 100, status="vermisst"), e("W", 100, status="verkauft"), e("X", 100, status="in_reparatur"), e("Y", 100, status="vermisst")]
    erg = auswerten(erwartet, [g("V", 100), g("Z", 100)], [100])
    assert erg.wieder_aufgetaucht == ("V",)
    assert erg.vermisst_vorschlag == ("X",)  # Y ist schon vermisst, W ausser Betrieb
    assert erg.unbekannt == ("Z",)


def test_V7_leere_eingabe_und_ungueltige_menge():
    erg = auswerten([], [], [100])
    assert erg.gefunden == () and erg.vermisst_vorschlag == () and erg.unbekannt == ()
    with pytest.raises(ValueError, match="menge_ungueltig"):
        auswerten([e("A", 100)], [g("A", 100, 0)], [100])


def test_V8_mehr_gesehen_ist_ein_hinweis_ohne_buchung():
    erg = auswerten([e("S", 100, 40), e("T", 100, 5)], [g("S", 100, 45), g("T", 100, 5)], [100])
    assert erg.gefunden == ("S", "T") and erg.fehlmengen == () and erg.vermisst_vorschlag == ()
    assert [(m.inventarnummer, m.erwartet, m.gesehen, m.differenz) for m in erg.mehr_gesehen] == [("S", 40, 45, 5)]
