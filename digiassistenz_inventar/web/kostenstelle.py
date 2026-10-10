"""Stücke an Kern-Seiten: der Reiter an der Kostenstelle und die Zeilen in Verwaltung → Übersicht."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from digiassistenz_kern import Kostenstelle
from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..dienstlogik import sicht

router = APIRouter()


@router.get("/inventar/kostenstelle/{kostenstelle_id}", response_class=HTMLResponse)
def reiter(
    kostenstelle_id: int, sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> HTMLResponse:
    """Vor Ort und angekündigt auf dieser Kostenstelle; eine fremde Kostenstelle gibt es nicht (N7)."""
    zeile = sitzung.db.execute(sitzung.abfrage(Kostenstelle).where(Kostenstelle.id == kostenstelle_id)).scalars().first()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "sehen")
    orte = sitzung.db.execute(
        sitzung.abfrage(m.Standort).where(m.Standort.bis.is_(None), m.Standort.kostenstelle_id == kostenstelle_id)).scalars().all()
    kommt = sitzung.db.execute(select(func.count()).select_from(m.Transfer).where(
        m.Transfer.mandant_id == sitzung.kontext.mandant_id, m.Transfer.status == "angekuendigt",
        m.Transfer.nach_kostenstelle_id == kostenstelle_id)).scalar_one()
    return gemeinsam.teil("teil_inventar_kostenstelle.html", vor_ort=len({int(o.stueck_id) for o in orte}),
                          angekuendigt=int(kommt), kostenstelle_id=kostenstelle_id, nummer=zeile.nummer)


@router.get("/inventar/uebersicht", response_class=HTMLResponse)
def uebersicht_teil(
    sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> HTMLResponse:
    """Das `<tbody>` für Verwaltung → Übersicht: Stücke gesamt, angekündigt, Prüfungen fällig, ohne Nachweis, Meldungen offen."""
    from .. import kacheln as modul_kacheln

    db = sitzung.db
    gesamt = db.execute(select(func.count()).select_from(sicht.stuecke(sitzung).subquery())).scalar_one()
    zahlen = {k.text_schluessel.rsplit(".", 1)[-1]: k.zahl for k in modul_kacheln.kacheln(db, sitzung)}
    angekuendigt = db.execute(select(func.count()).select_from(m.Transfer).where(
        m.Transfer.mandant_id == sitzung.kontext.mandant_id, m.Transfer.status == "angekuendigt")).scalar_one()
    zeilen = [("gesamt", int(gesamt)), ("angekuendigt", int(angekuendigt)),
              ("faellig", zahlen.get("pruefungen_faellig", 0)), ("ohne_nachweis", zahlen.get("ohne_nachweis", 0)),
              ("meldungen_offen", zahlen.get("meldungen_offen", 0))]
    return gemeinsam.teil("teil_inventar_uebersicht.html", zeilen=zeilen)
