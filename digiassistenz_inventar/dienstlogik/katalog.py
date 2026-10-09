"""Kataloge des Mandanten aus der Datenbank, als reine Katalogtypen (`rein.kataloge`), und Einstellungen."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from .. import modelle as m
from ..rein import kataloge


def einstellung(db: Any, mandant_id: int, schluessel: str, standard: str = "") -> str:
    wert = db.execute(select(m.Einstellung.wert).where(
        m.Einstellung.mandant_id == mandant_id, m.Einstellung.schluessel == schluessel)).scalar_one_or_none()
    return standard if wert is None else wert


def setze_einstellung(db: Any, mandant_id: int, schluessel: str, wert: str, benutzer_id: int | None) -> None:
    zeile = db.execute(select(m.Einstellung).where(
        m.Einstellung.mandant_id == mandant_id, m.Einstellung.schluessel == schluessel)).scalar_one_or_none()
    if zeile is None:
        db.add(m.Einstellung(mandant_id=mandant_id, schluessel=schluessel, wert=wert, geaendert_von=benutzer_id))
    else:
        zeile.wert, zeile.geaendert_von = wert, benutzer_id
    db.flush()


def gruppen(db: Any, mandant_id: int, nur_aktive: bool = True) -> list[kataloge.Gruppe]:
    zeilen = db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id).order_by(m.Gruppe.sortierung, m.Gruppe.id)).scalars().all()
    oben = {int(z.id): z.schluessel for z in zeilen}
    return [kataloge.Gruppe(z.schluessel, z.bezeichnung, z.kuerzel, oben.get(int(z.oben_id)) if z.oben_id else None, z.sortierung)
            for z in zeilen if z.aktiv or not nur_aktive]


def merkmale(db: Any, mandant_id: int) -> list[kataloge.Merkmal]:
    gruppen_schluessel = {int(g.id): g.schluessel for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    return [kataloge.Merkmal(gruppen_schluessel[int(z.gruppe_id)], z.schluessel, z.bezeichnung, z.typ, z.einheit,  # type: ignore[arg-type]
                             tuple(z.auswahl or ()), z.pflicht, z.sortierung)
            for z in db.execute(select(m.Merkmal).where(m.Merkmal.mandant_id == mandant_id, m.Merkmal.aktiv)
                                .order_by(m.Merkmal.sortierung, m.Merkmal.id)).scalars()]


def pruefarten(db: Any, mandant_id: int) -> list[kataloge.Pruefart]:
    gruppen_schluessel = {int(g.id): g.schluessel for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    je_art: dict[int, list[str]] = {}
    for z in db.execute(select(m.GruppePruefart).where(m.GruppePruefart.mandant_id == mandant_id, m.GruppePruefart.aktiv)).scalars():
        je_art.setdefault(int(z.pruefart_id), []).append(gruppen_schluessel[int(z.gruppe_id)])
    return [kataloge.Pruefart(p.schluessel, p.bezeichnung, p.intervall_monate, p.zaehler_intervall, p.rechtsgrund,  # type: ignore[arg-type]
                              p.durchfuehrung, tuple(je_art.get(int(p.id), [])), dict(p.intervall_je_merkmal or {}))
            for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mandant_id, m.Pruefart.aktiv)
                                .order_by(m.Pruefart.id)).scalars()]


def kostenstellen_nummern(sitzung: Any) -> dict[int, int]:
    """Nummer → Id der Kostenstellen, die diese Sitzung kennt (Nummern sind reine Ziffernblöcke)."""
    from digiassistenz_kern import Kostenstelle

    return {int(k.nummer): int(k.id) for k in sitzung.db.execute(sitzung.abfrage(Kostenstelle)).scalars() if str(k.nummer).isdigit()}
