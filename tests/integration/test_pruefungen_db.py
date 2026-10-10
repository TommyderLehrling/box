"""L13 und Umlauf 01 durch die echte Anwendung (Kern 0.15.3 + Inventar, PostgreSQL): Fällig-Liste, Prüfung mit Nachweis,
Prüfarten je Gruppe und Stück, Erinnerung als Modulprozess, Kaufdaten-Recht, Scan-Quelle, Startstandort.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from conftest import POLIER, POLIER_ZWEI, VERWALTER, _konto, anmelden, aufbau_pruefen
from digiassistenz_kern import Benutzer, BenutzerKostenstelle, Kostenstelle, Mandant
from digiassistenz_kern import rechte as kern_rechte
from digiassistenz_kern.sitzung import benutzersitzung, systemsitzung
from digiassistenz_kern.web import gemeinsam

from digiassistenz_inventar import erinnern
from digiassistenz_inventar.dienstlogik import erinnerungen, pflege, pruefung, stueck

pytestmark = pytest.mark.usefixtures("_aufbau")

PDF = b"%PDF-1.4\n% Nachweis\n"
HEUTE = dt.date.today()


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _ks(klient, nummer: str) -> int:
    anmelden(klient)
    antwort = klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                          data={"nummer": nummer, "bezeichnung": f"Baustelle {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"})
    assert antwort.status_code == 303
    with systemsitzung("pruefung.l13") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _neu(klient, bezeichnung: str, gruppe: str = "bueroausstattung", art: str = "klein", ks: str = "70101", **mehr) -> int:
    daten = {"bezeichnung": bezeichnung, "gruppe": gruppe, "art": art, "inventarnummer": "", "kostenstelle": ks, "menge": "1", **mehr}
    antwort = klient.post("/inventar/stueck/neu", data=daten, follow_redirects=False)
    assert antwort.status_code == 303, antwort.text[:400]
    return int(re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"]).group(1))


def _db(sql: str, **werte):
    with systemsitzung("pruefung.l13") as db:
        return db.execute(text(sql), werte).all()


def _block(html: str, kennung: str) -> str:
    teil = html.split(f'id="faellig-{kennung}"', 1)[1]
    return teil.split("</section>", 1)[0]


def _eintragen(k, sid: int, **felder):
    daten = {"pruefart": "dguv_v3_buero", "durchgefuehrt_am": HEUTE.isoformat(), "ergebnis": "bestanden", "durchfuehrung": "intern", **felder}
    nachweis = daten.pop("nachweis", PDF)
    dateien = {} if nachweis is None else {"nachweis": ("nachweis.pdf", io.BytesIO(nachweis), "application/pdf")}
    return k.post(f"/inventar/stueck/{sid}/pruefung", data=daten, files=dateien or None, follow_redirects=False)


def test_faellig_liste_pruefung_mit_nachweis_ampel_und_fehlerfaelle(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _neu(k, "Tischdrucker")
    nummer = _db("SELECT inventarnummer FROM inventar.stueck WHERE id = :i", i=sid)[0][0]
    seite = k.get("/inventar/faellig")
    assert seite.status_code == 200
    assert "Tischdrucker" in _block(seite.text, "ohne_nachweis") and "Tischdrucker" not in _block(seite.text, "ueberfaellig")
    assert f"/inventar/stueck/{sid}?pruefart=dguv_v3_buero&amp;weiter=faellig#pruefung-eintragen" in seite.text, "Taste je Zeile"
    dialog = k.get(f"/inventar/stueck/{sid}", params={"pruefart": "dguv_v3_buero", "weiter": "faellig"})
    assert 'id="pruefung-eintragen" open' in dialog.text and 'enctype="multipart/form-data"' in dialog.text
    assert 'name="weiter" value="faellig"' in dialog.text

    # Fehlerfälle schreiben nichts
    fehler = {
        "zukunft": (_eintragen(k, sid, durchgefuehrt_am=(HEUTE + dt.timedelta(days=2)).isoformat()), "Zukunft"),
        "gif": (_eintragen(k, sid, nachweis=b"GIF89a-kein-nachweis"), "PDF-, JPG- oder PNG"),
        "extern_ohne_pruefer": (_eintragen(k, sid, durchfuehrung="extern"), "Lieferanten wählen"),
        "art": (_eintragen(k, sid, pruefart="hu"), "gehört nicht zu diesem Stück"),
        "ohne_datum": (_eintragen(k, sid, durchgefuehrt_am=""), "Datum"),
        "ergebnis": (_eintragen(k, sid, ergebnis="vielleicht"), "unbekannt"),
    }
    for name, (antwort, stichwort) in fehler.items():
        assert antwort.status_code == 409 and stichwort in antwort.text, (name, antwort.text[:300])
    assert _db("SELECT count(*) FROM inventar.pruefung")[0][0] == 0

    # Eintragen mit Nachweis: Datei, Prüfsumme, Prüfer = der Eintragende, nächste Fälligkeit in 24 Monaten
    antwort = _eintragen(k, sid, weiter="faellig", bemerkung="alles gut")
    assert antwort.status_code == 303 and antwort.headers["location"] == "/inventar/faellig?fertig=pruefung"
    zeile = _db("SELECT id, nachweis_pfad, nachweis_sha256, pruefer_benutzer_id, pruefer_text, naechste_am, ergebnis, quelle FROM inventar.pruefung")[0]
    pid = zeile[0]
    assert (box.arbeitsordner / zeile[1]).read_bytes() == PDF and len(zeile[2]) == 64
    assert "/pruefbetrieb/stamm/" in zeile[1] and zeile[1].endswith("/pruefungen/nachweis.pdf")
    with systemsitzung("pruefung.l13") as db:
        verwalter = int(db.execute(select(Benutzer.id).where(Benutzer.anmeldename == VERWALTER)).scalar_one())
    assert zeile[3] == verwalter and zeile[4] == "" and zeile[6] == "bestanden" and zeile[7] == "web"
    assert zeile[5] == dt.date(HEUTE.year + 2, HEUTE.month, min(HEUTE.day, 28)) or zeile[5].year == HEUTE.year + 2
    nach = k.get("/inventar/faellig", params={"fertig": "pruefung"})
    assert "Tischdrucker" not in nach.text.split('id="faellig-ueberfaellig"', 1)[1] and "Prüfung eingetragen" in nach.text
    stueck_seite = k.get(f"/inventar/stueck/{sid}").text
    assert f"/inventar/pruefung/{pid}/nachweis" in stueck_seite and "Nachweis ansehen" in stueck_seite

    # Nachweis ansehen: derselbe Inhalt; verändert → Fehler; Polier ohne Kostenstelle: kein Recht
    datei = k.get(f"/inventar/pruefung/{pid}/nachweis")
    assert datei.status_code == 200 and datei.content == PDF and datei.headers["content-type"] == "application/pdf"
    assert datei.headers["x-content-type-options"] == "nosniff"
    pfad = box.arbeitsordner / zeile[1]
    pfad.write_bytes(PDF + b"manipuliert")
    kaputt = k.get(f"/inventar/pruefung/{pid}/nachweis")
    assert kaputt.status_code == 409 and "Prüfsumme" in kaputt.text
    pfad.write_bytes(PDF)
    k.post("/abmelden")
    anmelden(k, POLIER)
    assert k.get(f"/inventar/pruefung/{pid}/nachweis").status_code == 403
    assert k.get("/inventar/faellig").status_code == 403, "Polier hat weder pruefen noch werkstatt"
    assert k.post(f"/inventar/stueck/{sid}/pruefung", data={"pruefart": "dguv_v3_buero"}).status_code == 403
    k.post("/abmelden")
    anmelden(k)

    # Nicht bestanden: sofort überfällig (rot); ein Name geht vor dem gewählten Benutzer
    rot = _eintragen(k, sid, ergebnis="nicht_bestanden", pruefer_text="Elektro Weber", pruefer_benutzer_id=str(verwalter))
    assert rot.status_code == 303
    letzte = _db("SELECT pruefer_text, pruefer_benutzer_id, ergebnis FROM inventar.pruefung ORDER BY id DESC LIMIT 1")[0]
    assert letzte == ("Elektro Weber", None, "nicht_bestanden")
    seite = k.get("/inventar/faellig")
    assert "Tischdrucker" in _block(seite.text, "ueberfaellig") and "Tischdrucker" not in _block(seite.text, "ohne_nachweis")
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.pruefung_eingetragen'")[0][0] == 2
    # Filter: andere Prüfart / andere Kostenstelle → leer
    leer = k.get("/inventar/faellig", params={"pruefart": "hu"})
    assert "Tischdrucker" not in leer.text.split('id="faellig-ueberfaellig"', 1)[1]
    assert nummer in k.get("/inventar/faellig", params={"kostenstelle": "70101"}).text


def test_extern_mit_lieferant_zaehlerstand_aus_der_pruefung_und_foto_nachweis(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _neu(k, "Radlader", gruppe="baumaschine", art="gross")
    fehlt = _eintragen(k, sid, pruefart="wartung_betriebsstunden")
    assert fehlt.status_code == 409 and "Zählerstand" in fehlt.text
    png = bytes.fromhex("89504e470d0a1a0a") + b"x" * 20
    ok = k.post(f"/inventar/stueck/{sid}/pruefung", follow_redirects=False,
                data={"pruefart": "wartung_betriebsstunden", "durchgefuehrt_am": HEUTE.isoformat(), "ergebnis": "bestanden", "durchfuehrung": "extern",
                      "pruefer_text": "Werkstatt Nord", "zaehlerstand": "1.250,5".replace(".", ""), "bemerkung": ""},
                files={"nachweis": ("scan.jpeg", io.BytesIO(png), "image/jpeg")})
    assert ok.status_code == 303, ok.text[:300]
    zeile = _db("SELECT zaehlerstand, nachweis_pfad, durchfuehrung, pruefer_text FROM inventar.pruefung")[0]
    assert zeile[0] == Decimal("1250.500") and zeile[1].endswith(".png"), "die Endung kommt vom Inhalt, nicht vom Namen"
    assert zeile[2:] == ("extern", "Werkstatt Nord")
    assert _db("SELECT stand, quelle FROM inventar.zaehlerstand")[0] == (Decimal("1250.500"), "pruefung"), "Stand der Prüfung gilt als Ablesung"
    # nach 500 Betriebsstunden wäre sie fällig: Ablesung 1.760 → rot durch den Zähler
    assert k.post(f"/inventar/stueck/{sid}/zaehlerstand", data={"stand": "1760"}, follow_redirects=False).status_code == 303
    block = _block(k.get("/inventar/faellig").text, "ueberfaellig")
    assert "Radlader" in block and "Betriebsstunden" in block


def test_pruefarten_je_gruppe_und_je_stueck_und_intervall(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _neu(k, "Kopierer")
    # je Gruppe: das Intervall der Prüfart (24) mit 6 überschreiben — und die zweite Gruppe 'it' bleibt zugeordnet
    felder = {"schluessel": "dguv_v3_buero", "bezeichnung": "DGUV V3 Büro", "intervall_monate": "24", "durchfuehrung": "beides", "aktiv": "1",
              "g_it": "it", "g_bueroausstattung": "bueroausstattung", "gi_bueroausstattung": "6", "gi_it": ""}
    assert k.post("/inventar/verwaltung/pruefarten", data=felder, follow_redirects=False).status_code == 303
    assert _db("SELECT g.schluessel, gp.intervall_monate, gp.aktiv FROM inventar.gruppe_pruefart gp JOIN inventar.gruppe g ON g.id = gp.gruppe_id "
               "JOIN inventar.pruefart p ON p.id = gp.pruefart_id WHERE p.schluessel = 'dguv_v3_buero' ORDER BY 1") == [
        ("bueroausstattung", 6, True), ("it", None, True)]
    fehl = k.post("/inventar/verwaltung/pruefarten", data={**felder, "gi_bueroausstattung": "0"})
    assert fehl.status_code == 409
    seite = k.get(f"/inventar/stueck/{sid}").text
    assert 'id="pruefarten-stueck"' in seite and "6 Monate" in seite
    # eintragen: nächste Fälligkeit in 6 Monaten
    assert _eintragen(k, sid).status_code == 303
    erste = _db("SELECT naechste_am FROM inventar.pruefung ORDER BY id DESC LIMIT 1")[0][0]
    assert (erste.year - HEUTE.year) * 12 + erste.month - HEUTE.month == 6
    # je Stück: 3 Monate; danach gilt das für die nächste Prüfung
    assert k.post(f"/inventar/stueck/{sid}/pruefart", data={"pruefart": "dguv_v3_buero", "intervall_monate": "3", "aktiv": "1"},
                  follow_redirects=False).status_code == 303
    assert "3 Monate" in k.get(f"/inventar/stueck/{sid}").text
    assert _eintragen(k, sid).status_code == 303
    zweite = _db("SELECT naechste_am FROM inventar.pruefung ORDER BY id DESC LIMIT 1")[0][0]
    assert (zweite.year - HEUTE.year) * 12 + zweite.month - HEUTE.month == 3
    for ungueltig in ("0", "abc", "-4", "601"):
        assert k.post(f"/inventar/stueck/{sid}/pruefart", data={"pruefart": "dguv_v3_buero", "intervall_monate": ungueltig, "aktiv": "1"}).status_code == 409
    # abschalten: nichts mehr zu prüfen, Eintragen abgelehnt, die Zeile bleibt (nichts wird gelöscht)
    assert k.post(f"/inventar/stueck/{sid}/pruefart", data={"pruefart": "dguv_v3_buero"}, follow_redirects=False).status_code == 303
    assert _eintragen(k, sid).status_code == 409
    assert "Kopierer" not in k.get("/inventar/faellig").text.split('id="faellig-ueberfaellig"', 1)[1]
    assert _db("SELECT aktiv FROM inventar.stueck_pruefart")[0][0] is False
    # eigens hinzunehmen: Leitern gibt es in der Gruppe nicht — für dieses Stück schon
    assert "Leitern und Tritte" in k.get(f"/inventar/stueck/{sid}").text or "leitern_tritte" in k.get(f"/inventar/stueck/{sid}").text
    assert k.post(f"/inventar/stueck/{sid}/pruefart", data={"pruefart": "leitern_tritte", "intervall_monate": "", "aktiv": "1"},
                  follow_redirects=False).status_code == 303
    assert _eintragen(k, sid, pruefart="leitern_tritte").status_code == 303
    assert k.post(f"/inventar/stueck/{sid}/pruefart", data={"pruefart": "gibt_es_nicht", "aktiv": "1"}).status_code == 409
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.pruefart_stueck'")[0][0] == 3
    # Polier: keine Pflege der Prüfarten
    k.post("/abmelden")
    anmelden(k, POLIER)
    assert k.post(f"/inventar/stueck/{sid}/pruefart", data={"pruefart": "dguv_v3_buero", "aktiv": "1"}).status_code == 403


def _benutzer_id(name: str) -> int:
    with systemsitzung("pruefung.l13") as db:
        return int(db.execute(select(Benutzer.id).where(Benutzer.anmeldename == name)).scalar_one())


def test_erinnerung_pruefungen_an_werkstatt_nur_bei_neuem_und_montags(box) -> None:
    k = box.klient
    ks = _ks(k, "70101")
    with systemsitzung("pruefung.l13") as db:
        verwalter = db.execute(select(Benutzer).where(Benutzer.anmeldename == VERWALTER)).scalar_one()
        verwalter.email = "werkstatt@integration.invalid"
        kern_rechte.funktion_setzen(db, mandant_id=verwalter.mandant_id, art="werkstatt", benutzer_id=verwalter.id)
        mid = int(verwalter.mandant_id)
    _neu(k, "Altgerät")
    with benutzersitzung(_benutzer_id(VERWALTER), "pruefung.l13") as s:
        z = stueck.anlegen(s, bezeichnung="Frischgerät", gruppe="bueroausstattung", art="klein", kostenstelle_id=ks)
        pruefung.eintragen(s, "BA-00001", "dguv_v3_buero", dt.date(2023, 9, 1), "bestanden")  # 24 Monate: seit 2025-09-01 überfällig
        pruefung.eintragen(s, z.inventarnummer, "dguv_v3_buero", HEUTE, "bestanden")  # frisch: gar nichts
    dienstag, montag = dt.date(2026, 10, 13), dt.date(2026, 10, 19)
    mails = "SELECT count(*) FROM kern.mail_ausgang WHERE 'werkstatt@integration.invalid' = ANY(an)"
    with benutzersitzung(_benutzer_id(VERWALTER), "pruefung.l13") as s:
        assert erinnerungen.pruefungen_erinnern(s.db, mid, dienstag) == 1
        assert s.db.execute(text(mails)).scalar_one() == 1
        betreff, inhalt = s.db.execute(text("SELECT betreff, text FROM kern.mail_ausgang ORDER BY id DESC LIMIT 1")).one()
        assert "1 überfällig" in betreff and "Altgerät" in inhalt and "Frischgerät" not in inhalt
        assert erinnerungen.pruefungen_erinnern(s.db, mid, dienstag + dt.timedelta(days=1)) == 0, "nichts Neues, kein Montag: keine Mail"
        assert s.db.execute(text(mails)).scalar_one() == 1
        assert erinnerungen.pruefungen_erinnern(s.db, mid, montag) == 0
        assert s.db.execute(text(mails)).scalar_one() == 2, "montags kommt die Liste der Überfälligen noch einmal"
    # Tageslauf: idempotent je Tag; der Prozess prüft die Uhrzeit aus der Einstellung
    with benutzersitzung(_benutzer_id(VERWALTER), "pruefung.l13") as s:
        s.db.execute(text("UPDATE inventar.einstellung SET wert = '' WHERE schluessel = 'erinnern_letzter_lauf'"))
    tz = dt.timezone.utc
    assert erinnern.tick(dt.datetime(2026, 10, 14, 5, 59, tzinfo=tz)) == erinnern.Takt(None, False), "vor 06:00"
    takt = erinnern.tick(dt.datetime(2026, 10, 14, 6, 0, tzinfo=tz))
    assert takt.erledigt and takt.lauf is not None and takt.lauf.transfers == 0
    assert erinnern.tick(dt.datetime(2026, 10, 14, 6, 5, tzinfo=tz)) == erinnern.Takt(None, True), "heute schon gelaufen"
    assert _db("SELECT wert FROM inventar.einstellung WHERE schluessel = 'erinnern_letzter_lauf'")[0][0] == "2026-10-14"
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.erinnern_lauf'")[0][0] == 1
    # Uhrzeit ändern: 07:30 → um 06:30 nichts, um 07:30 der Lauf des nächsten Tages
    assert k.post("/inventar/verwaltung/einstellungen", data={"erinnern_um": "07:30"}, follow_redirects=False).status_code == 303
    assert k.post("/inventar/verwaltung/einstellungen", data={"erinnern_um": "halb acht"}).status_code == 409
    assert erinnern.tick(dt.datetime(2026, 10, 15, 6, 30, tzinfo=tz)) == erinnern.Takt(None, False)
    assert erinnern.tick(dt.datetime(2026, 10, 15, 7, 30, tzinfo=tz)).lauf is not None
    assert "werktage" in k.get("/inventar/verwaltung/einstellungen").text and "Kostenrechnung" in k.get("/inventar/verwaltung/einstellungen").text


def test_kaufdaten_aendern_nur_mit_kosten_pflegen_und_startwert_einkauf(box) -> None:
    k = box.klient
    ks = _ks(k, "70101")
    sid = _neu(k, "Messgerät", kaufpreis="100", kaufdatum="2026-01-15")
    with systemsitzung("pruefung.l13") as db:
        mid = int(db.execute(select(Mandant.id)).scalar_one())
        buero = _konto(db, mid, "buero@integration.invalid", "buero")
        einkauf = _konto(db, mid, "einkauf@integration.invalid", "einkauf")
        for b in (buero, einkauf):
            db.add(BenutzerKostenstelle(benutzer_id=b, kostenstelle_id=ks))
    # Verwalter hat alles: Preis steht und ist änderbar
    assert _db("SELECT kaufpreis FROM inventar.stueck WHERE id = :i", i=sid)[0][0] == Decimal("100.00")
    assert 'name="kaufpreis"' in k.get(f"/inventar/stueck/{sid}/aendern").text
    k.post("/abmelden")
    # Büro: pflegen und prüfen, aber kein kosten_sehen/kosten_pflegen — das Formular hat die Felder nicht, Änderung wirkt nicht
    anmelden(k, "buero@integration.invalid")
    form = k.get(f"/inventar/stueck/{sid}/aendern")
    assert form.status_code == 200 and 'name="kaufpreis"' not in form.text and 'name="kaufdatum"' not in form.text
    assert k.post(f"/inventar/stueck/{sid}/aendern", data={"bezeichnung": "Messgerät 2", "kaufpreis": "1"}, follow_redirects=False).status_code == 303
    assert _db("SELECT bezeichnung, kaufpreis FROM inventar.stueck WHERE id = :i", i=sid)[0] == ("Messgerät 2", Decimal("100.00"))
    with benutzersitzung(buero, "pruefung.l13") as s:
        with pytest.raises(gemeinsam.KeinRecht):
            pflege.aendern(s, "BA-00001", {"kaufpreis": Decimal("1")})
        with pytest.raises(gemeinsam.KeinRecht):
            stueck.anlegen(s, bezeichnung="X", gruppe="bueroausstattung", art="klein", kaufpreis=Decimal("5"))
        stueck.anlegen(s, bezeichnung="Ohne Preis", gruppe="bueroausstattung", art="klein")
    k.post("/abmelden")
    # Einkauf: sieht und ändert die Kaufdaten (Startwert der Vorlage seit Umlauf 01)
    anmelden(k, "einkauf@integration.invalid")
    form = k.get(f"/inventar/stueck/{sid}/aendern")
    assert 'name="kaufpreis"' in form.text and 'name="kaufdatum"' in form.text
    assert k.post(f"/inventar/stueck/{sid}/aendern", data={"bezeichnung": "Messgerät 2", "kaufpreis": "250,50", "kaufdatum": "2026-02-01"},
                  follow_redirects=False).status_code == 303
    assert _db("SELECT kaufpreis, kaufdatum FROM inventar.stueck WHERE id = :i", i=sid)[0] == (Decimal("250.50"), dt.date(2026, 2, 1))
    with systemsitzung("pruefung.l13") as db:
        assert {r[0] for r in db.execute(text(
            "SELECT r.aktion FROM kern.rolle_recht r JOIN kern.rolle o ON o.id = r.rolle_id WHERE o.schluessel = 'einkauf' AND r.modul = 'inventar'")).all()
            } >= {"sehen", "pflegen", "kosten_sehen", "kosten_pflegen"}


def test_startstandort_ist_pflicht_beim_anlegen(box) -> None:
    k = box.klient
    _ks(k, "70101")
    form = k.get("/inventar/stueck/neu").text
    assert 'id="wahl-start-ks"' in form and re.search(r'<select id="wahl-start-ks"[^>]*\brequired\b', form), "Pflichtwahl, nicht umgangen"
    leer = k.post("/inventar/stueck/neu", data={"bezeichnung": "Ohne Ort", "gruppe": "bueroausstattung", "art": "klein", "kostenstelle": ""})
    assert leer.status_code == 409 and "Startstandort" in leer.text
    assert _db("SELECT count(*) FROM inventar.stueck")[0][0] == 0
    fremd = k.post("/inventar/stueck/neu", data={"bezeichnung": "Fremd", "gruppe": "bueroausstattung", "art": "klein", "kostenstelle": "99999"})
    assert fremd.status_code == 409 and _db("SELECT count(*) FROM inventar.stueck")[0][0] == 0
    _neu(k, "Mit Ort")
    assert _db("SELECT count(*) FROM inventar.standort WHERE bis IS NULL")[0][0] == 1


def test_scan_quelle_handy_nur_aus_der_kamera(box) -> None:
    k = box.klient
    a, b = _ks(k, "70101"), _ks(k, "70102")
    with systemsitzung("pruefung.l13") as db:
        for name, ks in ((POLIER, a), (POLIER_ZWEI, b)):
            db.add(BenutzerKostenstelle(benutzer_id=int(db.execute(select(Benutzer.id).where(Benutzer.anmeldename == name)).scalar_one()), kostenstelle_id=ks))
    ids = [_neu(k, f"Gerät {n}", ks="70101") for n in ("eins", "zwei")]
    for sid in ids:
        assert k.post("/inventar/transfer/abgang", data={"stueck_id": str(sid), "von": str(a), "nach": "70102", "menge": "1",
                                                          "eintrag_schluessel": str(uuid.uuid4())}, follow_redirects=False).status_code == 303
    nummern = [r[0] for r in _db("SELECT inventarnummer FROM inventar.stueck ORDER BY id")]
    # der QR-Weg: ks und art werden zusammen weitergegeben, art nie ohne ks, getippt nie
    assert k.get(f"/inventar/s/{nummern[0]}?ks={b}&art=kamera", follow_redirects=False).headers["location"] == f"/inventar/stueck/{ids[0]}?ks={b}&art=kamera"
    assert k.get(f"/inventar/s/{nummern[0]}?art=kamera", follow_redirects=False).headers["location"] == f"/inventar/stueck/{ids[0]}"
    assert k.get(f"/inventar/s?nummer={nummern[0]}&ks={b}&art=kamera", follow_redirects=False).headers["location"] == f"/inventar/stueck/{ids[0]}?ks={b}"
    k.post("/abmelden")
    anmelden(k, POLIER_ZWEI)
    seite = k.get(f"/inventar/stueck/{ids[0]}", params={"ks": str(b), "art": "kamera"}).text
    assert 'name="art" value="kamera"' in seite
    assert 'name="art"' not in k.get(f"/inventar/stueck/{ids[1]}", params={"ks": str(b)}).text
    assert k.post("/inventar/transfer/scan", data={"stueck_id": str(ids[0]), "kostenstelle": str(b), "art": "kamera",
                                                   "eintrag_schluessel": str(uuid.uuid4())}, follow_redirects=False).status_code == 303
    assert k.post("/inventar/transfer/scan", data={"stueck_id": str(ids[1]), "kostenstelle": str(b),
                                                   "eintrag_schluessel": str(uuid.uuid4())}, follow_redirects=False).status_code == 303
    quellen = dict(_db("SELECT stueck_id, quelle FROM inventar.standort WHERE kostenstelle_id = :b AND bis IS NULL", b=b))
    assert quellen == {ids[0]: "handy", ids[1]: "web"}


def test_import_ohne_kosten_pflegen_nimmt_keine_kaufdaten(box) -> None:
    from openpyxl import Workbook

    from digiassistenz_inventar.rein.import_vorlage import BLATT, SPALTEN

    k = box.klient
    ks = _ks(k, "70101")
    with systemsitzung("pruefung.l13") as db:
        mid = int(db.execute(select(Mandant.id)).scalar_one())
        benutzer_id = _konto(db, mid, "pfleger@integration.invalid", "polier")  # buchen, aber nicht kosten_pflegen
        db.add(BenutzerKostenstelle(benutzer_id=benutzer_id, kostenstelle_id=ks))
        kern_rechte.setzen(db, benutzer=db.get(Benutzer, benutzer_id), schluessel="inventar.pflegen", gewaehrt=True, grund="Prüfung")
    wb = Workbook()
    ws = wb.active
    ws.title = BLATT
    ws.append(list(SPALTEN))
    ws.append(["BA-00777", "Plotter", "bueroausstattung", "klein", "HP", "", "SN-9", 2022, "2022-05-01", "1999,00", "", 70101, 1, ""])
    puffer = io.BytesIO()
    wb.save(puffer)
    k.post("/abmelden")
    anmelden(k, "pfleger@integration.invalid")
    bericht = k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"}, files={"datei": ("i.xlsx", io.BytesIO(puffer.getvalue()), "application/octet-stream")})
    assert bericht.status_code == 200 and 'value="einspielen"' in bericht.text
    kennung = re.search(r'name="datei" value="([0-9a-f]{32})"', bericht.text).group(1)
    assert k.post("/inventar/verwaltung/import", data={"aktion": "einspielen", "datei": kennung}).status_code == 200
    assert _db("SELECT bezeichnung, kaufpreis, kaufdatum FROM inventar.stueck") == [("Plotter", None, None)]
    nochmal = k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"}, files={"datei": ("i.xlsx", io.BytesIO(puffer.getvalue()), "application/octet-stream")})
    assert nochmal.status_code == 200 and "weicht vom Bestand ab" not in nochmal.text, "zweiter Lauf: Kaufdaten zählen ohne das Recht nicht als Abweichung"
    assert _db("SELECT count(*) FROM inventar.stueck")[0][0] == 1
