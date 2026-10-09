"""Stück anlegen und Status setzen — die Anwendungsfälle der Pflege (Recht `pflegen`, `stilllegen`, `werkstatt`)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein import stueck_status
from ..rein.nummernformat import normalisiere
from . import katalog, laden, nummer as nummernvergabe

OBJEKT_TYP = "inventar.stueck"


def _benutzer(sitzung: Any) -> int | None:
    return None if sitzung.benutzer is None else int(sitzung.benutzer.id)


def gruppe_holen(sitzung: Any, schluessel: str) -> m.Gruppe:
    zeile = sitzung.db.execute(select(m.Gruppe).where(
        m.Gruppe.mandant_id == sitzung.kontext.mandant_id, m.Gruppe.schluessel == schluessel)).scalar_one_or_none()
    if zeile is None:
        raise ValueError("stueck.gruppe_unbekannt")
    return zeile


def _merkmale_schreiben(db: Any, mandant_id: int, stueck: m.Stueck, werte: dict[str, str], benutzer_id: int | None) -> None:
    katalog_gruppe = {z.schluessel: z for z in db.execute(select(m.Merkmal).where(
        m.Merkmal.mandant_id == mandant_id, m.Merkmal.gruppe_id == stueck.gruppe_id, m.Merkmal.aktiv)).scalars()}
    for schluessel, wert in werte.items():
        spalte = katalog_gruppe.get(schluessel)
        if spalte is None:
            raise ValueError("stueck.merkmal_unbekannt")
        zahl = None
        if spalte.typ == "zahl":
            try:
                zahl = Decimal(str(wert).replace(",", "."))
            except InvalidOperation as fehler:
                raise ValueError("stueck.merkmal_wert_ungueltig") from fehler
        elif spalte.typ == "auswahl" and wert not in (spalte.auswahl or []):
            raise ValueError("stueck.merkmal_wert_ungueltig")
        db.add(m.StueckMerkmal(mandant_id=mandant_id, stueck_id=stueck.id, merkmal_id=spalte.id, wert=str(wert),
                               wert_zahl=zahl, geaendert_von=benutzer_id))
    db.flush()


def anlegen(
    sitzung: Any, *, bezeichnung: str, gruppe: str, art: str, inventarnummer: str | None = None, hersteller: str = "",
    typ: str = "", seriennummer: str = "", baujahr: int | None = None, lieferant_id: int | None = None,
    kaufdatum: dt.date | None = None, kaufpreis: Decimal | None = None, kostenstelle_id: int | None = None, menge: int = 1,
    merkmale: dict[str, str] | None = None, besonderheiten: str = "", quelle: str = "web", pruefen: bool = True,
    protokollieren: bool = True,
) -> m.Stueck:
    """Legt ein Stück an, auf Wunsch mit Startstandort (Recht `buchen` dort). Die Nummer: gegeben oder vergeben."""
    if not sitzung.darf("inventar", "pflegen"):
        raise gemeinsam.KeinRecht("inventar", "pflegen")
    if kostenstelle_id is not None and not sitzung.darf("inventar", "buchen", kostenstelle_id):
        raise gemeinsam.KeinRecht("inventar", "buchen")
    if not bezeichnung.strip():
        raise ValueError("stueck.bezeichnung_fehlt")
    if art not in m.ART:
        raise ValueError("stueck.art_unbekannt")
    if menge < 1 or (art != "menge" and menge != 1):
        raise ValueError("stueck.menge_ungueltig")
    db, mid, benutzer = sitzung.db, sitzung.kontext.mandant_id, _benutzer(sitzung)
    zeile_gruppe = gruppe_holen(sitzung, gruppe)
    jetzt = zeit.jetzt_utc()
    if inventarnummer is None or not inventarnummer.strip():
        nummer = nummernvergabe.naechste_nummer(db, mid, zeile_gruppe.kuerzel, zeit.heute().year)
    else:
        nummer = normalisiere(inventarnummer)
        if pruefen and not nummernvergabe.passt(db, mid, nummer):
            raise ValueError("stueck.nummer_passt_nicht")
        if db.execute(select(m.Stueck.id).where(m.Stueck.mandant_id == mid, m.Stueck.inventarnummer == nummer)).first():
            raise ValueError("stueck.nummer_vergeben")
    zeile = m.Stueck(
        mandant_id=mid, inventarnummer=nummer, bezeichnung=bezeichnung.strip(), gruppe_id=zeile_gruppe.id, art=art,
        hersteller=hersteller, typ=typ, seriennummer=seriennummer, baujahr=baujahr, lieferant_id=lieferant_id,
        kaufdatum=kaufdatum, kaufpreis=kaufpreis, besonderheiten=besonderheiten, quelle=quelle, status_seit=jetzt,
        zaehler_einheit="h" if art == "gross" else None, angelegt_von=benutzer)
    db.add(zeile)
    db.flush()
    _merkmale_schreiben(db, mid, zeile, merkmale or {}, benutzer)
    if kostenstelle_id is not None:
        db.add(m.Standort(mandant_id=mid, stueck_id=zeile.id, kostenstelle_id=kostenstelle_id, menge=menge, von=jetzt,
                          quelle=quelle, von_person=benutzer))
        db.flush()
    if protokollieren:
        protokoll.schreiben(db, mandant_id=mid, aktion="inventar.stueck_angelegt", objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id),
                            neu_wert=nummer, benutzer_id=benutzer, kostenstelle_id=kostenstelle_id)
    return zeile


def status_wechseln(sitzung: Any, inventarnummer: str, neu: str, grund: str = "") -> m.Stueck:
    """Status mit Grund (Pflicht außer bei der Rückkehr aus `vermisst`); Recht `stilllegen`, für `in_reparatur` `werkstatt`."""
    from .transfer import finde_stueck

    aktion = "werkstatt" if neu == "in_reparatur" else "stilllegen"
    if not sitzung.darf("inventar", aktion):
        raise gemeinsam.KeinRecht("inventar", aktion)
    zeile = finde_stueck(sitzung, inventarnummer, aktion)
    jetzt = zeit.jetzt_utc()
    wechsel = stueck_status.wechsle(zeile.status, neu, grund, laden.person(_benutzer(sitzung)), jetzt)
    alt, zeile.status, zeile.status_seit, zeile.status_grund = zeile.status, neu, jetzt, wechsel.grund
    zeile.geaendert_am, zeile.geaendert_von = jetzt, _benutzer(sitzung)
    sitzung.db.flush()
    protokoll.schreiben(sitzung.db, mandant_id=sitzung.kontext.mandant_id, aktion=laden.aktion_aus(wechsel.protokoll),
                        objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id), alt_wert=alt,
                        neu_wert=f"{neu}: {wechsel.grund}" if wechsel.grund else neu, benutzer_id=_benutzer(sitzung))
    return zeile
