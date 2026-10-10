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
from digiassistenz_kern import Benutzer, BenutzerKostenstelle, Kostenstelle, Mandant
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
    assert _rep(k, erste, "abschliessen", datum=HEUTE.isoformat()).status_code == 409, "offen kann man nicht abschließen"
    assert _rep(k, erste, "beginnen", datum=HEUTE.isoformat(), kosten="250,50").headers["location"] == "/inventar/werkstatt?fertig=reparatur_begonnen"
    assert _status(sid) == "in_reparatur"
    assert _db("SELECT kosten, kosten_quelle FROM inventar.reparatur WHERE id = :i", i=erste)[0] == (Decimal("250.50"), "geschaetzt")
    seite = k.get(f"/inventar/stueck/{sid}").text
    assert 'id="hinweis-in-reparatur"' in seite and "weiter buchen" in seite
    # „Buchen bleibt möglich“: der Abgang eines Stücks in Reparatur geht
    abgang = k.post("/inventar/transfer/abgang", follow_redirects=False, data={
        "stueck_id": str(sid), "von": str(a), "nach": "70102", "menge": "1", "eintrag_schluessel": str(uuid.uuid4())})
    assert abgang.status_code == 303 and _status(sid) == "in_reparatur"
    assert _rep(k, zweite, "beginnen", datum=HEUTE.isoformat()).status_code == 303
    gestern = (HEUTE - dt.timedelta(days=1)).isoformat()
    assert _rep(k, erste, "abschliessen", datum=gestern).status_code == 409, "Ende vor Beginn"
    assert _rep(k, erste, "abschliessen", datum=HEUTE.isoformat(), kosten="300", kosten_quelle="rechnung").status_code == 303
    assert _status(sid) == "in_reparatur", "die zweite Reparatur läuft noch"
    assert _db("SELECT kosten, kosten_quelle, status FROM inventar.reparatur WHERE id = :i", i=erste)[0] == (Decimal("300.00"), "rechnung", "erledigt")
    assert _rep(k, zweite, "zurueckziehen").status_code == 409
    assert _rep(k, zweite, "zurueckziehen", grund="Auftrag storniert").status_code == 303
    assert _status(sid) == "aktiv", "nichts läuft mehr: wieder aktiv"
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
    assert _rep(k, rid, "abschliessen", datum=HEUTE.isoformat()).status_code == 303 and _status(sid) == "aktiv"
    assert _db("SELECT kosten, kosten_quelle FROM inventar.reparatur WHERE id = :i", i=rid)[0] == (None, None)
    assert _rep(k, rid, "rechnung", kosten="10").status_code == 403
    assert "Reparaturkosten" not in k.get(f"/inventar/stueck/{sid}").text.split("Meldungen und Reparaturen", 1)[1].split("</details>", 1)[0]
