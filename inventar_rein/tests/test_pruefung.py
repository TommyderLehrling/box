"""Prueffaelle fuer pruefung (R1-R12)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from inventar_rein.kataloge import lade_pruefarten
from inventar_rein.pruefung import (
    Eintrag,
    Ueberschreibung,
    Zuordnung,
    eintragen,
    faellig_liste,
    gesamt_ampel,
    ohne_nachweis,
    pruefstand,
    zuordnungen_fuer,
)

HEUTE = date(2026, 10, 8)
DGUV = Zuordnung("dguv_v3", 12, None)
WARTUNG = Zuordnung("wartung_betriebsstunden", 12, 500)


def eintrag(art: str, tag: date, ergebnis: str = "bestanden", stand: D | None = None) -> Eintrag:
    return Eintrag(art, tag, ergebnis, stand)  # type: ignore[arg-type]


def test_R1_zuordnung_ueber_die_gruppe():
    arten = lade_pruefarten()
    fz = {z.pruefart for z in zuordnungen_fuer("fahrzeug", arten)}
    assert fz == {"feuerloescher", "hu", "uvv_fahrzeug", "tachograph", "sp_sicherheitspruefung", "verbandkasten"}
    bm = {z.pruefart: z for z in zuordnungen_fuer("baumaschine", arten)}
    assert bm["wartung_betriebsstunden"].zaehler_intervall == 500
    assert zuordnungen_fuer("vermessung", arten) == []


def test_R2_zuordnung_je_stueck_anpassen_und_abschalten():
    arten = lade_pruefarten()
    ueber = [Ueberschreibung("hu", intervall_monate=12), Ueberschreibung("tachograph", aktiv=False)]
    z = {x.pruefart: x for x in zuordnungen_fuer("fahrzeug", arten, ueber)}
    assert z["hu"].intervall_monate == 12 and "tachograph" not in z and z["uvv_fahrzeug"].intervall_monate == 12
    with pytest.raises(ValueError, match="intervall_ungueltig"):
        zuordnungen_fuer("fahrzeug", arten, [Ueberschreibung("hu", intervall_monate=0)])


def test_R3_eintragen_berechnet_die_naechste_faelligkeit():
    folge = eintragen(DGUV, date(2026, 8, 31), "bestanden", HEUTE)
    assert folge.naechste_am == date(2027, 8, 31) and folge.naechste_bei_zaehler is None
    folge = eintragen(WARTUNG, date(2026, 10, 1), "maengel", HEUTE, D("1200.5"))
    assert (folge.naechste_am, folge.naechste_bei_zaehler) == (date(2027, 10, 1), D("1700.5"))


def test_R4_nicht_bestanden_ist_sofort_wieder_faellig():
    folge = eintragen(DGUV, date(2026, 10, 7), "nicht_bestanden", HEUTE)
    assert folge.naechste_am == date(2026, 10, 7)


def test_R5_eintragen_prueft_die_eingabe():
    with pytest.raises(ValueError, match="ergebnis_unbekannt"):
        eintragen(DGUV, HEUTE, "gut", HEUTE)
    with pytest.raises(ValueError, match="datum_in_zukunft"):
        eintragen(DGUV, date(2026, 10, 9), "bestanden", HEUTE)
    with pytest.raises(ValueError, match="zaehlerstand_fehlt"):
        eintragen(WARTUNG, HEUTE, "bestanden", HEUTE)
    with pytest.raises(ValueError, match="zaehlerstand_ungueltig"):
        eintragen(WARTUNG, HEUTE, "bestanden", HEUTE, D("-1"))


def test_R6_stand_nach_datum_mit_ampel():
    gruen = pruefstand(DGUV, eintrag("dguv_v3", date(2026, 1, 15)), HEUTE)
    assert (gruen.faellig_am, gruen.ampel, gruen.grund) == (date(2027, 1, 15), "gruen", "datum")
    gelb = pruefstand(DGUV, eintrag("dguv_v3", date(2025, 10, 20)), HEUTE)
    assert (gelb.faellig_am, gelb.tage, gelb.ampel) == (date(2026, 10, 20), 12, "gelb")
    rot = pruefstand(DGUV, eintrag("dguv_v3", date(2025, 10, 8)), HEUTE)
    assert (rot.faellig_am, rot.tage, rot.ampel) == (HEUTE, 0, "rot")  # am Faelligkeitstag rot


def test_R7_zaehler_kann_frueher_faellig_machen():
    letzte = eintrag("wartung_betriebsstunden", date(2026, 3, 1), stand=D("1000"))
    ruhig = pruefstand(WARTUNG, letzte, HEUTE, zaehler_jetzt=D("1200"))
    assert (ruhig.ampel, ruhig.grund, ruhig.faellig_bei_zaehler, ruhig.zaehler_rest) == ("gruen", "datum", D("1500"), D("300"))
    gelb = pruefstand(WARTUNG, letzte, HEUTE, zaehler_jetzt=D("1460"))
    assert (gelb.ampel, gelb.grund, gelb.zaehler_rest) == ("gelb", "zaehler", D("40"))
    rot = pruefstand(WARTUNG, letzte, HEUTE, zaehler_jetzt=D("1500"))
    assert (rot.ampel, rot.grund, rot.zaehler_rest) == ("rot", "zaehler", D("0"))
    ueber = pruefstand(WARTUNG, letzte, HEUTE, zaehler_jetzt=D("1620.5"))
    assert ueber.zaehler_rest == D("-120.5") and ueber.ampel == "rot"


def test_R8_datum_kann_trotz_ruhigem_zaehler_rot_sein():
    letzte = eintrag("wartung_betriebsstunden", date(2025, 6, 1), stand=D("1000"))
    stand = pruefstand(WARTUNG, letzte, HEUTE, zaehler_jetzt=D("1100"))
    assert (stand.ampel, stand.grund) == ("rot", "datum")
    ohne_zaehler = pruefstand(WARTUNG, eintrag("wartung_betriebsstunden", date(2026, 3, 1)), HEUTE, zaehler_jetzt=D("9999"))
    assert ohne_zaehler.faellig_bei_zaehler is None and ohne_zaehler.ampel == "gruen"  # kein Stand bei der Pruefung bekannt


def test_R9_nie_geprueft_ist_unbekannt_und_nicht_bestanden_rot():
    neu = pruefstand(DGUV, None, HEUTE)
    assert (neu.grund, neu.faellig_am, neu.tage, neu.ampel) == ("nie_geprueft", None, None, "unbekannt")
    durchgefallen = pruefstand(DGUV, eintrag("dguv_v3", date(2026, 10, 1), "nicht_bestanden"), HEUTE)
    assert (durchgefallen.grund, durchgefallen.ampel, durchgefallen.tage) == ("nicht_bestanden", "rot", -7)
    with pytest.raises(ValueError, match="pruefart_passt_nicht"):
        pruefstand(DGUV, eintrag("hu", HEUTE), HEUTE)


def test_R13_unbekannt_ist_nicht_gruen_und_hat_einen_eigenen_block():
    unbekannt = pruefstand(DGUV, None, HEUTE)
    gruen = pruefstand(DGUV, eintrag("dguv_v3", date(2026, 10, 1)), HEUTE)
    gelb = pruefstand(DGUV, eintrag("dguv_v3", date(2025, 10, 20)), HEUTE)
    assert gesamt_ampel([gruen, unbekannt]) == "unbekannt"
    assert gesamt_ampel([gruen, unbekannt, gelb]) == "gelb"
    staende = [("B-2", unbekannt), ("B-1", unbekannt), ("B-3", gelb), ("B-4", gruen)]
    assert [n for n, _ in faellig_liste(staende)] == ["B-3"]
    assert [n for n, _ in ohne_nachweis(staende)] == ["B-1", "B-2"]


def test_R10_gesamt_ampel_ist_die_schlechteste():
    gruen = pruefstand(DGUV, eintrag("dguv_v3", date(2026, 9, 1)), HEUTE, HEUTE)
    gelb = pruefstand(DGUV, eintrag("dguv_v3", date(2025, 10, 20)), HEUTE, HEUTE)
    rot = pruefstand(DGUV, eintrag("dguv_v3", date(2024, 1, 1)), HEUTE, HEUTE)
    assert gesamt_ampel([]) == "gruen"
    assert gesamt_ampel([gruen, gelb]) == "gelb"
    assert gesamt_ampel([gruen, gelb, rot]) == "rot"


def test_R11_faellig_liste_sortiert_rot_vor_gelb_dann_nach_datum():
    def stand(nummer: str, tag: date):
        return nummer, pruefstand(DGUV, eintrag("dguv_v3", tag), HEUTE, HEUTE)
    liste = [stand("B", date(2026, 9, 1)),  # gruen, faellt raus
             stand("C", date(2025, 10, 25)),  # gelb 25.10.
             stand("A", date(2025, 10, 20)),  # gelb 20.10.
             stand("E", date(2025, 5, 1)),  # rot 1.5.
             stand("D", date(2025, 9, 1))]  # rot 1.9.
    assert [n for n, _ in faellig_liste(liste)] == ["E", "D", "A", "C"]
    assert [n for n, _ in faellig_liste(liste, nur=("rot",))] == ["E", "D"]
    assert len(faellig_liste(liste, nur=("gruen", "gelb", "rot"))) == 5


def test_R12_eingabe_bleibt_unveraendert_und_ergebnisse_sind_wiederholbar():
    letzte = eintrag("dguv_v3", date(2026, 1, 15))
    erster = pruefstand(DGUV, letzte, HEUTE, date(2025, 1, 1))
    assert pruefstand(DGUV, letzte, HEUTE, date(2025, 1, 1)) == erster
    assert letzte == eintrag("dguv_v3", date(2026, 1, 15))
