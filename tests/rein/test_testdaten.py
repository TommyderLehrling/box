"""Prueffaelle fuer testdaten (T1-T11)."""
from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from digiassistenz_inventar.rein.fristen import ampel, naechste_faelligkeit
from digiassistenz_inventar.rein.import_vorlage import SPALTEN, lies
from digiassistenz_inventar.rein.kataloge import lade_gruppen, lade_merkmale, lade_pruefarten
from digiassistenz_inventar.rein.nummernformat import Muster, entspricht
from digiassistenz_inventar.rein.testdaten import GEWICHTE, STANDARD_ANZAHL, erzeuge

GRUPPEN, MERKMALE, PRUEFARTEN = lade_gruppen(), lade_merkmale(), lade_pruefarten()
KS = [100, 200, 300, 400, 500]
STICHTAG = date(2026, 10, 8)
MUSTER = Muster("{gruppe}-{nr:5}")


def daten(seed: int = 1, anzahl: int = STANDARD_ANZAHL, muster: Muster = MUSTER):
    return erzeuge(seed, anzahl, GRUPPEN, MERKMALE, PRUEFARTEN, KS, muster, STICHTAG)


@pytest.fixture(scope="module")
def gross():
    return daten()


def anteil(zaehler: int, gesamt: int) -> float:
    return 100 * zaehler / gesamt


def test_T1_anzahl_stimmt(gross):
    assert STANDARD_ANZAHL == 2500
    assert len(gross.stuecke) == 2500
    assert len(daten(2, 37).stuecke) == 37
    assert len(daten(3, 1).stuecke) == 1


def test_T2_verteilung_auf_gruppen_plus_minus_zwei_prozent(gross):
    n = len(gross.stuecke)
    je = Counter(z.gruppe for z in gross.stuecke)
    eimer = {"baumaschine": 8, "fahrzeug": 6, ("kleingeraet", "werkzeug", "elektro"): 50,
             ("container", "schalung_ruestung"): 10, ("bueroausstattung", "it"): 20,
             ("anbaugeraet", "vermessung", "hebezeug_anschlag"): 6}
    for gruppen, soll in eimer.items():
        gruppen = (gruppen,) if isinstance(gruppen, str) else gruppen
        assert abs(anteil(sum(je[g] for g in gruppen), n) - soll) <= 2, gruppen
    assert set(je) == set(GEWICHTE)


@pytest.mark.parametrize("muster", ["{nr:5}", "{gruppe}-{nr:5}", "G-{jahr}-{nr:4}", "{jahr2}/{gruppe}/{nr:3}"])
def test_T3_nummern_eindeutig_und_musterkonform(muster):
    m = Muster(muster)
    d = daten(5, 600, m)
    nummern = [z.inventarnummer for z in d.stuecke]
    assert len(set(nummern)) == len(nummern)
    assert all(entspricht(m, n) for n in nummern)


def test_T4_determinismus():
    assert daten(7, 300) == daten(7, 300)
    assert daten(7, 300) != daten(8, 300)


def test_T5_stuecke_bestehen_den_import(tmp_path: Path):
    d = daten(11, 400)
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventar"
    namen = sorted({k for z in d.stuecke for k in z.merkmale})
    ws.append(list(SPALTEN) + [f"m:{k}" for k in namen])
    for z in d.stuecke:
        ws.append([z.inventarnummer, z.bezeichnung, z.gruppe, z.art, z.hersteller, z.typ, z.seriennummer, z.baujahr,
                   z.kaufdatum.strftime("%d.%m.%Y"), str(z.kaufpreis), z.lieferant, z.kostenstelle, z.menge,
                   z.besonderheiten] + [z.merkmale.get(k) for k in namen])
    datei = tmp_path / "test.xlsx"
    wb.save(datei)
    zeilen, fehler = lies(datei, GRUPPEN, MERKMALE, KS, MUSTER, STICHTAG)
    assert fehler == () and len(zeilen) == 400
    assert [z.inventarnummer for z in zeilen] == [z.inventarnummer for z in d.stuecke]


def test_T6_namen_hersteller_und_keine_echten_seriennummern(gross):
    assert all(z.seriennummer.startswith("TEST-") for z in gross.stuecke)
    assert len({z.bezeichnung for z in gross.stuecke}) > 30
    assert {"Hydraulikbagger 21 t", "Nivelliergerät", "Bürocontainer 20 ft"} <= {z.bezeichnung for z in gross.stuecke}
    assert len({z.hersteller for z in gross.stuecke}) >= 5
    assert all(z.kostenstelle in KS and z.bezeichnung for z in gross.stuecke)


def test_T7_kaufdaten_preise_und_arten(gross):
    for z in gross.stuecke:
        assert 0 < (STICHTAG - z.kaufdatum).days <= 3650
        assert z.kaufpreis > 0 and 1950 <= z.baujahr <= z.kaufdatum.year
        assert (z.menge > 1) == (z.art == "menge") or z.menge == 1
    bm = [z.kaufpreis for z in gross.stuecke if z.gruppe == "baumaschine"]
    wz = [z.kaufpreis for z in gross.stuecke if z.gruppe == "werkzeug"]
    assert min(bm) >= 25000 and max(wz) <= 1200
    assert {z.art for z in gross.stuecke if z.gruppe in ("baumaschine", "fahrzeug")} == {"gross"}
    assert {"gross", "klein", "menge"} <= {z.art for z in gross.stuecke}


def test_T8_besonderheiten_etwa_ein_fuenftel(gross):
    mit = sum(1 for z in gross.stuecke if z.besonderheiten)
    assert abs(anteil(mit, len(gross.stuecke)) - 20) <= 1


def test_T9_transfers_etwa_fuenf_prozent_angekuendigt(gross):
    n = len(gross.stuecke)
    assert abs(anteil(len(gross.transfers), n) - 5) <= 1
    nach_nummer = {z.inventarnummer: z for z in gross.stuecke}
    for t in gross.transfers:
        z = nach_nummer[t.stueck]
        assert t.status == "angekuendigt" and t.von_kostenstelle == z.kostenstelle != t.nach_kostenstelle
        assert 1 <= t.menge <= z.menge and t.abgang_am.tzinfo is not None
        assert t.beendet_am is None and t.eingang_schluessel is None
    assert len({t.id for t in gross.transfers}) == len(gross.transfers)


def test_T10_pruefungen_je_zugeordneter_pruefart_mit_ampelverteilung(gross):
    soll = Counter((z.inventarnummer, p.schluessel) for z in gross.stuecke for p in PRUEFARTEN if z.gruppe in p.gruppen)
    assert Counter((n, a) for n, a, _, _ in gross.pruefungen) == soll
    intervall = {p.schluessel: p.intervall_monate for p in PRUEFARTEN}
    kauf = {z.inventarnummer: z.kaufdatum for z in gross.stuecke}
    for nummer, art, durchgefuehrt, faellig in gross.pruefungen:
        assert faellig == naechste_faelligkeit(durchgefuehrt, intervall[art])
        assert kauf[nummer] <= durchgefuehrt <= STICHTAG
    farben = Counter(ampel(f, STICHTAG) for *_, f in gross.pruefungen)
    n = len(gross.pruefungen)
    assert abs(anteil(farben["rot"], n) - 8) <= 2
    assert abs(anteil(farben["gelb"], n) - 10) <= 2


def test_T11_zaehlerstaende_nur_fuer_gross(gross):
    art = {z.inventarnummer: z.art for z in gross.stuecke}
    assert gross.zaehlerstaende and all(art[n] == "gross" for n, _, _ in gross.zaehlerstaende)
    assert {n for n, _, _ in gross.zaehlerstaende} == {n for n, a in art.items() if a == "gross"}
    je: dict[str, list[tuple[Decimal, date]]] = {}
    for n, stand, tag in gross.zaehlerstaende:
        je.setdefault(n, []).append((stand, tag))
    for staende in je.values():
        assert len(staende) == 2
        (s1, t1), (s2, t2) = staende
        assert t1 < t2 <= STICHTAG and 0 < s1 < s2


def test_T12_ungueltige_eingabe():
    for kw in ({"anzahl": 0}, {"kostenstellen": []}, {"gruppen": []}):
        args = {"seed": 1, "anzahl": 10, "gruppen": GRUPPEN, "merkmale": MERKMALE, "pruefarten": PRUEFARTEN,
                "kostenstellen": KS, "muster": MUSTER, "stichtag": STICHTAG, **kw}
        with pytest.raises(ValueError, match="testdaten.eingabe_ungueltig"):
            erzeuge(**args)


def test_T16_namenslisten_kommen_aus_der_datei_und_sind_unveraenderlich(tmp_path):
    from digiassistenz_inventar.rein.testdaten import lade_namen
    n = lade_namen()
    assert n["namen"]["baumaschine"][0] == "Hydraulikbagger 21 t" and isinstance(n["hersteller"], tuple)
    kaputt = tmp_path / "n.json"
    kaputt.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="namen_feld_fehlt"):
        lade_namen(kaputt)
    with pytest.raises(ValueError, match="namen_unlesbar"):
        lade_namen(tmp_path / "gibt_es_nicht.json")
