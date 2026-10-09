"""Prueffaelle fuer beispielbetrieb (E1-E9): 50 Stuecke, eigener Import, Zustaende nach Spec Abschnitt 16."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from inventar_rein.bestand import StueckInfo, bestand
from inventar_rein.beispielbetrieb import lade_beispielbetrieb, pruefstaende, schreibe_importdatei, zustaende
from inventar_rein.import_plan import plane
from inventar_rein.import_vorlage import lies
from inventar_rein.kataloge import lade_gruppen, lade_merkmale, lade_pruefarten
from inventar_rein.nummernformat import Muster
from inventar_rein.pruefung import gesamt_ampel
from inventar_rein.transfer import scan_ist_hier, status_auf, ueberfaellige

B = lade_beispielbetrieb()
Z = zustaende(B)
HEUTE = B.heute
BAUHOF, BAU_A, BAU_B, WERKSTATT, BUERO = 1000, 79795, 80010, 2000, 3000
ZONE = timezone(timedelta(hours=2))
BAGGER = "BM-04711"


def offen(nummer: str) -> list[tuple[int, int]]:
    return sorted((s.kostenstelle, s.menge) for s in Z[nummer].standorte if s.bis is None)


def test_E1_fuenfzig_stuecke_stimmig_mit_den_katalogen():
    assert len(B.stuecke) == 50 and B.heute == date(2026, 10, 9)
    gruppen = {g.schluessel for g in lade_gruppen()}
    arten = {p.schluessel: p for p in lade_pruefarten()}
    nummern = {s.zeile.inventarnummer for s in B.stuecke}
    assert len(nummern) == 50 and {s.zeile.gruppe for s in B.stuecke} == gruppen
    for s in B.stuecke:
        assert all(s.zeile.gruppe in arten[k].gruppen for k in s.pruefarten), s.zeile.inventarnummer
    assert {k.nummer for k in B.kostenstellen} == {1000, 79795, 80010, 2000, 3000}
    assert [p.kennung for p in B.personen] == ["polier.eins", "polier.zwei", "dispo", "werkstatt"]
    assert all(n in nummern for n, _ in B.pruefungen) and all(n in nummern for n, *_ in B.zaehlerstaende)


def test_E2_beispielbetrieb_besteht_den_eigenen_import(tmp_path: Path):
    datei = tmp_path / "beispiel.xlsx"
    schreibe_importdatei(B, datei, lade_merkmale())
    zeilen, fehler = lies(datei, lade_gruppen(), lade_merkmale(), [k.nummer for k in B.kostenstellen],
                          Muster("{gruppe}-{nr:5}"), HEUTE)
    assert fehler == ()
    assert zeilen == tuple(s.zeile for s in B.stuecke)
    zweiter_lauf = plane(zeilen, {z.inventarnummer: z for z in zeilen})
    assert zweiter_lauf.neu == () and len(zweiter_lauf.unveraendert) == 50 and zweiter_lauf.abweichend == ()


def test_E3_bagger_4711_ist_auf_79795_angekuendigt_und_nicht_vor_ort():
    assert offen(BAGGER) == [(BAUHOF, 1)]
    angekuendigt = [t for t in Z[BAGGER].transfers if t.status == "angekuendigt"]
    assert [(t.von_kostenstelle, t.nach_kostenstelle, t.abgang_von, t.quelle) for t in angekuendigt] == [
        (BAUHOF, BAU_A, "dispo", "web")]
    assert status_auf(Z[BAGGER], BAU_A, HEUTE) == ((1, "angekuendigt"),)
    assert status_auf(Z[BAGGER], BAUHOF, HEUTE) == ((1, "vor_ort"),)
    # Tieflöffel gehoert zum Bagger und ist mit angekuendigt
    assert [(t.nach_kostenstelle, t.quelle) for t in Z["AG-00001"].transfers] == [(BAU_A, "system")]


def test_E4_abschnitt_16_scan_und_dritter_ort():
    erste = scan_ist_hier(Z[BAGGER], BAGGER, BAU_A, "polier.eins", datetime(2026, 10, 9, 8, tzinfo=ZONE), "handy", "neu-1")
    assert offen_von(erste.zustand) == [(BAU_A, 1)]
    assert [s.kostenstelle for s in erste.zustand.standorte if s.bis is not None] == [BAUHOF]
    zweite = scan_ist_hier(erste.zustand, BAGGER, BAU_B, "polier.zwei", datetime(2026, 10, 9, 9, tzinfo=ZONE), "handy", "neu-2")
    system = zweite.zustand.transfers[-1]
    assert (system.von_kostenstelle, system.nach_kostenstelle, system.status, system.quelle) == (BAU_A, BAU_B, "bestaetigt", "system")
    assert offen_von(zweite.zustand) == [(BAU_B, 1)]


def offen_von(z) -> list[tuple[int, int]]:
    return sorted((s.kostenstelle, s.menge) for s in z.standorte if s.bis is None)


def test_E5_bestand_dienst_trennt_vor_ort_und_angekuendigt():
    infos = [(StueckInfo(s.zeile.inventarnummer, s.zeile.bezeichnung, s.zeile.gruppe, s.zeile.gruppe, s.zeile.art, s.status),
              Z[s.zeile.inventarnummer]) for s in B.stuecke]
    auf_a = bestand(infos, BAU_A, None, HEUTE)
    zeile = [r for r in auf_a if r["inventarnummer"] == BAGGER]
    assert [r["status"] for r in zeile] == ["angekuendigt"]
    assert not [r for r in auf_a if r["inventarnummer"] == "KG-00006" or r["inventarnummer"] == "BM-00006"]


def test_E6_pruefstaende_zeigen_die_faelle():
    stand = pruefstaende(B, lade_pruefarten())

    def ampel(nummer: str, art: str | None = None) -> str:
        zeilen = [s for s in stand[nummer] if art is None or s.pruefart == art]
        return gesamt_ampel(zeilen)

    assert ampel("KG-00001") == "rot" and stand["KG-00001"][0].tage < 0          # Ruettelplatte ueberfaellig
    assert ampel("KG-00002") == "gruen" and ampel("KG-00003") == "gelb"
    radlader = next(s for s in stand["BM-00003"] if s.pruefart == "wartung_betriebsstunden")
    assert (radlader.ampel, radlader.grund) == ("gelb", "zaehler")                 # Zaehler 1480 von 1500
    assert ampel("BM-00004") == "unbekannt" and ampel("HZ-00003") == "unbekannt"
    assert (ampel("FZ-00001", "hu"), ampel("FZ-00002", "hu"), ampel("FZ-00003", "hu")) == ("gelb", "rot", "gruen")
    zaehlung = Counter(s.ampel for staende in stand.values() for s in staende)
    assert zaehlung["rot"] == 2 and zaehlung["unbekannt"] == 3 and zaehlung["gelb"] == 3


def test_E7_mengen_und_fehlmenge_und_ueberfaelliger_transfer():
    assert offen("SR-00001") == [(BAU_A, 25), (BAU_B, 15)]
    assert offen("WZ-00001") == [(BAUHOF, 7), (BAU_A, 8)]
    fehl = [t for t in Z["WZ-00001"].transfers if t.status == "angekuendigt"]
    assert [(t.menge, t.grund) for t in fehl] == [(2, "transfer.fehlmenge")]
    alle = [t for z in Z.values() for t in ueberfaellige(z, HEUTE, 3)]
    assert [t.stueck for t in alle] == ["EL-00001"]           # Fehlmenge (2 Werktage) und Bagger (1 Werktag) noch nicht
    assert offen("KG-00001") == [(BAU_B, 1)] and Z["KG-00001"].transfers[0].quelle == "system"


def test_E8_werkstatt_vermisst_miete_zubehoer():
    meldungen = {n: m for n, m in B.meldungen}
    assert (meldungen["KG-00004"].status, meldungen["KG-00005"].status) == ("in_arbeit", "offen")
    assert [(n, r.status) for n, r in B.reparaturen] == [("KG-00004", "in_arbeit")]
    status = {s.zeile.inventarnummer: s.status for s in B.stuecke}
    assert (status["KG-00004"], status["KG-00006"]) == ("in_reparatur", "vermisst")
    assert Counter(status.values()) == Counter({"aktiv": 48, "in_reparatur": 1, "vermisst": 1})
    miete = next(s for s in B.stuecke if s.zeile.inventarnummer == "BM-00005").miete
    assert miete is not None and (miete.von, miete.bis) == (date(2026, 9, 1), date(2026, 11, 30))
    assert B.zubehoer == (("AG-00001", BAGGER), ("AG-00003", "BM-00002"))
    assert offen("AG-00003") == [(BAU_A, 1)]


def test_E9_fehler_im_beispielbetrieb_werden_gemeldet(tmp_path: Path):
    with pytest.raises(ValueError, match="datei_unlesbar"):
        lade_beispielbetrieb(tmp_path / "gibt_es_nicht.json")
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="datei_unlesbar"):
        lade_beispielbetrieb(kaputt)
