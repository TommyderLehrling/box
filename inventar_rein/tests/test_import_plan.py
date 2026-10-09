"""Prueffaelle fuer import_plan (M1-M6)."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from inventar_rein.import_plan import plane
from inventar_rein.import_vorlage import ImportZeile


def zeile(nr: str, gruppe: str = "baumaschine", art: str = "gross", **felder) -> ImportZeile:
    basis = ImportZeile(2, nr, "Bagger", gruppe, art, "Teramax", "AB-100", "TEST-1", 2020, date(2020, 3, 15), D("1000"),
                        "Weber", 100, 1, "", {"betriebsgewicht": "21"})
    return replace(basis, **felder)


def test_M1_erster_lauf_alles_neu_mit_bericht():
    zeilen = [zeile("BM-1"), zeile("BM-2"), zeile("FZ-1", "fahrzeug"), zeile("SR-1", "schalung_ruestung", "menge", menge=40)]
    plan = plane(zeilen, {})
    assert len(plan.neu) == 4 and plan.unveraendert == () and plan.abweichend == ()
    assert [(b.gruppe, b.art, b.neu) for b in plan.bericht] == [
        ("baumaschine", "gross", 2), ("fahrzeug", "gross", 1), ("schalung_ruestung", "menge", 1)]


def test_M2_zweiter_lauf_aendert_nichts():
    zeilen = [zeile("BM-1"), zeile("BM-2")]
    bestand = {z.inventarnummer: z for z in plane(zeilen, {}).neu}
    zweit = plane(zeilen, bestand)
    assert zweit.neu == () and zweit.abweichend == () and zweit.unveraendert == ("BM-1", "BM-2")
    assert [(b.neu, b.unveraendert) for b in zweit.bericht] == [(0, 2)]


def test_M3_abweichungen_werden_gemeldet_aber_nicht_uebernommen():
    bestand = {"BM-1": zeile("BM-1")}
    neu = zeile("BM-1", hersteller="Anders", kaufpreis=D("999"), merkmale={"betriebsgewicht": "22"})
    plan = plane([neu], bestand)
    assert plan.neu == () and plan.unveraendert == ()
    assert plan.abweichend == (type(plan.abweichend[0])("BM-1", ("hersteller", "kaufpreis", "merkmale")),)
    assert (plan.bericht[0].abweichend, plan.bericht[0].neu) == (1, 0)
    assert bestand["BM-1"].hersteller == "Teramax"  # Bestand unberuehrt


def test_M4_standortangaben_zaehlen_nicht_als_abweichung():
    bestand = {"BM-1": zeile("BM-1", kostenstelle=200, menge=3)}
    plan = plane([zeile("BM-1")], bestand)
    assert plan.abweichend == () and plan.unveraendert == ("BM-1",)


def test_M5_nummern_werden_normalisiert():
    bestand = {"BM-00017": zeile("BM-00017")}
    plan = plane([zeile(" bm-00017 ")], bestand)
    assert plan.neu == () and plan.unveraendert == ("BM-00017",)


def test_M6_doppelte_nummer_in_der_eingabe_ist_fehler():
    with pytest.raises(ValueError, match="nummer_doppelt"):
        plane([zeile("BM-1"), zeile("bm-1")], {})
    assert plane([], {}).bericht == ()


def test_M7_hinweis_je_abweichendem_feld():
    bestand = {"BM-1": zeile("BM-1")}
    plan = plane([zeile("BM-1", hersteller="Anders", kaufpreis=D("999"))], bestand)
    assert [(h.text_schluessel, h.detail) for h in plan.hinweise] == [
        ("import.hinweis.abweichung", "BM-1:hersteller"), ("import.hinweis.abweichung", "BM-1:kaufpreis")]
    assert plane([zeile("BM-1")], bestand).hinweise == ()
