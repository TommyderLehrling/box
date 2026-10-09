"""Kacheln des Inventars (Zahl, Text, Weg) aus `rein.kacheln` — vorerst oben auf `/inventar`.

# Brücke 025: wird Posteingang-Kachel, sobald Verbindung.kacheln einen Vertrag hat (Steckbrief 11: ohne Vertrag)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from digiassistenz_kern import zeit

from . import modelle as m
from .dienste import stueck_infos
from .dienstlogik import laden, pruefstand, sicht
from .rein import kacheln as rein_kacheln
from .rein import werkstatt

Kachel = rein_kacheln.Kachel


def _meldungen(db: Session, sitzung: Any, nummern: dict[int, str]) -> list[tuple[str, werkstatt.Meldung]]:
    q = sitzung.abfrage(m.Meldung).where(m.Meldung.stueck_id.in_(list(nummern)))
    return [(nummern[int(z.stueck_id)], werkstatt.Meldung(
        z.art, z.status, z.beschreibung, laden.person(z.gemeldet_von), z.gemeldet_am,  # type: ignore[arg-type]
        None if z.bearbeitet_von is None else laden.person(z.bearbeitet_von), z.erledigt_am, z.rueckmeldung, z.grund))
        for z in db.execute(q).scalars()]


def _reparaturen(db: Session, sitzung: Any, nummern: dict[int, str]) -> list[tuple[str, werkstatt.Reparatur]]:
    q = select(m.Reparatur).where(m.Reparatur.mandant_id == sitzung.kontext.mandant_id, m.Reparatur.stueck_id.in_(list(nummern)))
    return [(nummern[int(z.stueck_id)], werkstatt.Reparatur(
        z.status, z.durchfuehrung, z.begonnen_am, z.beendet_am, z.kosten, z.kosten_quelle, z.grund))  # type: ignore[arg-type]
        for z in db.execute(q).scalars()]


def kacheln(db: Session, sitzung: Any) -> tuple[Kachel, ...]:
    """Was ansteht, nach den Rechten der Sitzung; Kacheln ohne Recht und mit Zahl 0 fehlen."""
    mid, heute = sitzung.kontext.mandant_id, zeit.heute()
    zeilen = list(db.execute(sicht.stuecke(sitzung)).scalars())
    if not zeilen:
        return ()
    infos = stueck_infos(db, sitzung, zeilen, heute)
    zustaende = laden.lade_zustaende(db, mid, zeilen)
    nummern = {int(z.id): z.inventarnummer for z in zeilen}
    meine = sicht.erlaubte_kostenstellen(sitzung, "scannen")
    if meine is None:
        meine = tuple(sorted({t.nach_kostenstelle for z in zustaende.values() for t in z.transfers}))
    frist = int(pruefstand._einstellung(db, mid, "transfer_frist_werktage", "3"))
    alle = rein_kacheln.kacheln(
        [(infos[n], zustaende[n]) for n in infos], pruefstand.staende(db, mid, zeilen, heute),
        _meldungen(db, sitzung, nummern), heute, _reparaturen(db, sitzung, nummern), meine, frist)
    return tuple(k for k in alle if sitzung.darf(*k.recht.split(".", 1)))
