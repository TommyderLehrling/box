"""L14 Werkstatt (G4) durch die echte Anwendung: Posteingang, Rückmeldung an den Melder, Reparatur-Vorgang, Status `in_reparatur`."""

from __future__ import annotations

import datetime as dt
import io
import re
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from conftest import _konto, anmelden, aufbau_pruefen
from digiassistenz_kern import Benutzer, BenutzerKostenstelle, Kostenstelle, Lieferant, Mandant, mail
from digiassistenz_kern import rechte as kern_rechte
from digiassistenz_kern.sitzung import systemsitzung

pytestmark = pytest.mark.usefixtures("_aufbau")

HEUTE = dt.date.today()
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _ks(klient, nummer: str) -> int:
    anmelden(klient)
    antwort = klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                          data={"nummer": nummer, "bezeichnung": f"Baustelle {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"})
    assert antwort.status_code == 303
    with systemsitzung("pruefung.l14") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _db(sql: str, **werte):
    with systemsitzung("pruefung.l14") as db:
        return db.execute(text(sql), werte).all()


def _konto_mit(name: str, vorlage: str, *kostenstellen: int, werkstatt: bool = False, email: str = "") -> int:
    with systemsitzung("pruefung.l14") as db:
        mid = int(db.execute(select(Mandant.id)).scalar_one())
        benutzer = _konto(db, mid, name, vorlage)
        for k in kostenstellen:
            db.add(BenutzerKostenstelle(benutzer_id=benutzer, kostenstelle_id=k))
        konto = db.get(Benutzer, benutzer)
        if email:
            konto.email = email
        if werkstatt:
            kern_rechte.setzen(db, benutzer=konto, schluessel="inventar.werkstatt", gewaehrt=True, grund="Prüffall")
        return benutzer


def _stueck(klient, bezeichnung: str = "Radlader", gruppe: str = "baumaschine", art: str = "gross", ks: str = "70101") -> int:
    antwort = klient.post("/inventar/stueck/neu", follow_redirects=False, data={
        "bezeichnung": bezeichnung, "gruppe": gruppe, "art": art, "inventarnummer": "", "kostenstelle": ks, "menge": "1"})
    assert antwort.status_code == 303, antwort.text[:300]
    return int(re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"]).group(1))


def _melden(klient, sid: int, ks: int, beschreibung: str = "Hydraulikschlauch undicht", foto: bool = True) -> int:
    dateien = {"foto": ("s.png", io.BytesIO(PNG), "image/png")} if foto else None
    antwort = klient.post(f"/inventar/stueck/{sid}/meldung", follow_redirects=False,
                          data={"kostenstelle_id": str(ks), "beschreibung": beschreibung, "buchung": str(uuid.uuid4())}, files=dateien)
    assert antwort.status_code == 303, antwort.text[:300]
    return int(_db("SELECT max(id) FROM inventar.meldung")[0][0])


def _weiter(klient, mid: int, neu: str, **felder):
    return klient.post(f"/inventar/werkstatt/meldung/{mid}/weiter", data={"neu": neu, **felder}, follow_redirects=False)


def _rep(klient, rid: int, aktion: str, **felder):
    return klient.post(f"/inventar/werkstatt/reparatur/{rid}/weiter", data={"aktion": aktion, **felder}, follow_redirects=False)


def _status(sid: int) -> str:
    return _db("SELECT status FROM inventar.stueck WHERE id = :i", i=sid)[0][0]


def _grund(sid: int) -> str:
    return _db("SELECT status_grund FROM inventar.stueck WHERE id = :i", i=sid)[0][0]


def _ab(klient, rid: int, **felder):
    """Reparatur abschließen mit den Pflichtangaben (Datum, was gemacht wurde); einzelne lassen sich überschreiben."""
    return _rep(klient, rid, "abschliessen", **{"datum": HEUTE.isoformat(), "arbeit": "Schlauch getauscht", **felder})


def _firma(name: str = "Hydraulik Nord") -> int:
    with systemsitzung("pruefung.l14") as db:
        mid = int(db.execute(select(Mandant.id)).scalar_one())
        satz = Lieferant(mandant_id=mid, name_gedruckt=name, kurzname=name)
        db.add(satz)
        db.flush()
        return int(satz.id)


def _benutzer_id(name: str) -> int:
    with systemsitzung("pruefung.l14") as db:
        return int(db.execute(select(Benutzer.id).where(Benutzer.anmeldename == name)).scalar_one())


def _mails(adresse: str):
    return _db("SELECT betreff, text, status, mandant_id FROM kern.mail_ausgang WHERE :a = ANY(an) ORDER BY id", a=adresse)


def test_meldung_durch_den_posteingang_mit_rueckmeldung_an_den_melder(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k)
    nummer = _db("SELECT inventarnummer FROM inventar.stueck WHERE id = :i", i=sid)[0][0]
    _konto_mit("melder@l14.invalid", "polier", a, email="melder@werkstatt.invalid")
    _konto_mit("werkstatt@l14.invalid", "polier", a, werkstatt=True)
    k.post("/abmelden")
    anmelden(k, "melder@l14.invalid")
    meldung = _melden(k, sid, a)
    assert k.get("/inventar/werkstatt").status_code == 403, "der Melder ist nicht die Werkstatt"
    assert _weiter(k, meldung, "angenommen").status_code == 403
    foto = k.get(f"/inventar/meldung/{meldung}/foto")
    assert foto.status_code == 200 and foto.content == PNG and foto.headers["content-type"] == "image/png"
    assert foto.headers["content-disposition"].startswith("inline;") and foto.headers["x-content-type-options"] == "nosniff"
    k.post("/abmelden")

    anmelden(k, "werkstatt@l14.invalid")
    seite = k.get("/inventar/werkstatt")
    assert seite.status_code == 200 and nummer in seite.text.split('id="werkstatt-offen"', 1)[1].split("</section>", 1)[0]
    assert "Hydraulikschlauch undicht" in seite.text and f"/inventar/meldung/{meldung}/foto" in seite.text
    assert 'href="/inventar/werkstatt"' in k.get("/inventar").text, "die Kachel „Meldungen offen“ führt in die Werkstatt"
    assert '/inventar/werkstatt"' in k.get("/inventar").text and ">Werkstatt<" in k.get("/inventar").text, "Menüpunkt für `werkstatt`"

    assert _weiter(k, meldung, "angenommen").headers["location"] == "/inventar/werkstatt?fertig=angenommen"
    assert nummer in k.get("/inventar/werkstatt").text.split('id="werkstatt-angenommen"', 1)[1].split("</section>", 1)[0]
    assert _weiter(k, meldung, "angenommen").status_code == 409, "angenommen ist nicht erneut annehmbar"
    assert _weiter(k, meldung, "in_arbeit").status_code == 303
    assert nummer in k.get("/inventar/werkstatt").text.split('id="werkstatt-in-arbeit"', 1)[1].split("</section>", 1)[0]
    ohne = _weiter(k, meldung, "erledigt")
    assert ohne.status_code == 409 and "Rückmeldung" in ohne.text, "Erledigen braucht die Rückmeldung"
    assert _weiter(k, meldung, "gibtsnicht").status_code == 409
    assert _db("SELECT count(*) FROM kern.mail_ausgang WHERE 'melder@werkstatt.invalid' = ANY(an)")[0][0] == 0
    fertig = _weiter(k, meldung, "erledigt", rueckmeldung="Schlauch getauscht, Probelauf ohne Befund")
    assert fertig.status_code == 303
    zeile = _db("SELECT status, rueckmeldung, bearbeitet_von, erledigt_am IS NOT NULL FROM inventar.meldung WHERE id = :i", i=meldung)[0]
    assert zeile[0] == "erledigt" and zeile[1].startswith("Schlauch getauscht") and zeile[2] is not None and zeile[3] is True
    betreff, inhalt = _db("SELECT betreff, text FROM kern.mail_ausgang WHERE 'melder@werkstatt.invalid' = ANY(an)")[0]
    assert nummer in betreff and "Schlauch getauscht" in inhalt and "Hydraulikschlauch undicht" in inhalt
    assert _weiter(k, meldung, "in_arbeit").status_code == 409, "erledigt ist Endstand"
    erledigt = k.get("/inventar/werkstatt").text.split('id="werkstatt-erledigt"', 1)[1].split("</section>", 1)[0]
    assert nummer in erledigt and "Schlauch getauscht" in erledigt, "wer/wann/Rückmeldung stehen im Posteingang"
    stueck_seite = k.get(f"/inventar/stueck/{sid}").text
    assert "Schlauch getauscht, Probelauf ohne Befund" in stueck_seite, "Vermerk am Stück"
    assert "Meldung erledigt" in stueck_seite, "und im Verlauf"
    # zurückziehen braucht den Grund; danach ist nichts mehr zu tun
    zweite = _melden(k, sid, a, "Lack zerkratzt", foto=False)
    assert _weiter(k, zweite, "zurueckgezogen").status_code == 409
    assert _weiter(k, zweite, "zurueckgezogen", grund="doppelt gemeldet").status_code == 303
    assert _db("SELECT status, grund FROM inventar.meldung WHERE id = :i", i=zweite)[0] == ("zurueckgezogen", "doppelt gemeldet")
    assert _weiter(k, zweite, "angenommen").status_code == 409
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion LIKE 'inventar.meldung_%'")[0][0] == 6  # 2 angelegt, angenommen, in Arbeit, erledigt, zurückgezogen
    assert _weiter(k, 999999, "angenommen").status_code == 403, "fremde oder fehlende Meldung"


def test_reparatur_setzt_und_hebt_in_reparatur_auf_und_buchen_bleibt_moeglich(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    _ks(k, "70102")
    sid = _stueck(k)
    meldung = _melden(k, sid, a, foto=False)
    assert _weiter(k, meldung, "angenommen").status_code == 303
    dialog = k.get("/inventar/werkstatt", params={"neu_meldung": str(meldung)})
    assert 'id="reparatur-anlegen" open' in dialog.text and 'name="meldung_id"' in dialog.text
    assert 'id="reparatur-anlegen" open' in k.get("/inventar/werkstatt", params={"neu_stueck": str(sid)}).text
    anlegen = k.post("/inventar/werkstatt/reparatur", follow_redirects=False, data={"meldung_id": str(meldung), "durchfuehrung": "intern"})
    assert anlegen.headers["location"] == "/inventar/werkstatt?fertig=reparatur_angelegt"
    erste = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    assert _db("SELECT status, meldung_id, beschreibung FROM inventar.reparatur WHERE id = :i", i=erste)[0] == ("offen", meldung, "Hydraulikschlauch undicht")
    assert _status(sid) == "aktiv", "offen ist noch keine Reparatur"
    for schlecht, stichwort in (({"durchfuehrung": "daheim"}, "intern oder extern"), ({"durchfuehrung": "extern", "lieferant_id": "999999"}, "Lieferant"),
                                ({"durchfuehrung": "intern", "stueck_id": "", "meldung_id": ""}, "welcher Meldung")):
        antwort = k.post("/inventar/werkstatt/reparatur", data={"meldung_id": str(meldung), **schlecht})
        assert antwort.status_code == 409 and stichwort in antwort.text, (schlecht, antwort.text[:200])
    # zwei Reparaturen am Stück: es bleibt in Reparatur, bis die letzte endet
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "extern", "beschreibung": "Lackierung"})
    zweite = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    assert _rep(k, erste, "beginnen", datum="").status_code == 409
    assert _rep(k, erste, "beginnen", datum=HEUTE.isoformat(), kosten="abc").status_code == 409
    assert _ab(k, erste).status_code == 409, "offen kann man nicht abschließen"
    assert _rep(k, erste, "beginnen", datum=HEUTE.isoformat(), kosten="250,50").headers["location"] == "/inventar/werkstatt?fertig=reparatur_begonnen"
    assert _status(sid) == "in_reparatur" and _grund(sid) == f"reparatur:{erste}", "die Automatik schreibt ihren Grund"
    assert _db("SELECT kosten, kosten_quelle FROM inventar.reparatur WHERE id = :i", i=erste)[0] == (Decimal("250.50"), "geschaetzt")
    seite = k.get(f"/inventar/stueck/{sid}").text
    assert 'id="hinweis-in-reparatur"' in seite and "weiter buchen" in seite
    # „Buchen bleibt möglich“: der Abgang eines Stücks in Reparatur geht
    abgang = k.post("/inventar/transfer/abgang", follow_redirects=False, data={
        "stueck_id": str(sid), "von": str(a), "nach": "70102", "menge": "1", "eintrag_schluessel": str(uuid.uuid4())})
    assert abgang.status_code == 303 and _status(sid) == "in_reparatur"
    assert _rep(k, zweite, "beginnen", datum=HEUTE.isoformat()).status_code == 303
    gestern = (HEUTE - dt.timedelta(days=1)).isoformat()
    assert _ab(k, erste, datum=gestern).status_code == 409, "Ende vor Beginn"
    assert _ab(k, erste, kosten="300", kosten_quelle="rechnung").status_code == 303
    assert _status(sid) == "in_reparatur", "die zweite Reparatur läuft noch"
    assert _db("SELECT kosten, kosten_quelle, status FROM inventar.reparatur WHERE id = :i", i=erste)[0] == (Decimal("300.00"), "rechnung", "erledigt")
    assert _rep(k, zweite, "zurueckziehen").status_code == 409
    assert _rep(k, zweite, "zurueckziehen", grund="Auftrag storniert").status_code == 303
    assert _status(sid) == "aktiv" and _grund(sid) == "", "nichts läuft mehr: wieder aktiv"
    assert _db("SELECT status, grund FROM inventar.reparatur WHERE id = :i", i=zweite)[0] == ("zurueckgezogen", "Auftrag storniert")
    assert _rep(k, zweite, "beginnen", datum=HEUTE.isoformat()).status_code == 409
    assert _rep(k, erste, "rechnung", kosten="310,00").status_code == 303
    assert _rep(k, erste, "rechnung", kosten="").status_code == 409
    assert _db("SELECT kosten, kosten_quelle FROM inventar.reparatur WHERE id = :i", i=erste)[0] == (Decimal("310.00"), "rechnung")
    assert _rep(k, erste, "unbekannt").status_code == 409
    fertig = k.get("/inventar/werkstatt").text.split('id="werkstatt-reparaturen-fertig"', 1)[1]
    assert "310,00" in fertig and "Rechnung" in fertig
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion LIKE 'inventar.reparatur_%'")[0][0] == 7


def test_status_in_reparatur_von_hand_nur_zwischen_aktiv_und_in_reparatur(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _stueck(k)
    setzen = lambda wert: k.post(f"/inventar/werkstatt/stueck/{sid}/status", data={"setzen": wert}, follow_redirects=False)  # noqa: E731
    assert setzen("0").status_code == 409, "es ist gar nicht in Reparatur"
    assert setzen("1").headers["location"] == "/inventar/werkstatt?fertig=status_gesetzt" and _status(sid) == "in_reparatur"
    assert setzen("1").status_code == 409
    liste = k.get("/inventar/werkstatt").text.split('id="werkstatt-in-reparatur"', 1)[1].split("</section>", 1)[0]
    assert f"/inventar/stueck/{sid}" in liste and "Reparatur aufheben" in liste
    assert setzen("0").headers["location"] == "/inventar/werkstatt?fertig=status_aufgehoben" and _status(sid) == "aktiv"
    assert k.post("/inventar/werkstatt/stueck/999999/status", data={"setzen": "1"}).status_code == 403
    k.post(f"/inventar/stueck/{sid}/status", data={"status": "stillgelegt", "grund": "Totalschaden"})
    assert setzen("1").status_code == 409, "ein stillgelegtes Stück geht nicht in Reparatur"


def test_werkstatt_ohne_kostenrechte_arbeitet_ohne_betraege(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k)
    _konto_mit("nurwerkstatt@l14.invalid", "polier", a, werkstatt=True)
    k.post("/abmelden")
    anmelden(k, "nurwerkstatt@l14.invalid")
    assert k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "intern"}).status_code in (200, 303)
    rid = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    seite = k.get("/inventar/werkstatt")
    assert 'name="kosten"' not in seite.text and "<th>Reparaturkosten" not in seite.text
    assert _rep(k, rid, "beginnen", datum=HEUTE.isoformat(), kosten="50").status_code == 403, "Beträge trägt nur ein, wer Kosten pflegen darf"
    assert _status(sid) == "aktiv"
    assert _rep(k, rid, "beginnen", datum=HEUTE.isoformat()).status_code == 303 and _status(sid) == "in_reparatur"
    assert _ab(k, rid).status_code == 303 and _status(sid) == "aktiv"
    assert _db("SELECT kosten, kosten_quelle FROM inventar.reparatur WHERE id = :i", i=rid)[0] == (None, None)
    assert _rep(k, rid, "rechnung", kosten="10").status_code == 403
    assert "Reparaturkosten" not in k.get(f"/inventar/stueck/{sid}").text.split("Meldungen und Reparaturen", 1)[1].split("</details>", 1)[0]


def test_hand_bleibt_hand_ein_von_hand_gesperrtes_stueck_bleibt_gesperrt(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _stueck(k)
    # von Hand gesperrt, mit dem Grund der Werkstatt
    gesperrt = k.post(f"/inventar/werkstatt/stueck/{sid}/status", data={"setzen": "1", "grund": "Rahmen gerissen"}, follow_redirects=False)
    assert gesperrt.status_code == 303 and _status(sid) == "in_reparatur" and _grund(sid) == "Rahmen gerissen"
    # ein kleiner Vorgang beginnt und endet: der Status bleibt, der Grund auch
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "intern", "beschreibung": "Schraube nachziehen"})
    rid = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    assert _rep(k, rid, "beginnen", datum=HEUTE.isoformat()).status_code == 303
    assert _status(sid) == "in_reparatur" and _grund(sid) == "Rahmen gerissen", "Hand bleibt Hand: die Automatik schreibt nichts darüber"
    assert _ab(k, rid).status_code == 303
    assert _status(sid) == "in_reparatur" and _grund(sid) == "Rahmen gerissen", "bleibt gesperrt, bis die Werkstatt es von Hand aufhebt"
    assert k.post(f"/inventar/werkstatt/stueck/{sid}/status", data={"setzen": "0"}, follow_redirects=False).status_code == 303
    assert _status(sid) == "aktiv"
    # und umgekehrt: was die Automatik gesperrt hat, hebt die Automatik auf
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "intern"})
    neu = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    _rep(k, neu, "beginnen", datum=HEUTE.isoformat())
    assert _grund(sid) == f"reparatur:{neu}"
    _ab(k, neu)
    assert _status(sid) == "aktiv"


def test_abschluss_verlangt_wer_wo_was_wann(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k)
    firma = _firma()
    verwalter = _benutzer_id("verwalter@integration.invalid")
    # extern ohne Firma, ohne Arbeit, ohne Datum: nichts wird abgeschlossen
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "extern"})
    ext = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    assert _db("SELECT lieferant_id, arbeit FROM inventar.reparatur WHERE id = :i", i=ext)[0] == (None, ""), "beim Anlegen ist alles freiwillig"
    _rep(k, ext, "beginnen", datum=HEUTE.isoformat())
    for felder, stichwort in (({}, "Firma"), ({"lieferant_id": "999999"}, "Lieferant"), ({"lieferant_id": str(firma), "arbeit": " "}, "was gemacht"),
                              ({"lieferant_id": str(firma), "datum": ""}, "Datum")):
        antwort = _ab(k, ext, **felder)
        assert antwort.status_code == 409 and stichwort in antwort.text, (felder, antwort.text[:200])
    assert _db("SELECT status FROM inventar.reparatur WHERE id = :i", i=ext)[0][0] == "in_arbeit"
    assert _status(sid) == "in_reparatur"
    assert _ab(k, ext, lieferant_id=str(firma), arbeit="Hydraulikpumpe getauscht").status_code == 303
    assert _db("SELECT lieferant_id, arbeit, durchgefuehrt_von, status FROM inventar.reparatur WHERE id = :i", i=ext)[0] == (
        firma, "Hydraulikpumpe getauscht", None, "erledigt")
    # intern: die Person ist vorbelegt mit der Abschließenden; eine Fremde oder ein unbekanntes Konto geht nicht
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "intern"})
    intern = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    _rep(k, intern, "beginnen", datum=HEUTE.isoformat())
    assert _ab(k, intern, durchgefuehrt_von="999999").status_code == 409
    assert _ab(k, intern).status_code == 303
    assert _db("SELECT durchgefuehrt_von, arbeit, lieferant_id FROM inventar.reparatur WHERE id = :i", i=intern)[0] == (verwalter, "Schlauch getauscht", None)
    # eine andere Person ist wählbar
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "intern"})
    dritte = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    _rep(k, dritte, "beginnen", datum=HEUTE.isoformat())
    _konto_mit("schrauber@l14.invalid", "polier", a)
    schrauber = _benutzer_id("schrauber@l14.invalid")
    assert _ab(k, dritte, durchgefuehrt_von=str(schrauber)).status_code == 303
    assert _db("SELECT durchgefuehrt_von FROM inventar.reparatur WHERE id = :i", i=dritte)[0][0] == schrauber
    # Stück-Seite und Posteingang zeigen wer und was
    seite = k.get(f"/inventar/stueck/{sid}").text
    assert "Hydraulikpumpe getauscht" in seite and "Hydraulik Nord" in seite and "Schrauber" in seite
    fertig = k.get("/inventar/werkstatt").text.split('id="werkstatt-reparaturen-fertig"', 1)[1]
    assert "Hydraulikpumpe getauscht" in fertig and "Hydraulik Nord" in fertig and "Schrauber" in fertig
    # der Dialog öffnet sich zu genau einer laufenden Reparatur
    _rep(k, ext, "unbekannt")
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "extern"})
    laeuft = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    _rep(k, laeuft, "beginnen", datum=HEUTE.isoformat())
    dialog = k.get("/inventar/werkstatt", params={"abschluss": str(laeuft)}).text
    assert 'id="reparatur-abschliessen" open' in dialog and 'name="arbeit"' in dialog and 'name="lieferant_id"' in dialog
    assert 'id="reparatur-abschliessen"' not in k.get("/inventar/werkstatt", params={"abschluss": str(ext)}).text, "eine erledigte hat keinen Abschluss-Dialog"
    assert 'id="reparatur-abschliessen"' not in k.get("/inventar/werkstatt", params={"abschluss": "abc"}).text


def test_abschluss_mit_haken_erledigt_die_meldung_und_benachrichtigt_den_melder(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k)
    nummer = _db("SELECT inventarnummer FROM inventar.stueck WHERE id = :i", i=sid)[0][0]
    _konto_mit("melder@l14.invalid", "polier", a, email="melder@werkstatt.invalid")
    _konto_mit("werkstatt@l14.invalid", "polier", a, werkstatt=True)
    k.post("/abmelden")
    anmelden(k, "melder@l14.invalid")
    erste, zweite, dritte = (_melden(k, sid, a, text, foto=False) for text in ("Schlauch undicht", "Lack ab", "Licht defekt"))
    k.post("/abmelden")
    anmelden(k, "werkstatt@l14.invalid")

    def vorgang(meldung: int) -> int:
        k.post("/inventar/werkstatt/reparatur", data={"meldung_id": str(meldung), "durchfuehrung": "intern"})
        rid = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
        _rep(k, rid, "beginnen", datum=HEUTE.isoformat())
        return rid

    # mit Haken, Rückmeldung leer: die Arbeit wird zur Rückmeldung — die Meldung war noch nicht einmal angenommen
    rid = vorgang(erste)
    antwort = _ab(k, rid, meldung_erledigen="1", arbeit="Schlauch getauscht, Probelauf ohne Befund")
    assert antwort.status_code == 303 and antwort.headers["location"] == "/inventar/werkstatt?fertig=reparatur_abgeschlossen_meldung"
    zeile = _db("SELECT status, rueckmeldung, bearbeitet_von, erledigt_am IS NOT NULL FROM inventar.meldung WHERE id = :i", i=erste)[0]
    assert zeile[0] == "erledigt" and zeile[1] == "Schlauch getauscht, Probelauf ohne Befund" and zeile[2] is not None and zeile[3] is True
    betreff, text, status, mandant = _mails("melder@werkstatt.invalid")[0]
    assert nummer in betreff and "Probelauf ohne Befund" in text and "Schlauch undicht" in text
    assert status == "wartend" and mandant is not None, "eingereiht, nichts versendet, ein Vorgang der Firma"
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.meldung_angenommen'")[0][0] == 1, "offen → angenommen → erledigt im selben Zug"
    # mit Haken und eigener Rückmeldung
    rid = vorgang(zweite)
    _ab(k, rid, meldung_erledigen="1", arbeit="Lack ausgebessert", rueckmeldung="Lack ist wieder heil, bitte schonen")
    assert _db("SELECT status, rueckmeldung FROM inventar.meldung WHERE id = :i", i=zweite)[0] == ("erledigt", "Lack ist wieder heil, bitte schonen")
    assert "bitte schonen" in _mails("melder@werkstatt.invalid")[1][1]
    # ohne Haken: die Meldung bleibt, keine Mail
    vorher = len(_mails("melder@werkstatt.invalid"))
    rid = vorgang(dritte)
    assert _ab(k, rid, arbeit="Birne gewechselt").status_code == 303
    assert _db("SELECT status FROM inventar.meldung WHERE id = :i", i=dritte)[0][0] == "offen"
    assert len(_mails("melder@werkstatt.invalid")) == vorher
    # eine bereits erledigte Meldung wird auch mit Haken nicht noch einmal erledigt
    rid = vorgang(erste)
    assert _ab(k, rid, meldung_erledigen="1", arbeit="Nachkontrolle").headers["location"] == "/inventar/werkstatt?fertig=reparatur_abgeschlossen"
    assert len(_mails("melder@werkstatt.invalid")) == vorher


def test_scheitert_das_einreihen_bleiben_abschluss_und_erledigung_gueltig(box, monkeypatch) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k)
    _konto_mit("melder@l14.invalid", "polier", a, email="melder@werkstatt.invalid")
    _konto_mit("werkstatt@l14.invalid", "polier", a, werkstatt=True)
    k.post("/abmelden")
    anmelden(k, "melder@l14.invalid")
    meldung = _melden(k, sid, a, foto=False)
    k.post("/abmelden")
    anmelden(k, "werkstatt@l14.invalid")
    k.post("/inventar/werkstatt/reparatur", data={"meldung_id": str(meldung), "durchfuehrung": "intern"})
    rid = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    _rep(k, rid, "beginnen", datum=HEUTE.isoformat())

    def kaputt(*_a, **_k):
        raise RuntimeError("Warteschlange kaputt")

    monkeypatch.setattr(mail, "einreihen", kaputt)
    antwort = _ab(k, rid, meldung_erledigen="1", arbeit="Schlauch getauscht")
    assert antwort.status_code == 303, antwort.text[:200]
    assert _db("SELECT status FROM inventar.reparatur WHERE id = :i", i=rid)[0][0] == "erledigt"
    assert _db("SELECT status, rueckmeldung FROM inventar.meldung WHERE id = :i", i=meldung)[0] == ("erledigt", "Schlauch getauscht")
    assert _status(sid) == "aktiv"
    assert _mails("melder@werkstatt.invalid") == []
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.mail_nicht_eingereiht' AND objekt_id = :i", i=sid)[0][0] == 1
    assert "Mail nicht eingereiht" in k.get(f"/inventar/stueck/{sid}").text, "der Vermerk steht im Verlauf des Stücks"


def test_zurueckziehen_sagt_es_dem_melder_ohne_adresse_wird_vermerkt(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k)
    nummer = _db("SELECT inventarnummer FROM inventar.stueck WHERE id = :i", i=sid)[0][0]
    _konto_mit("melder@l14.invalid", "polier", a, email="melder@werkstatt.invalid")
    _konto_mit("stumm@l14.invalid", "polier", a)  # kein Konto mit Adresse
    _konto_mit("werkstatt@l14.invalid", "polier", a, werkstatt=True)
    k.post("/abmelden")
    anmelden(k, "melder@l14.invalid")
    laut = _melden(k, sid, a, "Doppelt gemeldet", foto=False)
    k.post("/abmelden")
    anmelden(k, "stumm@l14.invalid")
    still = _melden(k, sid, a, "Auch doppelt", foto=False)
    k.post("/abmelden")
    anmelden(k, "werkstatt@l14.invalid")
    assert _weiter(k, laut, "angenommen").status_code == 303 and _mails("melder@werkstatt.invalid") == [], "Annehmen: keine Mail"
    assert _weiter(k, laut, "in_arbeit").status_code == 303 and _mails("melder@werkstatt.invalid") == [], "Übernehmen: keine Mail"
    assert _weiter(k, laut, "zurueckgezogen", grund="Ist dieselbe wie die davor").status_code == 303
    betreff, text, status, mandant = _mails("melder@werkstatt.invalid")[0]
    assert nummer in betreff and "zurückgezogen" in betreff and "Ist dieselbe wie die davor" in text and status == "wartend" and mandant is not None
    # kein Konto-Adresse: nichts eingereiht, aber vermerkt
    assert _weiter(k, still, "zurueckgezogen", grund="Versehen").status_code == 303
    assert _db("SELECT count(*) FROM kern.mail_ausgang")[0][0] == 1
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.mail_ohne_adresse' AND objekt_id = :i", i=sid)[0][0] == 1
    assert "keine Adresse" in k.get(f"/inventar/stueck/{sid}").text


def test_foto_am_stueck_ist_abrufbar_mit_pruefsumme_und_recht(box) -> None:
    k = box.klient
    _ks(k, "70101")
    antwort = k.post("/inventar/stueck/neu", follow_redirects=False, data={
        "bezeichnung": "Rüttelplatte", "gruppe": "baumaschine", "art": "gross", "inventarnummer": "", "kostenstelle": "70101", "menge": "1"},
        files={"foto": ("platte.png", io.BytesIO(PNG), "image/png")})
    assert antwort.status_code == 303, antwort.text[:300]
    sid = int(re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"]).group(1))
    foto = k.get(f"/inventar/stueck/{sid}/foto")
    assert foto.status_code == 200 and foto.content == PNG and foto.headers["content-type"] == "image/png"
    assert foto.headers["content-disposition"].startswith("inline;") and foto.headers["x-content-type-options"] == "nosniff"
    assert f'src="/inventar/stueck/{sid}/foto"' in k.get(f"/inventar/stueck/{sid}").text, "die Stück-Seite zeigt es"
    # ein Stück ohne Foto und ein fremdes Stück gibt es hier nicht
    ohne = _stueck(k, "Handwagen", "baumaschine", "klein")
    assert k.get(f"/inventar/stueck/{ohne}/foto").status_code == 403
    assert f'src="/inventar/stueck/{ohne}/foto"' not in k.get(f"/inventar/stueck/{ohne}").text, "ohne Foto kein Bild"
    assert k.get("/inventar/stueck/999999/foto").status_code == 403
    # die Datei wurde verändert → die Prüfsumme sagt es
    pfad = _db("SELECT foto_pfad FROM inventar.stueck WHERE id = :i", i=sid)[0][0]
    datei = box.arbeitsordner / pfad
    datei.write_bytes(PNG + b"x")
    kaputt = k.get(f"/inventar/stueck/{sid}/foto")
    assert kaputt.status_code == 409 and "Prüfsumme" in kaputt.text
    datei.write_bytes(PNG)
    datei.unlink()
    assert "fehlt" in k.get(f"/inventar/stueck/{sid}/foto").text
    # wer das Stück nicht sehen darf, sieht auch sein Foto nicht (Polier ohne Kostenstelle)
    datei.write_bytes(PNG)
    k.post("/abmelden")
    anmelden(k, "polier@integration.invalid")
    assert k.get(f"/inventar/stueck/{sid}/foto").status_code == 403
