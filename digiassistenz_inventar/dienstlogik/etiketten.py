"""Etikettenbogen: Auswahl → `rein.etiketten.bogen_html` → WeasyPrint → PDF; Ablage `export/etiketten_<datum>.pdf`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Mandant, zeit
from digiassistenz_kern.web import gemeinsam

from .. import dateien
from .. import modelle as m
from ..rein import etiketten as rein
from . import katalog, sicht

LAYOUTS = {"70x36_3x8": rein.Layout()}


def layout(db: Any, mandant_id: int) -> rein.Layout:
    return LAYOUTS.get(katalog.einstellung(db, mandant_id, "etikett_layout", "70x36_3x8"), rein.Layout())


def bogen(sitzung: Any, nummern: list[str] | None, basis_url: str) -> str:
    """Das HTML des Bogens für die Auswahl (ohne Auswahl: alle sichtbaren Stücke, höchstens 2000)."""
    if not sitzung.darf("inventar", "pflegen"):
        raise gemeinsam.KeinRecht("inventar", "pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    abfrage = sicht.stuecke(sitzung).order_by(m.Stueck.inventarnummer).limit(2000)
    if nummern:
        abfrage = abfrage.where(m.Stueck.inventarnummer.in_(nummern))
    gruppen = {int(g.id): g.bezeichnung for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    firma = sitzung.db.execute(select(Mandant.name).where(Mandant.id == mid)).scalar_one()
    liste = [rein.Etikett(s.inventarnummer, s.bezeichnung, gruppen[int(s.gruppe_id)], firma) for s in db.execute(abfrage).scalars()]
    return rein.bogen_html(liste, basis_url, layout(db, mid))


def pdf_ablegen(sitzung: Any, html: str, arbeitsordner: Path) -> tuple[bytes, Path]:
    """Erzeugt das PDF und legt es im Exportordner des Mandanten ab (nie eine vorhandene Datei ersetzen)."""
    from weasyprint import HTML

    inhalt = HTML(string=html).write_pdf()
    ordnername = sitzung.db.execute(select(Mandant.ordnername).where(Mandant.id == sitzung.kontext.mandant_id)).scalar_one()
    pfad, _ = dateien.speichern(dateien.exportordner(arbeitsordner, ordnername), f"etiketten_{zeit.heute().isoformat()}.pdf", inhalt)
    return inhalt, pfad
