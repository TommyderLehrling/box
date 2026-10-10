"""L16 Feiertage durch die echte Anwendung: Bundesland und eigene Tage in den Einstellungen, Wirkung auf Werktage, Vorhaltung und Fristen."""

from __future__ import annotations

import datetime as dt
import re
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from conftest import anmelden, aufbau_pruefen
from digiassistenz_inventar.dienstlogik import feiertage
from digiassistenz_kern import Kostenstelle, Mandant
from digiassistenz_kern.sitzung import systemsitzung

pytestmark = pytest.mark.usefixtures("_aufbau")

ZEILE = re.compile(r'<tr><td>([^<]+)</td><td class="zahl">(\d+)</td><td class="zahl">([\d.,]+)</td></tr>')


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _db(sql: str, **werte):
    with systemsitzung("pruefung.l16") as db:
        return db.execute(text(sql), werte).all()


def _tun(sql: str, **werte) -> None:
    with systemsitzung("pruefung.l16") as db:
        db.execute(text(sql), werte)


def _ks(klient, nummer: str) -> int:
    anmelden(klient)
    antwort = klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                          data={"nummer": nummer, "bezeichnung": f"Baustelle {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"})
    assert antwort.status_code == 303
    with systemsitzung("pruefung.l16") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _mandant() -> int:
    with systemsitzung("pruefung.l16") as db:
        return int(db.execute(select(Mandant.id)).scalar_one())


def _einstellen(k, **werte):
    return k.post("/inventar/verwaltung/einstellungen", data=werte, follow_redirects=False)


def _tage(html: str) -> dict[str, str]:
    block = html.split('id="kosten-summen"', 1)[1].split("</table>", 1)[0]
    return {n: (t, b) for n, t, b in ZEILE.findall(block)}


def test_bundesland_und_eigene_tage_in_den_einstellungen(box) -> None:
    k = box.klient
    _ks(k, "70101")
    seite = k.get("/inventar/verwaltung/einstellungen", params={"jahr": "2026"}).text
    assert 'id="e-bundesland"' in seite and "freie-tage-leer" in seite, "Standard: kein Bundesland, keine Feiertage"
    assert _einstellen(k, bundesland="XX").status_code == 409
    assert _einstellen(k, bundesland="sn").status_code == 303
    assert _db("SELECT wert FROM inventar.einstellung WHERE schluessel = 'bundesland'") == [("SN",)]
    seite = k.get("/inventar/verwaltung/einstellungen", params={"jahr": "2026"}).text
    assert "Buß- und Bettag" in seite and "18.11.2026" in seite and "Tag der Deutschen Einheit" in seite
    assert "Fronleichnam" not in seite, "Sachsen hat keinen landesweiten Fronleichnam"
    # eigener Tag: anlegen, ändern, abschalten, wieder einschalten — gelöscht wird nichts
    assert k.post("/inventar/verwaltung/einstellungen/tage", data={"datum": "2026-12-24", "bezeichnung": "Betriebsruhe", "aktiv": "1"},
                  follow_redirects=False).status_code == 303
    assert "Betriebsruhe" in k.get("/inventar/verwaltung/einstellungen", params={"jahr": "2026"}).text
    assert k.post("/inventar/verwaltung/einstellungen/tage", data={"datum": "2026-12-24", "bezeichnung": "Betriebsruhe", "aktiv": "0"},
                  follow_redirects=False).status_code == 303
    assert _db("SELECT aktiv FROM inventar.feiertag") == [(False,)]
    assert "24.12.2026" not in k.get("/inventar/verwaltung/einstellungen", params={"jahr": "2026"}).text.split('id="eigene-tage"')[0], \
        "abgeschaltet: nicht mehr unter den freien Tagen"
    assert k.post("/inventar/verwaltung/einstellungen/tage", data={"datum": "2026-12-24", "bezeichnung": "Betriebsruhe 2026", "aktiv": "1"},
                  follow_redirects=False).status_code == 303
    assert _db("SELECT bezeichnung, aktiv FROM inventar.feiertag") == [("Betriebsruhe 2026", True)], "ein Tag, eine Zeile"
    assert k.post("/inventar/verwaltung/einstellungen/tage", data={"datum": "kein Datum", "bezeichnung": "x", "aktiv": "1"}).status_code == 409
    assert k.post("/inventar/verwaltung/einstellungen/tage", data={"datum": "2026-12-27", "bezeichnung": " ", "aktiv": "1"}).status_code == 409
    aktionen = {z[0] for z in _db("SELECT aktion FROM kern.protokoll WHERE aktion LIKE 'inventar.feiertag%'")}
    assert aktionen == {"inventar.feiertag_angelegt", "inventar.feiertag_geaendert"}


def test_werktage_an_einer_stelle(box) -> None:
    k = box.klient
    _ks(k, "70101")
    mid = _mandant()
    # Mo 16.11. bis Fr 20.11.2026
    von, bis = dt.date(2026, 11, 16), dt.date(2026, 11, 20)
    with systemsitzung("pruefung.l16") as db:
        assert feiertage.werktage(db, von, bis, mid) == 5, "ohne Bundesland nur Montag bis Freitag"
        assert feiertage.werktage(db, bis, von, mid) == 0
    assert _einstellen(k, bundesland="SN").status_code == 303
    with systemsitzung("pruefung.l16") as db:
        assert feiertage.werktage(db, von, bis, mid) == 4, "Buß- und Bettag fällt aus"
    assert k.post("/inventar/verwaltung/einstellungen/tage", data={"datum": "2026-11-20", "bezeichnung": "Brückentag", "aktiv": "1"},
                  follow_redirects=False).status_code == 303
    with systemsitzung("pruefung.l16") as db:
        assert feiertage.werktage(db, von, bis, mid) == 3
        assert feiertage.werktage(db, dt.date(2026, 11, 18), dt.date(2026, 11, 18), mid) == 0, "ein Feiertag allein: null Werktage"
        assert feiertage.eigene_tage(db, mid) == {dt.date(2026, 11, 20)}
    # Frist: der Abgang liegt vor dem Feiertag, gezählt wird bis heute
    abgang = SimpleNamespace(status="angekuendigt", abgang_am=dt.datetime(2026, 11, 16, 9, 0))
    with systemsitzung("pruefung.l16") as db:
        frei = feiertage.frei_fuer_transfers(db, mid, [SimpleNamespace(transfers=[abgang])], dt.date(2026, 11, 20))
        assert frei == {dt.date(2026, 11, 18), dt.date(2026, 11, 20)}
        assert feiertage.frei_fuer_transfers(db, mid, [SimpleNamespace(transfers=[])], dt.date(2026, 11, 20)) == frozenset()


def test_vorhaltung_nach_werktagen_ohne_feiertage(box) -> None:
    k = box.klient
    _ks(k, "70101")
    antwort = k.post("/inventar/stueck/neu", follow_redirects=False, data={
        "bezeichnung": "Schalungsträger", "gruppe": "schalung_ruestung", "art": "menge", "inventarnummer": "", "kostenstelle": "70101", "menge": "1",
        "kaufpreis": "1000"})
    assert antwort.status_code == 303, antwort.text[:300]
    sid = int(re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"]).group(1))
    _tun("UPDATE inventar.standort SET von = '2026-11-01 08:00:00+01' WHERE stueck_id = :i", i=sid)
    assert _einstellen(k, werktage="21,67").status_code == 303
    zeitraum = {"von": "2026-11-16", "bis": "2026-11-20"}
    assert _tage(k.get("/inventar/kosten", params=zeitraum).text) == {"70101 Baustelle 70101": ("5", "3,30")}
    assert _einstellen(k, bundesland="SN").status_code == 303
    assert _tage(k.get("/inventar/kosten", params=zeitraum).text) == {"70101 Baustelle 70101": ("4", "2,64")}
    assert k.post("/inventar/verwaltung/einstellungen/tage", data={"datum": "2026-11-20", "bezeichnung": "Brückentag", "aktiv": "1"},
                  follow_redirects=False).status_code == 303
    assert _tage(k.get("/inventar/kosten", params=zeitraum).text) == {"70101 Baustelle 70101": ("3", "1,98")}
    # Kalendertage (Standard) sind von Feiertagen unberührt
    assert _einstellen(k, werktage="0").status_code == 303
    assert _tage(k.get("/inventar/kosten", params=zeitraum).text) == {"70101 Baustelle 70101": ("5", "2,40")}
