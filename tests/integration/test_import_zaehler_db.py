"""L16 Zählerstand im Excel-Import: Quelle `import`, zu niedrig oder ohne Zähler nur vermerkt, Vorschau schreibt nichts."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import select, text

from conftest import VERWALTER, anmelden, aufbau_pruefen
from digiassistenz_kern import Benutzer
from digiassistenz_kern.sitzung import benutzersitzung, systemsitzung

from digiassistenz_inventar.dienstlogik import import_lauf
from digiassistenz_inventar.rein.import_vorlage import BLATT, SPALTEN

pytestmark = pytest.mark.usefixtures("_aufbau")


@pytest.fixture(scope="module")
def _aufbau() -> None:
    aufbau_pruefen({"inventar"})


def _sitzung():
    with systemsitzung("pruefung.l16") as db:
        benutzer = int(db.execute(select(Benutzer.id).where(Benutzer.anmeldename == VERWALTER)).scalar_one())
    return benutzersitzung(benutzer, "pruefung.l16")


def _ks(klient, nummer: str) -> None:
    anmelden(klient)
    assert klient.post("/verwaltung/kostenstelle/neu", follow_redirects=False,
                       data={"nummer": nummer, "bezeichnung": f"KS {nummer}", "strasse": "Weg 1", "plz": "25813", "ort": "Husum"}).status_code == 303


def _staende() -> list[tuple[str, Decimal, str]]:
    with systemsitzung("pruefung.l16") as db:
        return [(r[0], r[1], r[2]) for r in db.execute(text(
            "SELECT s.inventarnummer, z.stand, z.quelle FROM inventar.zaehlerstand z JOIN inventar.stueck s ON s.id = z.stueck_id "
            "ORDER BY z.id")).all()]


def _datei(pfad: Path, *zeilen: tuple[str, str, str, object]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = BLATT
    ws.append(list(SPALTEN))
    for nummer, gruppe, art, stand in zeilen:
        ws.append([nummer, f"Gerät {nummer}", gruppe, art, "", "", "", None, None, None, "", 1000, 1, "", stand])
    wb.save(pfad)
    return pfad


def test_zaehlerstand_aus_dem_import(box, tmp_path: Path) -> None:
    _ks(box.klient, "1000")
    erste = _datei(tmp_path / "eins.xlsx", ("BM-00001", "baumaschine", "gross", 120), ("BA-00001", "bueroausstattung", "klein", 5),
                   ("BM-00002", "baumaschine", "gross", None))
    with _sitzung() as s:
        vorschau = import_lauf.bericht(s, erste)
        assert vorschau.lesen.fehler == () and vorschau.zaehlerstaende == (("BM-00001", Decimal("120")),)
        assert vorschau.zaehler_hinweise == (("import.hinweis.zaehlerstand_ohne_zaehler", "BA-00001"),)
    assert _staende() == [], "die Vorschau schreibt nichts"
    with _sitzung() as s:
        erg = import_lauf.einspielen(s, erste)
        assert erg.angelegt == 3 and erg.zaehlerstaende == (("BM-00001", Decimal("120")),)
    assert _staende() == [("BM-00001", Decimal("120"), "import")]
    # zweiter Lauf: BM-00001 mit niedrigerem Stand (nur vermerkt), BM-00002 neu mit Stand; gleicher Stand wie der letzte tut nichts
    zweite = _datei(tmp_path / "zwei.xlsx", ("BM-00001", "baumaschine", "gross", 100), ("BM-00002", "baumaschine", "gross", 50),
                    ("BA-00001", "bueroausstattung", "klein", None))
    with _sitzung() as s:
        erg = import_lauf.einspielen(s, zweite)
        assert erg.angelegt == 0
        assert erg.zaehlerstaende == (("BM-00002", Decimal("50")),)
        assert erg.zaehler_hinweise == (("import.hinweis.zaehlerstand_zu_niedrig", "BM-00001: 100 < 120"),)
    assert _staende() == [("BM-00001", Decimal("120"), "import"), ("BM-00002", Decimal("50"), "import")]
    dritte = _datei(tmp_path / "drei.xlsx", ("BM-00001", "baumaschine", "gross", 120), ("BM-00002", "baumaschine", "gross", 75))
    with _sitzung() as s:
        erg = import_lauf.einspielen(s, dritte)
        assert erg.zaehlerstaende == (("BM-00002", Decimal("75")),) and erg.zaehler_hinweise == ()
    assert len(_staende()) == 3


def test_ablesedatum_aus_dem_import(box, tmp_path: Path) -> None:
    _ks(box.klient, "1000")
    pfad = tmp_path / "ablesung.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = BLATT
    ws.append(list(SPALTEN))
    for nummer, stand, datum in (("BM-00001", 120, "03.02.2025"), ("BM-00002", 50, None), ("BM-00003", 70, "2999-01-01")):
        ws.append([nummer, f"Gerät {nummer}", "baumaschine", "gross", "", "", "", None, None, None, "", 1000, 1, "", stand, datum])
    wb.save(pfad)
    with _sitzung() as s:
        assert [f.text_schluessel for f in import_lauf.pruefen(s, pfad).fehler] == ["import.fehler.ablesedatum_zukunft"]
        with pytest.raises(ValueError, match="fehler_in_datei"):
            import_lauf.einspielen(s, pfad)
    ws["P4"] = "01.03.2025"
    wb.save(pfad)
    with _sitzung() as s:
        import_lauf.einspielen(s, pfad)
    with systemsitzung("pruefung.l16a") as db:
        zeiten = dict(db.execute(text("SELECT s.inventarnummer, z.abgelesen_am FROM inventar.zaehlerstand z JOIN inventar.stueck s ON s.id = z.stueck_id")).all())
    assert zeiten["BM-00001"].date().isoformat() == "2025-02-03" and zeiten["BM-00003"].date().isoformat() == "2025-03-01"
    assert zeiten["BM-00002"].date() >= dt.date.today() - dt.timedelta(days=1), "leer = Zeitpunkt des Imports"


def test_import_seite_zeigt_zaehlerstaende_und_hinweise(box, tmp_path: Path) -> None:
    k = box.klient
    _ks(k, "1000")
    datei = _datei(tmp_path / "web.xlsx", ("BM-00001", "baumaschine", "gross", 120), ("BA-00001", "bueroausstattung", "klein", 5))
    antwort = k.post("/inventar/verwaltung/import", data={"aktion": "pruefen"},
                     files={"datei": ("web.xlsx", datei.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert antwort.status_code == 200
    assert "Zählerstände aus der Datei: 1" in antwort.text and "BA-00001" in antwort.text and "keinen Zähler" in antwort.text
