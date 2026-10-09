"""Prueffaelle fuer import_vorlage (I1-I16)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook, load_workbook

from inventar_rein.import_vorlage import FEHLER_SCHLUESSEL, SPALTEN, erzeuge_vorlage, lies, lies_mit_hinweisen
from inventar_rein.kataloge import lade_gruppen, lade_merkmale
from inventar_rein.nummernformat import Muster

GRUPPEN, MERKMALE = lade_gruppen(), lade_merkmale()
KS = [100, 200, 1000]
HEUTE = date(2026, 10, 8)
GUT: dict[str, Any] = {"Inventarnummer": "BM-00017", "Bezeichnung": "Hydraulikbagger 21 t", "Gruppe": "baumaschine",
                       "Art": "gross", "Kostenstelle": 100}


def schreibe(pfad: Path, zeilen: list[dict[str, Any]], extra: tuple[str, ...] = (), kopf: list[str] | None = None) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventar"
    spalten = kopf if kopf is not None else list(SPALTEN) + list(extra)
    ws.append(spalten)
    for z in zeilen:
        ws.append([z.get(s) for s in spalten])
    wb.save(pfad)
    return pfad


def lese(tmp_path: Path, zeilen, extra=(), muster=None, kopf=None):
    datei = schreibe(tmp_path / "test.xlsx", zeilen, extra, kopf)
    return lies(datei, GRUPPEN, MERKMALE, KS, muster, HEUTE)


def schluessel(fehler) -> list[tuple[int, str, str]]:
    return [(f.zeile, f.spalte, f.text_schluessel) for f in fehler]


def test_I1_vorlage_hat_kopf_beispiele_dropdowns_und_kommentare(tmp_path: Path):
    datei = tmp_path / "vorlage.xlsx"
    erzeuge_vorlage(datei, GRUPPEN, MERKMALE)
    wb = load_workbook(datei)
    ws = wb["Inventar"]
    kopf = [c.value for c in ws[1]]
    assert tuple(kopf[:14]) == SPALTEN
    assert "m:kennzeichen" in kopf and "m:schutzklasse" in kopf
    assert len(kopf) == 14 + len({m.schluessel for m in MERKMALE})
    assert ws["A2"].value and ws["A3"].value and ws["A4"].value is None
    kommentar = ws.cell(row=1, column=kopf.index("m:kennzeichen") + 1).comment.text
    assert "gruppe=fahrzeug" in kommentar and "pflicht=1" in kommentar
    assert len(ws.data_validations.dataValidation) == 2
    assert wb["Listen"].sheet_state == "hidden"
    assert wb["Listen"]["A2"].value == "baumaschine" and wb["Listen"]["B4"].value == "menge"


def test_I2_vorlage_ist_selbst_lesbar_und_beispiele_werden_uebersprungen(tmp_path: Path):
    datei = tmp_path / "vorlage.xlsx"
    erzeuge_vorlage(datei, GRUPPEN, MERKMALE)
    erg = lies_mit_hinweisen(datei, GRUPPEN, MERKMALE, KS, Muster("{gruppe}-{nr:5}"), HEUTE)
    assert (erg.zeilen, erg.fehler) == ((), ())
    assert [(h.zeile, h.text_schluessel) for h in erg.hinweise] == [
        (2, "import.hinweis.beispiel_uebersprungen"), (3, "import.hinweis.beispiel_uebersprungen")]
    assert lies(datei, GRUPPEN, MERKMALE, KS, None, HEUTE) == ((), ())


def test_I17_beispielzeile_zaehlt_nicht_als_doppelte_nummer(tmp_path: Path):
    beispiel = {**GUT, "Besonderheiten": "beispiel: bitte loeschen"}
    echt = {**GUT, "Besonderheiten": "echt"}
    datei = schreibe(tmp_path / "t.xlsx", [beispiel, echt])
    erg = lies_mit_hinweisen(datei, GRUPPEN, MERKMALE, KS, None, HEUTE)
    assert erg.fehler == () and [z.inventarnummer for z in erg.zeilen] == ["BM-00017"]
    assert [h.zeile for h in erg.hinweise] == [2]


def test_I18_gruppe_als_schluessel_oder_bezeichnung_ohne_gross_klein(tmp_path: Path):
    bezeichnung = next(g.bezeichnung for g in GRUPPEN if g.schluessel == "baumaschine")
    zeilen = [{**GUT, "Inventarnummer": "BM-1", "Gruppe": bezeichnung.upper()},
              {**GUT, "Inventarnummer": "BM-2", "Gruppe": " Baumaschine "},
              {**GUT, "Inventarnummer": "BM-3", "Gruppe": "gibt es nicht"}]
    ergebnis, fehler = lese(tmp_path, zeilen)
    assert [(z.inventarnummer, z.gruppe) for z in ergebnis] == [("BM-1", "baumaschine"), ("BM-2", "baumaschine")]
    assert schluessel(fehler) == [(4, "Gruppe", "import.fehler.gruppe_unbekannt")]


def test_I3_pflichtfelder(tmp_path: Path):
    zeilen = [{**GUT, "Inventarnummer": f"P{i}", spalte: None}
              for i, spalte in enumerate(("Inventarnummer", "Bezeichnung", "Gruppe", "Art", "Kostenstelle"))]
    ergebnis, fehler = lese(tmp_path, zeilen)
    assert ergebnis == ()
    assert schluessel(fehler) == [(2 + i, s, "import.fehler.pflicht_fehlt") for i, s in
                                  enumerate(("Inventarnummer", "Bezeichnung", "Gruppe", "Art", "Kostenstelle"))]


def test_I4_gruppe_und_art_pruefen(tmp_path: Path):
    _, fehler = lese(tmp_path, [{**GUT, "Gruppe": "raumschiff"}, {**GUT, "Inventarnummer": "X2", "Art": "riesig"}])
    assert (2, "Gruppe", "import.fehler.gruppe_unbekannt") in schluessel(fehler)
    assert (3, "Art", "import.fehler.art_unbekannt") in schluessel(fehler)


def test_I5_menge_nur_bei_art_menge(tmp_path: Path):
    ok = [{**GUT, "Inventarnummer": "S1", "Gruppe": "schalung_ruestung", "Art": "menge", "Menge": 40},
          {**GUT, "Inventarnummer": "S2", "Art": "gross", "Menge": None},
          {**GUT, "Inventarnummer": "S3", "Art": "klein", "Menge": 1}]
    zeilen, fehler = lese(tmp_path, ok)
    assert fehler == () and [z.menge for z in zeilen] == [40, 1, 1]
    schlecht = [{**GUT, "Inventarnummer": "S4", "Art": "menge", "Menge": None},
                {**GUT, "Inventarnummer": "S5", "Art": "menge", "Menge": 0},
                {**GUT, "Inventarnummer": "S6", "Art": "klein", "Menge": 5},
                {**GUT, "Inventarnummer": "S7", "Art": "menge", "Menge": "viele"}]
    zeilen, fehler = lese(tmp_path, schlecht)
    assert zeilen == ()
    assert [f.text_schluessel for f in fehler] == ["import.fehler.menge_ungueltig", "import.fehler.menge_ungueltig",
                                                   "import.fehler.menge_nur_bei_menge", "import.fehler.menge_ungueltig"]


def test_I6_kostenstelle_muss_in_der_liste_stehen(tmp_path: Path):
    zeilen, fehler = lese(tmp_path, [{**GUT, "Kostenstelle": 999}, {**GUT, "Inventarnummer": "X2", "Kostenstelle": "Bauhof"},
                                     {**GUT, "Inventarnummer": "X3", "Kostenstelle": "1000"}])
    assert [(f.zeile, f.text_schluessel) for f in fehler] == [(2, "import.fehler.kostenstelle_unbekannt"),
                                                              (3, "import.fehler.kostenstelle_ungueltig")]
    assert [z.kostenstelle for z in zeilen] == [1000]


def test_I7_kaufpreis(tmp_path: Path):
    preise = [("1234.56", "1234.56"), ("1.234,56", "1234.56"), ("1234,5", "1234.5"), (0, "0"), (99.5, "99.5")]
    zeilen, fehler = lese(tmp_path, [{**GUT, "Inventarnummer": f"P{i}", "Kaufpreis": p} for i, (p, _) in enumerate(preise)])
    assert fehler == () and [z.kaufpreis for z in zeilen] == [Decimal(w) for _, w in preise]
    zeilen, fehler = lese(tmp_path, [{**GUT, "Kaufpreis": -1}, {**GUT, "Inventarnummer": "P9", "Kaufpreis": "viel"},
                                     {**GUT, "Inventarnummer": "P8", "Kaufpreis": "NaN"}])
    assert [f.text_schluessel for f in fehler] == ["import.fehler.kaufpreis_negativ"] + ["import.fehler.kaufpreis_ungueltig"] * 2


def test_I8_datumsformate(tmp_path: Path):
    daten = ["15.03.2020", "2020-03-15", datetime(2020, 3, 15), date(2020, 3, 15), "5.3.2020"]
    zeilen, fehler = lese(tmp_path, [{**GUT, "Inventarnummer": f"D{i}", "Kaufdatum": d} for i, d in enumerate(daten)])
    assert fehler == ()
    assert [z.kaufdatum for z in zeilen] == [date(2020, 3, 15)] * 4 + [date(2020, 3, 5)]
    _, fehler = lese(tmp_path, [{**GUT, "Kaufdatum": "31.02.2020"}, {**GUT, "Inventarnummer": "D9", "Kaufdatum": "gestern"}])
    assert [f.text_schluessel for f in fehler] == ["import.fehler.datum_ungueltig"] * 2


def test_I9_baujahr_bereich(tmp_path: Path):
    ok, fehler = lese(tmp_path, [{**GUT, "Baujahr": 1950}, {**GUT, "Inventarnummer": "B2", "Baujahr": 2026.0},
                                 {**GUT, "Inventarnummer": "B3", "Baujahr": "2015"}])
    assert fehler == () and [z.baujahr for z in ok] == [1950, 2026, 2015]
    _, fehler = lese(tmp_path, [{**GUT, "Baujahr": 1949}, {**GUT, "Inventarnummer": "B5", "Baujahr": 2027},
                                {**GUT, "Inventarnummer": "B6", "Baujahr": "alt"}])
    assert [f.text_schluessel for f in fehler] == ["import.fehler.baujahr_bereich"] * 2 + ["import.fehler.baujahr_ungueltig"]


def test_I10_doppelte_nummer_trifft_beide_zeilen(tmp_path: Path):
    zeilen, fehler = lese(tmp_path, [GUT, {**GUT, "Inventarnummer": " bm-00017 "}, {**GUT, "Inventarnummer": "BM-00018"}])
    assert [z.inventarnummer for z in zeilen] == ["BM-00018"]
    assert schluessel(fehler) == [(2, "Inventarnummer", "import.fehler.nummer_doppelt"),
                                  (3, "Inventarnummer", "import.fehler.nummer_doppelt")]
    assert {f.wert for f in fehler} == {"BM-00017"}


def test_I11_nummer_muss_zum_muster_passen(tmp_path: Path):
    muster = Muster("{gruppe}-{nr:5}")
    zeilen, fehler = lese(tmp_path, [GUT, {**GUT, "Inventarnummer": "17"}, {**GUT, "Inventarnummer": "bm-00018"}], muster=muster)
    assert [z.inventarnummer for z in zeilen] == ["BM-00017", "BM-00018"]  # normalisiert
    assert schluessel(fehler) == [(3, "Inventarnummer", "import.fehler.nummer_muster")]
    zeilen, fehler = lese(tmp_path, [{**GUT, "Inventarnummer": "17"}], muster=None)
    assert fehler == () and len(zeilen) == 1


def test_I12_merkmale(tmp_path: Path):
    extra = ("m:betriebsgewicht", "m:schnellwechsler", "m:kennzeichen", "m:foo", "m:hu_faellig", "m:beheizt")
    zeilen, fehler = lese(tmp_path, [{**GUT, "m:betriebsgewicht": "21,5", "m:schnellwechsler": "MS08"}], extra)
    assert fehler == () and zeilen[0].merkmale == {"betriebsgewicht": "21.5", "schnellwechsler": "MS08"}
    schlecht = [{**GUT, "Inventarnummer": "M1", "m:betriebsgewicht": "schwer"},
                {**GUT, "Inventarnummer": "M2", "m:schnellwechsler": "XY99"},
                {**GUT, "Inventarnummer": "M3", "m:kennzeichen": "MZ-AB 1"},  # gehoert zu Fahrzeug
                {**GUT, "Inventarnummer": "M4", "m:foo": "x"},
                {**GUT, "Inventarnummer": "M5", "m:betriebsgewicht": 21}]
    zeilen, fehler = lese(tmp_path, schlecht, extra)
    assert [(f.zeile, f.text_schluessel) for f in fehler] == [
        (2, "import.fehler.merkmal_zahl"), (3, "import.fehler.merkmal_auswahl"),
        (4, "import.fehler.merkmal_unbekannt_fuer_gruppe"), (5, "import.fehler.merkmal_unbekannt_fuer_gruppe")]
    assert [z.inventarnummer for z in zeilen] == ["M5"]
    fz = {**GUT, "Gruppe": "fahrzeug", "m:hu_faellig": "2027-05-01", "m:beheizt": None}
    zeilen, fehler = lese(tmp_path, [{**fz, "m:kennzeichen": "MZ-AB 1"}, {**fz, "Inventarnummer": "F2", "m:kennzeichen": "MZ-AB 2", "m:hu_faellig": "bald"}], extra)
    assert zeilen[0].merkmale == {"kennzeichen": "MZ-AB 1", "hu_faellig": "2027-05-01"}
    assert [(f.zeile, f.text_schluessel) for f in fehler] == [(3, "import.fehler.merkmal_datum")]


def test_I13_pflichtmerkmal_fehlt_und_ja_nein(tmp_path: Path):
    _, fehler = lese(tmp_path, [{**GUT, "Gruppe": "fahrzeug"}], extra=("m:kennzeichen",))
    assert schluessel(fehler) == [(2, "m:kennzeichen", "import.fehler.merkmal_pflicht_fehlt")]
    _, fehler = lese(tmp_path, [{**GUT, "Gruppe": "fahrzeug"}])  # Spalte fehlt ganz
    assert schluessel(fehler) == [(2, "m:kennzeichen", "import.fehler.merkmal_pflicht_fehlt")]
    extra = ("m:containertyp", "m:beheizt")
    co = {**GUT, "Gruppe": "container", "m:containertyp": "Büro"}
    zeilen, fehler = lese(tmp_path, [{**co, "m:beheizt": "Ja"}, {**co, "Inventarnummer": "C2", "m:beheizt": False},
                                     {**co, "Inventarnummer": "C3", "m:beheizt": "vielleicht"}], extra)
    assert [z.merkmale["beheizt"] for z in zeilen] == ["ja", "nein"]
    assert [f.text_schluessel for f in fehler] == ["import.fehler.merkmal_ja_nein"]


def test_I14_teilimport_und_leere_zeilen(tmp_path: Path):
    zeilen, fehler = lese(tmp_path, [GUT, {}, {**GUT, "Inventarnummer": "BM-2", "Kostenstelle": 5}, {**GUT, "Inventarnummer": "BM-3"}, {}, {}])
    assert [(z.zeile, z.inventarnummer) for z in zeilen] == [(2, "BM-00017"), (5, "BM-3")]
    assert [f.zeile for f in fehler] == [4]


def test_I15_kopf_muss_stimmen(tmp_path: Path):
    kopf = list(SPALTEN)
    kopf[0], kopf[1] = kopf[1], kopf[0]
    zeilen, fehler = lese(tmp_path, [GUT], kopf=kopf)
    assert zeilen == () and schluessel(fehler) == [(1, "", "import.fehler.kopf_ungueltig")]
    zeilen, fehler = lese(tmp_path, [GUT], extra=("Foo", "m:betriebsgewicht"))
    assert len(zeilen) == 1 and schluessel(fehler) == [(1, "Foo", "import.fehler.spalte_unbekannt")]


def test_I16_jeder_fehlerschluessel_ist_erreichbar(tmp_path: Path):
    extra = ("Foo", "m:betriebsgewicht", "m:schnellwechsler", "m:hu_faellig", "m:beheizt", "m:kennzeichen")
    zeilen = [
        {**GUT, "Inventarnummer": None}, {**GUT, "Inventarnummer": "G1", "Gruppe": "x"}, {**GUT, "Inventarnummer": "G2", "Art": "x"},
        {**GUT, "Inventarnummer": "G3", "Menge": 0, "Art": "menge"}, {**GUT, "Inventarnummer": "G4", "Menge": 3},
        {**GUT, "Inventarnummer": "G5", "Kostenstelle": "x"}, {**GUT, "Inventarnummer": "G6", "Kostenstelle": 7},
        {**GUT, "Inventarnummer": "G7", "Kaufpreis": "x"}, {**GUT, "Inventarnummer": "G8", "Kaufpreis": -1},
        {**GUT, "Inventarnummer": "G9", "Kaufdatum": "x"}, {**GUT, "Inventarnummer": "H1", "Baujahr": "x"},
        {**GUT, "Inventarnummer": "H2", "Baujahr": 1900}, {**GUT, "Inventarnummer": "H3"}, {**GUT, "Inventarnummer": "H3"},
        {**GUT, "Inventarnummer": "H4", "m:kennzeichen": "x"}, {**GUT, "Gruppe": "fahrzeug", "Inventarnummer": "H5"},
        {**GUT, "Inventarnummer": "H6", "m:betriebsgewicht": "x"}, {**GUT, "Gruppe": "fahrzeug", "Inventarnummer": "H7", "m:kennzeichen": "MZ-1", "m:hu_faellig": "x"},
        {**GUT, "Inventarnummer": "H8", "m:schnellwechsler": "x"}, {**GUT, "Gruppe": "container", "Inventarnummer": "H9", "m:beheizt": "x"},
    ]
    _, fehler = lese(tmp_path, zeilen, extra, muster=Muster("{gruppe}-{nr:5}"))
    _, kopf_fehler = lese(tmp_path, [GUT], kopf=["x"])
    gefunden = {f.text_schluessel for f in fehler} | {f.text_schluessel for f in kopf_fehler}
    assert gefunden == set(FEHLER_SCHLUESSEL)
