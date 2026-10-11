"""L16 Mengenabfrage bei laufender Inventur: der Scan eines Mengenartikels fragt die Menge vor Ort, bucht nichts, die Inventur rechnet die Fehlmenge."""

from __future__ import annotations

import datetime as dt
import re
import uuid

import pytest
from sqlalchemy import select, text

from conftest import anmelden, aufbau_pruefen
from digiassistenz_kern import Kostenstelle
from digiassistenz_kern.sitzung import systemsitzung

pytestmark = pytest.mark.usefixtures("_aufbau")

HEUTE = dt.date.today()


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _db(sql: str, **werte):
    with systemsitzung("pruefung.l16") as db:
        return db.execute(text(sql), werte).all()


def _ks(klient, nummer: str) -> int:
    anmelden(klient)
    antwort = klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                          data={"nummer": nummer, "bezeichnung": f"Baustelle {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"})
    assert antwort.status_code == 303
    with systemsitzung("pruefung.l16") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _stueck(k, bezeichnung: str, gruppe: str, art: str, menge: str = "1") -> int:
    antwort = k.post("/inventar/stueck/neu", follow_redirects=False, data={
        "bezeichnung": bezeichnung, "gruppe": gruppe, "art": art, "inventarnummer": "", "kostenstelle": "70101", "menge": menge})
    assert antwort.status_code == 303, antwort.text[:300]
    return int(re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"]).group(1))


def _scan(k, sid: int, ks: int, **mehr):
    return k.post("/inventar/transfer/scan", follow_redirects=False,
                  data={"stueck_id": str(sid), "kostenstelle": str(ks), "eintrag_schluessel": str(uuid.uuid4()), **mehr})


def _stichtag(k) -> None:
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "stichtag", "stichtag": HEUTE.isoformat()}, follow_redirects=False).status_code == 303


def _zeile(k, sid: int, ks: int) -> tuple[str, str, str]:
    html = k.get("/inventar/verwaltung/inventur").text
    block = html.split(f'id="inventur-{sid}-{ks}"', 1)[1].split("</tr>", 1)[0]
    zellen = re.findall(r'<td[^>]*>(.*?)</td>', block, flags=re.S)
    return zellen[2], zellen[3], re.sub(r"<[^>]+>", "", zellen[4]).strip()


def test_ohne_inventur_wie_bisher(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k, "Schalungsträger", "schalung_ruestung", "menge", "10")
    assert 'id="zaehl-abfrage"' not in k.get(f"/inventar/stueck/{sid}", params={"ks": str(a)}).text
    assert _scan(k, sid, a).status_code == 303
    assert _db("SELECT alt_wert FROM kern.protokoll WHERE aktion = 'inventar.inventur_gesehen'") == [(f"ks:{a}",)]
    # auch eine mitgeschickte Zahl zählt ohne Stichtag nicht
    assert _scan(k, sid, a, gesehen_menge="3").status_code == 303
    assert {r[0] for r in _db("SELECT alt_wert FROM kern.protokoll WHERE aktion = 'inventar.inventur_gesehen'")} == {f"ks:{a}"}


def test_mengenabfrage_merkt_die_menge_und_bucht_nichts(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    menge = _stueck(k, "Schalungsträger", "schalung_ruestung", "menge", "10")
    klein = _stueck(k, "Bohrmaschine", "bueroausstattung", "klein")
    _stichtag(k)
    seite = k.get(f"/inventar/stueck/{menge}", params={"ks": str(a)}).text
    assert 'id="zaehl-abfrage"' in seite and 'name="gesehen_menge"' in seite and 'value="10"' in seite, "vorbelegt mit der Buchmenge"
    assert 'id="zaehl-abfrage"' not in k.get(f"/inventar/stueck/{klein}", params={"ks": str(a)}).text, "nur Mengenartikel"
    assert _scan(k, menge, a, gesehen_menge="0").status_code == 409
    assert _scan(k, menge, a, gesehen_menge="7").status_code == 303
    assert _db("SELECT alt_wert FROM kern.protokoll WHERE aktion = 'inventar.inventur_gesehen'") == [(f"ks:{a};menge:7",)]
    assert _db("SELECT menge, bis FROM inventar.standort WHERE stueck_id = :i", i=menge) == [(10, None)], "nichts gebucht"
    assert _db("SELECT count(*) FROM inventar.transfer WHERE stueck_id = :i", i=menge) == [(0,)], "kein Transfer entstanden"
    assert _zeile(k, menge, a) == ("10", "7", "Teilweise gesehen")
    # L16a: die Zahl bleibt änderbar — das Feld wird wieder angeboten (vorbelegt mit der gezählten Menge);
    # ein gewöhnlicher Scan ohne Zahl macht sie nicht rückgängig, ein zweiter mit Zahl überschreibt die letzte Sichtung
    seite = k.get(f"/inventar/stueck/{menge}", params={"ks": str(a)}).text
    assert 'id="zaehl-abfrage"' in seite and 'value="7"' in seite
    assert _scan(k, menge, a).status_code == 303
    assert _zeile(k, menge, a) == ("10", "7", "Teilweise gesehen")
    assert _scan(k, menge, a, gesehen_menge="10").status_code == 303
    assert _zeile(k, menge, a) == ("10", "10", "Gesehen")
    assert _db("SELECT menge FROM inventar.standort WHERE stueck_id = :i AND bis IS NULL", i=menge) == [(10,)], "weiterhin nichts gebucht"


def test_volle_menge_gilt_als_gesehen_und_zu_viel_wird_nicht_gebucht(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    voll = _stueck(k, "Schalungsträger", "schalung_ruestung", "menge", "10")
    viel = _stueck(k, "Absperrgitter", "schalung_ruestung", "menge", "4")
    _stichtag(k)
    assert _scan(k, voll, a, gesehen_menge="10").status_code == 303
    assert _scan(k, viel, a, gesehen_menge="6").status_code == 303
    assert _zeile(k, voll, a) == ("10", "10", "Gesehen")
    assert _zeile(k, viel, a) == ("4", "6", "Gesehen")
    assert _db("SELECT menge FROM inventar.standort WHERE stueck_id = :i AND bis IS NULL", i=viel) == [(4,)]
    # L16a: der Überschuss wird nicht gebucht und mit Hinweis gemeldet
    antwort = _scan(k, viel, a, gesehen_menge="6")
    assert antwort.status_code == 303 and "mehr=6-4" in antwort.headers["location"]
    assert "6 vor Ort, 4 gebucht — Überschuss nicht gebucht; bitte im Büro klären" in k.get(antwort.headers["location"]).text
    assert "hinweis-mehrmenge" not in k.get(f"/inventar/stueck/{viel}", params={"ks": str(a)}).text


def test_inventur_abschliessen_schreibt_csv_merkt_sich_den_abschluss_und_loescht_den_stichtag(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k, "Schalungsträger", "schalung_ruestung", "menge", "10")
    _stichtag(k)
    assert _scan(k, sid, a, gesehen_menge="7").status_code == 303
    antwort = k.post("/inventar/verwaltung/inventur", data={"aktion": "abschliessen"}, follow_redirects=False)
    assert antwort.status_code == 303 and "fertig=abgeschlossen" in antwort.headers["location"]
    seite = k.get("/inventar/verwaltung/inventur").text
    assert 'id="inventur-letzte"' in seite and HEUTE.strftime("%d.%m.%Y") in seite, "letzte Inventur mit Stichtag"
    assert 'id="inventur-stichtag"' in seite and "inventur-ks-" not in seite, "Stichtag gelöscht: nichts mehr zu zeigen"
    letzte = _db("SELECT wert FROM inventar.einstellung WHERE schluessel = 'inventur_letzte'")[0][0]
    stichtag, _, pfad = letzte.partition("|")
    assert stichtag == HEUTE.isoformat() and re.search(rf"export/inventur_{stichtag}_\d{{8}}-\d{{6}}\.csv", pfad), pfad
    assert _db("SELECT wert FROM inventar.einstellung WHERE schluessel = 'inventur_stichtag'") in ([], [("",)])
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.inventur_abgeschlossen'") == [(1,)]
    datei = k.get(f"/inventar/kosten/auszug/{pfad.rsplit('/', 1)[-1]}")
    assert datei.status_code == 200 and "Schalungsträger" in datei.content.decode("utf-8-sig")
    assert _db("SELECT menge FROM inventar.standort WHERE stueck_id = :i AND bis IS NULL", i=sid) == [(10,)], "Abschließen bucht nichts"
    # ohne laufende Inventur gibt es nichts abzuschließen
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "abschliessen"}, follow_redirects=False).status_code == 409
