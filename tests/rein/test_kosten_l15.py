"""Prueffaelle L15 (G5): Saetze mit Sollwerten aus Spec 8, Mengenartikel, Kalender- gegen Werktage, CSV-Auszuege."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from digiassistenz_inventar.rein.kosten import (
    Kostenparameter,
    kalkulatorisch_aus_satz,
    kalkulatorisch_bis,
    kostensatz,
    satz_aus_monat,
    vorhaltung,
)
from digiassistenz_inventar.rein.kostenexport import BLOECKE, KOPF, csv_text, dateiname
from digiassistenz_inventar.rein.transfer import Standort
from digiassistenz_inventar.rein.verrechnung import VerrechnungsStueck, miete_gegen_eigen, verrechne

ZONE = timezone(timedelta(hours=2))
BAGGER = Kostenparameter(D("150000.00"), D("15000.00"), 96, D("4.0"), D("12.0"))


def tag(monat: int, t: int) -> datetime:
    return datetime(2026, monat, t, 8, 0, tzinfo=ZONE)


def standort(ks: int, von: datetime, bis: datetime | None, menge: int = 1) -> Standort:
    return Standort("X-1", ks, menge, von, bis, None, "web", "anna")


# ---- Saetze: ein Beispiel je Groesse, Sollwerte von Hand gerechnet -----------------------------------------------

def test_L15_1_ein_bagger_gross():
    s = kostensatz(BAGGER)
    assert (s.satz_monat, s.satz_tag, s.satz_woche) == (D("3156.25"), D("105.21"), D("736.46"))


def test_L15_2_ein_kleingeraet():
    """Bohrhammer 1.200 EUR, 60 Monate, 5 % Rest, 4 % Zins, 12 % Reparatur: 19 + 2 + 12 = 33 je Monat, 1,10 je Tag."""
    s = kostensatz(Kostenparameter(D("1200"), D("60"), 60, D("4"), D("12")))
    assert (s.abschreibung_monat, s.zins_monat, s.reparatur_monat) == (D("19.00"), D("2.00"), D("12.00"))
    assert (s.satz_monat, s.satz_tag, s.satz_woche) == (D("33.00"), D("1.10"), D("7.70"))


def test_L15_3_ein_werkzeug_ohne_restwert():
    """Schlagschrauber 300 EUR, 36 Monate, ohne Rest, 4 %, 5 %: 8,33 + 0,50 + 1,25 = 10,08 je Monat."""
    s = kostensatz(Kostenparameter(D("300"), D("0"), 36, D("4"), D("5")))
    assert (s.abschreibung_monat, s.zins_monat, s.reparatur_monat, s.satz_monat) == (D("8.33"), D("0.50"), D("1.25"), D("10.08"))


def test_L15_4_kalender_gegen_werktage_im_satz():
    kalender = kostensatz(BAGGER)
    werktage = kostensatz(Kostenparameter(D("150000"), D("15000"), 96, D("4"), D("12"), tage_je_monat=D("21.67")))
    assert kalender.satz_monat == werktage.satz_monat == D("3156.25")
    assert (kalender.satz_tag, werktage.satz_tag) == (D("105.21"), D("145.65"))


def test_L15_5_satz_aus_monat_fuer_von_hand_gesetzte_saetze():
    assert satz_aus_monat(D("3156.25")) == (D("105.21"), D("736.46"))
    assert satz_aus_monat(D("3156.25"), D("21.67")) == (D("145.65"), D("1019.55"))
    with pytest.raises(ValueError, match="tage_je_monat_ungueltig"):
        satz_aus_monat(D("1"), D("0"))


def test_L15_6_kalkulatorisch_bis_heute_mit_gegebenem_monatssatz():
    """Volle Monate seit dem Kauf mal Monatssatz, hoechstens die Nutzungsdauer."""
    kauf = date(2024, 1, 15)
    assert kalkulatorisch_aus_satz(D("3156.25"), 96, kauf, date(2026, 1, 14)) == D("72593.75")  # 23 volle Monate: 23 * 3156,25
    assert kalkulatorisch_aus_satz(D("3156.25"), 96, kauf, date(2026, 1, 15)) == D("75750.00")  # 24 volle Monate: 24 * 3156,25
    assert kalkulatorisch_aus_satz(D("10"), 12, kauf, date(2040, 1, 1)) == D("120.00"), "nie ueber die Nutzungsdauer"
    assert kalkulatorisch_aus_satz(D("10"), 12, kauf, date(2023, 1, 1)) == D("0.00"), "vor dem Kauf nichts"
    assert kalkulatorisch_aus_satz(kostensatz(BAGGER).satz_monat, 96, kauf, date(2026, 1, 15)) == kalkulatorisch_bis(BAGGER, kauf, date(2026, 1, 15))
    with pytest.raises(ValueError):
        kalkulatorisch_aus_satz(D("-1"), 12, kauf, kauf)


# ---- Mengenartikel (E2) und Kalender- gegen Werktage in der Vorhaltung --------------------------------------------

def test_L15_7_mengenartikel_vorhaltung_ist_satz_mal_tage_mal_menge():
    """40 Schalungstraeger, 2,50 je Stueck und Tag, zehn Tage: 40 * 10 * 2,50 = 1.000."""
    erg = vorhaltung([standort(5, tag(10, 1), None, menge=40)], date(2026, 10, 1), date(2026, 10, 10), D("2.50"))
    assert erg[0].tage == 10 and erg[0].betrag == D("1000.00")
    ohne = vorhaltung([standort(5, tag(10, 1), None, menge=40)], date(2026, 10, 1), date(2026, 10, 10), D("2.50"), mit_menge=False)
    assert ohne[0].betrag == D("25.00")


def test_L15_8_kalendertage_gegen_werktage():
    """1. bis 14. Oktober 2026 (Donnerstag bis Mittwoch): 14 Kalendertage, 10 Werktage."""
    orte = [standort(5, tag(9, 1), None)]
    kalender = vorhaltung(orte, date(2026, 10, 1), date(2026, 10, 14), D("100"))
    werktage = vorhaltung(orte, date(2026, 10, 1), date(2026, 10, 14), D("100"), werktage=True)
    assert (kalender[0].tage, kalender[0].betrag) == (14, D("1400.00"))
    assert (werktage[0].tage, werktage[0].betrag) == (10, D("1000.00"))
    feiertag = vorhaltung(orte, date(2026, 10, 1), date(2026, 10, 14), D("100"), werktage=True, feiertage=[date(2026, 10, 12)])
    assert feiertag[0].tage == 9


def test_L15_9_vorhaltung_ueber_einen_teil_eingang_hinweg():
    """10 Stueck laufen am 10.10. von A ab; 6 kommen am 12.10. auf B an (Teil-Eingang), 4 am 15.10.: unterwegs zaehlt nirgends."""
    orte = [
        standort(1, tag(10, 1), tag(10, 10), menge=10),
        standort(2, tag(10, 12), None, menge=6),
        standort(2, tag(10, 15), None, menge=4),
    ]
    erg = {v.kostenstelle: v for v in vorhaltung(orte, date(2026, 10, 1), date(2026, 10, 20), D("2"))}
    assert (erg[1].tage, erg[1].betrag) == (9, D("180.00"))  # 1. bis 9.10. a 10 Stueck
    assert erg[2].tage == 9 + 6 and erg[2].betrag == D("2") * (9 * 6 + 6 * 4)  # 12.-20.10. mal 6, 15.-20.10. mal 4


def test_L15_10_verrechnung_je_kostenstelle_und_stueck():
    bagger = VerrechnungsStueck("BM-1", "bm", D("100"), None, (standort(1, tag(10, 1), tag(10, 6)), standort(2, tag(10, 6), None)))
    erg = verrechne([bagger], [], date(2026, 10, 1), date(2026, 10, 10))
    assert [(z.kostenstelle, z.tage, z.betrag_vorhaltung) for z in erg.zeilen] == [(1, 5, D("500.00")), (2, 5, D("500.00"))]
    assert [(s.schluessel, s.betrag_vorhaltung) for s in erg.je_kostenstelle] == [("1", D("500.00")), ("2", D("500.00"))]


def test_L15_11_miete_gegen_eigen_mit_und_ohne_vergleich():
    eigen = VerrechnungsStueck("BM-1", "bm", D("100"), None, ())
    teuer = VerrechnungsStueck("BM-2", "bm", D("200"), None, ())
    miete = VerrechnungsStueck("MI-1", "bm", D("0"), None, (), True, date(2026, 10, 1), date(2026, 10, 10), D("2500"))
    mittel = miete_gegen_eigen([eigen, teuer, miete], date(2026, 10, 1), date(2026, 10, 31))[0]
    assert (mittel.tage, mittel.miete, mittel.eigen, mittel.differenz) == (10, D("2500.00"), D("1500.00"), D("1000.00"))
    gewaehlt = miete_gegen_eigen([eigen, teuer, miete], date(2026, 10, 1), date(2026, 10, 31), vergleichsstueck="BM-1")[0]
    assert (gewaehlt.eigen, gewaehlt.differenz) == (D("1000.00"), D("1500.00"))
    ohne = miete_gegen_eigen([miete], date(2026, 10, 1), date(2026, 10, 31))[0]
    assert (ohne.eigen, ohne.differenz) == (None, None)
    with pytest.raises(ValueError, match="vergleichsstueck_unbekannt"):
        miete_gegen_eigen([eigen, miete], date(2026, 10, 1), date(2026, 10, 31), vergleichsstueck="XX-9")


# ---- CSV-Auszuege ----------------------------------------------------------------------------------------------

def test_L15_12_csv_mit_semikolon_dezimalkomma_und_kopfzeile():
    text = csv_text("kostenstelle", [("79795 Husum", "BM-1", 5, D("500.00")), ("79800", "BM-2", 3, D("12.5"))])
    zeilen = text.split("\r\n")
    assert zeilen[0] == "kostenstelle;inventarnummer;tage;betrag_vorhaltung"
    assert zeilen[1] == "79795 Husum;BM-1;5;500,00" and zeilen[2] == "79800;BM-2;3;12,5" and zeilen[3] == ""
    assert csv_text("miete", [("MI-1", "bm", 10, D("2500"), None, None)]).split("\r\n")[1] == "MI-1;bm;10;2500;;"
    with pytest.raises(ValueError, match="spaltenzahl"):
        csv_text("kostenstelle", [("nur", "zwei")])


def test_L15_13_alle_bloecke_haben_einen_kopf_und_der_dateiname_traegt_den_zeitstempel():
    assert set(BLOECKE) <= set(KOPF) and "inventur" in KOPF
    zeit = datetime(2026, 10, 10, 14, 5, 9)
    assert dateiname("stueck", zeit) == "kosten_stueck_20261010-140509.csv"
    assert dateiname("inventur", zeit) == "inventur_20261010-140509.csv"
    with pytest.raises(ValueError, match="block_unbekannt"):
        dateiname("gibtsnicht", zeit)
    assert csv_text("anlagenbuch", [("BM-1", "Bagger", "Baumaschinen", date(2020, 3, 15), D("1000"), "Händler", None, "")]).split("\r\n")[1] == \
        "BM-1;Bagger;Baumaschinen;2020-03-15;1000;Händler;;"
