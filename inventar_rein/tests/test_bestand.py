"""Prueffaelle fuer bestand (D1-D9)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from inventar_rein.bestand import StueckInfo, bestand, finde_stueck, stueck_auskunft
from inventar_rein.transfer import Standort, Zustand, abgang_buchen, eingang_bestaetigen

ZONE = timezone(timedelta(hours=2))
A, B = 100, 200


def zeit(tag: int) -> datetime:
    return datetime(2026, 10, tag, 8, 0, tzinfo=ZONE)


def info(nr: str, art: str = "gross", status: str = "aktiv", gruppe: str = "baumaschine", text: str = "Baumaschinen", **kw):
    return StueckInfo(nr, f"Stueck {nr}", gruppe, text, art, status, **kw)


def auf(nr: str, ks: int, menge: int = 1, tag: int = 1) -> Zustand:
    return Zustand((Standort(nr, ks, menge, zeit(tag), None, None, "web", "anna"),), ())


def test_D1_vor_ort_zeile_hat_alle_schluessel_ohne_preise_und_personen():
    zeilen = bestand([(info("BM-1"), auf("BM-1", A))], A, None, date(2026, 10, 8))
    assert zeilen == [{"inventarnummer": "BM-1", "bezeichnung": "Stueck BM-1", "gruppe": "baumaschine", "gruppe_text": "Baumaschinen",
                       "art": "gross", "menge": 1, "seit": date(2026, 10, 1), "status": "vor_ort", "hinweis": ""}]
    assert not {"preis", "kaufpreis", "person", "von_person"} & set(zeilen[0])


def test_D2_angekuendigt_nur_fuer_heute():
    z = abgang_buchen(auf("BM-1", A), "BM-1", A, B, 1, "bernd", zeit(7), "handy", "k1").zustand
    heute = date(2026, 10, 8)
    ziel = bestand([(info("BM-1"), z)], B, None, heute)
    assert [(r["status"], r["seit"]) for r in ziel] == [("angekuendigt", date(2026, 10, 7))]
    assert bestand([(info("BM-1"), z)], B, date(2026, 10, 7), heute) == []  # Vergangenheit: nur bestaetigter Standort
    assert [r["status"] for r in bestand([(info("BM-1"), z)], A, None, heute)] == ["vor_ort"]


def test_D3_nach_eingang_zaehlt_der_neue_standort_ab_dem_eingangstag():
    z = abgang_buchen(auf("BM-1", A), "BM-1", A, B, 1, "bernd", zeit(7), "handy", "k1").zustand
    z = eingang_bestaetigen(z, z.transfers[0].id, "carla", zeit(8), "handy").zustand
    heute = date(2026, 10, 9)
    assert [r["status"] for r in bestand([(info("BM-1"), z)], B, None, heute)] == ["vor_ort"]
    assert bestand([(info("BM-1"), z)], A, None, heute) == []
    assert [r["inventarnummer"] for r in bestand([(info("BM-1"), z)], A, date(2026, 10, 7), heute)] == ["BM-1"]
    assert [r["inventarnummer"] for r in bestand([(info("BM-1"), z)], A, date(2026, 10, 8), heute)] == []  # Eingangstag zaehlt zum Ziel


def test_D4_mengenartikel_einmal_je_kostenstelle_mit_summe():
    z = Zustand((Standort("S-1", A, 30, zeit(1), None, None, "web", "a"), Standort("S-1", A, 10, zeit(2), None, None, "web", "a")), ())
    zeilen = bestand([(info("S-1", art="menge"), z)], A, None, date(2026, 10, 8))
    assert len(zeilen) == 1 and zeilen[0]["menge"] == 40 and zeilen[0]["seit"] == date(2026, 10, 1)
    einzeln = bestand([(info("BM-1"), Zustand((Standort("BM-1", A, 3, zeit(1), None, None, "web", "a"),), ()))], A, None, date(2026, 10, 8))
    assert einzeln[0]["menge"] == 1  # gross/klein immer 1


def test_D5_endzustaende_erscheinen_nicht_und_hinweise():
    stuecke = [(info("A", status="verkauft"), auf("A", A)), (info("B", status="in_reparatur"), auf("B", A)),
               (info("C", status="vermisst"), auf("C", A)), (info("D", pruefung_ueberfaellig=True), auf("D", A)),
               (info("E"), auf("E", A))]
    zeilen = {r["inventarnummer"]: r["hinweis"] for r in bestand(stuecke, A, None, date(2026, 10, 8))}
    assert zeilen == {"B": "stueck_status.hinweis_in_reparatur", "C": "stueck_status.hinweis_vermisst",
                      "D": "bestand.hinweis_pruefung_ueberfaellig", "E": ""}


def test_D6_gruppenfilter_und_sortierung():
    stuecke = [(info("Z-1", gruppe="it", text="IT"), auf("Z-1", A)), (info("B-2", text="Baumaschinen"), auf("B-2", A)),
               (info("B-1", text="Baumaschinen"), auf("B-1", A))]
    zeilen = bestand(stuecke, A, None, date(2026, 10, 8))
    assert [r["inventarnummer"] for r in zeilen] == ["B-1", "B-2", "Z-1"]
    assert [r["inventarnummer"] for r in bestand(stuecke, A, None, date(2026, 10, 8), gruppe="it")] == ["Z-1"]


def test_D7_stichtag_vor_dem_standort_liefert_nichts():
    assert bestand([(info("BM-1"), auf("BM-1", A, tag=5))], A, date(2026, 10, 4), date(2026, 10, 8)) == []


def test_D8_nummernsuche_getrimmt_und_unabhaengig_von_gross_klein():
    liste = [info("BM-00017"), info("FZ-00002")]
    assert finde_stueck(liste, " bm-00017 ").inventarnummer == "BM-00017"
    assert finde_stueck(liste, "BM-00018") is None and finde_stueck(liste, "  ") is None


def test_D9_stueck_auskunft():
    z = abgang_buchen(auf("BM-1", A), "BM-1", A, B, 1, "bernd", zeit(7), "handy", "k1").zustand
    antwort = stueck_auskunft(info("BM-1", status="in_reparatur"), z)
    assert antwort == {"inventarnummer": "BM-1", "bezeichnung": "Stueck BM-1", "gruppe": "baumaschine", "gruppe_text": "Baumaschinen",
                       "art": "gross", "status": "in_reparatur", "standort_kostenstelle_id": A, "standort_seit": date(2026, 10, 1)}
    assert stueck_auskunft(info("BM-1", status="verschrottet"), z) is None
    ohne = stueck_auskunft(info("X"), Zustand((), ()))
    assert ohne["standort_kostenstelle_id"] is None and ohne["standort_seit"] is None
