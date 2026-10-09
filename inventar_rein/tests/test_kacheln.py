"""Prueffaelle fuer kacheln (H1-H4), mit dem Beispielbetrieb."""
from __future__ import annotations

from dataclasses import replace

from inventar_rein.bestand import StueckInfo
from inventar_rein.beispielbetrieb import lade_beispielbetrieb, pruefstaende, zustaende
from inventar_rein.kacheln import Kachel, kacheln
from inventar_rein.kataloge import lade_pruefarten

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
        Kachel("inventar.kachel.pruefungen_faellig", 5, "inventar.faellig", "inventar.pruefen"),
        Kachel("inventar.kachel.ohne_nachweis", 3, "inventar.faellig", "inventar.pruefen"),
        Kachel("inventar.kachel.transfers_an_mich", 3, "inventar.hier", "inventar.scannen"),
        Kachel("inventar.kachel.transfers_ueberfaellig", 1, "inventar.uebersicht", "inventar.buchen"),
        Kachel("inventar.kachel.meldungen_offen", 1, "inventar.werkstatt", "inventar.werkstatt"),
        Kachel("inventar.kachel.reparaturen_in_arbeit", 1, "inventar.werkstatt", "inventar.werkstatt"),
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
