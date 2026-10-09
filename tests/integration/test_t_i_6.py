"""T-I-6 und T-K-14 — drei Pakete: Kern, Belegerfassung und Inventar; eines fällt weg und kommt zurück.

Aufbau: Kern, Belegerfassung **und** Inventar installiert. Läuft im Wegwerf-Container der Belegerfassung, in den das
Inventar zusätzlich eingebaut wird (`tests/integration/laufen.md`) — nie im Betrieb. Muster: `test_t_i_4.py` des Kerns.

„Wegfallen“ heißt, wie es ein Verwalter tut: `kern.modul.aktiv = false` (ausblenden, nie löschen). Dann muss das andere
Modul **unverändert** laufen, die Rechte des weggefallenen stehen **stumm** in der Datenbank, und wenn es zurückkommt,
gilt alles wie vorher — nichts verloren, nichts neu vergeben. Beide Richtungen. T-K-14: zwischen zwei Modulschemata gibt es
keinen Fremdschlüssel — nur in den Kern.

**Von Box nicht ausgeführt:** die Belegerfassung steht ihr nicht zur Verfügung. Die Datei folgt dem Muster von T-I-4; VSC fährt sie.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from conftest import anmelden, aufbau_pruefen, menuewege, tote_links
from digiassistenz_kern import BenutzerRecht, Modul
from digiassistenz_kern import modul as kern_modul
from digiassistenz_kern.sitzung import systemsitzung

MODULE = {"beleg", "inventar"}
WEGE = {"beleg": "/pruefen", "inventar": "/inventar"}
BAUSTEIN = {"beleg": ("beleg", "sehen"), "inventar": ("inventar", "sehen")}


@pytest.fixture(scope="module", autouse=True)
def _t_i_6_aufbau() -> None:
    aufbau_pruefen(MODULE)


def _schalten(schluessel: str, aktiv: bool) -> None:
    with systemsitzung("pruefung.t_i_6") as db:
        db.execute(select(Modul).where(Modul.schluessel == schluessel)).scalar_one().aktiv = aktiv


def _rechte_des(modul: str) -> set[tuple[int, str, str]]:
    """Die Rechtezeilen aller Benutzer, die einem Modul gehören — Zeile für Zeile."""
    with systemsitzung("pruefung.t_i_6") as db:
        besitz = {(m, a) for m, a, b in db.execute(text("SELECT modul, aktion, besitzer FROM kern.recht")) if b == modul}
        return {(int(s.benutzer_id), s.modul, s.aktion) for s in db.execute(select(BenutzerRecht)).scalars() if (s.modul, s.aktion) in besitz}


@pytest.mark.parametrize("weg_faellt,bleibt", [("inventar", "beleg"), ("beleg", "inventar")])
def test_t_i_6_eines_faellt_weg_und_kommt_zurueck(box, weg_faellt: str, bleibt: str) -> None:
    klient = box.klient
    anmelden(klient)
    vorher_wege = menuewege(klient.get(WEGE[bleibt]).text)
    vorher_rechte = _rechte_des(weg_faellt)
    assert WEGE[weg_faellt] in vorher_wege and WEGE[bleibt] in vorher_wege
    assert vorher_rechte, f"der Verwalter trägt Rechte von {weg_faellt}"
    _schalten(weg_faellt, False)
    try:
        anmelden(klient)  # die Rechte hängen an der Sitzung
        seite = klient.get(WEGE[bleibt])
        assert seite.status_code == 200
        wege = menuewege(seite.text)
        assert WEGE[weg_faellt] not in wege, "das Modul ist weg, sein Menü auch"
        assert WEGE[bleibt] in wege
        assert tote_links(klient, seite.text) == []
        assert _rechte_des(weg_faellt) == vorher_rechte, "stumm, nicht weg"
        assert klient.get(WEGE[weg_faellt]).status_code in (403, 404)
        with systemsitzung("pruefung.t_i_6") as db:
            kern_modul.speicher_leeren(db)
            assert kern_modul.baustein_sichtbar(db, *BAUSTEIN[weg_faellt]) is False
            assert kern_modul.baustein_sichtbar(db, *BAUSTEIN[bleibt]) is True
        for weg in ("/verwaltung", "/verwaltung/kostenstellen", "/verwaltung/lieferanten", "/verwaltung/vorlagen"):
            assert klient.get(weg).status_code == 200, weg
        if bleibt == "inventar":  # die Suche des Inventars läuft ohne die Belegerfassung weiter
            assert klient.get("/suche", params={"q": "x"}).status_code == 200
    finally:
        _schalten(weg_faellt, True)
    anmelden(klient)
    assert menuewege(klient.get(WEGE[bleibt]).text) == vorher_wege, "zurück — dasselbe Menü wie vorher"
    assert _rechte_des(weg_faellt) == vorher_rechte, "dieselben Rechte, nichts neu vergeben"
    assert klient.get(WEGE[weg_faellt]).status_code == 200


def test_t_k_14_kein_fremdschluessel_zwischen_modulen(box) -> None:
    """T-K-14: `pg_constraint` kennt keinen Fremdschlüssel von einem Modulschema in ein anderes."""
    module = set(kern_modul.schemata()) - {"kern"}
    assert module == MODULE, "ein leerer Suchraum ist kein Grün"
    with systemsitzung("pruefung.t_k_14") as db:
        paare = db.execute(text(
            "SELECT c.conname, ns.nspname, nz.nspname FROM pg_constraint c"
            " JOIN pg_class q ON q.oid = c.conrelid JOIN pg_namespace ns ON ns.oid = q.relnamespace"
            " JOIN pg_class z ON z.oid = c.confrelid JOIN pg_namespace nz ON nz.oid = z.relnamespace"
            " WHERE c.contype = 'f'")).all()
    assert paare, "ein leerer Suchraum ist kein Grün — es gibt Fremdschlüssel in den Kern"
    assert [f"{n}: {v} → {z}" for n, v, z in paare if v in module and z in module and v != z] == []
    assert {z for _, v, z in paare if v in module} <= module | {"kern"}
