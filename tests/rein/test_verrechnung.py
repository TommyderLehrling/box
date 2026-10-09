"""Prueffaelle fuer verrechnung (G1-G7)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from digiassistenz_inventar.rein.verrechnung import (
    CSV_SPALTEN,
    MieteGegenEigen,
    VerrechnungsStueck,
    csv_text,
    miete_gegen_eigen,
    schreibe_csv,
    verrechne,
)
from digiassistenz_inventar.rein.transfer import Standort

ZONE = timezone(timedelta(hours=2))
VON, BIS = date(2026, 10, 1), date(2026, 10, 15)


def st(nummer: str, ks: int, tag_von: int, tag_bis: int | None, menge: int = 1) -> Standort:
    ende = None if tag_bis is None else datetime(2026, 10, tag_bis, 8, tzinfo=ZONE)
    return Standort(nummer, ks, menge, datetime(2026, 10, tag_von, 8, tzinfo=ZONE), ende, None, "web", "anna")


A = VerrechnungsStueck("A", "baumaschine", D("100.00"), D("50.00"), (st("A", 100, 1, 11), st("A", 200, 11, None)))
B = VerrechnungsStueck("B", "schalung_ruestung", D("2.00"), None, (st("B", 100, 1, None, 40),))
STUNDEN = [(date(2026, 10, 3), 100, "A", D("8")), (date(2026, 10, 4), 100, "A", D("7.5")),
           (date(2026, 10, 12), 200, "A", D("6")), (date(2026, 10, 20), 200, "A", D("9"))]


def test_G1_vorhaltung_plus_stunden_je_kostenstelle_und_stueck():
    v = verrechne([A, B], STUNDEN, VON, BIS)
    z = {(x.kostenstelle, x.inventarnummer): x for x in v.zeilen}
    assert (z[(100, "A")].tage, z[(100, "A")].betrag_vorhaltung, z[(100, "A")].stunden, z[(100, "A")].betrag_stunden,
            z[(100, "A")].summe) == (10, D("1000.00"), D("15.5"), D("775.00"), D("1775.00"))
    assert (z[(200, "A")].tage, z[(200, "A")].summe) == (5, D("800.00"))
    assert (z[(100, "B")].tage, z[(100, "B")].betrag_vorhaltung, z[(100, "B")].summe) == (15, D("1200.00"), D("1200.00"))
    assert v.hinweise == ()  # Stunden vom 20.10. liegen ausserhalb und zaehlen nicht


def test_G2_summen_je_kostenstelle_und_je_stueck():
    v = verrechne([A, B], STUNDEN, VON, BIS)
    ks = {s.schluessel: s for s in v.je_kostenstelle}
    assert [s.schluessel for s in v.je_kostenstelle] == ["100", "200"]
    assert (ks["100"].tage, ks["100"].stunden, ks["100"].summe) == (25, D("15.5"), D("2975.00"))
    assert ks["200"].summe == D("800.00")
    stueck = {s.schluessel: s for s in v.je_stueck}
    assert (stueck["A"].tage, stueck["A"].betrag_vorhaltung, stueck["A"].betrag_stunden, stueck["A"].summe) == (
        15, D("1500.00"), D("1075.00"), D("2575.00"))
    assert sum(s.summe for s in v.je_kostenstelle) == sum(s.summe for s in v.je_stueck) == D("3775.00")


def test_G3_stunden_ohne_stundensatz_zaehlen_null_mit_hinweis():
    v = verrechne([A, B], [(date(2026, 10, 2), 100, "B", D("3"))], VON, BIS)
    zeile = next(x for x in v.zeilen if x.inventarnummer == "B")
    assert (zeile.stunden, zeile.betrag_stunden) == (D("3"), D("0.00"))
    assert v.hinweise == ("verrechnung.satz_stunde_fehlt:B",)


def test_G4_stunden_ohne_standort_und_werktage():
    v = verrechne([A], [(date(2026, 10, 5), 300, "A", D("2"))], VON, BIS)
    assert any((x.kostenstelle, x.tage, x.summe) == (300, 0, D("100.00")) for x in v.zeilen)
    w = verrechne([B], [], VON, BIS, werktage=True)  # 1.-15.10.2026: 11 Werktage (3.10. ist Samstag)
    assert w.zeilen[0].tage == 11 and w.zeilen[0].betrag_vorhaltung == D("880.00")
    frei = verrechne([B], [], VON, BIS, werktage=True, feiertage=[date(2026, 10, 2)])
    assert frei.zeilen[0].tage == 10


def test_G5_ungueltige_eingaben():
    with pytest.raises(ValueError, match="zeitraum_ungueltig"):
        verrechne([A], [], BIS, VON)
    with pytest.raises(ValueError, match="stueck_unbekannt"):
        verrechne([A], [(VON, 100, "X", D("1"))], VON, BIS)
    with pytest.raises(ValueError, match="stunden_ungueltig"):
        verrechne([A], [(VON, 100, "A", D("-1"))], VON, BIS)
    assert verrechne([], [], VON, BIS) == verrechne([], [], VON, BIS) and verrechne([], [], VON, BIS).zeilen == ()


def test_G6_miete_gegen_eigen_ueber_den_datensatz():
    eigen1 = VerrechnungsStueck("E1", "baumaschine", D("105.21"), None, ())
    eigen2 = VerrechnungsStueck("E2", "baumaschine", D("95.00"), None, ())
    miete = VerrechnungsStueck("M1", "baumaschine", D("0"), None, (), True, date(2026, 10, 5), date(2026, 10, 14), D("2000"))
    ohne = VerrechnungsStueck("M2", "container", D("0"), None, (), True, date(2026, 9, 1), date(2026, 11, 30), D("900"))
    erg = miete_gegen_eigen([eigen1, eigen2, miete, ohne], date(2026, 10, 1), date(2026, 10, 31))
    assert erg == (MieteGegenEigen("M1", "baumaschine", 10, D("2000.00"), D("1001.05"), D("998.95")),
                   MieteGegenEigen("M2", "container", 31, D("900.00"), None, None))
    unvollstaendig = VerrechnungsStueck("M3", "baumaschine", D("0"), None, (), True, None, None, None)
    with pytest.raises(ValueError, match="miete_unvollstaendig"):
        miete_gegen_eigen([unvollstaendig], VON, BIS)


def test_G7_csv_text_und_datei(tmp_path):
    v = verrechne([A, B], STUNDEN, VON, BIS)
    text = csv_text(v.zeilen)
    zeilen = text.split("\r\n")
    assert zeilen[0] == ";".join(CSV_SPALTEN)
    assert zeilen[1] == "100;A;10;1000,00;15.5;775,00;1775,00".replace("15.5", "15,5")
    assert csv_text(v.zeilen, ",", False).split("\r\n")[1] == "100,A,10,1000.00,15.5,775.00,1775.00"
    datei = tmp_path / "verrechnung.csv"
    schreibe_csv(datei, v.zeilen)
    assert datei.read_bytes().startswith(b"\xef\xbb\xbf") and datei.read_bytes().decode("utf-8-sig") == text


def test_G8_vergleichsstueck_ersetzt_den_gruppenmittelwert():
    eigen1 = VerrechnungsStueck("E1", "baumaschine", D("100.00"), None, ())
    eigen2 = VerrechnungsStueck("E2", "baumaschine", D("50.00"), None, ())
    miete = VerrechnungsStueck("M1", "baumaschine", D("0"), None, (), True, date(2026, 10, 1), date(2026, 10, 10), D("900"))
    alle = [eigen1, eigen2, miete]
    mittel = miete_gegen_eigen(alle, VON, BIS)[0]
    assert (mittel.tage, mittel.eigen, mittel.differenz) == (10, D("750.00"), D("150.00"))
    gewaehlt = miete_gegen_eigen(alle, VON, BIS, vergleichsstueck="E1")[0]
    assert (gewaehlt.eigen, gewaehlt.differenz) == (D("1000.00"), D("-100.00"))
    je_miete = miete_gegen_eigen(alle, VON, BIS, vergleichsstueck={"M1": "E2"})[0]
    assert je_miete.eigen == D("500.00")
    ohne_eintrag = miete_gegen_eigen(alle, VON, BIS, vergleichsstueck={"M9": "E2"})[0]
    assert ohne_eintrag.eigen == D("750.00")  # kein Eintrag fuer M1: Gruppenmittelwert
    with pytest.raises(ValueError, match="vergleichsstueck_unbekannt"):
        miete_gegen_eigen(alle, VON, BIS, vergleichsstueck="M1")  # ein Mietstueck ist kein eigenes Stueck
