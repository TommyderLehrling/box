"""Die Seiten von L11/L12 durch die echte Anwendung des Kerns (Kern + Inventar, PostgreSQL) — Anlegen, Buchen, Pflegen.

Gleicher Aufbau wie T-I-5 (`aufbau_pruefen({"inventar"})`). Jeder Fall meldet sich an, legt Kostenstellen über die Kern-Seite
an und geht nur über Wege der Oberfläche (kein Datenbankzugriff außer zum Prüfen und zum Zuordnen eines Polier-Kontos).
"""

from __future__ import annotations

import io
import re
import uuid
from decimal import Decimal

import pytest
from openpyxl import Workbook
from sqlalchemy import select, text

from conftest import POLIER, POLIER_ZWEI, VERWALTER, anmelden, aufbau_pruefen
from digiassistenz_kern import BenutzerKostenstelle, Kostenstelle
from digiassistenz_kern.sitzung import systemsitzung
from digiassistenz_kern.texte import t

pytestmark = pytest.mark.usefixtures("_seiten_aufbau")

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


@pytest.fixture(scope="module")
def _seiten_aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _ks(klient, nummer: str) -> int:
    antwort = klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                          data={"nummer": nummer, "bezeichnung": f"Baustelle {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"})
    assert antwort.status_code == 303
    with systemsitzung("pruefung.seiten") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _zuordnen(benutzer: str, *ks: int) -> None:
    with systemsitzung("pruefung.seiten") as db:
        bid = int(db.execute(text("SELECT id FROM kern.benutzer WHERE anmeldename = :n"), {"n": benutzer}).scalar_one())
        for k in ks:
            db.add(BenutzerKostenstelle(benutzer_id=bid, kostenstelle_id=k))


def _neu(klient, bezeichnung: str = "Hydraulikbagger", nummer: str = "", ks: str = "70101", gruppe: str = "baumaschine", art: str = "gross", **mehr) -> int:
    daten = {"bezeichnung": bezeichnung, "gruppe": gruppe, "art": art, "inventarnummer": nummer, "kostenstelle": ks, "menge": "1", **mehr}
    antwort = klient.post("/inventar/stueck/neu", data=daten, follow_redirects=False)
    assert antwort.status_code == 303, antwort.text[:400]
    treffer = re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"])
    assert treffer, antwort.headers["location"]
    return int(treffer.group(1))


def _db_ein(sql: str, **werte):
    with systemsitzung("pruefung.seiten") as db:
        return db.execute(text(sql), werte).all()


def test_liste_ordner_suche_und_qr_ziel(box) -> None:
    k = box.klient
    anmelden(k)
    _ks(k, "70101")
    sid = _neu(k, "Hydraulikbagger", "BM-00007", seriennummer="CAT-4711")
    _neu(k, "Radlader", "BM-00008")
    seite = k.get("/inventar")
    assert seite.status_code == 200 and "BM-00007" in seite.text and "BM-00008" in seite.text and 'id="inventar-liste"' in seite.text
    teil = k.get("/inventar/liste", params={"q": "cat-47"})
    assert teil.status_code == 200 and "BM-00007" in teil.text and "BM-00008" not in teil.text and "<html" not in teil.text
    assert "BM-00008" in k.get("/inventar/liste", params={"q": "70101"}).text, "Suche nach dem Ort"
    assert "BM-00007" not in k.get("/inventar/liste", params={"status": "vermisst"}).text
    assert "BM-00007" in k.get("/inventar/liste", params={"kostenstelle": "70101"}).text
    ordner = k.get("/inventar", params={"ansicht": "ordner"})
    assert ordner.status_code == 200 and "inventar-gruppe" in ordner.text and "BM-00007" in ordner.text
    sortiert = k.get("/inventar/liste", params={"sortieren": "nummer", "richtung": "ab"}).text
    assert sortiert.index("BM-00008") < sortiert.index("BM-00007")
    ziel = k.get("/inventar/s/bm-00007", follow_redirects=False)
    assert ziel.status_code == 303 and ziel.headers["location"] == f"/inventar/stueck/{sid}"
    assert k.get("/inventar/s/CAT-4711?ks=5", follow_redirects=False).headers["location"] == f"/inventar/stueck/{sid}?ks=5"
    assert k.get("/inventar/s/gibt-es-nicht", follow_redirects=False).status_code == 403
    assert k.get("/inventar/s", params={"nummer": "BM-00008"}, follow_redirects=False).status_code == 303


def test_stueck_anlegen_aendern_foto_status_zubehoer_zaehler_meldung_verlauf(box) -> None:
    k = box.klient
    anmelden(k)
    _ks(k, "70101")
    form = k.get("/inventar/stueck/neu")
    assert form.status_code == 200 and 'name="inventarnummer"' in form.text and "wahl-start-ks" in form.text
    teil = k.get("/inventar/merkmale", params={"gruppe": "baumaschine", "neu": "1"})
    assert "m_betriebsgewicht" in teil.text and 'hx-swap-oob="true"' in teil.text and "BM-" in teil.text
    sid = _neu(k, "Hydraulikbagger", kaufpreis="52.000,00".replace(".", "").replace(",", "."), m_betriebsgewicht="12,5")
    nummer = _db_ein("SELECT inventarnummer FROM inventar.stueck WHERE id = :i", i=sid)[0][0]
    assert re.fullmatch(r"BM-\d{5}", nummer), "Nummer aus dem Muster vergeben"
    seite = k.get(f"/inventar/stueck/{sid}", params={"fertig": "angelegt"})
    assert seite.status_code == 200 and 'id="statuszeile"' in seite.text and nummer in seite.text and "12,5" in seite.text
    assert seite.text.index("<h1>") < seite.text.index('id="statuszeile"') < seite.text.index("<details open>")
    assert t("inventar.fertig.angelegt") in seite.text and "52000" in seite.text.replace(".", "").replace(" ", "")
    # Ändern mit Foto
    aendern = k.post(f"/inventar/stueck/{sid}/aendern", follow_redirects=False,
                     data={"bezeichnung": "Hydraulikbagger 20 t", "hersteller": "Cat", "m_betriebsgewicht": "20"},
                     files={"foto": ("foto.png", io.BytesIO(PNG), "image/png")})
    assert aendern.status_code == 303, aendern.text[:300]
    zeile = _db_ein("SELECT bezeichnung, hersteller, foto_pfad, foto_sha256 FROM inventar.stueck WHERE id = :i", i=sid)[0]
    assert zeile[0] == "Hydraulikbagger 20 t" and zeile[1] == "Cat" and zeile[2] and len(zeile[3]) == 64
    assert (box.arbeitsordner / zeile[2]).read_bytes() == PNG
    falsch = k.post(f"/inventar/stueck/{sid}/aendern", data={"bezeichnung": "x"}, files={"foto": ("a.gif", io.BytesIO(b"GIF89a"), "image/gif")})
    assert falsch.status_code == 409 and t("inventar.code.dateien.foto_typ") in falsch.text
    assert _db_ein("SELECT bezeichnung FROM inventar.stueck WHERE id = :i", i=sid)[0][0] == "Hydraulikbagger 20 t", "Fehler schreibt nichts"
    unecht = k.post(f"/inventar/stueck/{sid}/aendern", data={"bezeichnung": "x"}, files={"foto": ("a.png", io.BytesIO(b"kein Bild"), "image/png")})
    assert unecht.status_code == 409 and t("inventar.code.dateien.foto_typ") in unecht.text, "die Angabe allein genügt nicht"
    # Status mit Grund
    assert k.post(f"/inventar/stueck/{sid}/status", data={"status": "stillgelegt", "grund": ""}).status_code == 409
    assert k.post(f"/inventar/stueck/{sid}/status", data={"status": "stillgelegt", "grund": "Totalschaden"}, follow_redirects=False).status_code == 303
    assert _db_ein("SELECT status FROM inventar.stueck WHERE id = :i", i=sid)[0][0] == "stillgelegt"
    # Zubehör und Bauteil (Katalog leer: erst anlegen)
    löffel = _neu(k, "Tieflöffel", "BM-00500", art="klein")
    assert k.post(f"/inventar/stueck/{löffel}/zubehoer", data={"haupt_nummer": nummer}, follow_redirects=False).status_code == 303
    assert k.post(f"/inventar/stueck/{löffel}/zubehoer", data={"haupt_nummer": nummer}).status_code == 409
    beziehung = _db_ein("SELECT id FROM inventar.beziehung WHERE gueltig_bis IS NULL AND art = 'gehoert_zu'")[0][0]
    assert "Tieflöffel" in k.get(f"/inventar/stueck/{sid}").text
    assert k.post(f"/inventar/stueck/{löffel}/zubehoer", data={"beenden": str(beziehung)}, follow_redirects=False).status_code == 303
    assert _db_ein("SELECT gueltig_bis IS NOT NULL FROM inventar.beziehung WHERE id = :i", i=beziehung)[0][0], "beendet, nicht gelöscht"
    assert k.post("/inventar/verwaltung/bauteile", data={"bauteilnummer": "HF-1", "bezeichnung": "Hydraulikfilter", "preis": "12,50", "aktiv": "1"},
                  follow_redirects=False).status_code == 303
    bauteil = _db_ein("SELECT id FROM inventar.bauteil WHERE bauteilnummer = 'HF-1'")[0][0]
    assert k.post(f"/inventar/stueck/{sid}/bauteil", data={"bauteil_id": str(bauteil)}, follow_redirects=False).status_code == 303
    assert "Hydraulikfilter" in k.get(f"/inventar/stueck/{sid}").text
    # Zählerstand: aufsteigend, Einheit vom Stück
    assert k.post(f"/inventar/stueck/{sid}/zaehlerstand", data={"stand": "120,5"}, follow_redirects=False).status_code == 303
    assert k.post(f"/inventar/stueck/{sid}/zaehlerstand", data={"stand": "100"}).status_code == 409
    assert _db_ein("SELECT stand, einheit, quelle FROM inventar.zaehlerstand")[0] == (Decimal("120.500"), "h", "web")
    # Schaden melden
    ks_id = _db_ein("SELECT kostenstelle_id FROM inventar.standort WHERE stueck_id = :i AND bis IS NULL", i=sid)[0][0]
    buchung = str(uuid.uuid4())
    daten = {"kostenstelle_id": str(ks_id), "beschreibung": "Hydraulikschlauch undicht", "buchung": buchung}
    assert k.post(f"/inventar/stueck/{sid}/meldung", data=daten, files={"foto": ("s.png", io.BytesIO(PNG), "image/png")}, follow_redirects=False).status_code == 303
    assert k.post(f"/inventar/stueck/{sid}/meldung", data=daten, follow_redirects=False).status_code == 303
    assert _db_ein("SELECT count(*) FROM inventar.meldung")[0][0] == 1, "dieselbe Buchung zweimal: eine Meldung"
    assert _db_ein("SELECT status, foto_sha256 IS NOT NULL FROM inventar.meldung")[0] == ("offen", True)
    verlauf = k.get(f"/inventar/stueck/{sid}").text
    for erwartet in ("inventar.stueck_angelegt", "stueck_geaendert", "stueck_status"):
        assert any(erwartet in a for (a,) in _db_ein("SELECT aktion FROM kern.protokoll WHERE objekt_typ = 'inventar.stueck' AND objekt_id = :i", i=sid)), erwartet
    assert t("inventar.aktion.stueck_angelegt") in verlauf and t("inventar.aktion.meldung_angelegt") in verlauf
    assert "Hydraulikschlauch undicht" in verlauf


def test_abgang_eingang_scan_und_zurueckziehen_bis_zur_hier_seite(box) -> None:
    k = box.klient
    anmelden(k)
    a, b = _ks(k, "70101"), _ks(k, "70102")
    _zuordnen(POLIER, a)
    _zuordnen(POLIER_ZWEI, b)
    sid = _neu(k, "Plattenrüttler", "BM-00101", art="klein", ks="70101")
    menge = _neu(k, "Absperrgitter", "BM-00102", art="menge", ks="70101", menge="10")
    schluessel = str(uuid.uuid4())
    abgang = {"stueck_id": str(sid), "von": str(a), "nach": "70102", "menge": "1", "grund": "Bedarf", "eintrag_schluessel": schluessel}
    assert k.post("/inventar/transfer/abgang", data=abgang, follow_redirects=False).status_code == 303
    assert k.post("/inventar/transfer/abgang", data=abgang, follow_redirects=False).status_code == 303, "zweimal absenden bucht einmal"
    assert _db_ein("SELECT count(*) FROM inventar.transfer WHERE stueck_id = :i", i=sid)[0][0] == 1
    fehler = k.post("/inventar/transfer/abgang", data={**abgang, "nach": "70101", "eintrag_schluessel": str(uuid.uuid4())})
    assert fehler.status_code == 409 and t("inventar.code.transfer.gleiche_kostenstelle") in fehler.text
    teil = k.post("/inventar/transfer/abgang", follow_redirects=False,
                  data={"stueck_id": str(menge), "von": str(a), "nach": "70102", "menge": "4", "grund": "", "eintrag_schluessel": str(uuid.uuid4())})
    assert teil.status_code == 303
    tid = _db_ein("SELECT id FROM inventar.transfer WHERE stueck_id = :i", i=sid)[0][0]
    mid_t = _db_ein("SELECT id FROM inventar.transfer WHERE stueck_id = :i", i=menge)[0][0]
    k.post("/abmelden")
    # Polier 2 auf Ziel: Hier-Seite, angekündigt, Teil-Eingang
    anmelden(k, POLIER_ZWEI)
    hier = k.get("/inventar/hier")
    assert hier.status_code == 200 and "BM-00101" in hier.text and "BM-00102" in hier.text and f"/inventar/transfer/{tid}/eingang" in hier.text
    assert "/inventar/scannen?ks=" in hier.text and 'name="menge"' in hier.text
    assert k.get("/inventar/scannen").status_code == 200
    assert k.get("/inventar/stueck/neu").status_code == 403 and k.get("/inventar/verwaltung").status_code == 403
    assert k.post(f"/inventar/transfer/{tid}/eingang", data={"weiter": "hier"}, follow_redirects=False).headers["location"] == "/inventar/hier?fertig=eingang"
    assert _db_ein("SELECT status FROM inventar.transfer WHERE id = :i", i=tid)[0][0] == "bestaetigt"
    assert k.post(f"/inventar/transfer/{mid_t}/eingang", data={"menge": "3", "weiter": "hier"}, follow_redirects=False).status_code == 303
    assert _db_ein("SELECT sum(menge) FROM inventar.standort WHERE stueck_id = :i AND bis IS NULL AND kostenstelle_id = :k", i=menge, k=b)[0][0] == 3
    nach = k.get("/inventar/hier").text
    assert "BM-00101" in nach and t("inventar.fertig.eingang") not in nach
    assert k.get("/inventar/hier", params={"fertig": "eingang"}).text.count("✓") >= 1
    # Polier 1 (Ursprung) sieht das Stück am Ziel nicht mehr, aber Polier 2 darf zurückziehen nur mit buchen auf der Herkunft: nein
    assert k.post(f"/inventar/transfer/{tid}/zurueck", data={"grund": "x"}).status_code in (403, 409)
    k.post("/abmelden")
    # Scan „ist hier“ durch den Polier der Herkunft: das Stück steht zwar dort, aber ein Scan auf fremder Kostenstelle ist verboten
    anmelden(k, POLIER)
    seite = k.get(f"/inventar/stueck/{menge}", params={"ks": str(a)})
    assert seite.status_code == 200 and 'id="scan-tasten"' in seite.text
    scan = k.post("/inventar/transfer/scan", data={"stueck_id": str(menge), "kostenstelle": str(a), "eintrag_schluessel": str(uuid.uuid4())}, follow_redirects=False)
    assert scan.status_code in (303, 409)
    fremd = k.post("/inventar/transfer/scan", data={"stueck_id": str(menge), "kostenstelle": str(b), "eintrag_schluessel": str(uuid.uuid4())})
    assert fremd.status_code == 403
    assert "/inventar/stueck/neu" not in k.get("/inventar").text, "Polier hat keine Neu-Taste"
    k.post("/abmelden")
    # Zurückziehen durch den Verwalter, solange noch offen: neuer Abgang, dann zurück mit Grund
    anmelden(k)
    zwei = str(uuid.uuid4())
    k.post("/inventar/transfer/abgang", data={"stueck_id": str(sid), "von": str(b), "nach": "70101", "menge": "1", "eintrag_schluessel": zwei})
    offen = _db_ein("SELECT id FROM inventar.transfer WHERE stueck_id = :i AND status = 'angekuendigt'", i=sid)[0][0]
    assert k.post(f"/inventar/transfer/{offen}/zurueck", data={"grund": ""}).status_code == 409
    assert k.post(f"/inventar/transfer/{offen}/zurueck", data={"grund": "falsch gebucht"}, follow_redirects=False).status_code == 303
    assert _db_ein("SELECT status FROM inventar.transfer WHERE id = :i", i=offen)[0][0] == "zurueckgezogen"
    verlauf = k.get(f"/inventar/stueck/{sid}").text
    assert t("inventar.code.transfer.abgang") in verlauf and t("inventar.code.transfer.eingang") in verlauf and t("inventar.code.transfer.zurueckgezogen") in verlauf


def test_verwaltung_kataloge_einstellungen_und_rechte(box) -> None:
    k = box.klient
    anmelden(k)
    _ks(k, "70101")
    kacheln = k.get("/inventar/verwaltung")
    assert kacheln.status_code == 200 and "/inventar/verwaltung/import" in kacheln.text and "/inventar/verwaltung/testdaten" in kacheln.text
    for seite in ("gruppen", "merkmale", "pruefarten", "bauteile", "kostensaetze", "einstellungen", "import", "etiketten", "testdaten"):
        assert k.get(f"/inventar/verwaltung/{seite}").status_code == 200, seite
    ok = lambda antwort: antwort.status_code == 303  # noqa: E731
    assert ok(k.post("/inventar/verwaltung/gruppen", data={"schluessel": "geruest", "bezeichnung": "Gerüste", "kuerzel": "GR", "sortierung": "99", "aktiv": "1"}, follow_redirects=False))
    assert k.post("/inventar/verwaltung/gruppen", data={"schluessel": "doppelt", "bezeichnung": "X", "kuerzel": "GR", "aktiv": "1"}).status_code == 409
    assert k.post("/inventar/verwaltung/gruppen", data={"schluessel": "klein", "bezeichnung": "X", "kuerzel": "g"}).status_code == 409
    assert ok(k.post("/inventar/verwaltung/gruppen", data={"schluessel": "geruest", "bezeichnung": "Gerüste", "kuerzel": "GR"}, follow_redirects=False))
    assert _db_ein("SELECT aktiv FROM inventar.gruppe WHERE schluessel = 'geruest'")[0][0] is False, "ausgeblendet statt gelöscht"
    assert ok(k.post("/inventar/verwaltung/merkmale", data={"gruppe": "geruest", "schluessel": "feldlaenge", "bezeichnung": "Feldlänge", "typ": "zahl", "einheit": "m", "aktiv": "1"}, follow_redirects=False))
    assert k.post("/inventar/verwaltung/merkmale", data={"gruppe": "geruest", "schluessel": "wahl", "bezeichnung": "W", "typ": "auswahl", "auswahl": ""}).status_code == 409
    assert ok(k.post("/inventar/verwaltung/pruefarten", data={
        "schluessel": "geruestpruefung", "bezeichnung": "Gerüstprüfung", "intervall_monate": "12", "durchfuehrung": "extern", "g_geruest": "geruest",
        "je_merkmal": "", "aktiv": "1"}, follow_redirects=False))
    assert _db_ein("SELECT count(*) FROM inventar.gruppe_pruefart gp JOIN inventar.gruppe g ON g.id = gp.gruppe_id WHERE g.schluessel = 'geruest' AND gp.aktiv")[0][0] == 1
    assert k.post("/inventar/verwaltung/pruefarten", data={"schluessel": "x", "bezeichnung": "X", "intervall_monate": "0"}).status_code == 409
    assert ok(k.post("/inventar/verwaltung/kostensaetze", data={"gruppe": "geruest", "nutzungsdauer": "120", "zins": "4", "reparatur": "2", "satz_monat": "30,5"}, follow_redirects=False))
    assert k.post("/inventar/verwaltung/kostensaetze", data={"gruppe": "geruest", "nutzungsdauer": "120", "zins": "4", "reparatur": "2"}).status_code == 409
    assert ok(k.post("/inventar/verwaltung/einstellungen", data={"transfer_frist_werktage": "5", "nummernmuster": "{gruppe}-{jahr}-{nr:4}"}, follow_redirects=False))
    assert _db_ein("SELECT wert FROM inventar.einstellung WHERE schluessel = 'transfer_frist_werktage'")[0][0] == "5"
    assert k.post("/inventar/verwaltung/einstellungen", data={"nummernmuster": "{nr}"}).status_code == 409
    neu_nr = _neu(k, "Rahmen", "", gruppe="geruest", art="klein", m_feldlaenge="3")
    assert re.fullmatch(r"GR-\d{4}-\d{4}", _db_ein("SELECT inventarnummer FROM inventar.stueck WHERE id = :i", i=neu_nr)[0][0])
    # Polier: keine Verwaltung, keine Preise
    k.post("/abmelden")
    anmelden(k, POLIER)
    for weg in ("/inventar/verwaltung", "/inventar/verwaltung/gruppen", "/inventar/verwaltung/import", "/inventar/verwaltung/etiketten"):
        assert k.get(weg).status_code == 403, weg
    assert k.post("/inventar/verwaltung/gruppen", data={"schluessel": "x", "bezeichnung": "X", "kuerzel": "XX"}).status_code == 403


def _datei(zeilen: list[list]) -> bytes:
    from digiassistenz_inventar.rein.import_vorlage import BLATT, SPALTEN

    wb = Workbook()
    ws = wb.active
    ws.title = BLATT
    ws.append(list(SPALTEN))
    for z in zeilen:
        ws.append(z)
    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


def test_import_etiketten_und_testdaten(box) -> None:
    k = box.klient
    anmelden(k)
    _ks(k, "70101")
    vorlage = k.get("/inventar/verwaltung/import/vorlage")
    assert vorlage.status_code == 200 and vorlage.content[:2] == b"PK" and "spreadsheetml" in vorlage.headers["content-type"]
    gut = _datei([["BM-00300", "Rüttelplatte", "baumaschine", "klein", "Wacker", "", "SN-1", 2021, "", "", "", 70101, 1, ""],
                  ["BM-00301", "Stampfer", "baumaschine", "klein", "Wacker", "", "SN-2", 2021, "", "", "", 70101, 1, ""]])
    bericht = k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"}, files={"datei": ("start.xlsx", io.BytesIO(gut), "application/octet-stream")})
    assert bericht.status_code == 200 and "BM-00300" not in bericht.text and 'value="einspielen"' in bericht.text
    kennung = re.search(r'name="datei" value="([0-9a-f]{32})"', bericht.text).group(1)
    assert _db_ein("SELECT count(*) FROM inventar.stueck")[0][0] == 0, "Prüfen schreibt nichts"
    fertig = k.post("/inventar/verwaltung/import", data={"aktion": "einspielen", "datei": kennung})
    assert fertig.status_code == 200 and t("inventar.import.angelegt", anzahl=2) in fertig.text
    assert _db_ein("SELECT count(*) FROM inventar.stueck")[0][0] == 2
    wieder = k.post("/inventar/verwaltung/import", data={"aktion": "einspielen", "datei": kennung})
    assert wieder.status_code == 200 and _db_ein("SELECT count(*) FROM inventar.stueck")[0][0] == 2, "zweiter Lauf legt nichts neu an"
    schlecht = _datei([["BM-00302", "", "gibtsnicht", "klein", "", "", "", "", "", "", "", 70101, 1, ""]])
    fehlerbericht = k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"}, files={"datei": ("f.xlsx", io.BytesIO(schlecht), "application/octet-stream")})
    assert fehlerbericht.status_code == 200 and 'value="einspielen"' not in fehlerbericht.text and t("inventar.import.fehler.gruppe_unbekannt") in fehlerbericht.text
    kennung2 = re.search(r"([0-9a-f]{32})", (box.arbeitsordner / "inventar" / "pruefbetrieb" / "import").glob("*.xlsx").__next__().name).group(1)
    assert k.post("/inventar/verwaltung/import", data={"aktion": "einspielen", "datei": kennung2 if kennung2 != kennung else "0" * 32}).status_code == 409
    assert k.post("/inventar/verwaltung/import", data={"aktion": "einspielen", "datei": "../../etc/passwd"}).status_code == 409
    assert k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"}).status_code == 409
    kaputt = k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"}, files={"datei": ("k.xlsx", io.BytesIO(b"kein zip"), "application/octet-stream")})
    assert kaputt.status_code == 409 and t("inventar.code.import_lauf.datei_unlesbar") in kaputt.text
    # Etiketten
    pdf = k.post("/inventar/verwaltung/etiketten", data={"gruppe": "baumaschine", "nummern": "", "kostenstelle": "70101"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF" and "attachment" in pdf.headers["content-disposition"]
    assert list((box.arbeitsordner / "inventar" / "pruefbetrieb" / "export").glob("etiketten_*.pdf"))
    assert k.post("/inventar/verwaltung/etiketten", data={"nummern": "XX-1"}).status_code in (200, 409)
    assert k.post("/inventar/verwaltung/etiketten", data={"gruppe": "it"}).status_code == 409, "nichts zu drucken"
    # Testdaten nur bis zur Auslieferung
    erste = k.post("/inventar/verwaltung/testdaten", data={"seed": "7", "anzahl": "30"})
    assert erste.status_code == 200 and "30" in erste.text
    assert _db_ein("SELECT count(*) FROM inventar.stueck")[0][0] >= 30
    assert k.post("/inventar/verwaltung/einstellungen", data={"auslieferung_am": "2026-10-09"}, follow_redirects=False).status_code == 303
    assert k.post("/inventar/verwaltung/testdaten", data={"seed": "8", "anzahl": "5"}).status_code == 409
    assert "/inventar/verwaltung/testdaten" not in k.get("/inventar/verwaltung").text
    assert k.post("/inventar/verwaltung/einstellungen", data={"auslieferung_am": ""}).status_code == 409, "die Auslieferung nimmt niemand zurück"
