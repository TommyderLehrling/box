"""Prueffaelle fuer daten/texte_de.json (X1-X7)."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from digiassistenz_inventar.rein.import_vorlage import FEHLER_SCHLUESSEL
from digiassistenz_inventar.rein.stueck_status import ALLE as STUECK_STATUS

PAKET = Path(__file__).resolve().parents[2] / "digiassistenz_inventar"
SEITEN = ("uebersicht", "hier", "faellig", "werkstatt", "kosten", "stueck", "transfer", "meldung", "pruefung",
          "verwaltung", "gruppen", "merkmale", "pruefarten", "bauteile", "kostensaetze", "einstellungen",
          "import", "etiketten", "testdaten", "auslieferung", "handy_scannen", "scannen")
PRAEFIXE = {"gruppe", "merkmal", "pruefart", "muster", "nummernformat", "kataloge", "fristen", "kosten",
            "transfer", "etiketten", "testdaten", "zubehoer", "inventur", "bauteil", "pruefung", "stueck_status",
            "meldung", "reparatur", "werkstatt", "import_plan", "bestand", "beispielbetrieb",
            "verrechnung", "stueck", "nummer", "dateien", "laden", "import_lauf"}


@pytest.fixture(scope="module")
def texte() -> dict[str, str]:
    return json.loads((PAKET / "texte" / "de.json").read_text(encoding="utf-8"))


def codes_im_quelltext() -> set[str]:
    """Alle Meldungsschluessel (Fehler und Protokoll) aus den Modulen, ohne Detailanhang."""
    gefunden: set[str] = set()
    for datei in PAKET.rglob("*.py"):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
                kopf = knoten.value.split(":")[0]
                if not kopf.endswith(".json") and re.fullmatch(r"[a-z_0-9]+(\.[a-z_0-9]+)+", kopf) and kopf.split(".")[0] in PRAEFIXE:
                    gefunden.add(kopf)
    gefunden |= {f"stueck_status.{s}" for s in STUECK_STATUS}  # dynamisch gebaut: stueck_status.<neu>
    return gefunden


def test_X1_gueltiges_json_mit_erlaubten_schluesseln(texte):
    assert isinstance(texte, dict) and texte
    for k, v in texte.items():
        assert k.startswith(("inventar.", "hilfe.inventar_", "recht.inventar_", "app.modul")), k
        assert isinstance(v, str) and v.strip(), k


def test_X2_jede_seite_hat_liegt_tasten_danach(texte):
    for seite in SEITEN:
        for teil in ("liegt", "tasten", "danach"):
            assert f"hilfe.inventar_{seite}.{teil}" in texte, (seite, teil)
        assert f"hilfe.inventar_{seite}" in texte, seite  # der vierte Schluessel des Seitenkopfs
    assert len([k for k in texte if k.startswith("hilfe.inventar_")]) == 4 * len(SEITEN)


def test_X3_alle_import_fehler_sind_vorhanden(texte):
    for schluessel in FEHLER_SCHLUESSEL:
        assert f"inventar.{schluessel}" in texte, schluessel


def test_X4_alle_meldungsschluessel_der_module_haben_einen_text(texte):
    fehlt = sorted(c for c in codes_im_quelltext() if f"inventar.code.{c}" not in texte)
    assert fehlt == []


def test_X5_keine_verwaisten_meldungstexte(texte):
    vorhanden = {k[len("inventar.code."):] for k in texte if k.startswith("inventar.code.")}
    assert sorted(vorhanden - codes_im_quelltext()) == []


def test_X6_begriffe_aus_dem_auftrag(texte):
    for status in ("aktiv", "in_reparatur", "vermisst", "stillgelegt", "verkauft", "verschrottet"):
        assert f"inventar.status.{status}" in texte
    assert texte["inventar.transfer.taste.abgang"] == "Abgang buchen"
    assert texte["inventar.transfer.taste.eingang"] == "Ist angekommen"
    assert texte["inventar.transfer.taste.hier"] == "Ist hier"
    assert texte["inventar.transfer.taste.zurueckziehen"] == "Zurückziehen"
    assert texte["inventar.erinnerung.transfer"] == "Transfer seit {tage} Werktagen nicht bestätigt"
    assert texte["inventar.kosten.hinweis"] == "kalkulatorisch, nicht steuerlich"
    for ergebnis in ("bestanden", "maengel", "nicht_bestanden"):  # Begriffe der Spec v0.2, Abschnitt 7
        assert f"inventar.pruefung.ergebnis.{ergebnis}" in texte
    for status in ("offen", "angenommen", "in_arbeit", "erledigt", "zurueckgezogen"):
        assert f"inventar.meldung.status.{status}" in texte
    for art in ("schaden", "reparatur", "wartung", "sonstiges"):
        assert f"inventar.meldung.art.{art}" in texte
    for status in ("offen", "in_arbeit", "erledigt", "zurueckgezogen"):
        assert f"inventar.reparatur.status.{status}" in texte
    for neu in ("aktiv", "in_reparatur", "vermisst", "stillgelegt", "verkauft", "verschrottet"):  # Protokollschluessel stueck_status.<neu>
        assert f"inventar.code.stueck_status.{neu}" in texte
    for art in ("gross", "klein", "menge"):
        assert f"inventar.art.{art}" in texte
    for ampel in ("gruen", "gelb", "rot"):
        assert f"inventar.pruefung.ampel.{ampel}" in texte


def test_X7_stil_ohne_ausrufezeichen_und_ohne_du_oder_sie_anrede(texte):
    for k, v in texte.items():
        assert "!" not in v, k
        assert not re.search(r"\b(Sie|Ihr|Ihre|Ihnen|Du|Dein|Deine|Dir|Dich)\b", v), k
        assert not re.search(r"\b(tragen|geben|klicken|wählen)\s+(Sie|du)\b", v, re.I), k


class _Dummy(dict):
    def __missing__(self, key: str) -> str:
        return "x"


def test_X8_jeder_text_laesst_sich_mit_einem_dummy_mapping_formatieren(texte):
    for k, v in texte.items():
        v.format_map(_Dummy())  # wörtliche Klammern sind als doppelte Klammern maskiert
    assert texte["inventar.code.muster.nr_fehlt"].format_map(_Dummy()) == "{nr:N} fehlt im Muster"


def test_X9_neue_begriffe_aus_auftrag_02(texte):
    for schluessel in ("inventar.pruefung.ampel.unbekannt", "inventar.import.hinweis.beispiel_uebersprungen",
                       "inventar.import.hinweis.abweichung", "inventar.code.transfer.fehlmenge",
                       "inventar.code.inventur.mehr_gesehen"):
        assert schluessel in texte
