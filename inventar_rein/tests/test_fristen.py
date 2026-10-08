"""Prueffaelle fuer fristen (F1-F12)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from inventar_rein.fristen import (
    ampel,
    faellig_nach_zaehler,
    naechste_faelligkeit,
    naechste_nach_zaehler,
    tage_bis,
    werktage_addieren,
    werktage_zwischen,
)


def test_F1_monatsarithmetik_beispiele_aus_dem_auftrag():
    assert naechste_faelligkeit(date(2026, 3, 15), 12) == date(2027, 3, 15)
    assert naechste_faelligkeit(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert naechste_faelligkeit(date(2028, 2, 29), 12) == date(2029, 2, 28)


def test_F2_monatsarithmetik_weitere_faelle():
    assert naechste_faelligkeit(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert naechste_faelligkeit(date(2027, 12, 15), 1) == date(2028, 1, 15)
    assert naechste_faelligkeit(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert naechste_faelligkeit(date(2026, 4, 30), 1) == date(2026, 5, 30)
    assert naechste_faelligkeit(date(2026, 3, 15), 60) == date(2031, 3, 15)


def test_F3_intervall_muss_mindestens_ein_monat_sein():
    with pytest.raises(ValueError):
        naechste_faelligkeit(date(2026, 3, 15), 0)


def test_F4_ampel_grenzen():
    faellig = date(2026, 6, 30)
    assert ampel(faellig, date(2026, 5, 1)) == "gruen"  # 60 Tage
    assert ampel(faellig, date(2026, 5, 31)) == "gelb"  # 30 Tage, Grenze gehoert zu gelb
    assert ampel(faellig, date(2026, 5, 30)) == "gruen"  # 31 Tage
    assert ampel(faellig, date(2026, 6, 29)) == "gelb"  # 1 Tag
    assert ampel(faellig, date(2026, 7, 1)) == "rot"


def test_F5_ampel_am_tag_der_faelligkeit_ist_rot():
    assert ampel(date(2026, 6, 30), date(2026, 6, 30)) == "rot"


def test_F6_gelb_ab_tagen_null_ist_nie_gelb():
    faellig = date(2026, 6, 30)
    assert ampel(faellig, date(2026, 6, 29), gelb_ab_tagen=0) == "gruen"
    assert ampel(faellig, date(2026, 6, 30), gelb_ab_tagen=0) == "rot"
    with pytest.raises(ValueError):
        ampel(faellig, date(2026, 6, 1), gelb_ab_tagen=-1)


def test_F7_tage_bis_negativ_wenn_ueberfaellig():
    assert tage_bis(date(2026, 6, 30), date(2026, 6, 20)) == 10
    assert tage_bis(date(2026, 6, 30), date(2026, 6, 30)) == 0
    assert tage_bis(date(2026, 6, 30), date(2026, 7, 3)) == -3


def test_F8_zaehlerfaelligkeit():
    assert not faellig_nach_zaehler(Decimal("1000"), Decimal("1499.9"), 500)
    assert faellig_nach_zaehler(Decimal("1000"), Decimal("1500"), 500)
    assert faellig_nach_zaehler(Decimal("1000"), Decimal("1700.5"), 500)
    assert not faellig_nach_zaehler(Decimal("1000"), Decimal("900"), 500)  # Zaehler zurueck
    with pytest.raises(ValueError):
        faellig_nach_zaehler(Decimal("0"), Decimal("1"), 0)


def test_F9_naechster_zaehlerstand():
    assert naechste_nach_zaehler(Decimal("1234.5"), 500) == Decimal("1734.5")
    with pytest.raises(ValueError):
        naechste_nach_zaehler(Decimal("0"), 0)


def test_F10_werktage_ueber_ein_wochenende():
    donnerstag, freitag, montag, dienstag = (date(2026, 10, d) for d in (8, 9, 12, 13))
    assert werktage_zwischen(donnerstag, freitag) == 1
    assert werktage_zwischen(donnerstag, montag) == 2  # von exklusiv, bis inklusiv
    assert werktage_zwischen(donnerstag, dienstag) == 3
    assert werktage_zwischen(freitag, date(2026, 10, 11)) == 0  # nur Wochenende
    assert werktage_zwischen(donnerstag, donnerstag) == 0
    assert werktage_zwischen(dienstag, donnerstag) == 0  # bis vor von


def test_F11_werktage_ueber_einen_feiertag():
    donnerstag, montag = date(2026, 4, 30), date(2026, 5, 4)
    maifeiertag = [date(2026, 5, 1)]  # Freitag
    assert werktage_zwischen(donnerstag, montag) == 2
    assert werktage_zwischen(donnerstag, montag, maifeiertag) == 1
    assert werktage_zwischen(donnerstag, montag, iter(maifeiertag)) == 1
    assert werktage_zwischen(donnerstag, montag, [date(2026, 5, 2)]) == 2  # Samstag zaehlt eh nicht


def test_F12_werktage_addieren():
    donnerstag = date(2026, 10, 8)
    assert werktage_addieren(donnerstag, 0) == donnerstag
    assert werktage_addieren(donnerstag, 1) == date(2026, 10, 9)
    assert werktage_addieren(donnerstag, 2) == date(2026, 10, 12)
    assert werktage_addieren(donnerstag, 3) == date(2026, 10, 13)
    assert werktage_addieren(donnerstag, 3, [date(2026, 10, 9)]) == date(2026, 10, 14)
    assert werktage_addieren(date(2026, 10, 10), 1) == date(2026, 10, 12)  # Start am Samstag
    for anzahl in range(0, 12):  # Gegenprobe zu werktage_zwischen
        ziel = werktage_addieren(donnerstag, anzahl, [date(2026, 10, 9)])
        assert werktage_zwischen(donnerstag, ziel, [date(2026, 10, 9)]) == anzahl
    with pytest.raises(ValueError):
        werktage_addieren(donnerstag, -1)
