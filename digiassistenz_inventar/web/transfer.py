"""Buchen: Abgang, Eingang (auch teilweise), „ist hier“ per Scan und Zurückziehen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..dienstlogik import liste, stueckseite, transfer
from . import helfer
from .stueck import _text, formular

router = APIRouter()
WEG = "/inventar/transfer"


def _weiter(request: Request, f: dict[str, Any], stueck_id: int, fertig: str) -> HTMLResponse:
    """Zurück dorthin, wo gebucht wurde: auf die Hier-Seite oder die Stück-Seite — mit Vermerk ✓."""
    if _text(f, "weiter") == "hier":
        return gemeinsam.umleiten(f"/inventar/hier?fertig={fertig}", request)
    return gemeinsam.umleiten(f"/inventar/stueck/{stueck_id}?fertig={fertig}", request)


def _transfer(sitzung: Sitzung, transfer_id: int) -> tuple[m.Transfer, m.Stueck]:
    """Der Transfer samt Stück — nur, wenn die Sitzung das Stück sehen darf (sonst „kein Recht“, N7)."""
    zeile = sitzung.db.execute(select(m.Transfer).where(
        m.Transfer.mandant_id == sitzung.kontext.mandant_id, m.Transfer.id == transfer_id)).scalar_one_or_none()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "sehen")
    return zeile, stueckseite.holen(sitzung, int(zeile.stueck_id))


@router.post(WEG + "/abgang", response_class=HTMLResponse)
def abgang(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "buchen")),
) -> HTMLResponse:
    stueck_id = helfer.ganzzahl(_text(f, "stueck_id"), 0) or 0
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        nach = liste.kostenstelle_id(sitzung, _text(f, "nach"))
        if nach is None:
            raise ValueError("web.kostenstelle_fehlt")
        transfer.abgang_buchen(
            sitzung, zeile.inventarnummer, helfer.ganzzahl(_text(f, "von"), 0) or 0, nach, helfer.ganzzahl(_text(f, "menge"), 1) or 1,
            _text(f, "eintrag_schluessel"), _text(f, "grund"), "web")
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _weiter(request, f, stueck_id, "abgang")


@router.post(WEG + "/scan", response_class=HTMLResponse)
def scan(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "scannen")),
) -> HTMLResponse:
    stueck_id = helfer.ganzzahl(_text(f, "stueck_id"), 0) or 0
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        transfer.scan_ist_hier(sitzung, zeile.inventarnummer, helfer.ganzzahl(_text(f, "kostenstelle"), 0) or 0,
                               _text(f, "eintrag_schluessel"), None, "handy" if _text(f, "art") == "kamera" else "web")
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _weiter(request, f, stueck_id, "scan")


@router.post(WEG + "/{transfer_id}/eingang", response_class=HTMLResponse)
def eingang(
    transfer_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "scannen")),
) -> HTMLResponse:
    zeile, stueck = _transfer(sitzung, transfer_id)
    menge = helfer.ganzzahl(_text(f, "menge"))
    try:
        transfer.eingang_bestaetigen(sitzung, stueck.inventarnummer, zeile.eintrag_schluessel,
                                     menge if stueck.art == "menge" else None, _text(f, "eingang_schluessel") or None, "web")
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _weiter(request, f, int(stueck.id), "eingang")


@router.post(WEG + "/{transfer_id}/zurueck", response_class=HTMLResponse)
def zurueck(
    transfer_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "buchen")),
) -> HTMLResponse:
    zeile, stueck = _transfer(sitzung, transfer_id)
    try:
        transfer.zurueckziehen(sitzung, stueck.inventarnummer, zeile.eintrag_schluessel, _text(f, "grund"), "web")
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _weiter(request, f, int(stueck.id), "zurueck")
