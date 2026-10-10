"""Jede Vorlage rendert mit `StrictUndefined` und einem Fake-Kontext (Kern-Umgebung, Rahmen als Stub)."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, StrictUndefined, UndefinedError

from pfade import PAKET

RAHMEN = "<main>{% block titel %}{% endblock %}{% block inhalt %}{% endblock %}</main>"
AKTIONEN = ("sehen", "scannen", "buchen", "melden", "pflegen", "pruefen", "werkstatt", "stilllegen", "kosten_sehen", "kosten_pflegen", "einstellen")
JETZT = dt.datetime(2026, 10, 9, 8, 30, tzinfo=dt.timezone.utc)
HEUTE = dt.date(2026, 10, 9)


def darf(alles: bool = True) -> dict[str, bool]:
    return {f"darf_{a}": alles for a in AKTIONEN}


def wahl(feld: str = "kostenstelle"):
    from digiassistenz_kern.web.wahlfeld import Wahl

    return Wahl(art="kostenstelle", feld=feld, kennung=f"wahl-{feld}", optionen=[{"wert": "79795", "text": "79795 · Husum", "gewaehlt": False}],
                leer="inventar.alle", modul="inventar", aktion="sehen", beschriftung="inventar.feld.kostenstelle")


ZEILE = {"id": 1, "nummer": "BM-00001", "bezeichnung": "Bagger", "gruppe": "Baumaschinen", "steht_auf": "79795 Husum", "seit": JETZT,
         "angekuendigt_auf": "", "status": "aktiv", "ampel": "gelb", "ampel_zeichen": "⚠"}
ANGEKUENDIGT = {**ZEILE, "id": 2, "nummer": "BM-00002", "steht_auf": "", "angekuendigt_auf": "79800 Nord", "seit": None}
FILTER = SimpleNamespace(q="bag", status="", gruppe="", kostenstelle="", angekuendigt=False, faellig=False)
SEITE = SimpleNamespace(zeilen=[ZEILE, ANGEKUENDIGT], gesamt=250, nummer=2, letzte=3)
LISTE = dict(filter=FILTER, seite_inhalt=SEITE, spalte="nummer", absteigend=False, grundweg="/inventar?q=bag&ansicht=liste",
             filterweg="q=bag")
UEBERSICHT = dict(
    LISTE, ansicht="liste", ordner=[], kacheln=[{"text": "inventar.kachel.pruefungen_faellig", "zahl": 3, "weg": "/inventar/faellig"}],
    gruppen=[("baumaschinen", "Baumaschinen")], wahl_ks=wahl(), stati=["aktiv", "vermisst"], **darf())
def _faellig_zeile(nr: int, ampel: str, zeichen: str, **mehr):
    return {"id": nr, "nummer": f"BM-0000{nr}", "bezeichnung": "Bagger", "gruppe": "Baumaschinen", "ort": "79795 Husum", "pruefart": "uvv",
            "pruefart_name": "UVV", "ampel": ampel, "zeichen": zeichen, "faellig_am": HEUTE, "hinweis": "überfällig seit 3 Tagen", **mehr}


FAELLIG = dict(
    filter=SimpleNamespace(pruefart="", kostenstelle="", gruppe=""), arten=[("uvv", "UVV")], gruppen=[("bm", "Baumaschinen")], wahl_ks=wahl(),
    fertig=True, zaehler_hinweis="", uebersicht=SimpleNamespace(
        ueberfaellig=SimpleNamespace(zeilen=[_faellig_zeile(1, "rot", "✗")], gesamt=1, gekuerzt=False),
        faellig=SimpleNamespace(zeilen=[_faellig_zeile(2, "gelb", "⚠")], gesamt=250, gekuerzt=True),
        ohne_nachweis=SimpleNamespace(zeilen=[], gesamt=0, gekuerzt=False), gelesen=252, abgeschnitten=True), **darf())
ORT = SimpleNamespace(titel="79795 Husum", anzahl=1, kinder=[], stuecke=[ZEILE])
ORDNER = [SimpleNamespace(titel="Baumaschinen", anzahl=1, kinder=[ORT], stuecke=[])]
STUECK = SimpleNamespace(id=1, inventarnummer="BM-00001", bezeichnung="Bagger", art="gross", hersteller="Cat", typ="320", seriennummer="S1",
                         baujahr=2020, besonderheiten="", status="aktiv", status_grund="", quelle="web", zaehler_einheit="h",
                         kaufpreis=Decimal("1000"), kaufdatum=HEUTE, lieferant_id=None, gruppe_id=1)
OFFEN = {"kostenstelle_id": 5, "kostenstelle": "79795 Husum", "menge": 1, "seit": JETZT, "darf_buchen": True, "darf_scannen": True, "darf_melden": True}
TRANSFER = {"id": 9, "menge": 1, "von": "79795 Husum", "nach": "79800 Nord", "nach_id": 6, "abgang_am": JETZT, "grund": "", "darf_eingang": True,
            "darf_zurueck": True}
STUECK_SEITE = dict(
    stueck=STUECK, gruppe=SimpleNamespace(bezeichnung="Baumaschinen"), merkmale=[{"bezeichnung": "Gewicht", "wert": "12", "einheit": "t"}],
    offen=[OFFEN], verlauf_orte=[{"kostenstelle": "79795 Husum", "menge": 1, "von": JETZT, "bis": None, "quelle": "web"}],
    transfers=[TRANSFER], pruefstaende=[{"art": "UVV", "ampel": "gelb", "zeichen": "⚠", "faellig_am": HEUTE, "hinweis": "fällig in 5 Tagen"}],
    ampel="gelb", ampel_zeichen="⚠", ampel_hinweis="fällig in 5 Tagen",
    pruefungen=[{"id": 4, "art": "UVV", "am": HEUTE, "ergebnis": "bestanden", "durchfuehrung": "intern", "pruefer": "Meier", "naechste": HEUTE, "nachweis": True},
                {"id": 5, "art": "UVV", "am": HEUTE, "ergebnis": "maengel", "durchfuehrung": "extern", "pruefer": "TÜV", "naechste": HEUTE, "nachweis": False}],
    meldungen=[{"id": 8, "art": "schaden", "beschreibung": "Kratzer", "status": "offen", "am": JETZT, "von": "Eins", "hat_foto": False,
                "bearbeiter": "", "erledigt_am": None, "rueckmeldung": "", "grund": ""},
               {"id": 9, "art": "reparatur", "beschreibung": "Schlauch undicht", "status": "erledigt", "am": JETZT, "von": "Eins", "hat_foto": True,
                "bearbeiter": "Werkstatt", "erledigt_am": JETZT, "rueckmeldung": "Schlauch getauscht", "grund": ""}],
    reparaturen=[{"status": "offen", "beschreibung": "", "begonnen": HEUTE, "beendet": None, "kosten": Decimal("10"), "durchfuehrung": "intern", "grund": ""}],
    zaehlerstaende=[{"stand": Decimal("12.5"), "einheit": "h", "am": JETZT, "quelle": "web"}],
    zubehoer=[{"beziehung_id": 3, "id": 2, "nummer": "BM-00002", "bezeichnung": "Löffel"}], haupt={"beziehung_id": 4, "id": 7, "nummer": "BM-00007", "bezeichnung": "Kran"},
    bauteile=[{"beziehung_id": 5, "nummer": "B1", "bezeichnung": "Filter", "preis": Decimal("9.9")}],
    kosten={"kaufpreis": Decimal("1000"), "kaufdatum": HEUTE, "buchwert_extern": None, "mietkosten": None, "miete": False, "satz_monat": Decimal("5"),
            "satz_tag": None, "nutzungsdauer": 96},
    verlauf=[{"am": JETZT, "text": "Stück angelegt", "alt": None, "neu": "BM-00001", "wer": "Eins", "fuer": "Zwei"}],
    lieferant="Händler", steht_auf="79795 Husum", seit=JETZT, angekuendigt_auf="79800 Nord", fertig="angelegt", wahl_nach=wahl("nach"),
    von_ks=[OFFEN], melde_ks=[OFFEN], bauteile_katalog=[(1, "B1 Filter")], status_moeglich=["vermisst"], hauptlage="eingang", buchung="k-1",
    scan_ks="5", scan_ok=True, scan_art="kamera",
    pruefen_arten=[{"schluessel": "uvv", "bezeichnung": "UVV"}, {"schluessel": "sp", "bezeichnung": "Sicherheitsprüfung"}], pruefen_vorgabe="uvv", pruefen_offen=True,
    pruefen_weiter="faellig", benutzer_auswahl=[(1, "Eins"), (2, "Zwei")], benutzer_ich=1, wahl_pruefer_lieferant=wahl("pruefer_lieferant_id"),
    heute_iso=HEUTE.isoformat(), zaehler_hinweis="",
    pruefarten_stueck=[{"schluessel": "uvv", "bezeichnung": "UVV", "katalog_intervall": 12, "gruppe_intervall": None, "stueck_intervall": 6, "aktiv": True,
                        "herkunft": "gruppe", "wirksam": 6, "zaehler_intervall": None, "je_merkmal": False},
                       {"schluessel": "sp", "bezeichnung": "Sicherheitsprüfung", "katalog_intervall": 24, "gruppe_intervall": None, "stueck_intervall": None,
                        "aktiv": False, "herkunft": "stueck", "wirksam": None, "zaehler_intervall": None, "je_merkmal": False}],
    pruefarten_dazu=[("elt", "Elektroprüfung")], **darf())
def _meldung_zeile(nr: int, status: str, **mehr):
    return {"id": nr, "stueck_id": 1, "nummer": "BM-00001", "bezeichnung": "Bagger", "stueck_status": "aktiv", "art": "schaden",
            "beschreibung": "Schlauch undicht", "ort": "79795 Husum", "status": status, "am": JETZT, "von": "Eins", "bearbeiter": "",
            "erledigt_am": None, "rueckmeldung": "", "hat_foto": True, **mehr}


def _reparatur_zeile(nr: int, status: str, **mehr):
    return {"id": nr, "stueck_id": 1, "nummer": "BM-00001", "bezeichnung": "Bagger", "stueck_status": "aktiv", "status": status,
            "durchfuehrung": "extern", "beschreibung": "Hydraulik", "lieferant": "Firma X", "begonnen": HEUTE, "beendet": None,
            "kosten": Decimal("120"), "kosten_quelle": "geschaetzt", "laeuft": status == "in_arbeit", **mehr}


WERKSTATT = dict(
    p=SimpleNamespace(
        offen=[_meldung_zeile(1, "offen")], angenommen=[_meldung_zeile(2, "angenommen", bearbeiter="Werkstatt", stueck_status="in_reparatur")],
        in_arbeit=[_meldung_zeile(3, "in_arbeit", bearbeiter="Werkstatt")],
        erledigt=[_meldung_zeile(4, "erledigt", bearbeiter="Werkstatt", erledigt_am=JETZT, rueckmeldung="Schlauch getauscht")],
        reparaturen=[_reparatur_zeile(5, "offen"), _reparatur_zeile(6, "in_arbeit")],
        reparaturen_fertig=[_reparatur_zeile(7, "erledigt", beendet=HEUTE)],
        stuecke_in_reparatur=[{"id": 1, "nummer": "BM-00001", "bezeichnung": "Bagger", "seit": JETZT}]),
    fertig="", ziel=None, heute_iso=HEUTE.isoformat(), wahl_lieferant=wahl("lieferant_id"), **darf())
FORM = dict(zeile=None, titel_form="Neues Stück", gruppen=[("baumaschinen", "Baumaschinen")], gruppe_gewaehlt=1,
            felder=[{"schluessel": "gewicht", "bezeichnung": "Gewicht", "typ": "zahl", "einheit": "t", "auswahl": [], "pflicht": True, "wert": ""},
                    {"schluessel": "klasse", "bezeichnung": "Klasse", "typ": "auswahl", "einheit": "", "auswahl": ["a", "b"], "pflicht": False, "wert": "a"},
                    {"schluessel": "ja", "bezeichnung": "Ja", "typ": "ja_nein", "einheit": "", "auswahl": [], "pflicht": False, "wert": "ja"},
                    {"schluessel": "tag", "bezeichnung": "Tag", "typ": "datum", "einheit": "", "auswahl": [], "pflicht": False, "wert": ""},
                    {"schluessel": "text", "bezeichnung": "Text", "typ": "text", "einheit": "", "auswahl": [], "pflicht": False, "wert": ""}],
            vorschlag="BM-00002", ist_neu=True, arten=["gross", "klein", "menge"], wahl_ks=wahl(), wahl_lieferant=wahl("lieferant_id"),
            buchung="k-1", **darf())
KATALOG_FERTIG = dict(fertig=True, **darf())
LEER_EINTRAG = dict(schluessel="", bezeichnung="", kuerzel="", oben="", sortierung=0, aktiv=True)
KONTEXT = {
    "inventar_uebersicht.html": UEBERSICHT,
    "teil_inventar_liste.html": LISTE,
    "inventar_stueck.html": STUECK_SEITE,
    "inventar_stueck_form.html": FORM,
    "teil_inventar_merkmale.html": dict(felder=FORM["felder"], vorschlag="BM-00002", ist_neu=True),
    "inventar_hier.html": dict(
        kostenstellen=[(5, "79795 Husum"), (6, "79800 Nord")], gewaehlt=5, buchung="k-1", fertig="eingang",
        angekuendigt=[{"id": 9, "stueck_id": 2, "nummer": "BM-00002", "bezeichnung": "Löffel", "art": "menge", "menge": 4, "von": "79800 Nord", "abgang_am": JETZT}],
        vor_ort=[{"stueck_id": 1, "nummer": "BM-00001", "bezeichnung": "Bagger", "menge": 1, "seit": JETZT, "hat_zaehler": True, "status": "aktiv"}], **darf()),
    "inventar_scannen.html": dict(kostenstellen=[(5, "79795 Husum"), (6, "79800 Nord")], gewaehlt=5, **darf()),
    "inventar_faellig.html": FAELLIG,
    "inventar_werkstatt.html": WERKSTATT,
    "inventar_verwaltung.html": dict(kacheln=[("gruppen", "/inventar/verwaltung/gruppen", 12), ("import", "/inventar/verwaltung/import", None)]),
    "inventar_verwaltung_gruppen.html": dict(KATALOG_FERTIG, eintrag=LEER_EINTRAG, zeilen=[
        {"schluessel": "bm", "bezeichnung": "Baumaschinen", "kuerzel": "BM", "oben": "", "sortierung": 1, "aktiv": True, "startwert": True}]),
    "inventar_verwaltung_merkmale.html": dict(KATALOG_FERTIG, gruppen=[("bm", "Baumaschinen")], gruppe="bm", typen=["text", "auswahl"], zeilen=[
        {"schluessel": "gewicht", "bezeichnung": "Gewicht", "typ": "text", "einheit": "t", "auswahl": "", "pflicht": False, "sortierung": 1,
         "aktiv": True, "startwert": False}],
        eintrag={"schluessel": "", "bezeichnung": "", "typ": "text", "einheit": "", "auswahl": "", "pflicht": False, "sortierung": 0, "aktiv": True}),
    "inventar_verwaltung_pruefarten.html": dict(KATALOG_FERTIG, gruppen=[("bm", "Baumaschinen")], durchfuehrungen=["intern", "extern"], zeilen=[
        {"schluessel": "uvv", "bezeichnung": "UVV", "intervall": 12, "zaehler": "", "rechtsgrund": "DGUV", "durchfuehrung": "intern",
         "je_merkmal": "klasse=a:24", "gruppen": ["bm"], "gruppen_intervall": {"bm": 6}, "aktiv": True, "startwert": True}],
        eintrag={"schluessel": "", "bezeichnung": "", "intervall": 12, "zaehler": "", "rechtsgrund": "", "durchfuehrung": "intern", "je_merkmal": "",
                 "gruppen": [], "gruppen_intervall": {}, "aktiv": True}),
    "inventar_verwaltung_bauteile.html": dict(KATALOG_FERTIG, zeigt_preis=True, zeilen=[
        {"nummer": "B1", "bezeichnung": "Filter", "hersteller": "X", "preis": Decimal("9.9"), "hinweis": "", "aktiv": True}],
        eintrag={"nummer": "", "bezeichnung": "", "hersteller": "", "preis": "", "hinweis": "", "aktiv": True}),
    "inventar_verwaltung_kostensaetze.html": dict(KATALOG_FERTIG, heute=HEUTE, gruppen=[("bm", "Baumaschinen")], zeilen=[
        {"gruppe": "Baumaschinen", "ab": HEUTE, "nutzungsdauer": 96, "zins": Decimal("4"), "reparatur": Decimal("2"), "restwert": None,
         "monat": Decimal("100"), "tag": None, "woche": None, "stunde": None, "quelle": "manuell"}]),
    "inventar_verwaltung_einstellungen.html": dict(KATALOG_FERTIG, auslieferung="", felder=[("nummernmuster", "{gruppe}-{nr:5}"), ("tage_je_monat", "30")]),
    "inventar_verwaltung_import.html": dict(bericht={
        "fehler": [{"zeile": 3, "spalte": "Gruppe", "text": "import.fehler.gruppe_unbekannt", "wert": "xx"}], "hinweise": [{"zeile": 2, "text": "import.hinweis.beispiel_uebersprungen"}],
        "gelesen": 5, "je_gruppe": [{"gruppe": "bm", "art": "gross", "neu": 2, "unveraendert": 1, "abweichend": 0}],
        "abweichungen": [{"text": "import.hinweis.abweichung", "detail": "BM-1:typ"},
                         {"text": "import.hinweis.kostenstelle_ohne_recht", "detail": "BM-9 (70101)"}], "kaufdaten_uebersprungen": 3, "neu": 2, "angelegt": 0, "unbekannte_lieferanten": ["Firma X"]},
        datei="0123456789abcdef0123456789abcdef", **darf()),
    "inventar_verwaltung_etiketten.html": dict(gruppen=[("bm", "Baumaschinen")], wahl_ks=wahl(), **darf()),
    "inventar_verwaltung_testdaten.html": dict(erlaubt=True, **darf()),
    "teil_inventar_fertig.html": dict(text="fertig"),
    "teil_inventar_kostenstelle.html": dict(vor_ort=2, angekuendigt=1, kostenstelle_id=5, nummer="79795"),
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


def render(umgebung, name, **aenderungen):
    return umgebung.get_template(name).render(**{**KONTEXT[name], **aenderungen})


def test_liste_zeigt_zeilen_ampel_angekuendigt_und_weiter(umgebung):
    html = render(umgebung, "inventar_uebersicht.html")
    assert "BM-00001" in html and "/inventar/stueck/1" in html and "seite=3" in html and "seite=1" in html
    assert "angekündigt auf 79800 Nord" in html and 'href="/inventar/faellig"' in html and "/inventar/stueck/neu" in html


def test_liste_ohne_pflegerecht_hat_keine_neu_taste(umgebung):
    html = render(umgebung, "inventar_uebersicht.html", darf_pflegen=False)
    assert "/inventar/stueck/neu" not in html


def test_ordner_zeigt_gruppe_und_ort_zugeklappt(umgebung):
    html = render(umgebung, "inventar_uebersicht.html", ansicht="ordner", ordner=ORDNER, seite_inhalt=None)
    assert "<details class=\"inventar-gruppe\">" in html and "79795 Husum" in html and "open" not in html.split("inventar-gruppe")[1][:40]


def test_statuszeile_ist_das_erste_element_unter_dem_seitenkopf(umgebung):
    html = render(umgebung, "inventar_stueck.html")
    assert html.index("<h1>") < html.index('id="statuszeile"') < html.index("<details open>")
    assert "steht auf 79795 Husum" in html and "/inventar/transfer/9/eingang" in html and 'action="/inventar/transfer/abgang"' in html


def test_stueck_ohne_rechte_hat_keine_tasten_und_keine_preise(umgebung):
    html = render(umgebung, "inventar_stueck.html", **darf(False), kosten=None, von_ks=[], melde_ks=[], status_moeglich=[], hauptlage="",
                  transfers=[{**TRANSFER, "darf_eingang": False, "darf_zurueck": False}], scan_ok=False,
                  bauteile=[{"beziehung_id": 5, "nummer": "B1", "bezeichnung": "Filter", "preis": None}])
    for spur in ("/aendern", "/inventar/transfer/abgang", "/eingang", "/stueck/1/meldung", "/zubehoer", "/bauteil", "/status", "/zurueck",
                 "/inventar/werkstatt"):
        assert spur not in html, spur
    assert "Kaufpreis" not in html and "9,90" not in html


def test_scan_tasten_nur_mit_ks_und_recht(umgebung):
    assert 'id="scan-tasten"' in render(umgebung, "inventar_stueck.html")
    assert 'id="scan-tasten"' not in render(umgebung, "inventar_stueck.html", scan_ok=False)


def test_hier_hat_zwei_bloecke_und_scannen_taste(umgebung):
    html = render(umgebung, "inventar_hier.html")
    assert "hier-angekuendigt" in html and "hier-vor-ort" in html and "/inventar/scannen?ks=5" in html
    assert 'name="menge"' in html and "/inventar/transfer/9/eingang" in html


def test_hier_ohne_scannen_hat_keine_eingangstaste(umgebung):
    html = render(umgebung, "inventar_hier.html", darf_scannen=False, darf_buchen=False, darf_melden=False)
    assert "/inventar/transfer/9/eingang" not in html and "/inventar/scannen" not in html and "#abgang-von" not in html


def test_reiter_und_tbody_sind_fragmente(umgebung):
    assert render(umgebung, "teil_inventar_uebersicht.html").lstrip().startswith("<tbody>")
    assert render(umgebung, "teil_inventar_kostenstelle.html").lstrip().startswith("<div")
    assert "kostenstelle=79795" in render(umgebung, "teil_inventar_kostenstelle.html")


def test_import_zeigt_einspielen_nur_ohne_fehler(umgebung):
    mit = render(umgebung, "inventar_verwaltung_import.html")
    assert "Einspielen" not in mit and "Gruppe ist im Katalog nicht vorhanden" in mit
    ohne = render(umgebung, "inventar_verwaltung_import.html", bericht={**KONTEXT["inventar_verwaltung_import.html"]["bericht"], "fehler": []})
    assert 'value="einspielen"' in ohne


def test_scan_tasten_tragen_die_kamera_nur_wenn_sie_im_kontext_steht(umgebung):
    assert 'name="art" value="kamera"' in render(umgebung, "inventar_stueck.html")
    assert 'name="art"' not in render(umgebung, "inventar_stueck.html", scan_art="")


def test_faellig_zeigt_drei_bloecke_und_die_taste_nur_mit_pruefen(umgebung):
    html = render(umgebung, "inventar_faellig.html")
    for kennung in ("ueberfaellig", "faellig", "ohne_nachweis"):
        assert f'id="faellig-{kennung}"' in html
    assert "/inventar/stueck/1?pruefart=uvv&amp;weiter=faellig#pruefung-eintragen" in html
    assert "250" in html and "252" in html, "gekürzt und abgeschnitten werden gesagt"
    ohne = render(umgebung, "inventar_faellig.html", darf_pruefen=False)
    assert "pruefart=uvv&amp;weiter" not in ohne and "BM-00001" in ohne


def test_pruefung_eintragen_dialog_nur_mit_pruefen_und_mit_datei_und_vorgabe(umgebung):
    html = render(umgebung, "inventar_stueck.html")
    assert 'action="/inventar/stueck/1/pruefung"' in html and 'enctype="multipart/form-data"' in html
    assert 'name="nachweis"' in html and 'id="pruefung-eintragen" open' in html and '<option value="uvv" selected>' in html
    assert 'name="weiter" value="faellig"' in html and 'name="pruefer_lieferant_id"' in html and "/inventar/pruefung/4/nachweis" in html
    assert "/inventar/pruefung/5/nachweis" not in html, "ohne Nachweis kein Link"
    ohne = render(umgebung, "inventar_stueck.html", darf_pruefen=False)
    assert "/pruefung\"" not in ohne and 'name="nachweis"' not in ohne


def test_pruefarten_des_stuecks_nur_mit_pflegen(umgebung):
    html = render(umgebung, "inventar_stueck.html")
    assert 'id="pruefarten-stueck"' in html and 'action="/inventar/stueck/1/pruefart"' in html and 'id="pruefart-dazu"' in html
    ohne = render(umgebung, "inventar_stueck.html", darf_pflegen=False)
    assert "/pruefart\"" not in ohne


def test_import_nennt_uebersprungene_kaufdaten_und_zeilen_ohne_recht(umgebung):
    html = render(umgebung, "inventar_verwaltung_import.html")
    assert "in 3 Zeilen übersprungen" in html and "Kostensätze pflegen" in html
    assert "BM-9 (70101)" in html and "nicht angelegt" in html
    ohne = render(umgebung, "inventar_verwaltung_import.html", bericht={**KONTEXT["inventar_verwaltung_import.html"]["bericht"], "kaufdaten_uebersprungen": 0})
    assert "Kaufpreis und Kaufdatum in" not in ohne


def test_zaehlerhinweis_steht_an_der_stueck_seite_und_in_der_faellig_liste(umgebung):
    satz = "Zählerstand 90 liegt unter dem letzten Stand 120"
    assert satz in render(umgebung, "inventar_stueck.html", zaehler_hinweis=satz)
    assert satz in render(umgebung, "inventar_faellig.html", zaehler_hinweis=satz)
    assert "liegt unter dem letzten Stand" not in render(umgebung, "inventar_stueck.html")


def test_werkstatt_zeigt_die_tasten_je_stand_der_meldung(umgebung):
    html = render(umgebung, "inventar_werkstatt.html")
    for kennung in ("offen", "angenommen", "in-arbeit", "reparaturen", "in-reparatur", "erledigt", "reparaturen-fertig"):
        assert f'id="werkstatt-{kennung}"' in html, kennung
    assert 'action="/inventar/werkstatt/meldung/1/weiter"' in html and 'value="angenommen"' in html, "offen: Annehmen"
    assert 'value="in_arbeit"' in html and 'id="erledigt-2"' in html and 'id="erledigt-3"' in html, "angenommen/in Arbeit: Übernehmen, Erledigen"
    assert 'id="erledigt-4"' not in html and "Schlauch getauscht" in html, "erledigt: nur die Rückmeldung"
    assert "/inventar/meldung/1/foto" in html and "/inventar/werkstatt?neu_meldung=2#reparatur-anlegen" in html
    assert 'action="/inventar/werkstatt/stueck/1/status"' in html
    assert 'id="beginnen-5"' in html and 'id="abschluss-6"' in html and 'id="rechnung-7"' in html
    assert 'name="kosten"' in html and "120,00" in html


def test_werkstatt_ohne_kostenrechte_hat_keine_kostenfelder_und_keine_preise(umgebung):
    ohne = {**WERKSTATT, **darf(False), "darf_werkstatt": True}
    ohne["p"] = SimpleNamespace(**{**vars(WERKSTATT["p"]), "reparaturen": [_reparatur_zeile(5, "in_arbeit", kosten=None, kosten_quelle=None)],
                                   "reparaturen_fertig": []})
    html = umgebung.get_template("inventar_werkstatt.html").render(**ohne)
    assert 'name="kosten"' not in html and "<th>Reparaturkosten" not in html and 'id="abschluss-5"' in html


def test_werkstatt_reparatur_dialog_steht_offen_zu_einem_ziel(umgebung):
    html = render(umgebung, "inventar_werkstatt.html", ziel={"meldung_id": 2, "stueck_id": 1, "nummer": "BM-00001", "bezeichnung": "Bagger",
                                                              "beschreibung": "Schlauch undicht"})
    assert 'id="reparatur-anlegen" open' in html and 'name="meldung_id" value="2"' in html and 'name="lieferant_id"' in html
    assert 'id="reparatur-anlegen"' not in render(umgebung, "inventar_werkstatt.html")
    assert "Das Stück ist in Reparatur" in render(umgebung, "inventar_werkstatt.html", fertig="status_gesetzt")


def test_stueck_seite_zeigt_rueckmeldung_foto_und_werkstatt_tasten(umgebung):
    html = render(umgebung, "inventar_stueck.html")
    assert "Schlauch getauscht" in html and "/inventar/meldung/9/foto" in html
    assert "/inventar/werkstatt?neu_stueck=1#reparatur-anlegen" in html
    assert "/inventar/werkstatt" not in render(umgebung, "inventar_stueck.html", darf_werkstatt=False)
    assert "id=\"hinweis-in-reparatur\"" not in html
    in_rep = render(umgebung, "inventar_stueck.html", stueck=SimpleNamespace(**{**vars(STUECK), "status": "in_reparatur"}))
    assert 'id="hinweis-in-reparatur"' in in_rep and "weiter buchen" in in_rep
