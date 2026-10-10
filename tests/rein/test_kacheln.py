"""Prueffaelle fuer kacheln (H1-H4), mit dem Beispielbetrieb."""
from __future__ import annotations

from dataclasses import replace

from digiassistenz_inventar.rein.bestand import StueckInfo
from digiassistenz_inventar.rein.beispielbetrieb import lade_beispielbetrieb, pruefstaende, zustaende
from digiassistenz_inventar.rein.kacheln import Kachel, kacheln
from digiassistenz_inventar.rein.kataloge import lade_pruefarten

B = lade_beispielbetrieb()
Z = zustaende(B)
STAENDE = pruefstaende(B, lade_pruefarten())
INFOS = [(StueckInfo(s.zeile.inventarnummer, s.zeile.bezeichnung, s.zeile.gruppe, s.zeile.gruppe, s.zeile.art, s.status),
          Z[s.zeile.inventarnummer]) for s in B.stuecke]


def lauf(**kw):
    args = dict(stuecke=INFOS, pruefstaende=STAENDE, meldungen=B.meldungen, heute=B.heute, reparaturen=B.reparaturen,
                meine_kostenstellen=[79795])
    args.update(kw)
    return kacheln(**args)  # type: ignore[arg-type]


def test_H1_alle_sechs_kacheln_im_beispielbetrieb():
    erg = lauf()
    assert erg == (
        Kachel("inventar.kachel.pruefungen_faellig", 5, "/inventar/faellig", (("inventar", "pruefen"), ("inventar", "werkstatt"))),
        Kachel("inventar.kachel.ohne_nachweis", 3, "/inventar/faellig", (("inventar", "pruefen"),)),
        Kachel("inventar.kachel.transfers_an_mich", 3, "/inventar/hier", (("inventar", "scannen"),)),
        Kachel("inventar.kachel.transfers_ueberfaellig", 1, "/inventar", (("inventar", "buchen"),)),
        Kachel("inventar.kachel.meldungen_offen", 1, "/inventar/werkstatt", (("inventar", "werkstatt"),)),
        Kachel("inventar.kachel.in_arbeit", 1, "/inventar/werkstatt", (("inventar", "werkstatt"),)),
    )


def test_H2_zahl_null_wird_weggelassen():
    assert lauf(stuecke=[], pruefstaende={}, meldungen=[], reparaturen=[]) == ()
    nur_polier_zwei = lauf(meine_kostenstellen=[80010])
    assert "inventar.kachel.transfers_an_mich" in [k.text_schluessel for k in nur_polier_zwei]  # EL-00001 ist auf 80010 angekuendigt
    assert next(k for k in nur_polier_zwei if k.text_schluessel.endswith("transfers_an_mich")).zahl == 1
    keiner = lauf(meine_kostenstellen=[])
    assert "inventar.kachel.transfers_an_mich" not in [k.text_schluessel for k in keiner]


def test_H3_endzustaende_zaehlen_nicht_und_frist_ist_einstellbar():
    infos = [(replace(i, status="verschrottet") if i.inventarnummer == "EL-00001" else i, z) for i, z in INFOS]
    namen = [k.text_schluessel for k in lauf(stuecke=infos)]
    assert "inventar.kachel.transfers_ueberfaellig" not in namen
    lang = lauf(frist_werktage=10)
    assert "inventar.kachel.transfers_ueberfaellig" not in [k.text_schluessel for k in lang]


def test_H4_nur_stuecke_der_uebergebenen_liste_zaehlen():
    nur_bagger = [x for x in INFOS if x[0].inventarnummer == "KG-00005"]
    erg = lauf(stuecke=nur_bagger)
    assert [(k.text_schluessel.split(".")[-1], k.zahl) for k in erg] == [("meldungen_offen", 1)]


def test_H5_angenommene_meldung_zaehlt_als_in_arbeit_und_ein_stueck_nur_einmal():
    from datetime import datetime, timezone

    from digiassistenz_inventar.rein.werkstatt import meldung_weiter, neue_meldung

    zeit = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    angenommen = meldung_weiter(neue_meldung("schaden", "Kabel ab", "polier.eins", zeit), "angenommen", "werkstatt", zeit)
    erg = lauf(meldungen=[("KG-00007", angenommen)], reparaturen=[])
    zahlen = {k.text_schluessel.split(".")[-1]: k.zahl for k in erg}
    assert zahlen.get("meldungen_offen") is None and zahlen["in_arbeit"] == 1
    doppelt = lauf(meldungen=[("KG-00004", angenommen)])  # KG-00004 hat schon eine Reparatur in Arbeit
    assert {k.text_schluessel.split(".")[-1]: k.zahl for k in doppelt}["in_arbeit"] == 1


def test_H6_die_pruefungs_kachel_gilt_fuer_pruefen_oder_werkstatt():
    """Wie der Menüpunkt „Fällig“: Tupel von Paaren, eines genügt (Form von `Menueeintrag.rechte`)."""
    kachel = next(k for k in lauf() if k.text_schluessel.endswith("pruefungen_faellig"))
    assert kachel.rechte == (("inventar", "pruefen"), ("inventar", "werkstatt"))
    ohne_nachweis = next(k for k in lauf() if k.text_schluessel.endswith("ohne_nachweis"))
    assert ohne_nachweis.rechte == (("inventar", "pruefen"),), "der Nachweis ist Sache der Prüfenden"
    for k in lauf():
        assert all(isinstance(r, tuple) and len(r) == 2 for r in k.rechte), k
