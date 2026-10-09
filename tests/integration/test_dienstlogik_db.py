"""Die Anwendungsfälle gegen die echte Datenbank (Auftrag 03 Abschnitt 9, `test_dienstlogik` — mit dem echten Kern statt Fake).

Aufbau wie T-I-5: Kern + Inventar. Jeder Fall nutzt eine echte `Sitzung` des Kerns (`benutzersitzung`), also echte
Rechte, echten Mandanten- und Kostenstellenfilter und das echte Protokoll.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from conftest import POLIER, VERWALTER, anmelden, aufbau_pruefen
from digiassistenz_kern import Benutzer, BenutzerKostenstelle, Kostenstelle
from digiassistenz_kern.sitzung import benutzersitzung, systemsitzung
from digiassistenz_kern.web import gemeinsam

from digiassistenz_inventar import dienste, kacheln, modelle as m
from digiassistenz_inventar.dienstlogik import erinnerungen, etiketten, import_lauf, laden, nummer, pruefung, stueck, testdaten, transfer

pytestmark = pytest.mark.usefixtures("_aufbau")


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _konto(name: str) -> int:
    with systemsitzung("pruefung.dl") as db:
        return int(db.execute(select(Benutzer.id).where(Benutzer.anmeldename == name)).scalar_one())


def _ks(klient, *nummern: str) -> dict[str, int]:
    anmelden(klient)
    ergebnis = {}
    for n in nummern:
        r = klient.post("/verwaltung/kostenstelle/neu", data={"nummer": n, "bezeichnung": f"KS {n}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"},
                        follow_redirects=False)
        assert r.status_code == 303
        with systemsitzung("pruefung.dl") as db:
            ergebnis[n] = int(db.execute(select(Kostenstelle.id).where(Kostenstelle.nummer == n)).scalar_one())
    return ergebnis


def _sitzung(name: str = VERWALTER):
    return benutzersitzung(_konto(name), "pruefung.dl")


def _zeilen(tabelle: str) -> int:
    with systemsitzung("pruefung.dl") as db:
        return int(db.execute(text(f"SELECT count(*) FROM inventar.{tabelle}")).scalar_one())


def _protokoll(aktion: str) -> int:
    with systemsitzung("pruefung.dl") as db:
        return int(db.execute(text("SELECT count(*) FROM kern.protokoll WHERE aktion = :a"), {"a": aktion}).scalar_one())


def test_nummernvergabe_nutzt_den_zaehler_und_prueft_das_muster(box) -> None:
    ks = _ks(box.klient, "1000")
    with _sitzung() as s:
        a = stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"])
        b = stueck.anlegen(s, bezeichnung="Walze", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"])
        assert (a.inventarnummer, b.inventarnummer) == ("BM-00001", "BM-00002")
        with pytest.raises(ValueError, match="stueck.nummer_passt_nicht"):
            stueck.anlegen(s, bezeichnung="X", gruppe="baumaschine", art="gross", inventarnummer="ZZ-1")
        with pytest.raises(ValueError, match="stueck.nummer_vergeben"):
            stueck.anlegen(s, bezeichnung="X", gruppe="baumaschine", art="gross", inventarnummer="bm-00001")
        eigene = stueck.anlegen(s, bezeichnung="Y", gruppe="baumaschine", art="gross", inventarnummer="BM-00003")
        assert nummer.naechste_nummer(s.db, s.kontext.mandant_id, "BM", 2026) == "BM-00004", "belegte Nummer wird übersprungen"
        assert eigene.id
    assert _zeilen("zaehler") == 1 and _protokoll("inventar.stueck_angelegt") == 3


def test_anlegen_braucht_pflegen_und_gruppe_art_merkmale(box) -> None:
    ks = _ks(box.klient, "1000")
    with _sitzung(POLIER) as s:
        with pytest.raises(gemeinsam.KeinRecht):
            stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross")
    with _sitzung() as s:
        with pytest.raises(ValueError, match="stueck.gruppe_unbekannt"):
            stueck.anlegen(s, bezeichnung="X", gruppe="gibt_es_nicht", art="gross")
        with pytest.raises(ValueError, match="stueck.art_unbekannt"):
            stueck.anlegen(s, bezeichnung="X", gruppe="baumaschine", art="riesig")
        with pytest.raises(ValueError, match="stueck.menge_ungueltig"):
            stueck.anlegen(s, bezeichnung="X", gruppe="baumaschine", art="gross", menge=3)
        with pytest.raises(ValueError, match="stueck.merkmal_unbekannt"):
            stueck.anlegen(s, bezeichnung="X", gruppe="baumaschine", art="gross", merkmale={"nein": "1"})
        z = stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"],
                           merkmale={"betriebsgewicht": "21,5"})
        assert z.zaehler_einheit == "h"
        assert s.db.execute(select(m.StueckMerkmal.wert_zahl)).scalar_one() == Decimal("21.5")


def test_transfer_abgang_scan_idempotenz_und_zubehoer(box) -> None:
    ks = _ks(box.klient, "1000", "79795")
    with _sitzung() as s:
        bagger = stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"])
        loeffel = stueck.anlegen(s, bezeichnung="Löffel", gruppe="anbaugeraet", art="klein", kostenstelle_id=ks["1000"])
        s.db.add(m.Beziehung(mandant_id=s.kontext.mandant_id, art="gehoert_zu", von_stueck_id=loeffel.id, zu_stueck_id=bagger.id))
        schluessel = str(uuid.uuid4())
        erg = transfer.abgang_buchen(s, bagger.inventarnummer, ks["1000"], ks["79795"], 1, schluessel, "Einsatz")
        assert erg.protokoll == ("transfer.abgang",)
        doppelt = transfer.abgang_buchen(s, bagger.inventarnummer, ks["1000"], ks["79795"], 1, schluessel)
        assert doppelt.aenderungen == () and doppelt.protokoll == ("transfer.doppelt",)
        vor_ort = {z["inventarnummer"]: z["status"] for z in dienste.bestand(s.db, s, ks["1000"])}
        kommt = {z["inventarnummer"]: z["status"] for z in dienste.bestand(s.db, s, ks["79795"])}
        assert vor_ort == {"BM-00001": "vor_ort", "AG-00001": "vor_ort"} or vor_ort[bagger.inventarnummer] == "vor_ort"
        assert kommt == {bagger.inventarnummer: "angekuendigt", loeffel.inventarnummer: "angekuendigt"}, "Zubehör folgt"
    with systemsitzung("pruefung.dl") as db:
        polier = _konto(POLIER)
        db.add(BenutzerKostenstelle(benutzer_id=polier, kostenstelle_id=ks["79795"]))
    with _sitzung(POLIER) as p:
        assert dienste.bestand(p.db, p, ks["1000"]) == [], "fremde Kostenstelle: leer, kein Fehler"
        scan = str(uuid.uuid4())
        erg = transfer.scan_ist_hier(p, bagger.inventarnummer, ks["79795"], scan, quelle="handy")
        assert erg.protokoll == ("transfer.eingang",)
        assert transfer.scan_ist_hier(p, bagger.inventarnummer, ks["79795"], scan).protokoll == ("transfer.doppelt",)
        jetzt = {z["inventarnummer"]: z["status"] for z in dienste.bestand(p.db, p, ks["79795"])}
        assert jetzt[bagger.inventarnummer] == "vor_ort" and jetzt[loeffel.inventarnummer] == "vor_ort"
        auskunft = dienste.stueck(p.db, p, inventarnummer="bm-00001")
        assert auskunft["standort_kostenstelle_id"] == ks["79795"] and set(auskunft) >= {"inventarnummer", "gruppe_text", "standort_seit"}
        assert dienste.stueck(p.db, p, inventarnummer="gibt es nicht") is None
        with pytest.raises(gemeinsam.KeinRecht):
            transfer.abgang_buchen(p, bagger.inventarnummer, ks["1000"], ks["79795"], 1, str(uuid.uuid4()))  # ab 1000 darf er nicht buchen
    with systemsitzung("pruefung.dl") as db:
        offen = db.execute(text("SELECT count(*) FROM inventar.standort WHERE bis IS NULL")).scalar_one()
        assert offen == 2 and db.execute(text("SELECT count(*) FROM inventar.standort")).scalar_one() == 4


def test_teil_eingang_zieht_die_fehlmenge_nach(box) -> None:
    ks = _ks(box.klient, "1000", "79795")
    with _sitzung() as s:
        z = stueck.anlegen(s, bezeichnung="Schaufel", gruppe="werkzeug", art="menge", menge=10, kostenstelle_id=ks["1000"])
        schluessel = str(uuid.uuid4())
        transfer.abgang_buchen(s, z.inventarnummer, ks["1000"], ks["79795"], 10, schluessel)
        erg = transfer.eingang_bestaetigen(s, z.inventarnummer, schluessel, menge=8, eingang_schluessel=str(uuid.uuid4()))
        assert "transfer.fehlmenge" in erg.protokoll
        orte = {(o.kostenstelle_id, int(o.menge)) for o in s.db.execute(select(m.Standort).where(m.Standort.bis.is_(None))).scalars()}
        assert orte == {(ks["1000"], 2), (ks["79795"], 8)} or (ks["79795"], 8) in orte
        offen = s.db.execute(select(m.Transfer).where(m.Transfer.status == "angekuendigt")).scalars().all()
        assert [(int(t.menge), t.eintrag_schluessel.endswith("|fehlmenge")) for t in offen] == [(2, True)]
        transfer.zurueckziehen(s, z.inventarnummer, offen[0].eintrag_schluessel, "Rest bleibt")
    assert _protokoll("inventar.transfer_zurueckgezogen") == 1


def test_status_nur_mit_grund_und_recht(box) -> None:
    ks = _ks(box.klient, "1000")
    with _sitzung() as s:
        z = stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"])
        with pytest.raises(ValueError, match="stueck_status.grund_fehlt"):
            stueck.status_wechseln(s, z.inventarnummer, "stillgelegt")
        assert stueck.status_wechseln(s, z.inventarnummer, "vermisst", "Inventur").status == "vermisst"
        assert stueck.status_wechseln(s, z.inventarnummer, "aktiv").status == "aktiv", "Rückkehr aus vermisst ohne Grund"
        assert dienste.bestand(s.db, s, ks["1000"])
        stueck.status_wechseln(s, z.inventarnummer, "verschrottet", "Totalschaden")
        assert dienste.bestand(s.db, s, ks["1000"]) == [] and dienste.stueck(s.db, s, inventarnummer=z.inventarnummer) is None
    with _sitzung(POLIER) as p, pytest.raises(gemeinsam.KeinRecht):
        stueck.status_wechseln(p, "BM-00001", "stillgelegt", "x")


def test_testdaten_zweimal_aendert_nichts_und_nach_auslieferung_gesperrt(box) -> None:
    ks = _ks(box.klient, "1000", "79795", "80010")
    with _sitzung() as s:
        n = testdaten.einspielen(s, seed=3, anzahl=60)
        assert n == 60
    zahlen = {t: _zeilen(t) for t in ("stueck", "standort", "transfer", "pruefung", "zaehlerstand")}
    assert zahlen["stueck"] == 60 and zahlen["standort"] == 60 and zahlen["transfer"] >= 1 and zahlen["pruefung"] > 60
    with _sitzung() as s:
        assert testdaten.einspielen(s, seed=3, anzahl=60) == 0
    assert {t: _zeilen(t) for t in zahlen} == zahlen
    with systemsitzung("pruefung.dl") as db:
        mid = int(db.execute(select(Kostenstelle.mandant_id).limit(1)).scalar_one())
        from digiassistenz_inventar.dienstlogik import katalog
        katalog.setze_einstellung(db, mid, "auslieferung_am", "2026-10-09", None)
    with _sitzung() as s, pytest.raises(ValueError, match="testdaten.nach_auslieferung"):
        testdaten.einspielen(s, seed=4, anzahl=5)


def test_import_idempotent_ueber_excel(box, tmp_path) -> None:
    from digiassistenz_inventar.rein.beispielbetrieb import lade_beispielbetrieb, schreibe_importdatei
    from digiassistenz_inventar.rein.kataloge import lade_merkmale

    b = lade_beispielbetrieb()
    ks = _ks(box.klient, *[str(k.nummer) for k in b.kostenstellen])
    datei = tmp_path / "import.xlsx"
    schreibe_importdatei(b, datei, lade_merkmale())
    with _sitzung() as s:
        erg = import_lauf.einspielen(s, datei)
        assert erg.angelegt == 50 and erg.lesen.fehler == () and sum(z.neu for z in erg.plan.bericht) == 50
        assert "Maschinenhandel Weber" in erg.lieferanten_unbekannt, "kein Lieferant wird angelegt, der Name wird gemeldet"
    assert _zeilen("stueck") == 50
    with _sitzung() as s:
        zweit = import_lauf.einspielen(s, datei)
        assert zweit.angelegt == 0 and len(zweit.plan.unveraendert) == 50 and zweit.plan.abweichend == ()
    assert _zeilen("stueck") == 50 and _protokoll("inventar.import") == 1
    with _sitzung(POLIER) as p, pytest.raises(gemeinsam.KeinRecht):
        import_lauf.pruefen(p, datei)


def test_import_mit_fehlerhafter_datei_schreibt_nichts(box, tmp_path) -> None:
    from openpyxl import Workbook

    from digiassistenz_inventar.rein.import_vorlage import BLATT, SPALTEN

    _ks(box.klient, "1000")
    wb = Workbook()
    ws = wb.active
    ws.title = BLATT
    ws.append(list(SPALTEN))
    ws.append(["BM-00001", "Bagger", "gibt_es_nicht", "gross", "", "", "", None, None, None, "", 1000, 1, ""])
    datei = tmp_path / "kaputt.xlsx"
    wb.save(datei)
    with _sitzung() as s:
        assert import_lauf.bericht(s, datei).plan is None
        with pytest.raises(ValueError, match="import.fehler_in_datei"):
            import_lauf.einspielen(s, datei)
    assert _zeilen("stueck") == 0


def test_etiketten_bogen_und_pdf(box) -> None:
    ks = _ks(box.klient, "1000")
    with _sitzung() as s:
        for _ in range(3):
            stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"])
        html = etiketten.bogen(s, None, "https://box.example")
        assert html.count("https://box.example/inventar/s/BM-0000") == 3
        inhalt, pfad = etiketten.pdf_ablegen(s, html, box.arbeitsordner)
        assert inhalt.startswith(b"%PDF") and pfad.parent.name == "export" and pfad.exists()
        assert etiketten.pdf_ablegen(s, html, box.arbeitsordner)[1] != pfad, "nie eine vorhandene Datei ersetzen"
    with _sitzung(POLIER) as p, pytest.raises(gemeinsam.KeinRecht):
        etiketten.bogen(p, None, "https://box.example")


def test_pruefung_eintragen_mit_nachweis_und_ampel(box) -> None:
    ks = _ks(box.klient, "1000")
    with _sitzung() as s:
        z = stueck.anlegen(s, bezeichnung="Rüttelplatte", gruppe="kleingeraet", art="klein", kostenstelle_id=ks["1000"])
        heute = dt.date.today()
        staende = dienste.stueck_infos(s.db, s, [z], heute)
        assert staende[z.inventarnummer].pruefung_ueberfaellig is False
        with pytest.raises(ValueError, match="pruefung.nicht_zugeordnet"):
            pruefung.eintragen(s, z.inventarnummer, "uvv_erdbau", heute, "bestanden")
        satz = pruefung.eintragen(s, z.inventarnummer, "dguv_v3_baustelle", heute, "bestanden", pruefer_text="Elektro Weber",
                                  nachweis=("nachweis.pdf", b"%PDF-1.4 test"), arbeitsordner=box.arbeitsordner)
        assert satz.nachweis_sha256 and (box.arbeitsordner / satz.nachweis_pfad).read_bytes() == b"%PDF-1.4 test"
        assert satz.naechste_am > heute
        from digiassistenz_inventar.dienstlogik import pruefstand
        stand = pruefstand.staende(s.db, s.kontext.mandant_id, [z], heute)[z.inventarnummer]
        assert {x.pruefart: x.ampel for x in stand}["dguv_v3_baustelle"] == "gruen"
    with _sitzung(POLIER) as p, pytest.raises(gemeinsam.KeinRecht):
        pruefung.eintragen(p, "BM-00001", "dguv_v3_baustelle", dt.date.today(), "bestanden")


def test_erinnerung_einmal_je_transfer_an_disposition_und_melder(box) -> None:
    ks = _ks(box.klient, "1000", "79795")
    with systemsitzung("pruefung.dl") as db:
        verwalter = db.execute(select(Benutzer).where(Benutzer.anmeldename == VERWALTER)).scalar_one()
        verwalter.email = "dispo@integration.invalid"
        from digiassistenz_kern import rechte as kern_rechte
        kern_rechte.funktion_setzen(db, mandant_id=verwalter.mandant_id, art="disposition", benutzer_id=verwalter.id)
    with _sitzung() as s:
        z = stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"])
        transfer.abgang_buchen(s, z.inventarnummer, ks["1000"], ks["79795"], 1, str(uuid.uuid4()))
        s.db.execute(text("UPDATE inventar.transfer SET abgang_am = now() - interval '14 days'"))
        mid = s.kontext.mandant_id
        assert erinnerungen.transfers_erinnern(s.db, mid) == 1
        assert erinnerungen.transfers_erinnern(s.db, mid) == 0, "idempotent"
        assert s.db.execute(text("SELECT count(*) FROM kern.mail_ausgang WHERE 'dispo@integration.invalid' = ANY(an)")).scalar_one() == 1
    assert _protokoll("inventar.transfer_erinnert") == 1


def test_kacheln_zaehlen_nach_den_rechten(box) -> None:
    ks = _ks(box.klient, "1000", "79795")
    with _sitzung() as s:
        z = stueck.anlegen(s, bezeichnung="Rüttelplatte", gruppe="kleingeraet", art="klein", kostenstelle_id=ks["1000"])
        transfer.abgang_buchen(s, z.inventarnummer, ks["1000"], ks["79795"], 1, str(uuid.uuid4()))
        s.db.add(m.Meldung(mandant_id=s.kontext.mandant_id, stueck_id=z.id, kostenstelle_id=ks["1000"], art="schaden", beschreibung="Kabel",
                           eintrag_schluessel=str(uuid.uuid4())))
        s.db.flush()
        namen = {k.text_schluessel.rsplit(".", 1)[-1]: k.zahl for k in kacheln.kacheln(s.db, s)}
        assert namen["ohne_nachweis"] == 5 and namen["transfers_an_mich"] == 1 and namen["meldungen_offen"] == 1
        assert all(k.weg.startswith("/inventar") for k in kacheln.kacheln(s.db, s))


def test_dienste_vertrag_rueckgabeschluessel_exakt(box) -> None:
    ks = _ks(box.klient, "1000")
    with _sitzung() as s:
        stueck.anlegen(s, bezeichnung="Bagger", gruppe="baumaschine", art="gross", kostenstelle_id=ks["1000"])
        zeile = dienste.bestand(s.db, s, ks["1000"])[0]
        assert set(zeile) == {"inventarnummer", "bezeichnung", "gruppe", "gruppe_text", "art", "menge", "seit", "status", "hinweis"}
        assert isinstance(zeile["seit"], dt.date) and zeile["menge"] == 1 and zeile["gruppe"] == "baumaschine"
        auskunft = dienste.stueck(s.db, s, inventarnummer="BM-00001")
        assert set(auskunft) == {"inventarnummer", "bezeichnung", "gruppe", "gruppe_text", "art", "status", "seriennummer",
                                 "hersteller", "standort_kostenstelle_id", "standort_seit"}
        assert dienste.DIENSTE[0][0] == "bestand" and dienste.DIENSTE[1][0] == "stueck"
