"""Prueffaelle fuer kataloge (K1-K10)."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from inventar_rein import kataloge as k


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
        gruppen, merkmale, pruefarten + [pruefarten[8]]
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
    assert "pruefart.gruppe_unbekannt:dguv_v3:gibt_es_nicht" in k.pruefe_kataloge(
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
    assert "pruefart.intervall_ungueltig:dguv_v3" in k.pruefe_kataloge(
        gruppen, merkmale, [replace(p, intervall_monate=0)]
    )
    assert "pruefart.zaehler_intervall_ungueltig:dguv_v3" in k.pruefe_kataloge(
        gruppen, merkmale, [replace(p, zaehler_intervall=0)]
    )
    assert "pruefart.durchfuehrung_unbekannt:dguv_v3:amtlich" in k.pruefe_kataloge(
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
    dguv = next(p for p in pruefarten if p.schluessel == "dguv_v3")
    assert set(dguv.gruppen) == {"elektro", "kleingeraet", "it", "bueroausstattung"}

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
