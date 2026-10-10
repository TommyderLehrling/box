"""Startdaten des Inventars — wiederholbar: was fehlt, wird angelegt, was da ist, bleibt (Auftrag 03 Abschnitt 7).

Gruppen, Merkmale, Prüfarten (mit Gruppen-Zuordnung) und die Kostensatz-Vorschläge kommen aus `rein/daten`,
dazu die Einstellungen. Es gibt **keine Stücke** — Testdaten nur über die Verwaltung.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from digiassistenz_kern import protokoll

from . import modelle as m
from .rein import kataloge
from .rein.kosten import lade_standardwerte

AKTION = "inventar.startdaten"
KOSTENSATZ_AB = dt.date(2000, 1, 1)
EINSTELLUNGEN: dict[str, str] = {
    "nummernmuster": "{gruppe}-{nr:5}",
    "transfer_frist_werktage": "3",
    "tage_je_monat": "30",
    "werktage": "0",
    "gelb_ab_tagen": "30",
    "zaehler_gelb_prozent": "10",
    "etikett_layout": "70x36_3x8",
    "zins_prozent": "4.0",
    "erinnern_um": "06:00",
    "pruefung_erinnern_tage": "14",
}


def _gruppen(db: Session, mandant_id: int) -> int:
    vorhanden = {g.schluessel: g for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    katalog = kataloge.lade_gruppen()
    neu = 0
    for g in katalog:
        if g.schluessel not in vorhanden:
            vorhanden[g.schluessel] = m.Gruppe(
                mandant_id=mandant_id, schluessel=g.schluessel, bezeichnung=g.bezeichnung, kuerzel=g.kuerzel,
                sortierung=g.sortierung, aktiv=True, startwert=True)
            db.add(vorhanden[g.schluessel])
            neu += 1
    db.flush()
    for g in katalog:  # die Obergruppe erst, wenn alle da sind
        zeile = vorhanden[g.schluessel]
        if g.oben and zeile.oben_id is None and zeile.startwert and g.oben in vorhanden:
            zeile.oben_id = vorhanden[g.oben].id
    db.flush()
    return neu


def _merkmale(db: Session, mandant_id: int) -> int:
    gruppen = {g.schluessel: g.id for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    vorhanden = {
        (gid, s) for gid, s in db.execute(
            select(m.Merkmal.gruppe_id, m.Merkmal.schluessel).where(m.Merkmal.mandant_id == mandant_id))
    }
    neu = 0
    for k in kataloge.lade_merkmale():
        gid = gruppen.get(k.gruppe)
        if gid is None or (gid, k.schluessel) in vorhanden:
            continue
        db.add(m.Merkmal(
            mandant_id=mandant_id, gruppe_id=gid, schluessel=k.schluessel, bezeichnung=k.bezeichnung, typ=k.typ,
            einheit=k.einheit, auswahl=list(k.auswahl), pflicht=k.pflicht, sortierung=k.sortierung, startwert=True))
        neu += 1
    db.flush()
    return neu


def _pruefarten(db: Session, mandant_id: int) -> int:
    katalog = kataloge.lade_pruefarten()
    vorhanden = {p.schluessel: p for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mandant_id)).scalars()}
    neu = 0
    for p in katalog:
        if p.schluessel not in vorhanden:
            vorhanden[p.schluessel] = m.Pruefart(
                mandant_id=mandant_id, schluessel=p.schluessel, bezeichnung=p.bezeichnung,
                intervall_monate=p.intervall_monate, zaehler_intervall=p.zaehler_intervall, rechtsgrund=p.rechtsgrund,
                durchfuehrung=p.durchfuehrung, intervall_je_merkmal=p.intervall_je_merkmal, startwert=True)
            db.add(vorhanden[p.schluessel])
            neu += 1
    db.flush()
    gruppen = {g.schluessel: g.id for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    zugeordnet = {
        (g, p) for g, p in db.execute(
            select(m.GruppePruefart.gruppe_id, m.GruppePruefart.pruefart_id).where(m.GruppePruefart.mandant_id == mandant_id))
    }
    for gruppe, pruefart in kataloge.gruppe_pruefart(katalog):
        gid, pid = gruppen.get(gruppe), vorhanden[pruefart].id
        if gid is not None and (gid, pid) not in zugeordnet:
            db.add(m.GruppePruefart(mandant_id=mandant_id, gruppe_id=gid, pruefart_id=pid, startwert=True))
            neu += 1
    db.flush()
    return neu


def _kostensaetze(db: Session, mandant_id: int) -> int:
    gruppen = {g.schluessel: g.id for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    vorhanden = set(db.execute(select(m.Kostensatz.gruppe_id).where(
        m.Kostensatz.mandant_id == mandant_id, m.Kostensatz.gruppe_id.is_not(None),
        m.Kostensatz.gueltig_ab == KOSTENSATZ_AB)).scalars())
    neu = 0
    for gruppe, w in lade_standardwerte().items():
        gid = gruppen.get(gruppe)
        if gid is None or gid in vorhanden:
            continue
        db.add(m.Kostensatz(
            mandant_id=mandant_id, gruppe_id=gid, gueltig_ab=KOSTENSATZ_AB, nutzungsdauer_monate=w.nutzungsdauer_monate,
            restwert_prozent=Decimal(w.restwert_prozent), zins_prozent=Decimal(w.zins_prozent),
            reparatur_prozent_jahr=Decimal(w.reparatur_prozent_jahr), quelle="vorschlag_box"))
        neu += 1
    db.flush()
    return neu


def _einstellungen(db: Session, mandant_id: int) -> int:
    vorhanden = set(db.execute(select(m.Einstellung.schluessel).where(m.Einstellung.mandant_id == mandant_id)).scalars())
    neu = 0
    for schluessel, wert in EINSTELLUNGEN.items():
        if schluessel not in vorhanden:
            db.add(m.Einstellung(mandant_id=mandant_id, schluessel=schluessel, wert=wert))
            neu += 1
    db.flush()
    return neu


def startdaten(db: Session, mandant: Any) -> None:
    """`(db, mandant)` — vom Kern nach den eigenen Startdaten gerufen, bei jedem Start."""
    mid = int(mandant.id)
    zahlen = {
        "gruppen": _gruppen(db, mid), "merkmale": _merkmale(db, mid), "pruefarten": _pruefarten(db, mid),
        "kostensaetze": _kostensaetze(db, mid), "einstellungen": _einstellungen(db, mid),
    }
    gesamt = sum(zahlen.values())
    if gesamt > 0:
        protokoll.schreiben(
            db, mandant_id=mid, aktion=AKTION, objekt_typ="inventar.startdaten",
            neu_wert=", ".join(f"{k}={v}" for k, v in zahlen.items() if v))
