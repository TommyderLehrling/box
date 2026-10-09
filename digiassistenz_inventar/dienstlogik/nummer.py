"""Inventarnummern vergeben: Muster aus der Einstellung, Zähler in `inventar.zaehler` unter `SELECT … FOR UPDATE`."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .. import modelle as m
from ..rein.nummernformat import Muster, entspricht, naechste, pruefe_muster, zaehler_schluessel
from . import katalog

STANDARD_MUSTER = "{gruppe}-{nr:5}"
VERSUCHE = 10_000


def muster(db: Any, mandant_id: int) -> Muster:
    text = katalog.einstellung(db, mandant_id, "nummernmuster", STANDARD_MUSTER)
    fehler = pruefe_muster(text)
    if fehler:
        raise ValueError(fehler[0])
    return Muster(text)


def passt(db: Any, mandant_id: int, nummer: str) -> bool:
    return entspricht(muster(db, mandant_id), nummer)


def _gesperrt(db: Any, mandant_id: int, schluessel: str) -> m.Zaehler:
    db.execute(insert(m.Zaehler).values(mandant_id=mandant_id, schluessel=schluessel, stand=0).on_conflict_do_nothing(
        constraint="uq_zaehler_schluessel"))
    return db.execute(select(m.Zaehler).where(m.Zaehler.mandant_id == mandant_id, m.Zaehler.schluessel == schluessel)
                      .with_for_update()).scalar_one()


def naechste_nummer(db: Any, mandant_id: int, gruppen_kuerzel: str, jahr: int) -> str:
    """Die nächste freie Nummer; eine Nummer, die es schon gibt (Import), wird übersprungen."""
    vorlage = muster(db, mandant_id)
    schluessel = zaehler_schluessel(vorlage, jahr, gruppen_kuerzel)
    zeile = _gesperrt(db, mandant_id, schluessel)
    for _ in range(VERSUCHE):
        nummer, neu = naechste(vorlage, {schluessel: int(zeile.stand)}, jahr, gruppen_kuerzel)
        zeile.stand = neu[schluessel]
        db.flush()
        if not db.execute(select(m.Stueck.id).where(m.Stueck.mandant_id == mandant_id, m.Stueck.inventarnummer == nummer)).first():
            return nummer
    raise ValueError("nummer.keine_frei")
