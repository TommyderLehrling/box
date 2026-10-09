"""Jede Vorlage rendert mit `StrictUndefined` und einem Fake-Kontext (Kern-Umgebung, Rahmen als Stub)."""
from __future__ import annotations

import pytest
from jinja2 import ChoiceLoader, DictLoader, StrictUndefined, UndefinedError

from pfade import PAKET

RAHMEN = "<main>{% block titel %}{% endblock %}{% block inhalt %}{% endblock %}</main>"

KONTEXT = {
    "inventar_uebersicht.html": dict(
        zeilen=[{"id": 1, "nummer": "BM-00001", "bezeichnung": "Bagger", "gruppe": "Baumaschinen", "steht_auf": "79795 Husum",
                 "status": "aktiv", "ampel": "✓"}],
        mehr=True, seite_nr=2, q="bag", kacheln=[{"text": "inventar.kachel.pruefungen_faellig", "zahl": 3, "weg": "/inventar/faellig"}]),
    "inventar_hier.html": dict(zeilen=[{"kostenstelle": "79795 Husum", "nummer": "BM-00001", "menge": 1}]),
    "inventar_faellig.html": dict(hinweis="später"),
    "inventar_verwaltung.html": dict(zahlen=[("gruppen", 12), ("merkmale", 45)]),
    "teil_inventar_kostenstelle.html": dict(vor_ort=2, angekuendigt=1, kostenstelle_id=5),
    "teil_inventar_uebersicht.html": dict(zeilen=[("gesamt", 4), ("angekuendigt", 1)]),
}


@pytest.fixture(scope="module")
def umgebung(angemeldet):
    from digiassistenz_kern.web import vorlagen

    env = vorlagen.umgebung().overlay(undefined=StrictUndefined)
    env.loader = ChoiceLoader([DictLoader({"rahmen.html": RAHMEN}), env.loader])
    return env


def test_jede_vorlage_hat_einen_kontext_im_test():
    vorhanden = {p.name for p in (PAKET / "vorlagen").glob("*.html")}
    assert vorhanden == set(KONTEXT), "neue Vorlage: Kontext hier eintragen"


@pytest.mark.parametrize("name", sorted(KONTEXT))
def test_vorlage_rendert(umgebung, name):
    html = umgebung.get_template(name).render(**KONTEXT[name])
    assert html.strip()
    assert "{{" not in html and "{%" not in html


def test_fehlende_variable_wird_gefangen(umgebung):
    with pytest.raises(UndefinedError):
        umgebung.get_template("inventar_faellig.html").render()


def test_uebersicht_zeigt_zeilen_kacheln_und_weiter(umgebung):
    html = umgebung.get_template("inventar_uebersicht.html").render(**KONTEXT["inventar_uebersicht.html"])
    assert "BM-00001" in html and 'href="/inventar/faellig"' in html and "seite=3" in html and "seite=1" in html


def test_reiter_und_tbody_sind_fragmente(umgebung):
    assert umgebung.get_template("teil_inventar_uebersicht.html").render(**KONTEXT["teil_inventar_uebersicht.html"]).lstrip().startswith("<tbody>")
    assert umgebung.get_template("teil_inventar_kostenstelle.html").render(**KONTEXT["teil_inventar_kostenstelle.html"]).lstrip().startswith("<div")
