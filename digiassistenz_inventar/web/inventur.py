"""Verwaltung → Inventar → Inventur (E10): Stichtag setzen, gesehen / nicht gesehen je Kostenstelle, Vermisst vorschlagen, CSV."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import gemeinsam

from .. import rechte
from ..dienstlogik import inventur, kostenrechnung
from . import helfer
from .stueck import _text, formular

router = APIRouter()
WEG = "/inventar/verwaltung/inventur"
FERTIG = ("stichtag", "vermisst", "export")
_RECHT = gemeinsam.verlangt_eines(("inventar", "stilllegen"), ("inventar", "einstellen"))


@router.get(WEG, response_class=HTMLResponse)
def inventur_seite(
    request: Request, fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(_RECHT),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    tag = inventur.stichtag(sitzung.db, mid)
    krumen = [(t("inventar.menue_verwaltung"), "/inventar/verwaltung"), (t("inventar.verwaltung.inventur"), "")]
    return gemeinsam.seite(
        request, sitzung, "inventar_verwaltung_inventur.html", aktiv="verwaltung", brotkrumen=krumen, stichtag=tag,
        bericht=inventur.bericht(sitzung), fertig=fertig if fertig in FERTIG else "", heute_iso=helfer.heute().isoformat(),
        exporte=kostenrechnung.exportierte_dateien(sitzung, helfer.arbeitsordner()), **rechte.darf_alle(sitzung))


@router.post(WEG, response_class=HTMLResponse)
def inventur_aendern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(_RECHT),
) -> HTMLResponse:
    aktion = _text(f, "aktion")
    try:
        if aktion == "stichtag":
            inventur.stichtag_setzen(sitzung, helfer.datum(_text(f, "stichtag")))
            fertig = "stichtag"
        elif aktion == "vermisst":
            inventur.als_vermisst_eintragen(sitzung, helfer.ganzzahl(_text(f, "stueck_id"), 0) or 0, _text(f, "grund"))
            fertig = "vermisst"
        elif aktion == "export":
            inventur.exportieren(sitzung, helfer.arbeitsordner())
            fertig = "export"
        else:
            raise ValueError("inventur.aktion_unbekannt")
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return gemeinsam.umleiten(f"{WEG}?fertig={fertig}", request)
