"""T-I-5 — nur Kern + Inventar (Auftrag 03, Abschnitt 9; Muster: T-I-2 des Kerns).

Aufbau: der Kern und das Inventar sind installiert, **kein** anderes Modul (`aufbau_pruefen`). Läuft im eigenen
Kern-Aufbau mit eigener Datenbank (`tests/integration/laufen.md`).

===================== ====================================================
Installation          genau Kern + Inventar; `digiassistenz` nicht findbar
Migration             `kern.` und `inventar.alembic_version`; 18 Tabellen; Konto ohne fremde Schemata
Startdaten            9 + 11 Bausteine; Ergänzung wirkt; Kataloge da; zweiter Start ändert nichts
Anmeldung             anmelden → `/inventar`; abmelden
Menü                  Inventar, Hier, Fällig; kein toter Link; Verwaltungszeile in der zweiten Kopfzeile
Kostenstelle          Reiter, Ordner durch das Ereignis, Zeile in Verwaltung → Übersicht
Rechte                Polier sieht seine Stücke, keine Verwaltung, keine Fälligkeitsliste
Suche                 Feld im Kopf und `/suche` nur mit `inventar.sehen`
Ohne Modul            Startseite `/verwaltung`, `/suche` 404
===================== ====================================================
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, select, text

from conftest import POLIER, POLIER_ZWEI, VERWALTER, anmelden, aufbau_pruefen, menuewege, tote_links
from digiassistenz_kern import BenutzerKostenstelle, Kostenstelle, Recht, Rolle, RolleRecht
from digiassistenz_kern import modul as kern_modul
from digiassistenz_kern.sitzung import systemsitzung
from digiassistenz_kern.texte import t

pytestmark = pytest.mark.usefixtures("_t_i_5_aufbau")

NEUE_KS = {"nummer": "70101", "bezeichnung": "Inventar", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"}


@pytest.fixture(scope="module")
def _t_i_5_aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _kostenstelle(klient, nummer: str = "70101") -> int:
    antwort = klient.post("/verwaltung/kostenstelle/neu", data={**NEUE_KS, "nummer": nummer}, follow_redirects=False)
    assert antwort.status_code == 303
    with systemsitzung("pruefung.t_i_5") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _stueck(db_url_box, kostenstelle_id: int, nummer: str = "BM-00001", bezeichnung: str = "Hydraulikbagger") -> int:
    from digiassistenz_inventar import modelle as m

    with systemsitzung("pruefung.t_i_5") as db:
        mandant_id = int(db.execute(select(Kostenstelle.mandant_id).where(Kostenstelle.id == kostenstelle_id)).scalar_one())
        gruppe = db.execute(select(m.Gruppe).where(m.Gruppe.schluessel == "baumaschine")).scalar_one()
        s = m.Stueck(mandant_id=mandant_id, inventarnummer=nummer, bezeichnung=bezeichnung, gruppe_id=gruppe.id, art="gross",
                     quelle="web", seriennummer="TEST-" + nummer)
        db.add(s)
        db.flush()
        from datetime import datetime, timezone

        db.add(m.Standort(mandant_id=mandant_id, stueck_id=s.id, kostenstelle_id=kostenstelle_id, menge=1,
                          von=datetime(2026, 9, 1, 8, tzinfo=timezone.utc), quelle="web"))
        return int(s.id)


def test_t_i_5_migration_nur_kern_und_inventar(box) -> None:
    from digiassistenz_inventar import modelle

    assert set(box.staende) == {"kern", "inventar"} and box.staende["inventar"] == "i0001_grundlinie"
    motor = create_engine(box.db_url)
    try:
        schemata = set(inspect(motor).get_schema_names())
        tabellen = set(inspect(motor).get_table_names(schema="inventar"))
        with motor.connect() as v:
            rollen = {r for (r,) in v.execute(text("SELECT rolname FROM pg_roles"))}
            erbt = v.execute(text("SELECT pg_has_role('inventar_nutzer', 'kern_nutzer', 'member')")).scalar()
            fremd = [s for s in schemata if s not in ("kern", "inventar", "public", "information_schema") and not s.startswith("pg_")
                     and v.execute(text("SELECT has_schema_privilege('inventar_nutzer', :s, 'USAGE')"), {"s": s}).scalar()]
    finally:
        motor.dispose()
    assert {"kern", "inventar"} <= schemata and "beleg" not in schemata
    assert tabellen == set(modelle.TABELLEN) | {"alembic_version"} and len(modelle.TABELLEN) == 18
    assert "inventar_nutzer" in rollen and erbt and "beleg_nutzer" not in rollen
    assert fremd == [], f"inventar_nutzer kommt an fremde Schemata: {fremd}"


def test_t_i_5_startdaten_und_vorlagen(box) -> None:
    with systemsitzung("pruefung.t_i_5") as db:
        bausteine = {(r.modul, r.aktion): r.besitzer for r in db.execute(select(Recht)).scalars()}
        rolle = db.execute(select(Rolle).where(Rolle.schluessel == "polier")).scalar_one()
        polier = {f"{s.modul}.{s.aktion}" for s in db.execute(select(RolleRecht).where(RolleRecht.rolle_id == rolle.id)).scalars()}
        zahlen = {n: db.execute(text(f"SELECT count(*) FROM inventar.{n}")).scalar_one()
                  for n in ("gruppe", "merkmal", "pruefart", "gruppe_pruefart", "kostensatz", "einstellung", "stueck")}
    assert len(bausteine) == 9 + 11
    assert {a for (m, a), b in bausteine.items() if b == "inventar"} == {
        "sehen", "scannen", "buchen", "melden", "pflegen", "pruefen", "werkstatt", "stilllegen", "kosten_sehen",
        "kosten_pflegen", "einstellen"}
    assert not any(m in ("beleg", "rechnung", "maske", "export") for m, _ in bausteine)
    assert {b for b in polier if b.startswith("inventar.")} == {
        "inventar.sehen", "inventar.scannen", "inventar.buchen", "inventar.melden"}
    assert zahlen == {"gruppe": 12, "merkmal": 45, "pruefart": 19, "gruppe_pruefart": 30, "kostensatz": 12,
                      "einstellung": 8, "stueck": 0}, "Startdaten ohne Stücke"


def test_t_i_5_zweiter_start_aendert_nichts(box) -> None:
    from digiassistenz_kern import startdaten

    def stand():
        with systemsitzung("pruefung.t_i_5") as db:
            return {n: db.execute(text(f"SELECT count(*) FROM inventar.{n}")).scalar_one()
                    for n in ("gruppe", "merkmal", "pruefart", "gruppe_pruefart", "kostensatz", "einstellung")}
    vorher = stand()
    startdaten.sichern_beim_start("Prüfbetrieb Inventar")
    assert stand() == vorher


def test_t_i_5_anmelden_menue_und_verwaltung(box) -> None:
    klient = box.klient
    assert anmelden(klient) == "/inventar"
    seite = klient.get("/inventar")
    assert seite.status_code == 200
    wege = menuewege(seite.text)
    assert {"/inventar", "/inventar/hier", "/inventar/faellig", "/verwaltung"} <= set(wege)
    for fremd in ("/pruefen", "/belege", "/ablegen", "/verwaltung/masken", "/baustelle"):
        assert fremd not in wege, fremd
    assert tote_links(klient, seite.text) == []
    for weg in ("/inventar/hier", "/inventar/faellig", "/inventar/verwaltung", "/verwaltung", "/verwaltung/uebersicht",
                "/verwaltung/kostenstellen", "/verwaltung/lieferanten", "/geraete"):
        antwort = klient.get(weg)
        assert antwort.status_code == 200, weg
        assert tote_links(klient, antwort.text) == [], weg
    # die zweite Kopfzeile unter „Verwaltung“ trägt das Inventar
    assert "/inventar/verwaltung" in menuewege(klient.get("/verwaltung").text)
    assert t("web.titel") in seite.text and klient.post("/abmelden", follow_redirects=False).status_code == 303


def test_t_i_5_kostenstelle_reiter_ordner_und_uebersicht(box) -> None:
    klient = box.klient
    anmelden(klient)
    ks = _kostenstelle(klient)
    assert (box.arbeitsordner / "inventar" / "pruefbetrieb" / "kostenstellen" / "70101").is_dir()  # Ereignis
    seite = klient.get(f"/verwaltung/kostenstelle/{ks}")
    assert seite.status_code == 200 and t("inventar.reiter_hier") in seite.text
    reiter = klient.get(f"/inventar/kostenstelle/{ks}")
    assert reiter.status_code == 200 and t("inventar.reiter.vor_ort", anzahl=0) in reiter.text
    assert klient.get("/inventar/kostenstelle/999999").status_code == 403  # gibt es nicht = kein Recht (N7)
    uebersicht = klient.get("/verwaltung")  # die Zeilen des Moduls stehen im Zustand der Verwaltung
    assert 'hx-get="/inventar/uebersicht"' in uebersicht.text
    teil = klient.get("/inventar/uebersicht")
    assert teil.status_code == 200 and teil.text.lstrip().startswith("<tbody>") and t("inventar.uebersicht.gesamt") in teil.text
    _stueck(box.db_url, ks)
    assert t("inventar.reiter.vor_ort", anzahl=1) in klient.get(f"/inventar/kostenstelle/{ks}").text
    assert t("inventar.n_stueck", anzahl=1) in klient.get("/verwaltung/uebersicht").text


def test_t_i_5_liste_zeigt_stuecke_und_der_polier_nur_seine(box) -> None:
    klient = box.klient
    anmelden(klient)
    eigene, fremde = _kostenstelle(klient, "70101"), _kostenstelle(klient, "70102")
    _stueck(box.db_url, eigene, "BM-00001", "Hydraulikbagger")
    _stueck(box.db_url, fremde, "BM-00002", "Radlader")
    with systemsitzung("pruefung.t_i_5") as db:
        polier = int(db.execute(text("SELECT id FROM kern.benutzer WHERE anmeldename = :n"), {"n": POLIER}).scalar_one())
        db.add(BenutzerKostenstelle(benutzer_id=polier, kostenstelle_id=eigene))
    alle = klient.get("/inventar").text
    assert "BM-00001" in alle and "BM-00002" in alle
    klient.post("/abmelden")
    anmelden(klient, POLIER)
    seite = klient.get("/inventar")
    assert seite.status_code == 200 and "BM-00001" in seite.text and "BM-00002" not in seite.text
    assert klient.get("/inventar/hier").status_code == 200
    assert klient.get("/inventar/faellig").status_code == 403, "der Polier prüft nicht"
    assert klient.get("/inventar/verwaltung").status_code == 403
    wege = menuewege(seite.text)
    assert "/inventar/faellig" not in wege and "/inventar/verwaltung" not in wege and "/inventar/hier" in wege
    klient.post("/abmelden")
    anmelden(klient, POLIER_ZWEI)  # nirgends zugeordnet: sieht nichts
    assert "BM-00001" not in klient.get("/inventar").text


def test_t_i_5_suche_nur_mit_dem_rahmen_baustein(box) -> None:
    klient = box.klient
    anmelden(klient)
    ks = _kostenstelle(klient)
    _stueck(box.db_url, ks)
    kopf = klient.get("/inventar").text
    assert '<form class="suchfeld"' in kopf
    antwort = klient.get("/suche", params={"q": "bagger"})
    assert antwort.status_code == 200 and 'id="suche-inventar"' in antwort.text and "BM-00001" in antwort.text
    klient.post("/abmelden")
    with systemsitzung("pruefung.t_i_5") as db:  # Polier 2 verliert inventar.sehen
        from digiassistenz_kern import Benutzer
        from digiassistenz_kern import rechte as kern_rechte

        b = db.execute(select(Benutzer).where(Benutzer.anmeldename == POLIER_ZWEI)).scalar_one()
        kern_rechte.setzen(db, benutzer=b, schluessel="inventar.sehen", gewaehrt=False, grund="Prüffall")
    anmelden(klient, POLIER_ZWEI)
    seite = klient.get("/verwaltung").text if klient.get("/verwaltung").status_code == 200 else ""
    assert klient.get("/suche", params={"q": "bagger"}).status_code == 404
    assert '<form class="suchfeld"' not in seite


def test_t_i_5_ganz_ohne_modul(box) -> None:
    kern_modul.abmelden("inventar")
    klient = box.klient
    assert anmelden(klient) == "/verwaltung"
    assert klient.get("/suche", params={"q": "x"}).status_code == 404
    assert tote_links(klient, klient.get("/verwaltung").text) == []
    assert t("web.titel") == t("app.name")
