"""Prueffaelle fuer kosten (C1-C14)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from inventar_rein.kosten import (
    Kostenparameter,
    Vorhaltung,
    gesamtkosten,
    kalkulatorisch_bis,
    kostensatz,
    miete_vs_eigen,
    restbuchwert_kalk,
    vorhaltung,
)
from inventar_rein.transfer import Standort

ZONE = timezone(timedelta(hours=2))
BAGGER = Kostenparameter(D("150000.00"), D("15000.00"), 96, D("4.0"), D("12.0"))


def tag(monat: int, t: int, stunde: int = 8) -> datetime:
    return datetime(2026, monat, t, stunde, 0, tzinfo=ZONE)


def standort(ks: int, von: datetime, bis: datetime | None, menge: int = 1) -> Standort:
    return Standort("BM-00017", ks, menge, von, bis, None, "web", "anna")


def test_bagger():
    s = kostensatz(BAGGER)
    assert s.abschreibung_monat == D("1406.25")
    assert s.zins_monat == D("250.00")
    assert s.reparatur_monat == D("1500.00")
    assert s.satz_monat == D("3156.25")
    assert s.satz_tag == D("105.21")
    assert s.satz_woche == D("736.46")  # aus dem ungerundeten Tagessatz, nicht 105,21 x 7


def test_C1_restwert_null():
    s = kostensatz(Kostenparameter(D("150000"), D("0"), 96, D("4"), D("12")))
    assert s.abschreibung_monat == D("1562.50")
    assert s.satz_monat == D("3312.50")


def test_C2_nutzungsdauer_ein_monat():
    p = Kostenparameter(D("1200"), D("200"), 1, D("0"), D("0"))
    s = kostensatz(p)
    assert (s.abschreibung_monat, s.zins_monat, s.reparatur_monat, s.satz_monat) == (D("1000.00"), D("0.00"), D("0.00"), D("1000.00"))
    assert kalkulatorisch_bis(p, date(2026, 1, 15), date(2026, 3, 1)) == D("1000.00")  # hoechstens 1 Monat
    assert restbuchwert_kalk(p, date(2026, 1, 15), date(2026, 3, 1)) == D("200.00")


def test_C3_werktage_variante_21_67():
    p = Kostenparameter(D("150000"), D("15000"), 96, D("4"), D("12"), tage_je_monat=D("21.67"))
    s = kostensatz(p)
    assert s.satz_monat == D("3156.25")
    assert s.satz_tag == D("145.65")  # 3156,25 / 21,67 = 145,6507
    assert s.satz_woche == D("1019.55")  # 145,6507 x 7 = 1019,5547


def test_C4_kaufmaennisch_gerundet_erst_am_ende():
    p = Kostenparameter(D("1000"), D("0"), 3, D("0"), D("0"))  # 333,3333 je Monat
    s = kostensatz(p)
    assert s.abschreibung_monat == D("333.33")
    assert s.satz_tag == D("11.11")
    assert kalkulatorisch_bis(p, date(2026, 1, 1), date(2026, 4, 1)) == D("1000.00")  # nicht 3 x 333,33
    p2 = Kostenparameter(D("1.00"), D("0"), 8, D("0"), D("0"))  # 0,125 -> 0,13 (kaufmaennisch)
    assert kostensatz(p2).abschreibung_monat == D("0.13")


def test_C5_vorhaltung_transfer_mitten_im_monat():
    satz = kostensatz(BAGGER).satz_tag
    a = standort(100, tag(9, 1), tag(10, 15))  # Abgang-/Eingangstag 15.10.
    b = standort(200, tag(10, 15), None)
    erg = vorhaltung([a, b], date(2026, 10, 1), date(2026, 10, 31), satz)
    assert erg == (
        Vorhaltung(100, 14, D("1472.94")),  # 1.-14.10., der 15. zaehlt schon zum Ziel
        Vorhaltung(200, 17, D("1788.57")),  # 15.-31.10.
    )
    assert sum(v.tage for v in erg) == 31


def test_C6_vorhaltung_zeitraum_schneidet_standorte():
    satz = D("100")
    s = standort(100, tag(9, 1), tag(10, 15))
    assert vorhaltung([s], date(2026, 10, 10), date(2026, 10, 20), satz) == (Vorhaltung(100, 5, D("500.00")),)
    assert vorhaltung([s], date(2026, 10, 15), date(2026, 10, 20), satz) == ()
    assert vorhaltung([s], date(2026, 8, 1), date(2026, 8, 31), satz) == ()
    nur_ein_tag = vorhaltung([standort(100, tag(10, 5), None)], date(2026, 10, 5), date(2026, 10, 5), satz)
    assert nur_ein_tag == (Vorhaltung(100, 1, D("100.00")),)


def test_C7_vorhaltung_fasst_standorte_je_kostenstelle_zusammen():
    s1 = standort(100, tag(10, 1), tag(10, 5))
    s2 = standort(100, tag(10, 10), tag(10, 12))
    erg = vorhaltung([s1, s2], date(2026, 10, 1), date(2026, 10, 31), D("10"))
    assert erg == (Vorhaltung(100, 6, D("60.00")),)


def test_C8_vorhaltung_menge_nur_auf_wunsch():
    s = standort(100, tag(10, 1), None, menge=40)
    ohne = vorhaltung([s], date(2026, 10, 1), date(2026, 10, 2), D("2.00"))
    mit = vorhaltung([s], date(2026, 10, 1), date(2026, 10, 2), D("2.00"), mit_menge=True)
    assert ohne[0].betrag == D("4.00") and mit[0].betrag == D("160.00")
    with pytest.raises(ValueError):
        vorhaltung([s], date(2026, 10, 2), date(2026, 10, 1), D("2.00"))


def test_C9_gesamtkosten():
    assert gesamtkosten(D("150000"), [D("1200.50"), D("300")]) == D("151500.50")
    assert gesamtkosten(D("1000"), []) == D("1000.00")


def test_C10_kalkulatorisch_bis_volle_monate_und_deckel():
    kauf = date(2020, 1, 31)
    assert kalkulatorisch_bis(BAGGER, kauf, date(2020, 1, 31)) == D("0.00")
    assert kalkulatorisch_bis(BAGGER, kauf, date(2020, 2, 27)) == D("0.00")
    assert kalkulatorisch_bis(BAGGER, kauf, date(2020, 2, 29)) == D("3156.25")  # Monatsende-Regel
    assert kalkulatorisch_bis(BAGGER, kauf, date(2021, 1, 31)) == D("37875.00")  # 12 Monate
    assert kalkulatorisch_bis(BAGGER, kauf, date(2040, 1, 1)) == D("303000.00")  # 96 x 3156,25
    assert kalkulatorisch_bis(BAGGER, kauf, date(2019, 1, 1)) == D("0.00")  # vor dem Kauf


def test_C11_miete_vs_eigen_positiv_und_negativ():
    assert miete_vs_eigen(D("900.00"), D("105.21"), 5) == (D("900.00"), D("526.05"), D("373.95"))
    assert miete_vs_eigen(D("300.00"), D("105.21"), 5) == (D("300.00"), D("526.05"), D("-226.05"))
    assert miete_vs_eigen(D("0"), D("105.21"), 0) == (D("0.00"), D("0.00"), D("0.00"))
    with pytest.raises(ValueError):
        miete_vs_eigen(D("1"), D("1"), -1)


def test_C12_restbuchwert_linear_und_nie_unter_restwert():
    kauf = date(2020, 1, 15)
    assert restbuchwert_kalk(BAGGER, kauf, date(2020, 1, 15)) == D("150000.00")
    assert restbuchwert_kalk(BAGGER, kauf, date(2021, 1, 15)) == D("133125.00")  # 12 x 1406,25 ab
    assert restbuchwert_kalk(BAGGER, kauf, date(2028, 1, 15)) == D("15000.00")  # nach Ablauf = Restwert
    assert restbuchwert_kalk(BAGGER, kauf, date(2050, 1, 1)) == D("15000.00")
    assert restbuchwert_kalk(BAGGER, kauf, date(2019, 1, 1)) == D("150000.00")


def test_C13_ungueltige_parameter():
    for p in (
        Kostenparameter(D("-1"), D("0"), 12, D("0"), D("0")),
        Kostenparameter(D("100"), D("200"), 12, D("0"), D("0")),
        Kostenparameter(D("100"), D("0"), 0, D("0"), D("0")),
        Kostenparameter(D("100"), D("0"), 12, D("-1"), D("0")),
        Kostenparameter(D("100"), D("0"), 12, D("0"), D("0"), tage_je_monat=D("0")),
    ):
        with pytest.raises(ValueError):
            kostensatz(p)


def test_C14_vorhaltung_in_werktagen():
    satz = D("100")
    a = standort(100, tag(9, 1), tag(10, 15))  # Abgang-/Eingangstag Do 15.10.
    b = standort(200, tag(10, 15), None)
    erg = vorhaltung([a, b], date(2026, 10, 1), date(2026, 10, 31), satz, werktage=True)
    assert erg == (Vorhaltung(100, 10, D("1000.00")), Vorhaltung(200, 12, D("1200.00")))  # 1.-14.10. bzw. 15.-31.10.
    frei = vorhaltung([a, b], date(2026, 10, 1), date(2026, 10, 31), satz, werktage=True,
                      feiertage=[date(2026, 10, 9), date(2026, 10, 20)])
    assert [v.tage for v in frei] == [9, 11]
    nur_wochenende = vorhaltung([standort(100, tag(10, 10), tag(10, 12))], date(2026, 10, 1), date(2026, 10, 31), satz, werktage=True)
    assert nur_wochenende == ()  # Sa 10. und So 11. zaehlen nicht
