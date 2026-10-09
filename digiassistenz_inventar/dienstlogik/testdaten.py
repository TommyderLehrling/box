"""Testdaten einspielen: `rein.testdaten.erzeuge` → derselbe Weg wie der Import. Nur solange `auslieferung_am` leer ist."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein import testdaten as erzeuger
from . import import_lauf, katalog, nummer as nummernvergabe


def erlaubt(db: Any, mandant_id: int) -> bool:
    return not katalog.einstellung(db, mandant_id, "auslieferung_am")


def einspielen(sitzung: Any, seed: int = 1, anzahl: int = erzeuger.STANDARD_ANZAHL) -> int:
    """Legt fiktive Stücke mit Transfers, Prüfungen und Zählerständen an; gleiche Eingabe, gleiche Daten, zweiter Lauf ändert nichts."""
    if not sitzung.darf("inventar", "einstellen"):
        raise gemeinsam.KeinRecht("inventar", "einstellen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    if not erlaubt(db, mid):
        raise ValueError("testdaten.nach_auslieferung")
    ks = katalog.kostenstellen_nummern(sitzung)
    if not ks:
        raise ValueError("testdaten.keine_kostenstelle")
    heute = zeit.heute()
    daten = erzeuger.erzeuge(seed, anzahl, katalog.gruppen(db, mid), katalog.merkmale(db, mid), katalog.pruefarten(db, mid),
                             sorted(ks), nummernvergabe.muster(db, mid), heute)
    schon = set(db.execute(select(m.Stueck.inventarnummer).where(m.Stueck.mandant_id == mid)).scalars())
    neu = [z for z in daten.stuecke if z.inventarnummer not in schon]
    import_lauf.anlegen(sitzung, neu, "testdaten")
    ids = {s.inventarnummer: int(s.id) for s in db.execute(select(m.Stueck).where(
        m.Stueck.mandant_id == mid, m.Stueck.inventarnummer.in_([z.inventarnummer for z in neu]))).scalars()}
    arten = {p.schluessel: int(p.id) for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid)).scalars()}
    vorhanden = set(db.execute(select(m.Transfer.eintrag_schluessel).where(m.Transfer.mandant_id == mid)).scalars())
    for t in daten.transfers:
        if t.stueck in ids and t.eintrag_schluessel not in vorhanden:
            db.add(m.Transfer(
                mandant_id=mid, stueck_id=ids[t.stueck], menge=t.menge, von_kostenstelle_id=ks[t.von_kostenstelle],
                nach_kostenstelle_id=ks[t.nach_kostenstelle], status="angekuendigt", abgang_am=t.abgang_am, grund="",
                quelle="import", eintrag_schluessel=t.eintrag_schluessel))
    for nummer, art, durch, faellig in daten.pruefungen:
        if nummer in ids:
            db.add(m.Pruefung(mandant_id=mid, stueck_id=ids[nummer], pruefart_id=arten[art], faellig_am=faellig, durchgefuehrt_am=durch,
                              ergebnis="bestanden", durchfuehrung="intern", quelle="testdaten", naechste_am=faellig))
    for nummer, stand, am in daten.zaehlerstaende:
        if nummer in ids:
            db.add(m.Zaehlerstand(mandant_id=mid, stueck_id=ids[nummer], stand=Decimal(stand), einheit="h", quelle="testdaten",
                                  abgelesen_am=dt.datetime.combine(am, dt.time(12), tzinfo=dt.timezone.utc)))
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.testdaten", objekt_typ="inventar.import",
                        neu_wert=f"Seed {seed}: {len(neu)} Stück", benutzer_id=None if sitzung.benutzer is None else int(sitzung.benutzer.id))
    return len(neu)
