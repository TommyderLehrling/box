"""L13a (Auftrag 05) durch die echte Anwendung: Startstandort mit `pflegen`, Import nach Rechten, Kachel für `werkstatt`."""

from __future__ import annotations

import datetime as dt
import io
import re
import uuid

import pytest
from openpyxl import Workbook
from sqlalchemy import select, text

from conftest import _konto, anmelden, aufbau_pruefen
from digiassistenz_kern import Benutzer, BenutzerKostenstelle, Kostenstelle, Mandant
from digiassistenz_kern import rechte as kern_rechte
from digiassistenz_kern.sitzung import benutzersitzung, systemsitzung
from digiassistenz_kern.texte import t

from digiassistenz_inventar.dienstlogik import pruefung
from digiassistenz_inventar.rein.import_vorlage import BLATT, SPALTEN

pytestmark = pytest.mark.usefixtures("_aufbau")


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _ks(klient, nummer: str) -> int:
    anmelden(klient)
    antwort = klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                          data={"nummer": nummer, "bezeichnung": f"Baustelle {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"})
    assert antwort.status_code == 303
    with systemsitzung("pruefung.l13a") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _db(sql: str, **werte):
    with systemsitzung("pruefung.l13a") as db:
        return db.execute(text(sql), werte).all()


def _konto_mit(name: str, vorlage: str, *kostenstellen: int) -> int:
    with systemsitzung("pruefung.l13a") as db:
        mid = int(db.execute(select(Mandant.id)).scalar_one())
        benutzer = _konto(db, mid, name, vorlage)
        for k in kostenstellen:
            db.add(BenutzerKostenstelle(benutzer_id=benutzer, kostenstelle_id=k))
        return benutzer


def _datei(zeilen: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = BLATT
    ws.append(list(SPALTEN))
    for z in zeilen:
        ws.append(z)
    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


def _pruefen(k, inhalt: bytes):
    return k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"}, files={"datei": ("i.xlsx", io.BytesIO(inhalt), "application/octet-stream")})


def test_buero_legt_mit_startstandort_an_und_bucht_nicht_um(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    _ks(k, "70102")
    _konto_mit("buero@l13a.invalid", "buero")
    k.post("/abmelden")
    anmelden(k, "buero@l13a.invalid")
    form = k.get("/inventar/stueck/neu")
    assert form.status_code == 200 and 'value="70101"' in form.text and 'value="70102"' in form.text, "die Wahl kommt aus `pflegen`"
    antwort = k.post("/inventar/stueck/neu", follow_redirects=False, data={
        "bezeichnung": "Aktenschrank", "gruppe": "bueroausstattung", "art": "klein", "inventarnummer": "", "kostenstelle": "70101", "menge": "1"})
    assert antwort.status_code == 303, antwort.text[:300]
    sid = int(re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"]).group(1))
    assert _db("SELECT kostenstelle_id FROM inventar.standort WHERE stueck_id = :i AND bis IS NULL", i=sid) == [(a,)]
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.stueck_angelegt' AND objekt_id = :i", i=sid)[0][0] == 1
    # jede Bewegung danach braucht `buchen`: das Büro hat es nicht
    abgang = k.post("/inventar/transfer/abgang", data={"stueck_id": str(sid), "von": str(a), "nach": "70102", "menge": "1",
                                                        "eintrag_schluessel": str(uuid.uuid4())})
    assert abgang.status_code == 403
    assert _db("SELECT count(*) FROM inventar.transfer")[0][0] == 0
    scan = k.post("/inventar/transfer/scan", data={"stueck_id": str(sid), "kostenstelle": str(a), "eintrag_schluessel": str(uuid.uuid4())})
    assert scan.status_code == 403


def test_import_legt_nur_auf_kostenstellen_mit_pflegen_an_und_nennt_den_rest(box) -> None:
    k = box.klient
    a, b = _ks(k, "70101"), _ks(k, "70102")
    sachbearbeiter = _konto_mit("sachbearbeiter@l13a.invalid", "polier", a, b)
    with systemsitzung("pruefung.l13a") as db:
        konto = db.get(Benutzer, sachbearbeiter)
        kern_rechte.setzen(db, benutzer=konto, schluessel="inventar.pflegen", gewaehrt=True, kostenstellen=[a], grund="Prüffall")
    inhalt = _datei([
        ["BA-00801", "Schreibtisch", "bueroausstattung", "klein", "", "", "", "", "", "", "", 70101, 1, ""],
        ["BA-00802", "Rollcontainer", "bueroausstattung", "klein", "", "", "", "", "", "", "", 70102, 1, ""]])
    k.post("/abmelden")
    anmelden(k, "sachbearbeiter@l13a.invalid")
    bericht = _pruefen(k, inhalt)
    assert bericht.status_code == 200
    assert "BA-00802 (70102)" in bericht.text and t("inventar.import.hinweis.kostenstelle_ohne_recht", detail="BA-00802 (70102)") in bericht.text
    kennung = re.search(r'name="datei" value="([0-9a-f]{32})"', bericht.text).group(1)
    fertig = k.post("/inventar/verwaltung/import", data={"aktion": "einspielen", "datei": kennung})
    assert fertig.status_code == 200 and t("inventar.import.angelegt", anzahl=1) in fertig.text
    assert _db("SELECT inventarnummer FROM inventar.stueck ORDER BY id") == [("BA-00801",)], "die Zeile ohne Recht ist nicht angelegt"
    zweiter = _pruefen(k, inhalt)
    assert "BA-00802 (70102)" in zweiter.text, "auch der zweite Lauf sagt es"
    assert _db("SELECT count(*) FROM inventar.stueck")[0][0] == 1


def test_kachel_pruefungen_faellig_auch_fuer_werkstatt(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    with benutzersitzung(int(_db("SELECT id FROM kern.benutzer ORDER BY id LIMIT 1")[0][0]), "pruefung.l13a") as s:
        from digiassistenz_inventar.dienstlogik import stueck as fachstueck

        z = fachstueck.anlegen(s, bezeichnung="Altgerät", gruppe="bueroausstattung", art="klein", kostenstelle_id=a)
        pruefung.eintragen(s, z.inventarnummer, "dguv_v3_buero", dt.date(2023, 9, 1), "bestanden")  # seit 2025-09-01 überfällig
    _konto_mit("werkstatt@l13a.invalid", "polier", a)
    _konto_mit("nurpolier@l13a.invalid", "polier", a)
    with systemsitzung("pruefung.l13a") as db:
        konto = db.execute(select(Benutzer).where(Benutzer.anmeldename == "werkstatt@l13a.invalid")).scalar_one()
        kern_rechte.setzen(db, benutzer=konto, schluessel="inventar.werkstatt", gewaehrt=True, grund="Prüffall")
    kachel = t("inventar.kachel.pruefungen_faellig")
    k.post("/abmelden")
    anmelden(k, "werkstatt@l13a.invalid")
    assert kachel in k.get("/inventar").text, "`werkstatt` sieht die Kachel wie den Menüpunkt „Fällig“"
    k.post("/abmelden")
    anmelden(k, "nurpolier@l13a.invalid")
    assert kachel not in k.get("/inventar").text, "ohne `pruefen` und ohne `werkstatt` keine Kachel"
