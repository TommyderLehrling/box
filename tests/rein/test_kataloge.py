"""Prueffaelle fuer kataloge (K1-K12)."""
from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from digiassistenz_inventar.rein import kataloge as k


@pytest.fixture()
def katalog() -> tuple[list[k.Gruppe], list[k.Merkmal], list[k.Pruefart]]:
    return k.lade_gruppen(), k.lade_merkmale(), k.lade_pruefarten()


def test_K1_startkataloge_sind_in_ordnung(katalog):
    assert k.pruefe_kataloge(*katalog) == []


def test_K2_umfang_der_startkataloge(katalog):
    gruppen, merkmale, pruefarten = katalog
    assert len(gruppen) == 12
    assert len(merkmale) >= 40
    assert len(pruefarten) >= 10
    for g in gruppen:
        anzahl = sum(1 for m in merkmale if m.gruppe == g.schluessel)
        assert 2 <= anzahl <= 6, g.schluessel


def test_K3_schluessel_doppelt(katalog):
    gruppen, merkmale, pruefarten = katalog
    assert "gruppe.schluessel_doppelt:fahrzeug" in k.pruefe_kataloge(
        gruppen + [replace(gruppen[1], kuerzel="XX")], merkmale, pruefarten
    )
    assert "merkmal.schluessel_doppelt:kennzeichen" in k.pruefe_kataloge(
        gruppen, merkmale + [merkmale[5]], pruefarten
    )
    assert "pruefart.schluessel_doppelt:hu" in k.pruefe_kataloge(
        gruppen, merkmale, pruefarten + [next(p for p in pruefarten if p.schluessel == "hu")]
    )


def test_K4_merkmal_zeigt_auf_unbekannte_gruppe(katalog):
    gruppen, merkmale, pruefarten = katalog
    kaputt = merkmale + [replace(merkmale[0], schluessel="neu", gruppe="gibt_es_nicht")]
    assert "merkmal.gruppe_unbekannt:neu:gibt_es_nicht" in k.pruefe_kataloge(
        gruppen, kaputt, pruefarten
    )


def test_K5_pruefart_zeigt_auf_unbekannte_gruppe(katalog):
    gruppen, merkmale, pruefarten = katalog
    kaputt = [replace(pruefarten[0], gruppen=("elektro", "gibt_es_nicht"))]
    assert "pruefart.gruppe_unbekannt:dguv_v3_baustelle:gibt_es_nicht" in k.pruefe_kataloge(
        gruppen, merkmale, kaputt
    )


def test_K6_auswahl_nur_bei_typ_auswahl_und_dann_nicht_leer(katalog):
    gruppen, merkmale, pruefarten = katalog
    leer = replace(merkmale[0], schluessel="a1", typ="auswahl", auswahl=())
    unerwartet = replace(merkmale[0], schluessel="a2", typ="text", auswahl=("x",))
    doppelt = replace(merkmale[0], schluessel="a3", typ="auswahl", auswahl=("x", "x"))
    unbekannt = replace(merkmale[0], schluessel="a4", typ="farbe")
    fehler = k.pruefe_kataloge(gruppen, [leer, unerwartet, doppelt, unbekannt], pruefarten)
    assert "merkmal.auswahl_leer:a1" in fehler
    assert "merkmal.auswahl_unerwartet:a2" in fehler
    assert "merkmal.auswahl_doppelt:a3" in fehler
    assert "merkmal.typ_unbekannt:a4:farbe" in fehler


def test_K7_intervalle_und_durchfuehrung(katalog):
    gruppen, merkmale, pruefarten = katalog
    p = pruefarten[0]
    assert "pruefart.intervall_ungueltig:dguv_v3_baustelle" in k.pruefe_kataloge(
        gruppen, merkmale, [replace(p, intervall_monate=0)]
    )
    assert "pruefart.zaehler_intervall_ungueltig:dguv_v3_baustelle" in k.pruefe_kataloge(
        gruppen, merkmale, [replace(p, zaehler_intervall=0)]
    )
    assert "pruefart.durchfuehrung_unbekannt:dguv_v3_baustelle:amtlich" in k.pruefe_kataloge(
        gruppen, merkmale, [replace(p, durchfuehrung="amtlich")]
    )


def test_K8_kuerzel_zwei_grossbuchstaben_und_eindeutig(katalog):
    gruppen, merkmale, pruefarten = katalog
    for schlecht in ("B", "BMX", "bm", "B1"):
        fehler = k.pruefe_kataloge([replace(gruppen[0], kuerzel=schlecht)], [], [])
        assert f"gruppe.kuerzel_ungueltig:baumaschine:{schlecht}" in fehler
    doppelt = [gruppen[0], replace(gruppen[1], kuerzel=gruppen[0].kuerzel)]
    assert "gruppe.kuerzel_doppelt:BM" in k.pruefe_kataloge(doppelt, [], [])


def test_K9_oben_muss_existieren(katalog):
    gruppen, merkmale, pruefarten = katalog
    kaputt = [replace(gruppen[0], oben="nirgends")]
    assert "gruppe.oben_unbekannt:baumaschine:nirgends" in k.pruefe_kataloge(kaputt, [], [])


def test_K10_lader_und_inhalt(katalog, tmp_path: Path):
    gruppen, merkmale, pruefarten = katalog
    assert all(g.oben is None for g in gruppen)
    kennzeichen = next(m for m in merkmale if m.schluessel == "kennzeichen")
    assert (kennzeichen.gruppe, kennzeichen.typ, kennzeichen.pflicht) == ("fahrzeug", "text", True)
    wartung = next(p for p in pruefarten if p.schluessel == "wartung_betriebsstunden")
    assert (wartung.intervall_monate, wartung.zaehler_intervall) == (12, 500)
    assert {"druckbehaelter_innen", "druckbehaelter_festigkeit"} <= {p.schluessel for p in pruefarten}
    baustelle = next(p for p in pruefarten if p.schluessel == "dguv_v3_baustelle")
    buero = next(p for p in pruefarten if p.schluessel == "dguv_v3_buero")
    assert (baustelle.intervall_monate, set(baustelle.gruppen)) == (3, {"elektro", "kleingeraet", "werkzeug"})
    assert (buero.intervall_monate, set(buero.gruppen)) == (24, {"it", "bueroausstattung"})
    assert "dguv_v3" not in {p.schluessel for p in pruefarten}
    nach = {p.schluessel: p for p in pruefarten}
    assert (nach["druckbehaelter_innen"].intervall_monate, nach["druckbehaelter_festigkeit"].intervall_monate,
            nach["druckbehaelter_aussen"].intervall_monate) == (60, 120, 24)
    assert (nach["hu"].intervall_monate, nach["sp_sicherheitspruefung"].intervall_monate) == (12, 6)
    assert (nach["kran"].intervall_monate, nach["hubarbeitsbuehne"].intervall_monate) == (12, 12)
    assert (nach["verbandkasten"].intervall_monate, nach["baustromverteiler"].gruppen) == (60, ("elektro",))
    klasse = next(m for m in merkmale if m.schluessel == "fahrzeugklasse")
    assert klasse.auswahl == ("pkw", "lkw_bis_3_5", "lkw_ueber_3_5", "anhaenger")

    fehlt = tmp_path / "gruppen.json"
    fehlt.write_text(json.dumps([{"schluessel": "x"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="kataloge.feld_fehlt"):
        k.lade_gruppen(fehlt)
    falsch = tmp_path / "falsch.json"
    falsch.write_text(json.dumps([{"schluessel": 5, "bezeichnung": "a", "kuerzel": "AA", "sortierung": 1}]))
    with pytest.raises(ValueError, match="kataloge.feld_typ"):
        k.lade_gruppen(falsch)
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="kataloge.datei_unlesbar"):
        k.lade_merkmale(kaputt)
    keine_liste = tmp_path / "objekt.json"
    keine_liste.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="kataloge.datei_form"):
        k.lade_pruefarten(keine_liste)
    with pytest.raises(ValueError, match="kataloge.datei_unlesbar"):
        k.lade_gruppen(tmp_path / "gibt_es_nicht.json")


def test_K11_bauteilkatalog_form_lader_und_passt_zu(tmp_path: Path):
    assert k.lade_bauteile() == []  # Startkatalog ist leer, nur die Form
    datei = tmp_path / "bauteile.json"
    datei.write_text(json.dumps([
        {"bauteilnummer": "HF-100", "bezeichnung": "Hydraulikfilter", "hersteller": "Teramax", "lieferant": "Weber",
         "preis_zuletzt": "49.90", "passt_zu_gruppen": ["baumaschine"]},
        {"bauteilnummer": "ZR-7", "bezeichnung": "Zahnriemen", "passt_zu_stuecke": ["BM-00017"]},
    ]), encoding="utf-8")
    bauteile = k.lade_bauteile(datei)
    assert bauteile[0].preis_zuletzt == Decimal("49.90") and bauteile[1].preis_zuletzt is None
    assert k.pruefe_bauteile(bauteile, k.lade_gruppen()) == []
    assert [b.bauteilnummer for b in k.passende_bauteile(bauteile, "baumaschine", "BM-00001")] == ["HF-100"]
    assert [b.bauteilnummer for b in k.passende_bauteile(bauteile, "baumaschine", "BM-00017")] == ["HF-100", "ZR-7"]
    assert k.passende_bauteile(bauteile, "it", "IT-00001") == []


def test_K12_bauteilkatalog_pruefung(tmp_path: Path):
    gruppen = k.lade_gruppen()
    b = k.Bauteil("A", "Teil", "", "", Decimal("1"), "", ("baumaschine",), ())
    kaputt = [replace(b, bauteilnummer=" ", bezeichnung=""), replace(b, preis_zuletzt=Decimal("-1")),
              replace(b, bauteilnummer="C", passt_zu_gruppen=()), replace(b, bauteilnummer="D", passt_zu_gruppen=("x",)),
              replace(b, bauteilnummer="E"), replace(b, bauteilnummer="E")]
    fehler = k.pruefe_bauteile(kaputt, gruppen)
    for erwartet in ("bauteil.nummer_leer", "bauteil.bezeichnung_leer: ", "bauteil.preis_negativ:A",
                     "bauteil.passt_zu_nichts:C", "bauteil.gruppe_unbekannt:D:x", "bauteil.nummer_doppelt:E"):
        assert erwartet in fehler, erwartet
    schlecht = tmp_path / "schlecht.json"
    schlecht.write_text(json.dumps([{"bauteilnummer": "X", "bezeichnung": "y", "preis_zuletzt": "viel"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="kataloge.feld_typ"):
        k.lade_bauteile(schlecht)


def test_K13_intervall_je_merkmal_wird_geprueft_und_gruppe_pruefart_kommt_aus_dem_katalog():
    gruppen, merkmale, pruefarten = k.lade_gruppen(), k.lade_merkmale(), k.lade_pruefarten()
    assert k.pruefe_kataloge(gruppen, merkmale, pruefarten) == []
    hu = next(p for p in pruefarten if p.schluessel == "hu")
    assert hu.intervall_je_merkmal["fahrzeugklasse"]["pkw"] == 24
    schlecht = [replace(hu, intervall_je_merkmal={"gibt_es_nicht": {"x": 3}})]
    assert k.pruefe_kataloge(gruppen, merkmale, schlecht) == ["pruefart.merkmal_unbekannt:hu:gibt_es_nicht"]
    schlecht = [replace(hu, intervall_je_merkmal={"fahrzeugklasse": {"ufo": 3}})]
    assert k.pruefe_kataloge(gruppen, merkmale, schlecht) == ["pruefart.merkmal_wert_unbekannt:hu:fahrzeugklasse:ufo"]
    schlecht = [replace(hu, intervall_je_merkmal={"fahrzeugklasse": {"pkw": 0}})]
    assert k.pruefe_kataloge(gruppen, merkmale, schlecht) == ["pruefart.intervall_je_merkmal_ungueltig:hu:fahrzeugklasse"]
    paare = k.gruppe_pruefart(pruefarten)
    assert ("fahrzeug", "hu") in paare and ("baumaschine", "uvv_erdbau") in paare
    assert len(paare) == sum(len(p.gruppen) for p in pruefarten)
