"""Verwaltung → Inventar: Einstieg mit den Katalogen (L11 baut die Pflegeseiten)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from .. import rechte

router = APIRouter()


@router.get("/inventar/verwaltung", response_class=HTMLResponse)
def verwaltung(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "einstellen"), ("inventar", "pflegen"))),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    zahlen = [
        (schluessel, int(sitzung.db.execute(select(func.count()).select_from(modell).where(modell.mandant_id == mid)).scalar_one()))
        for schluessel, modell in (("gruppen", m.Gruppe), ("merkmale", m.Merkmal), ("pruefarten", m.Pruefart),
                                   ("kostensaetze", m.Kostensatz), ("einstellungen", m.Einstellung))
    ]
    return gemeinsam.seite(request, sitzung, "inventar_verwaltung.html", aktiv="verwaltung", zahlen=zahlen,
                           brotkrumen=[], **rechte.darf_alle(sitzung))
