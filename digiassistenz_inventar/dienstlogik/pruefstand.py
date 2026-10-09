"""Prüfstand je Stück aus der Datenbank: Zuordnung (Gruppe, Stück, Merkmal) → letzte Prüfung → Ampel (`rein.pruefung`)."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import modelle as m
from ..rein import kataloge, pruefung


def _einstellung(db: Session, mandant_id: int, schluessel: str, standard: str) -> str:
    wert = db.execute(select(m.Einstellung.wert).where(
        m.Einstellung.mandant_id == mandant_id, m.Einstellung.schluessel == schluessel)).scalar_one_or_none()
    return standard if wert is None else wert


def staende(db: Session, mandant_id: int, stuecke: list[m.Stueck], heute: dt.date) -> dict[str, list[pruefung.Pruefstand]]:
    """Je Inventarnummer die Stände aller zugeordneten Prüfarten; ohne Prüfung `unbekannt`."""
    if not stuecke:
        return {}
    ids = [int(s.id) for s in stuecke]
    gruppen_schluessel = {int(g.id): g.schluessel for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    arten = {int(p.id): p for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mandant_id, m.Pruefart.aktiv)).scalars()}
    je_gruppe: dict[str, list[kataloge.Pruefart]] = {}
    for z in db.execute(select(m.GruppePruefart).where(m.GruppePruefart.mandant_id == mandant_id, m.GruppePruefart.aktiv)).scalars():
        p = arten.get(int(z.pruefart_id))
        if p is None:
            continue
        g = gruppen_schluessel[int(z.gruppe_id)]
        je_gruppe.setdefault(g, []).append(_rein(p, g, z.intervall_monate))
    ueber: dict[int, list[Any]] = {}
    for z in db.execute(select(m.StueckPruefart).where(m.StueckPruefart.stueck_id.in_(ids))).scalars():
        ueber.setdefault(int(z.stueck_id), []).append(z)
    merkmale: dict[int, dict[str, str]] = {}
    for sid, schluessel, wert in db.execute(
        select(m.StueckMerkmal.stueck_id, m.Merkmal.schluessel, m.StueckMerkmal.wert)
        .join(m.Merkmal, m.Merkmal.id == m.StueckMerkmal.merkmal_id).where(m.StueckMerkmal.stueck_id.in_(ids))
    ):
        merkmale.setdefault(int(sid), {})[schluessel] = wert
    letzte: dict[tuple[int, int], pruefung.Eintrag] = {}
    for p in db.execute(select(m.Pruefung).where(m.Pruefung.stueck_id.in_(ids)).order_by(m.Pruefung.durchgefuehrt_am, m.Pruefung.id)).scalars():
        letzte[(int(p.stueck_id), int(p.pruefart_id))] = pruefung.Eintrag(
            arten[int(p.pruefart_id)].schluessel if int(p.pruefart_id) in arten else str(p.pruefart_id),
            p.durchgefuehrt_am, p.ergebnis, p.zaehlerstand)  # type: ignore[arg-type]
    zaehler: dict[int, Decimal] = {}
    for z in db.execute(select(m.Zaehlerstand).where(m.Zaehlerstand.stueck_id.in_(ids)).order_by(m.Zaehlerstand.abgelesen_am, m.Zaehlerstand.id)).scalars():
        zaehler[int(z.stueck_id)] = z.stand
    gelb = int(_einstellung(db, mandant_id, "gelb_ab_tagen", "30"))
    gelb_zaehler = Decimal(_einstellung(db, mandant_id, "zaehler_gelb_prozent", "10")) / 100
    art_id = {p.schluessel: pid for pid, p in arten.items()}
    ergebnis: dict[str, list[pruefung.Pruefstand]] = {}
    for s in stuecke:
        sid, gruppe = int(s.id), gruppen_schluessel[int(s.gruppe_id)]
        katalog = list(je_gruppe.get(gruppe, []))
        eigene = ueber.get(sid, [])
        schon = {p.schluessel for p in katalog}
        for z in eigene:  # Zuordnung nur für dieses Stück
            p = arten.get(int(z.pruefart_id))
            if p is not None and z.aktiv and p.schluessel not in schon:
                katalog.append(_rein(p, gruppe, None))
        regeln = [pruefung.Ueberschreibung(arten[int(z.pruefart_id)].schluessel, z.intervall_monate, bool(z.aktiv))
                  for z in eigene if int(z.pruefart_id) in arten]
        zu = pruefung.zuordnungen_fuer(gruppe, katalog, regeln, merkmale.get(sid))
        ergebnis[s.inventarnummer] = [
            pruefung.pruefstand(z, letzte.get((sid, art_id[z.pruefart])), heute, zaehler.get(sid), gelb, gelb_zaehler) for z in zu]
    return ergebnis


def _rein(p: m.Pruefart, gruppe: str, intervall: int | None) -> kataloge.Pruefart:
    rein = kataloge.Pruefart(
        p.schluessel, p.bezeichnung, p.intervall_monate, p.zaehler_intervall, p.rechtsgrund, p.durchfuehrung,  # type: ignore[arg-type]
        (gruppe,), dict(p.intervall_je_merkmal or {}))
    return rein if intervall is None else replace(rein, intervall_monate=intervall, intervall_je_merkmal={})
