"""Prueffaelle fuer transfer (B1-B13 und Zusatzfaelle Z1-Z8)."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from inventar_rein.transfer import (
    Standort,
    Zustand,
    abgang_buchen,
    eingang_bestaetigen,
    erinnert,
    scan_ist_hier,
    status_auf,
    ueberfaellige,
    zubehoer_folgt,
    zurueckziehen,
)

ZONE = timezone(timedelta(hours=2))
A, B, C = 100, 200, 300
STUECK = "BM-00017"


def zeit(tag: int, stunde: int = 8) -> datetime:
    return datetime(2026, 10, tag, stunde, 0, tzinfo=ZONE)


def auf(ks: int, menge: int = 1, stueck: str = STUECK, tag: int = 1) -> Zustand:
    return Zustand((Standort(stueck, ks, menge, zeit(tag), None, None, "web", "anna"),), ())


def offen(z: Zustand) -> list[Standort]:
    return [s for s in z.standorte if s.bis is None]


def abgang(z: Zustand, nach: int = B, menge: int = 1, schluessel: str = "k1", tag: int = 8):
    return abgang_buchen(z, STUECK, A, nach, menge, "bernd", zeit(tag), "handy", schluessel)


def test_B1_abgang_kuendigt_an_ohne_neuen_standort():
    z = auf(A)
    erg = abgang(z)
    t = erg.zustand.transfers[0]
    assert (t.status, t.von_kostenstelle, t.nach_kostenstelle, t.menge) == ("angekuendigt", A, B, 1)
    assert erg.zustand.standorte == z.standorte
    assert [s.kostenstelle for s in offen(erg.zustand)] == [A]
    assert erg.protokoll == ("transfer.abgang",)
    assert [a.art for a in erg.aenderungen] == ["transfer_neu"]


def test_B2_status_auf_vor_und_nach_dem_abgang():
    erg = abgang(auf(A), tag=8)
    z = erg.zustand
    assert status_auf(z, B, date(2026, 10, 8)) == ((1, "angekuendigt"),)
    assert status_auf(z, A, date(2026, 10, 8)) == ((1, "vor_ort"),)
    assert status_auf(z, A, date(2026, 10, 7)) == ((1, "vor_ort"),)
    assert status_auf(z, B, date(2026, 10, 7)) == ()


def test_B3_scan_auf_ziel_bestaetigt_transfer():
    z = abgang(auf(A), tag=8).zustand
    erg = scan_ist_hier(z, STUECK, B, "carla", zeit(9), "handy", "k2")
    t = erg.zustand.transfers[0]
    assert (t.status, t.eingang_am, t.eingang_von) == ("bestaetigt", zeit(9), "carla")
    a_alt = next(s for s in erg.zustand.standorte if s.kostenstelle == A)
    b_neu = next(s for s in erg.zustand.standorte if s.kostenstelle == B)
    assert a_alt.bis == zeit(9)
    assert (b_neu.von, b_neu.bis, b_neu.transfer_id, b_neu.menge) == (zeit(9), None, t.id, 1)
    assert [s.kostenstelle for s in offen(erg.zustand)] == [B]
    assert status_auf(erg.zustand, B, date(2026, 10, 9)) == ((1, "vor_ort"),)
    assert status_auf(erg.zustand, A, date(2026, 10, 9)) == ()
    assert status_auf(erg.zustand, A, date(2026, 10, 8)) == ((1, "vor_ort"),)


def test_B3_eingang_bestaetigen_hat_dasselbe_ergebnis_wie_scan():
    z = abgang(auf(A)).zustand
    per_taste = eingang_bestaetigen(z, z.transfers[0].id, "carla", zeit(9), "handy")
    per_scan = scan_ist_hier(z, STUECK, B, "carla", zeit(9), "handy", "k2")
    gleich = replace(per_scan.zustand.transfers[0], eingang_schluessel=None)
    assert per_taste.zustand == Zustand(per_scan.zustand.standorte, (gleich,))
    assert per_scan.zustand.transfers[0].eingang_schluessel == "k2"


def test_B4_scan_ohne_offenen_transfer_legt_ab_und_zugang_an():
    erg = scan_ist_hier(auf(A), STUECK, B, "carla", zeit(9), "handy", "k5")
    t = erg.zustand.transfers[0]
    assert (t.status, t.abgang_von, t.quelle, t.von_kostenstelle) == ("bestaetigt", "carla", "system", A)
    assert "transfer.abgang_system" in erg.protokoll
    assert [s.kostenstelle for s in offen(erg.zustand)] == [B]
    assert offen(erg.zustand)[0].quelle == "handy"


def test_B5_scan_am_aktuellen_ort_sieht_nur():
    z = auf(A)
    erg = scan_ist_hier(z, STUECK, A, "carla", zeit(9), "handy", "k6")
    assert erg.zustand == z and erg.aenderungen == ()
    assert erg.protokoll == ("inventur.gesehen",)


def test_B6_scan_auf_drittem_ort_ueberholt_alten_transfer():
    z = abgang(auf(A), nach=B).zustand
    erg = scan_ist_hier(z, STUECK, C, "carla", zeit(9), "handy", "k7")
    alt, neu = erg.zustand.transfers
    assert (alt.status, alt.grund) == ("ueberholt", f"transfer.gesehen_auf:{C}")
    assert (neu.status, neu.von_kostenstelle, neu.nach_kostenstelle) == ("bestaetigt", A, C)
    assert [s.kostenstelle for s in offen(erg.zustand)] == [C]
    assert erg.protokoll[0] == "transfer.ueberholt"
    assert status_auf(erg.zustand, B, date(2026, 10, 9)) == ()


def test_B7_zurueckziehen_braucht_grund_und_nur_angekuendigt():
    z = abgang(auf(A)).zustand
    erg = zurueckziehen(z, z.transfers[0].id, "falsch gebucht", "dora", zeit(9))
    assert erg.zustand.transfers[0].status == "zurueckgezogen"
    assert erg.zustand.transfers[0].grund == "falsch gebucht"
    assert erg.zustand.standorte == z.standorte
    for leer in ("", "   "):
        with pytest.raises(ValueError):
            zurueckziehen(z, z.transfers[0].id, leer, "dora", zeit(9))
    fertig = eingang_bestaetigen(z, z.transfers[0].id, "carla", zeit(9), "handy").zustand
    with pytest.raises(ValueError):
        zurueckziehen(fertig, fertig.transfers[0].id, "doch nicht", "dora", zeit(10))
    with pytest.raises(ValueError):
        zurueckziehen(erg.zustand, erg.zustand.transfers[0].id, "nochmal", "dora", zeit(10))


def test_B8_mengenartikel_teilmenge():
    z = auf(A, menge=40)
    erg = abgang(z, menge=10)
    z1 = erg.zustand
    assert [(s.kostenstelle, s.menge) for s in offen(z1)] == [(A, 40)]
    assert (z1.transfers[0].menge, z1.transfers[0].status) == (10, "angekuendigt")
    assert status_auf(z1, B, date(2026, 10, 8)) == ((10, "angekuendigt"),)
    assert status_auf(z1, A, date(2026, 10, 8)) == ((40, "vor_ort"),)
    z2 = eingang_bestaetigen(z1, z1.transfers[0].id, "carla", zeit(9), "handy").zustand
    assert sorted((s.kostenstelle, s.menge) for s in offen(z2)) == [(A, 30), (B, 10)]
    with pytest.raises(ValueError):
        abgang(auf(A, menge=40), menge=41)
    with pytest.raises(ValueError):
        abgang(z1, menge=31, schluessel="k9")  # 10 sind schon reserviert


def test_B9_idempotenz_bei_gleichem_eintrag_schluessel():
    z = auf(A)
    erst = abgang(z, schluessel="uuid-1")
    zweit = abgang(erst.zustand, schluessel="uuid-1")
    assert zweit.aenderungen == () and zweit.zustand == erst.zustand
    scan1 = scan_ist_hier(auf(A), STUECK, B, "carla", zeit(9), "handy", "uuid-2")
    scan2 = scan_ist_hier(scan1.zustand, STUECK, B, "carla", zeit(9), "handy", "uuid-2")
    assert scan2.aenderungen == () and scan2.zustand == scan1.zustand


def test_B10_ueberfaellige_nach_werktagen_und_erinnert():
    z = abgang(auf(A), tag=8).zustand  # Donnerstag
    assert ueberfaellige(z, date(2026, 10, 12), 3) == ()  # Montag = 2 Werktage
    assert [t.id for t in ueberfaellige(z, date(2026, 10, 13), 3)] == [z.transfers[0].id]  # Dienstag = 3
    assert ueberfaellige(z, date(2026, 10, 13), 3, [date(2026, 10, 9)]) == ()  # Freitag frei
    z2 = erinnert(z, z.transfers[0].id, zeit(13)).zustand
    assert ueberfaellige(z2, date(2026, 10, 14), 3) == ()
    assert z2.transfers[0].erinnert_am == zeit(13)
    zweit = erinnert(z2, z2.transfers[0].id, zeit(14))
    assert zweit.aenderungen == () and zweit.zustand == z2


def test_B11_jede_aenderung_traegt_person_zeit_quelle():
    z = abgang(auf(A)).zustand
    ergebnisse = [
        abgang(auf(A)),
        scan_ist_hier(z, STUECK, B, "carla", zeit(9), "handy", "k2"),
        scan_ist_hier(auf(A), STUECK, B, "carla", zeit(9), "web", "k3"),
        scan_ist_hier(z, STUECK, C, "carla", zeit(9), "handy", "k4"),
        eingang_bestaetigen(z, z.transfers[0].id, "carla", zeit(9), "web"),
        zurueckziehen(z, z.transfers[0].id, "grund", "dora", zeit(9)),
        erinnert(z, z.transfers[0].id, zeit(9)),
    ]
    for erg in ergebnisse:
        assert erg.aenderungen
        for aend in erg.aenderungen:
            assert {"person", "zeit", "quelle"} <= set(aend.daten)
            assert aend.daten["person"] and aend.daten["zeit"].tzinfo is not None
            assert aend.daten["quelle"] in ("web", "handy", "import", "system")


def test_B11_naive_zeit_ist_fehler():
    naiv = datetime(2026, 10, 8, 8, 0)
    z = abgang(auf(A)).zustand
    tid = z.transfers[0].id
    with pytest.raises(ValueError, match="zeit_naiv"):
        abgang_buchen(auf(A), STUECK, A, B, 1, "bernd", naiv, "handy", "k")
    with pytest.raises(ValueError, match="zeit_naiv"):
        scan_ist_hier(z, STUECK, B, "carla", naiv, "handy", "k2")
    with pytest.raises(ValueError, match="zeit_naiv"):
        eingang_bestaetigen(z, tid, "carla", naiv, "handy")
    with pytest.raises(ValueError, match="zeit_naiv"):
        zurueckziehen(z, tid, "grund", "dora", naiv)
    with pytest.raises(ValueError, match="zeit_naiv"):
        erinnert(z, tid, naiv)


def test_B12_zubehoer_folgt_dem_hauptstueck():
    bagger, loeffel = "BM-00017", "AG-00003"
    zb = auf(A, stueck=bagger)
    zl = auf(A, stueck=loeffel)
    haupt = abgang_buchen(zb, bagger, A, B, 1, "bernd", zeit(8), "handy", "k1")
    erg = zubehoer_folgt(haupt, [loeffel], {loeffel: zl}, zeit(8))[loeffel]
    t = erg.zustand.transfers[0]
    assert (t.status, t.quelle, t.von_kostenstelle, t.nach_kostenstelle) == ("angekuendigt", "system", A, B)
    # danach kann der Loeffel einzeln gebucht werden
    einzeln = eingang_bestaetigen(erg.zustand, t.id, "carla", zeit(9), "handy")
    assert [s.kostenstelle for s in offen(einzeln.zustand)] == [B]
    # und der Eingang des Hauptstuecks zieht das Zubehoer mit
    haupt2 = eingang_bestaetigen(haupt.zustand, haupt.zustand.transfers[0].id, "carla", zeit(9), "handy")
    nach = zubehoer_folgt(haupt2, [loeffel], {loeffel: erg.zustand}, zeit(9))[loeffel]
    assert [s.kostenstelle for s in offen(nach.zustand)] == [B]
    assert nach.zustand.transfers[0].status == "bestaetigt"


def test_B13_stueck_ohne_standort_erster_scan_und_erster_abgang():
    leer = Zustand((), ())
    erg = scan_ist_hier(leer, STUECK, A, "carla", zeit(9), "import", "k1")
    t = erg.zustand.transfers[0]
    assert (t.von_kostenstelle, t.nach_kostenstelle, t.status) == (None, A, "bestaetigt")
    assert [(s.kostenstelle, s.quelle) for s in offen(erg.zustand)] == [(A, "import")]
    assert erg.protokoll[0] == "transfer.erstanlage"
    erg2 = abgang_buchen(leer, STUECK, A, B, 1, "bernd", zeit(9), "web", "k2")
    assert [(s.kostenstelle, s.quelle) for s in offen(erg2.zustand)] == [(A, "web")]
    assert erg2.zustand.transfers[0].status == "angekuendigt"


def test_Z1_teilmenge_zurueckziehen_aendert_den_bestand_nicht():
    z1 = abgang(auf(A, menge=40), menge=10).zustand
    erg = zurueckziehen(z1, z1.transfers[0].id, "irrtum", "dora", zeit(9), quelle="werkstatt")
    z2 = erg.zustand
    assert [(s.kostenstelle, s.menge) for s in offen(z2)] == [(A, 40)]
    assert z2.transfers[0].beendet_am == zeit(9)
    assert erg.aenderungen[0].daten["quelle"] == "werkstatt"
    assert status_auf(z2, B, date(2026, 10, 8)) == ((10, "angekuendigt"),)
    assert status_auf(z2, B, date(2026, 10, 9)) == ()


def test_Z2_teilmenge_ueberholt_geht_an_dritten_ort():
    z1 = abgang(auf(A, menge=40), menge=10).zustand
    z2 = scan_ist_hier(z1, STUECK, C, "carla", zeit(9), "handy", "k3").zustand
    assert sorted((s.kostenstelle, s.menge) for s in offen(z2)) == [(A, 30), (C, 10)]


def test_Z3_mengen_werden_am_ziel_zusammengefuehrt():
    z = Zustand(auf(A, 40).standorte + (Standort(STUECK, B, 5, zeit(1), None, None, "web", "anna"),), ())
    z1 = abgang(z, menge=10).zustand
    z2 = eingang_bestaetigen(z1, z1.transfers[0].id, "carla", zeit(9), "handy").zustand
    assert sorted((s.kostenstelle, s.menge) for s in offen(z2)) == [(A, 30), (B, 15)]


def test_Z4_scan_mit_menge_teilt_quelle_ab():
    erg = scan_ist_hier(auf(A, 40), STUECK, B, "carla", zeit(9), "handy", "k1", menge=4)
    assert sorted((s.kostenstelle, s.menge) for s in offen(erg.zustand)) == [(A, 36), (B, 4)]
    with pytest.raises(ValueError):
        scan_ist_hier(auf(A, 40), STUECK, B, "carla", zeit(9), "handy", "k2", menge=41)


def test_Z5_zweiter_abgang_auf_dasselbe_stueck_ist_fehler():
    z = abgang(auf(A)).zustand
    with pytest.raises(ValueError, match="menge_zu_gross"):
        abgang(z, nach=C, schluessel="k2")
    with pytest.raises(ValueError, match="nicht_auf_kostenstelle"):
        abgang_buchen(auf(B), STUECK, A, C, 1, "bernd", zeit(8), "web", "k3")


def test_Z6_eingang_zweimal_und_unbekannt_und_rueckwaerts():
    z = abgang(auf(A), tag=8).zustand
    tid = z.transfers[0].id
    fertig = eingang_bestaetigen(z, tid, "carla", zeit(9), "handy")
    nochmal = eingang_bestaetigen(fertig.zustand, tid, "emil", zeit(10), "web")
    assert nochmal.aenderungen == () and nochmal.protokoll == ("transfer.schon_bestaetigt",)
    with pytest.raises(ValueError, match="unbekannt"):
        eingang_bestaetigen(z, "t:gibt-es-nicht", "carla", zeit(9), "handy")
    with pytest.raises(ValueError, match="zeit_rueckwaerts"):
        eingang_bestaetigen(z, tid, "carla", zeit(7), "handy")


def test_Z7_eingabe_bleibt_unveraendert_und_sonstige_pruefungen():
    z = auf(A)
    vorher = (z.standorte, z.transfers)
    abgang(z)
    assert (z.standorte, z.transfers) == vorher
    with pytest.raises(ValueError, match="gleiche_kostenstelle"):
        abgang_buchen(z, STUECK, A, A, 1, "bernd", zeit(8), "web", "k")
    with pytest.raises(ValueError, match="quelle_unbekannt"):
        abgang_buchen(z, STUECK, A, B, 1, "bernd", zeit(8), "fax", "k")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="person_fehlt"):
        abgang_buchen(z, STUECK, A, B, 1, " ", zeit(8), "web", "k")
    with pytest.raises(ValueError, match="stueck_fremd"):
        abgang_buchen(z, "WZ-00001", A, B, 1, "bernd", zeit(8), "web", "k")
    with pytest.raises(ValueError, match="menge_ungueltig"):
        abgang_buchen(z, STUECK, A, B, 0, "bernd", zeit(8), "web", "k")


def test_Z8_status_auf_im_zeitverlauf():
    z = abgang(auf(A), tag=8).zustand
    z = eingang_bestaetigen(z, z.transfers[0].id, "carla", zeit(12), "handy").zustand
    assert status_auf(z, B, date(2026, 10, 10)) == ((1, "angekuendigt"),)
    assert status_auf(z, A, date(2026, 10, 11)) == ((1, "vor_ort"),)
    assert status_auf(z, B, date(2026, 10, 12)) == ((1, "vor_ort"),)
    assert status_auf(z, A, date(2026, 10, 12)) == ()


def test_B14_teil_eingang_bestaetigt_weniger_und_kuendigt_fehlmenge_an():
    z1 = abgang(auf(A, menge=40), menge=10).zustand
    erg = eingang_bestaetigen(z1, z1.transfers[0].id, "carla", zeit(9), "handy", menge=8)
    z2 = erg.zustand
    assert sorted((s.kostenstelle, s.menge) for s in offen(z2)) == [(A, 32), (B, 8)]
    alt, fehl = z2.transfers
    assert (alt.status, alt.menge) == ("bestaetigt", 8)
    assert (fehl.status, fehl.menge, fehl.grund, fehl.von_kostenstelle, fehl.nach_kostenstelle) == (
        "angekuendigt", 2, "transfer.fehlmenge", A, B)
    assert fehl.abgang_am == alt.abgang_am and fehl.erinnert_am is None
    assert fehl in ueberfaellige(z2, date(2026, 10, 14), 3)
    assert "transfer.fehlmenge" in erg.protokoll
    z3 = eingang_bestaetigen(z2, fehl.id, "carla", zeit(10), "handy").zustand
    assert sorted((s.kostenstelle, s.menge) for s in offen(z3)) == [(A, 30), (B, 10)]


def test_B15_scan_mit_menge_wie_teil_eingang_und_mehrmenge_ist_fehler():
    z1 = abgang(auf(A, menge=40), menge=10).zustand
    z2 = scan_ist_hier(z1, STUECK, B, "carla", zeit(9), "handy", "k2", menge=8).zustand
    assert sorted((s.kostenstelle, s.menge) for s in offen(z2)) == [(A, 32), (B, 8)]
    assert [t.menge for t in z2.transfers if t.status == "angekuendigt"] == [2]
    for aufruf in (
        lambda: scan_ist_hier(z1, STUECK, B, "carla", zeit(9), "handy", "k3", menge=12),
        lambda: eingang_bestaetigen(z1, z1.transfers[0].id, "carla", zeit(9), "handy", menge=12),
    ):
        with pytest.raises(ValueError, match="menge_zu_gross"):
            aufruf()
    with pytest.raises(ValueError, match="menge_ungueltig"):
        eingang_bestaetigen(z1, z1.transfers[0].id, "carla", zeit(9), "handy", menge=0)


def test_B16_wiederholter_scan_nach_teil_eingang_ist_still():
    z1 = abgang(auf(A, menge=40), menge=10).zustand
    z2 = scan_ist_hier(z1, STUECK, B, "carla", zeit(9), "handy", "k2", menge=8).zustand
    nochmal = scan_ist_hier(z2, STUECK, B, "carla", zeit(9, 9), "handy", "k2", menge=8)
    assert nochmal.aenderungen == () and nochmal.zustand == z2 and nochmal.protokoll == ("transfer.doppelt",)


def test_Z9_ueberholt_setzt_beendet_am_und_status_auf_endet_dann():
    z1 = abgang(auf(A), tag=8).zustand
    z2 = scan_ist_hier(z1, STUECK, C, "carla", zeit(10), "handy", "k3").zustand
    ueberholt = z2.transfers[0]
    assert (ueberholt.status, ueberholt.beendet_am) == ("ueberholt", zeit(10))
    assert status_auf(z2, B, date(2026, 10, 9)) == ((1, "angekuendigt"),)
    assert status_auf(z2, B, date(2026, 10, 10)) == ()
