"""L15 Kosten (G5) durch die echte Anwendung: Vorhaltung über Transfer und Teil-Eingang, Miete gegen eigen, CSV-Auszug, Rechte, Kostensatz je Stück,
Stichtags-Inventur, Zählerstände.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from conftest import POLIER, _konto, anmelden, aufbau_pruefen
from digiassistenz_kern import Benutzer, BenutzerKostenstelle, Kostenstelle, Mandant
from digiassistenz_kern import rechte as kern_rechte
from digiassistenz_kern.sitzung import systemsitzung

pytestmark = pytest.mark.usefixtures("_aufbau")

HEUTE = dt.date.today()
ZEILE = re.compile(r'<tr><td>([^<]+)</td><td class="zahl">(\d+)</td><td class="zahl">([\d.,]+)</td></tr>')


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _ks(klient, nummer: str) -> int:
    anmelden(klient)
    antwort = klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                          data={"nummer": nummer, "bezeichnung": f"Baustelle {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"})
    assert antwort.status_code == 303
    with systemsitzung("pruefung.l15") as db:
        return int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == nummer)).scalar_one())


def _db(sql: str, **werte):
    with systemsitzung("pruefung.l15") as db:
        return db.execute(text(sql), werte).all()


def _tun(sql: str, **werte) -> None:
    with systemsitzung("pruefung.l15") as db:
        db.execute(text(sql), werte)


def _konto_mit(name: str, vorlage: str, *kostenstellen: int, rechte: tuple[str, ...] = ()) -> int:
    with systemsitzung("pruefung.l15") as db:
        mid = int(db.execute(select(Mandant.id)).scalar_one())
        benutzer = _konto(db, mid, name, vorlage)
        for k in kostenstellen:
            db.add(BenutzerKostenstelle(benutzer_id=benutzer, kostenstelle_id=k))
        konto = db.get(Benutzer, benutzer)
        for r in rechte:
            kern_rechte.setzen(db, benutzer=konto, schluessel=f"inventar.{r}", gewaehrt=True, grund="Prüffall")
        return benutzer


def _stueck(klient, bezeichnung="Radlader", gruppe="baumaschine", art="gross", ks="70101", menge="1", **mehr) -> int:
    antwort = klient.post("/inventar/stueck/neu", follow_redirects=False, data={
        "bezeichnung": bezeichnung, "gruppe": gruppe, "art": art, "inventarnummer": "", "kostenstelle": ks, "menge": menge, **mehr})
    assert antwort.status_code == 303, antwort.text[:300]
    return int(re.search(r"/inventar/stueck/(\d+)\?fertig=angelegt", antwort.headers["location"]).group(1))


def _nummer(sid: int) -> str:
    return _db("SELECT inventarnummer FROM inventar.stueck WHERE id = :i", i=sid)[0][0]


def _summen(html: str) -> dict[str, tuple[int, str]]:
    """Die Tabelle „je Kostenstelle“: Name → (Tage, Betrag als Text)."""
    block = html.split('id="kosten-summen"', 1)[1].split("</table>", 1)[0]
    return {n: (int(t), b) for n, t, b in ZEILE.findall(block)}


def _scan(k, sid: int, ks: int):
    return k.post("/inventar/transfer/scan", follow_redirects=False, data={"stueck_id": str(sid), "kostenstelle": str(ks), "eintrag_schluessel": str(uuid.uuid4())})


def _teil_eingang_aufbauen(k):
    """Zehn Schalungsträger (Kaufpreis 1.000 je Stück) von A nach B: Abgang, Teil-Eingang von sechs; die Zeiten stehen danach fest."""
    a = _ks(k, "70101")
    b = _ks(k, "70102")
    sid = _stueck(k, "Schalungsträger", "schalung_ruestung", "menge", "70101", "10", kaufpreis="1000")
    assert k.post("/inventar/transfer/abgang", follow_redirects=False, data={
        "stueck_id": str(sid), "von": str(a), "nach": "70102", "menge": "10", "eintrag_schluessel": str(uuid.uuid4())}).status_code == 303
    tid = _db("SELECT id FROM inventar.transfer WHERE stueck_id = :i ORDER BY id", i=sid)[0][0]
    assert k.post(f"/inventar/transfer/{tid}/eingang", follow_redirects=False, data={"stueck_id": str(sid), "menge": "6"}).status_code == 303
    zeilen = _db("SELECT id, kostenstelle_id, menge FROM inventar.standort WHERE stueck_id = :i ORDER BY id", i=sid)
    assert [(z[1], int(z[2])) for z in zeilen] == [(a, 10), (a, 4), (b, 6)], "die vier, die noch nicht da sind, stehen weiter bei A"
    r1, r2, r3 = (z[0] for z in zeilen)
    _tun("UPDATE inventar.standort SET von = '2026-10-01 08:00:00+02', bis = '2026-10-06 08:00:00+02' WHERE id = :i", i=r1)
    _tun("UPDATE inventar.standort SET von = '2026-10-10 08:00:00+02' WHERE id IN (:a, :b)", a=r2, b=r3)
    return a, b, sid


def test_vorhaltung_je_kostenstelle_ueber_transfer_und_teil_eingang(box) -> None:
    k = box.klient
    _a, b, sid = _teil_eingang_aufbauen(k)
    # Satz je Stück: 1.000 Kaufpreis, 96 Monate, 10 % Rest, 4 % Zins, 4 % Reparatur → 14,375 je Monat, 0,48 je Tag
    seite = k.get(f"/inventar/stueck/{sid}").text
    assert 'id="kosten-satz"' in seite and "0,48" in seite and "14,38" in seite
    html = k.get("/inventar/kosten", params={"von": "2026-10-01", "bis": "2026-10-12"}).text
    # A: 1.–5.10. zehn Stück (5 Tage) und 10.–12.10. vier Stück (3 Tage); B: 10.–12.10. sechs Stück; unterwegs (6.–9.10.) zählt nirgends
    assert _summen(html) == {"70101 Baustelle 70101": (8, "29,76"), "70102 Baustelle 70102": (3, "8,64")}
    assert "Kalendertagen" in html
    # nur der Zeitraum zählt
    html = k.get("/inventar/kosten", params={"von": "2026-10-06", "bis": "2026-10-09"}).text
    assert "kosten-summen" not in html, "unterwegs: nichts steht vor Ort, nichts wird gerechnet"
    # ungültiger Zeitraum: der laufende Monat gilt, und die Seite sagt es
    assert "ungültig" in k.get("/inventar/kosten", params={"von": "2026-10-12", "bis": "2026-10-01"}).text
    # Werktage statt Kalendertage (Einstellung 21,67): A 3 + 1 Tage, B 1 Tag; Tagessatz 14,375 / 21,67 = 0,66
    assert k.post("/inventar/verwaltung/einstellungen", data={"werktage": "21,67"}, follow_redirects=False).status_code == 303
    html = k.get("/inventar/kosten", params={"von": "2026-10-01", "bis": "2026-10-12"}).text
    assert _summen(html) == {"70101 Baustelle 70101": (4, "22,44"), "70102 Baustelle 70102": (1, "3,96")}
    assert "Werktagen" in html
    assert k.post("/inventar/verwaltung/einstellungen", data={"werktage": "viel"}).status_code == 409
    # wer Kosten nur auf B sehen darf, sieht nur B
    _konto_mit("leiter@l15.invalid", "polier", b, rechte=("kosten_sehen",))
    k.post("/abmelden")
    anmelden(k, "leiter@l15.invalid")
    teil = k.get("/inventar/kosten", params={"von": "2026-10-01", "bis": "2026-10-12"})
    assert teil.status_code == 200 and _summen(teil.text) == {"70102 Baustelle 70102": (1, "3,96")}
    assert "70101 Baustelle 70101" not in teil.text.split('id="kosten-summen"', 1)[1].split("</table>", 1)[0]


def test_miete_gegen_eigen_und_zaehlerverlauf(box) -> None:
    k = box.klient
    _ks(k, "70101")
    eigen = _stueck(k, "Eigener Bagger", kaufpreis="150000", kaufdatum="2024-01-15")
    miet = _stueck(k, "Mietbagger")
    assert k.post(f"/inventar/stueck/{miet}/miete", data={"miete": "1", "von": "2026-10-01", "bis": "2026-10-10"}).status_code == 409, "ohne Mietkosten geht es nicht"
    assert k.post(f"/inventar/stueck/{miet}/miete", data={"miete": "1", "von": "2026-10-10", "bis": "2026-10-01", "mietkosten": "1"}).status_code == 409
    assert k.post(f"/inventar/stueck/{miet}/miete", data={"miete": "1", "von": "2026-10-01", "bis": "2026-10-10", "mietkosten": "2500"},
                  follow_redirects=False).status_code == 303
    html = k.get("/inventar/kosten", params={"von": "2026-10-01", "bis": "2026-10-31"}).text
    block = html.split('id="kosten-miete"', 1)[1].split("</section>", 1)[0]
    # Eigener Bagger: 105,21 je Tag; zehn Miettage → 1.052,10 eigen; 2.500,00 Miete; Differenz 1.447,90
    for erwartet in (_nummer(miet), '<td class="zahl">10</td>', "2.500,00", "1.052,10", "1.447,90"):
        assert erwartet in block, erwartet
    # ein bestimmtes Vergleichsstück; ein unbekanntes wird abgelehnt und gesagt
    ok = k.get("/inventar/kosten", params={"von": "2026-10-01", "bis": "2026-10-31", "vergleich": _nummer(eigen)}).text
    assert "1.052,10" in ok.split('id="kosten-miete"', 1)[1]
    falsch = k.get("/inventar/kosten", params={"von": "2026-10-01", "bis": "2026-10-31", "vergleich": "XX-99999"}).text
    assert "eigenes Stück" in falsch.split('id="kosten-miete"', 1)[1].split("</section>", 1)[0]
    # je Stück: Kaufpreis, kalkulatorische Kosten (Monate seit Kaufdatum × Monatssatz), Gesamtkosten
    zeile = html.split('id="kosten-stueck"', 1)[1].split("</section>", 1)[0]
    assert "150.000,00" in zeile and "105,21" in zeile
    monate = (HEUTE.year - 2024) * 12 + HEUTE.month - 1 - (1 if HEUTE.day < 15 else 0)
    erwartet = (Decimal("3156.25") * monate).quantize(Decimal("0.01"))
    assert f"{erwartet:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") in zeile
    # Zählerstände mit Quelle im Verlauf des Stücks
    assert k.post(f"/inventar/stueck/{eigen}/zaehlerstand", data={"stand": "1000"}, follow_redirects=False).status_code == 303
    assert k.post(f"/inventar/stueck/{eigen}/zaehlerstand", data={"stand": "900"}).status_code == 409, "unter dem letzten Stand: abgelehnt, mit Hinweis"
    verlauf = k.get("/inventar/kosten", params={"stueck": str(eigen)}).text.split('id="zaehler"', 1)[1].split("</section>", 1)[0]
    assert "1.000 h" in verlauf and "Eingabe" in verlauf


def test_csv_auszug_liegt_im_exportordner_und_wird_nie_ueberschrieben(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _stueck(k, "Eigener Bagger", kaufpreis="150000", kaufdatum="2024-01-15", lieferant_id="")
    k.post(f"/inventar/stueck/{sid}/aendern", data={"bezeichnung": "Eigener Bagger", "kaufpreis": "150000", "kaufdatum": "2024-01-15"})
    ordner = box.arbeitsordner / "inventar" / "pruefbetrieb" / "export"
    antwort = k.post("/inventar/kosten/export", follow_redirects=False, data={"block": "stueck", "von": "2026-10-01", "bis": "2026-10-31"})
    assert antwort.status_code == 303 and "fertig=export" in antwort.headers["location"]
    erste = sorted(ordner.glob("kosten_stueck_*.csv"))
    assert len(erste) == 1
    inhalt = erste[0].read_bytes()
    assert inhalt.startswith(b"\xef\xbb\xbf"), "BOM, damit Excel die Umlaute liest"
    zeilen = inhalt.decode("utf-8-sig").split("\r\n")
    assert zeilen[0].startswith("inventarnummer;bezeichnung;gruppe;kaufdatum;kaufpreis;satz_tag;satz_monat")
    assert zeilen[1].startswith(f"{_nummer(sid)};Eigener Bagger;Baumaschinen;2024-01-15;150000,00;105,21;3156,25;")
    # noch einmal, im selben Augenblick: eine zweite Datei, die erste bleibt, wie sie war
    k.post("/inventar/kosten/export", follow_redirects=False, data={"block": "stueck", "von": "2026-10-01", "bis": "2026-10-31"})
    zweite = sorted(ordner.glob("kosten_stueck_*.csv"))
    assert len(zweite) == 2 and erste[0] in zweite and erste[0].read_bytes() == inhalt
    # alle Blöcke lassen sich schreiben, der Anlagenbuch-Auszug trägt die Kaufdaten
    for block in ("kostenstelle", "miete", "anlagenbuch"):
        assert k.post("/inventar/kosten/export", follow_redirects=False, data={"block": block, "von": "2026-10-01", "bis": "2026-10-31"}).status_code == 303
    buch = next(ordner.glob("kosten_anlagenbuch_*.csv")).read_bytes().decode("utf-8-sig").split("\r\n")
    assert buch[0] == "inventarnummer;bezeichnung;gruppe;kaufdatum;kaufpreis;lieferant;buchwert_extern;afa_hinweis"
    assert buch[1].startswith(f"{_nummer(sid)};Eigener Bagger;Baumaschinen;2024-01-15;150000,00;")
    assert k.post("/inventar/kosten/export", data={"block": "gibtsnicht"}).status_code == 409
    seite = k.get("/inventar/kosten").text.split('id="exporte"', 1)[1]
    assert "kosten_stueck_" in seite and "kosten_anlagenbuch_" in seite
    assert _db("SELECT count(*) FROM kern.protokoll WHERE aktion = 'inventar.kosten_export'")[0][0] == 5


def test_poliere_sehen_keine_preise_und_aendern_nichts(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    sid = _stueck(k, kaufpreis="150000", kaufdatum="2024-01-15")
    _konto_mit("buero@l15.invalid", "buero", a)
    _konto_mit("einkauf@l15.invalid", "einkauf", a)
    k.post("/abmelden")
    anmelden(k, POLIER)
    _tun("INSERT INTO kern.benutzer_kostenstelle (benutzer_id, kostenstelle_id) SELECT id, :a FROM kern.benutzer WHERE anmeldename = :n", a=a, n=POLIER)
    assert k.get("/inventar/kosten").status_code == 403
    assert k.post("/inventar/kosten/export", data={"block": "stueck"}).status_code == 403
    assert k.post(f"/inventar/stueck/{sid}/kostensatz", data={"nutzungsdauer": "60", "zins": "4", "reparatur": "1"}).status_code == 403
    assert k.post(f"/inventar/stueck/{sid}/miete", data={"miete": "1"}).status_code == 403
    seite = k.get(f"/inventar/stueck/{sid}")
    assert seite.status_code == 200 and 'id="abschnitt-kosten"' not in seite.text and "150.000" not in seite.text
    assert 'href="/inventar/kosten"' not in k.get("/inventar").text, "kein Menüpunkt „Kosten“"
    assert _db("SELECT count(*) FROM inventar.kostensatz WHERE stueck_id IS NOT NULL")[0][0] == 0
    # Büro: pflegen, aber keine Kosten
    k.post("/abmelden")
    anmelden(k, "buero@l15.invalid")
    assert k.get("/inventar/kosten").status_code == 403 and 'id="abschnitt-kosten"' not in k.get(f"/inventar/stueck/{sid}").text
    # Einkauf: sieht und ändert
    k.post("/abmelden")
    anmelden(k, "einkauf@l15.invalid")
    assert k.get("/inventar/kosten").status_code == 200 and 'href="/inventar/kosten"' in k.get("/inventar").text
    assert 'action="/inventar/stueck/' in k.get(f"/inventar/stueck/{sid}").text.split('id="abschnitt-kosten"', 1)[1]


def test_kostensatz_je_stueck_ueberschreibt_den_der_gruppe(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _stueck(k, kaufpreis="150000", kaufdatum="2024-01-15")
    satz = lambda **w: k.post(f"/inventar/stueck/{sid}/kostensatz", follow_redirects=False, data={  # noqa: E731
        "nutzungsdauer": "60", "zins": "3", "reparatur": "5", "restwert": "0", "ab": HEUTE.isoformat(), **w})
    assert "Satz der Gruppe" in k.get(f"/inventar/stueck/{sid}").text and "3.156,25" in k.get(f"/inventar/stueck/{sid}").text
    # Parameter: 150.000 / 60 = 2.500 + 150.000 / 2 * 3 % / 12 = 187,50 + 150.000 * 5 % / 12 = 625 → 3.312,50 je Monat
    assert satz().status_code == 303
    seite = k.get(f"/inventar/stueck/{sid}").text
    assert "3.312,50" in seite and "Satz dieses Stücks" in seite and "Gerechnet" in seite
    assert _db("SELECT quelle, satz_monat FROM inventar.kostensatz WHERE stueck_id = :i", i=sid) == [("gerechnet", None)]
    # am selben Tag ein zweiter Satz: abgelehnt; Restwert über dem Kaufpreis: abgelehnt, nichts gespeichert
    assert satz().status_code == 409
    vorher = _db("SELECT count(*) FROM inventar.kostensatz WHERE stueck_id = :i", i=sid)[0][0]
    assert satz(ab=(HEUTE - dt.timedelta(days=30)).isoformat(), restwert="200000").status_code == 409
    assert satz(ab=(HEUTE - dt.timedelta(days=30)).isoformat(), nutzungsdauer="0").status_code == 409
    assert satz(ab=(HEUTE - dt.timedelta(days=30)).isoformat(), satz_tag="5").status_code == 409, "Tagessatz von Hand braucht den Monatssatz"
    assert _db("SELECT count(*) FROM inventar.kostensatz WHERE stueck_id = :i", i=sid)[0][0] == vorher
    # ein Satz von Hand gilt statt der Rechnung; fehlende Tages- und Wochensätze leitet die Seite aus dem Monatssatz ab
    assert satz(ab=(HEUTE + dt.timedelta(days=0)).isoformat(), satz_monat="3000").status_code == 409
    assert satz(ab=(HEUTE - dt.timedelta(days=1)).isoformat(), satz_monat="3000").status_code == 303
    # der jüngste Beginn bis heute gilt: der von heute (gerechnet) vor dem von gestern (von Hand)
    assert "3.312,50" in k.get(f"/inventar/stueck/{sid}").text
    # Gruppenzeile ohne Monatssatz ist „gerechnet“, mit Monatssatz „manuell“
    k.post("/inventar/verwaltung/kostensaetze", data={"gruppe": "it", "nutzungsdauer": "36", "zins": "4", "reparatur": "2", "ab": "2026-01-01"})
    k.post("/inventar/verwaltung/kostensaetze", data={"gruppe": "elektro", "nutzungsdauer": "36", "zins": "4", "reparatur": "2", "satz_monat": "10", "ab": "2026-01-01"})
    quellen = dict(_db("SELECT g.schluessel, ks.quelle FROM inventar.kostensatz ks JOIN inventar.gruppe g ON g.id = ks.gruppe_id WHERE ks.gueltig_ab = '2026-01-01'"))
    assert quellen == {"it": "gerechnet", "elektro": "manuell"}
    assert "Gerechnet am" in k.get("/inventar/verwaltung/kostensaetze").text


def test_stichtags_inventur_schlaegt_nur_vor_und_setzt_nichts_von_selbst(box) -> None:
    k = box.klient
    a = _ks(k, "70101")
    b = _ks(k, "70102")
    eins, zwei, drei = (_stueck(k, f"Gerät {n}", "bueroausstattung", "klein") for n in ("eins", "zwei", "drei"))
    seite = lambda: k.get("/inventar/verwaltung/inventur")  # noqa: E731
    assert "kein Stichtag" in seite().text
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "stichtag", "stichtag": (HEUTE + dt.timedelta(days=2)).isoformat()}).status_code == 409
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "stichtag", "stichtag": HEUTE.isoformat()}, follow_redirects=False).status_code == 303
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "unbekannt"}).status_code == 409
    # gesehen: eins (Ist hier), drei (Abgang nach B und Eingang bestätigt); nicht gesehen: zwei
    assert _scan(k, eins, a).status_code == 303
    assert k.post("/inventar/transfer/abgang", follow_redirects=False, data={
        "stueck_id": str(drei), "von": str(a), "nach": "70102", "menge": "1", "eintrag_schluessel": str(uuid.uuid4())}).status_code == 303
    tid = _db("SELECT id FROM inventar.transfer WHERE stueck_id = :i", i=drei)[0][0]
    assert k.post(f"/inventar/transfer/{tid}/eingang", follow_redirects=False, data={"stueck_id": str(drei)}).status_code == 303
    html = seite().text
    assert "1 gesehen, 1 nicht gesehen" not in html and re.search(r"2 gesehen, 1 nicht gesehen", html), html[html.index("Stichtag"):][:200]
    assert f'id="vermisst-{zwei}"' in html and f'id="vermisst-{eins}"' not in html and f'id="vermisst-{drei}"' not in html
    assert f'id="inventur-ks-{a}"' in html and f'id="inventur-ks-{b}"' in html
    # die Seite und der Vorschlag ändern nichts von selbst
    assert {r[0] for r in _db("SELECT status FROM inventar.stueck")} == {"aktiv"}
    # eintragen: nur von Hand, nur mit Grund
    nein = k.post("/inventar/verwaltung/inventur", data={"aktion": "vermisst", "stueck_id": str(zwei), "grund": " "})
    assert nein.status_code == 409 and _db("SELECT status FROM inventar.stueck WHERE id = :i", i=zwei)[0][0] == "aktiv"
    ja = k.post("/inventar/verwaltung/inventur", data={"aktion": "vermisst", "stueck_id": str(zwei), "grund": "Nicht auffindbar"}, follow_redirects=False)
    assert ja.status_code == 303 and _db("SELECT status, status_grund FROM inventar.stueck WHERE id = :i", i=zwei)[0] == ("vermisst", "Nicht auffindbar")
    assert "Schon als vermisst eingetragen" in seite().text and "Nicht auffindbar" in k.get(f"/inventar/stueck/{zwei}").text
    # taucht es wieder auf, sagt die Inventur es
    assert _scan(k, zwei, a).status_code == 303
    assert "Wieder aufgetaucht" in seite().text
    # CSV
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "export"}, follow_redirects=False).status_code == 303
    datei = next((box.arbeitsordner / "inventar" / "pruefbetrieb" / "export").glob("inventur_*.csv"))
    kopf, *zeilen = datei.read_bytes().decode("utf-8-sig").strip().split("\r\n")
    assert kopf == "kostenstelle;inventarnummer;bezeichnung;erwartet;gesehen;ergebnis" and len(zeilen) == 3
    # Stichtag zurücknehmen
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "stichtag", "stichtag": ""}, follow_redirects=False).status_code == 303
    assert "kein Stichtag" in seite().text
    # Poliere und Büro: kein Zugang
    k.post("/abmelden")
    anmelden(k, POLIER)
    assert k.get("/inventar/verwaltung/inventur").status_code == 403
    assert k.post("/inventar/verwaltung/inventur", data={"aktion": "vermisst", "stueck_id": str(eins), "grund": "x"}).status_code == 403


def test_zaehlerstand_aus_der_werkstatt_hat_die_quelle_und_den_hinweis(box) -> None:
    k = box.klient
    _ks(k, "70101")
    sid = _stueck(k)
    assert k.post(f"/inventar/stueck/{sid}/zaehlerstand", data={"stand": "1000"}, follow_redirects=False).status_code == 303
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "intern"})
    rid = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    k.post(f"/inventar/werkstatt/reparatur/{rid}/weiter", data={"aktion": "beginnen", "datum": HEUTE.isoformat()})
    zu_niedrig = k.post(f"/inventar/werkstatt/reparatur/{rid}/weiter", follow_redirects=False, data={
        "aktion": "abschliessen", "datum": HEUTE.isoformat(), "arbeit": "Ölwechsel", "zaehlerstand": "900"})
    assert zu_niedrig.status_code == 303 and zu_niedrig.headers["location"].endswith("stand=900&letzter=1000")
    assert "liegt unter dem letzten Stand 1000" in k.get(zu_niedrig.headers["location"]).text
    assert _db("SELECT count(*) FROM inventar.zaehlerstand")[0][0] == 1, "kein neuer Stand"
    k.post("/inventar/werkstatt/reparatur", data={"stueck_id": str(sid), "durchfuehrung": "intern"})
    rid = int(_db("SELECT max(id) FROM inventar.reparatur")[0][0])
    k.post(f"/inventar/werkstatt/reparatur/{rid}/weiter", data={"aktion": "beginnen", "datum": HEUTE.isoformat()})
    ok = k.post(f"/inventar/werkstatt/reparatur/{rid}/weiter", follow_redirects=False, data={
        "aktion": "abschliessen", "datum": HEUTE.isoformat(), "arbeit": "Ölwechsel", "zaehlerstand": "1250,5"})
    assert ok.status_code == 303 and "stand=" not in ok.headers["location"]
    assert _db("SELECT stand, quelle FROM inventar.zaehlerstand ORDER BY id DESC LIMIT 1")[0] == (Decimal("1250.500"), "werkstatt")
    verlauf = k.get("/inventar/kosten", params={"stueck": str(sid)}).text.split('id="zaehler"', 1)[1].split("</section>", 1)[0]
    assert "Werkstatt" in verlauf and "Eingabe" in verlauf and "1.250,5 h" in verlauf
    assert "Werkstatt" in k.get(f"/inventar/stueck/{sid}").text.split("Zählerstände", 1)[1]
    assert k.post(f"/inventar/werkstatt/reparatur/{rid}/weiter", data={"aktion": "abschliessen", "datum": HEUTE.isoformat(), "arbeit": "x", "zaehlerstand": "abc"}).status_code == 409
