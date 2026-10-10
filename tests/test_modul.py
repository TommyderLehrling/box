"""Die Modulbeschreibung ist schlüssig: Bausteine ↔ Menü-Rechte ↔ Texte (Auftrag 03, Abschnitt 9)."""
from __future__ import annotations

import json
import re
import tomllib

import pytest

from pfade import PAKET, WURZEL
from digiassistenz_inventar import modul, rechte

B = modul.BESCHREIBUNG
EIGENE = json.loads((PAKET / "texte" / "de.json").read_text(encoding="utf-8"))
BAUSTEINE = {b.schluessel for b in B.rechte.bausteine}
VORLAGEN_KERN = {"polier", "bauleiter", "abteilungsleiter", "buero", "buchhaltung", "einkauf", "abrechner",
                 "geschaeftsfuehrung", "pruefer", "verwalter"}


def paare(rechte_):
    return {f"{m}.{a}" for m, a in rechte_}


def test_vertrag_namen_wie_im_auftrag():
    assert (B.schluessel, B.startseite, B.schemata, B.prozesse, B.arbeitsordner) == (
        "inventar", "/inventar", ("inventar",), ("digiassistenz_inventar.erinnern",), ("inventar",))
    assert B.konfig_schluessel == ("INVENTAR_ETIKETT_URL",) and B.zeilenfilter == () and B.sichtbarkeit == "inventar.sehen"
    assert B.bezeichnung == "inventar.modul" and B.rechte.schluessel == "inventar"
    assert [(e.weg, e.schluessel, e.reihenfolge) for e in B.menuepunkte] == [
        ("/inventar", "inventar", 10), ("/inventar/hier", "inventar_hier", 11),
        ("/inventar/faellig", "inventar_faellig", 12), ("/inventar/werkstatt", "inventar_werkstatt", 13),
        ("/inventar/verwaltung", "inventar_verwaltung", 30)]
    assert B.menuepunkte[4].unterzeile and B.menuepunkte[4].auch == ("/inventar/verwaltung/",)
    assert B.menuepunkte[3].rechte == (("inventar", "werkstatt"),)


def test_elf_bausteine_und_die_sichtbarkeit_ist_einer_davon():
    assert len(BAUSTEINE) == 11 and BAUSTEINE == {f"inventar.{a}" for a in rechte.AKTIONEN}
    assert B.sichtbarkeit in BAUSTEINE


def test_jeder_baustein_in_menue_erweiterung_und_verbindung_existiert():
    genannt = set()
    for e in B.menuepunkte:
        genannt |= paare(e.rechte)
    for e in B.erweiterungen:
        genannt |= paare(e.rechte)
    for v in B.verbindungen:
        for e in v.menuepunkte:
            genannt |= {p for p in paare(e.rechte)}
    assert genannt <= BAUSTEINE


def test_ergaenzung_nennt_nur_die_neun_vorlagen_ohne_verwalter_und_nur_eigene_bausteine():
    namen = [e.vorlage for e in B.rechte.ergaenzung]
    assert set(namen) == VORLAGEN_KERN - {"verwalter"} and len(namen) == 9
    for e in B.rechte.ergaenzung:
        assert set(e.bausteine) <= BAUSTEINE
    nach = {e.vorlage: {b.split(".")[1] for b in e.bausteine} for e in B.rechte.ergaenzung}
    assert nach["polier"] == {"sehen", "scannen", "buchen", "melden"}
    assert nach["buchhaltung"] == {"sehen", "kosten_sehen", "kosten_pflegen"} and nach["pruefer"] == {"sehen"}
    assert "kosten_sehen" not in nach["polier"]  # Poliere sehen keine Preise


def test_nachzug_paare_fuer_alle_elf_bausteine_mit_grund():
    assert {b for b, _ in B.rechte.nachzug} == BAUSTEINE and len(B.rechte.nachzug) == 11
    assert {g for _, g in B.rechte.nachzug} == {"nachzug:inventar_einbau"}


def test_jeder_textschluessel_der_beschreibung_steht_in_de_json():
    schluessel = {B.bezeichnung} | {f"recht.inventar_{a}" for a in rechte.AKTIONEN}
    schluessel |= {e.text for e in B.menuepunkte} | {e.titel for e in B.erweiterungen}
    assert sorted(s for s in schluessel if s not in EIGENE) == []
    assert "app.modul" not in EIGENE  # Steckbrief 11: ein zweites Modul setzt es nicht


def test_erweiterungsstellen_sind_die_drei_aus_dem_auftrag():
    assert {(e.stelle, e.schluessel) for e in B.erweiterungen} == {
        ("kostenstelle.seite", "inventar"), ("verwaltung.uebersicht", "inventar"), ("verwaltung.uebersicht.kostenstelle", "inventar")}
    assert B.ereignisse[0][0] == "kostenstelle.angelegt"
    assert [v.braucht for v in B.verbindungen] == [modul.MODUL_BAUSTELLE] and B.verbindungen[0].menuepunkte == ()


def test_das_modul_laesst_sich_beim_kern_anmelden(angemeldet):
    from digiassistenz_kern import modul as kern_modul

    assert "inventar" in [b.schluessel for b in kern_modul.angemeldet()]
    assert callable(B.routen) and callable(B.kette) and callable(B.startdaten) and callable(B.suche)


def test_etikett_url_wird_geprueft(angemeldet):
    from types import SimpleNamespace

    from digiassistenz_kern.konfig import KonfigFehler

    B.konfig_pruefen(SimpleNamespace(modul_werte={}))
    B.konfig_pruefen(SimpleNamespace(modul_werte={"INVENTAR_ETIKETT_URL": "https://box.example"}))
    with pytest.raises(KonfigFehler):
        B.konfig_pruefen(SimpleNamespace(modul_werte={"INVENTAR_ETIKETT_URL": "box.example"}))


def test_modulbeschreibung_traegt_die_mindestfassung_des_kerns():
    """Seit kern-0.15.3: zu alter Kern → das Modul bleibt aus (Satz im Log)."""
    assert B.kern_mindestens == modul.KERN_MINDESTFASSUNG == "0.15.3"


def test_mindestfassung_des_kerns_steht_in_der_pyproject_und_als_konstante():
    daten = tomllib.loads((WURZEL / "pyproject.toml").read_text(encoding="utf-8"))
    assert f"digiassistenz-kern>={modul.KERN_MINDESTFASSUNG}" in daten["project"]["dependencies"]
    assert modul.KERN_MINDESTFASSUNG == "0.15.3"
    assert daten["project"]["entry-points"]["digiassistenz.module"]["inventar"] == "digiassistenz_inventar.modul:BESCHREIBUNG"
    assert re.fullmatch(r"\d+\.\d+\.\d+", modul.VERSION)
