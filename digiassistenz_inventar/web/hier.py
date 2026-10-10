"""Die Hier-Seite des Poliers: was kommt an, was steht hier — und der Weg zum Scannen im Browser."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from digiassistenz_kern import Kostenstelle
from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from .. import rechte
from ..dienstlogik import sicht
from . import helfer

router = APIRouter()
COOKIE_KS = "inventar_ks"
HOECHSTENS = 200


def meine_kostenstellen(sitzung: Sitzung) -> dict[int, str]:
    """Die Kostenstellen, auf denen die Sitzung scannen darf — `{id: "Nummer Bezeichnung"}`."""
    erlaubt = sicht.erlaubte_kostenstellen(sitzung, "scannen")
    abfrage = sitzung.abfrage(Kostenstelle).where(Kostenstelle.status == "aktiv")
    if erlaubt is not None:
        abfrage = abfrage.where(Kostenstelle.id.in_(erlaubt))
    zeilen = sitzung.db.execute(abfrage.order_by(Kostenstelle.nummer).limit(HOECHSTENS)).scalars()
    return {int(k.id): f"{k.nummer} {k.bezeichnung}" for k in zeilen}


def gewaehlte_kostenstelle(request: Request, kostenstellen: dict[int, str], ks: str) -> int | None:
    """Zuerst die Wahl in der Anfrage, dann die zuletzt gewählte im Cookie, sonst die erste."""
    for kandidat in (ks, request.cookies.get(COOKIE_KS, "")):
        if kandidat.isdigit() and int(kandidat) in kostenstellen:
            return int(kandidat)
    return next(iter(kostenstellen), None)


def _angekuendigt(sitzung: Sitzung, ks: int) -> list[dict[str, Any]]:
    mid = sitzung.kontext.mandant_id
    zeilen = sitzung.db.execute(
        select(m.Transfer, m.Stueck).join(m.Stueck, m.Stueck.id == m.Transfer.stueck_id).where(
            m.Transfer.mandant_id == mid, m.Transfer.status == "angekuendigt", m.Transfer.nach_kostenstelle_id == ks)
        .order_by(m.Transfer.abgang_am, m.Transfer.id).limit(HOECHSTENS)).all()
    von = sicht.kostenstellen_namen(sitzung, {int(x.von_kostenstelle_id) for x, _ in zeilen if x.von_kostenstelle_id is not None})
    return [{"id": int(x.id), "stueck_id": int(s.id), "nummer": s.inventarnummer, "bezeichnung": s.bezeichnung, "art": s.art,
             "menge": int(x.menge), "von": von.get(int(x.von_kostenstelle_id), "") if x.von_kostenstelle_id else "", "abgang_am": x.abgang_am}
            for x, s in zeilen]


def _vor_ort(sitzung: Sitzung, ks: int) -> list[dict[str, Any]]:
    zeilen = sitzung.db.execute(
        sitzung.abfrage(m.Standort).where(m.Standort.bis.is_(None), m.Standort.kostenstelle_id == ks)
        .order_by(m.Standort.stueck_id).limit(HOECHSTENS)).scalars().all()
    stuecke = {int(s.id): s for s in sitzung.db.execute(
        sicht.stuecke(sitzung).where(m.Stueck.id.in_([int(o.stueck_id) for o in zeilen]))).scalars()} if zeilen else {}
    return [{"stueck_id": int(o.stueck_id), "nummer": stuecke[int(o.stueck_id)].inventarnummer, "bezeichnung": stuecke[int(o.stueck_id)].bezeichnung,
             "menge": int(o.menge), "seit": o.von, "hat_zaehler": stuecke[int(o.stueck_id)].zaehler_einheit is not None,
             "status": stuecke[int(o.stueck_id)].status}
            for o in zeilen if int(o.stueck_id) in stuecke]


@router.get("/inventar/hier", response_class=HTMLResponse)
def hier(
    request: Request, ks: str = "", fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "scannen"), ("inventar", "sehen"))),
) -> HTMLResponse:
    kostenstellen = meine_kostenstellen(sitzung)
    gewaehlt = gewaehlte_kostenstelle(request, kostenstellen, ks)
    darf = rechte.darf_alle(sitzung, gewaehlt)
    antwort = gemeinsam.seite(
        request, sitzung, "inventar_hier.html", aktiv="inventar_hier", kostenstellen=list(kostenstellen.items()), gewaehlt=gewaehlt,
        angekuendigt=[] if gewaehlt is None else _angekuendigt(sitzung, gewaehlt),
        vor_ort=[] if gewaehlt is None else _vor_ort(sitzung, gewaehlt), buchung=helfer.neuer_schluessel(),
        fertig=fertig if fertig in ("abgang", "eingang", "zurueck", "scan", "zaehlerstand", "meldung") else "", **darf)
    if gewaehlt is not None:
        antwort.set_cookie(COOKIE_KS, str(gewaehlt), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 90)
    return antwort


@router.get("/inventar/scannen", response_class=HTMLResponse)
def scannen(
    request: Request, ks: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "scannen")),
) -> HTMLResponse:
    kostenstellen = meine_kostenstellen(sitzung)
    gewaehlt = gewaehlte_kostenstelle(request, kostenstellen, ks)
    return gemeinsam.seite(request, sitzung, "inventar_scannen.html", aktiv="inventar_hier", kostenstellen=list(kostenstellen.items()),
                           gewaehlt=gewaehlt, **rechte.darf_alle(sitzung, gewaehlt))
