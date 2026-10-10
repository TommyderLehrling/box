"""Die Werkstatt: Posteingang der Meldungen, Reparatur-Vorgänge, Status `in_reparatur` und das Foto zur Meldung."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.web import gemeinsam, wahlfeld

from .. import modelle as m
from .. import rechte
from ..dienstlogik import sicht, werkstatt
from . import helfer
from .stueck import _text, formular

router = APIRouter()
WEG = "/inventar/werkstatt"
FERTIG = ("angenommen", "in_arbeit", "erledigt", "zurueckgezogen", "reparatur_angelegt", "reparatur_begonnen", "reparatur_abgeschlossen",
          "reparatur_zurueckgezogen", "reparatur_rechnung", "status_gesetzt", "status_aufgehoben")


def _ziel_meldung(sitzung: Sitzung, kennung: str) -> dict[str, Any] | None:
    """Die Meldung, zu der ein Reparatur-Dialog offen steht (aus `?neu_meldung=`)."""
    if not kennung.isdigit():
        return None
    z = sitzung.db.execute(sitzung.abfrage(m.Meldung).where(m.Meldung.id == int(kennung))).scalar_one_or_none()
    s = None if z is None else sitzung.db.execute(sicht.stuecke(sitzung).where(m.Stueck.id == z.stueck_id)).scalars().first()
    return None if z is None or s is None else {"meldung_id": int(z.id), "stueck_id": int(s.id), "nummer": s.inventarnummer,
                                                 "bezeichnung": s.bezeichnung, "beschreibung": z.beschreibung}


def _ziel_stueck(sitzung: Sitzung, kennung: str) -> dict[str, Any] | None:
    if not kennung.isdigit():
        return None
    s = sitzung.db.execute(sicht.stuecke(sitzung).where(m.Stueck.id == int(kennung))).scalars().first()
    return None if s is None else {"meldung_id": 0, "stueck_id": int(s.id), "nummer": s.inventarnummer, "bezeichnung": s.bezeichnung, "beschreibung": ""}


@router.get(WEG, response_class=HTMLResponse)
def werkstatt_seite(
    request: Request, fertig: str = "", neu_meldung: str = "", neu_stueck: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "werkstatt")),
) -> HTMLResponse:
    ziel = _ziel_meldung(sitzung, neu_meldung) or _ziel_stueck(sitzung, neu_stueck)
    return gemeinsam.seite(
        request, sitzung, "inventar_werkstatt.html", aktiv="inventar_werkstatt", p=werkstatt.posteingang(sitzung),
        fertig=fertig if fertig in FERTIG else "", ziel=ziel, heute_iso=helfer.heute().isoformat(),
        wahl_lieferant=wahlfeld.lieferant(sitzung, feld="lieferant_id", leer="inventar.kein_lieferant", kennung="wahl-rep-lieferant"),
        **rechte.darf_alle(sitzung))


def _fertig(request: Request, schluessel: str) -> HTMLResponse:
    return gemeinsam.umleiten(f"{WEG}?fertig={schluessel}", request)


@router.post(WEG + "/meldung/{meldung_id}/weiter", response_class=HTMLResponse)
def meldung_weiter(
    meldung_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "werkstatt")),
) -> HTMLResponse:
    neu = _text(f, "neu")
    try:
        if neu not in werkstatt.MELDUNG_NEU:
            raise ValueError("meldung.status_unbekannt")
        werkstatt.meldung_weiter(sitzung, meldung_id, neu, _text(f, "rueckmeldung"), _text(f, "grund"))
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _fertig(request, neu)


@router.post(WEG + "/reparatur", response_class=HTMLResponse)
def reparatur_anlegen(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "werkstatt")),
) -> HTMLResponse:
    try:
        meldung_id = helfer.ganzzahl(_text(f, "meldung_id"), 0) or None
        stueck_id = helfer.ganzzahl(_text(f, "stueck_id"), 0) or 0
        nummer = None
        if meldung_id is None:
            nummer = sitzung.db.execute(sicht.stuecke(sitzung).where(m.Stueck.id == stueck_id)).scalars().first()
            nummer = None if nummer is None else nummer.inventarnummer
        werkstatt.reparatur_anlegen(
            sitzung, inventarnummer=nummer, meldung_id=meldung_id, durchfuehrung=_text(f, "durchfuehrung") or "intern",
            beschreibung=_text(f, "beschreibung"), lieferant_id=helfer.ganzzahl(_text(f, "lieferant_id")))
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _fertig(request, "reparatur_angelegt")


@router.post(WEG + "/reparatur/{reparatur_id}/weiter", response_class=HTMLResponse)
def reparatur_weiter(
    reparatur_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "werkstatt")),
) -> HTMLResponse:
    aktion = _text(f, "aktion")
    try:
        if aktion not in werkstatt.REPARATUR_AKTIONEN:
            raise ValueError("werkstatt.aktion_unbekannt")
        kosten = helfer.dezimal(_text(f, "kosten"))
        if aktion == "zurueckziehen":
            werkstatt.reparatur_zurueckziehen(sitzung, reparatur_id, _text(f, "grund"))
            return _fertig(request, "reparatur_zurueckgezogen")
        if aktion == "rechnung":
            if kosten is None:
                raise ValueError("reparatur.kosten_ungueltig")
            werkstatt.reparatur_rechnung(sitzung, reparatur_id, kosten)
            return _fertig(request, "reparatur_rechnung")
        am = helfer.datum(_text(f, "datum"))
        if am is None:
            raise ValueError("reparatur.datum_fehlt")
        if aktion == "beginnen":
            werkstatt.reparatur_beginnen(sitzung, reparatur_id, am, kosten)
            return _fertig(request, "reparatur_begonnen")
        werkstatt.reparatur_abschliessen(sitzung, reparatur_id, am, kosten, _text(f, "kosten_quelle") or "geschaetzt")
        return _fertig(request, "reparatur_abgeschlossen")
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)


@router.post(WEG + "/stueck/{stueck_id}/status", response_class=HTMLResponse)
def stueck_status(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "werkstatt")),
) -> HTMLResponse:
    setzen = _text(f, "setzen") == "1"
    try:
        werkstatt.in_reparatur_setzen(sitzung, stueck_id, setzen, _text(f, "grund"))
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _fertig(request, "status_gesetzt" if setzen else "status_aufgehoben")


@router.get("/inventar/meldung/{meldung_id}/foto")
def meldung_foto(
    meldung_id: int, sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> Response:
    """Das Foto zur Meldung zum Ansehen: nur für Meldungen, die man sehen darf; die Prüfsumme muss zum Datensatz passen."""
    try:
        name, inhalt = werkstatt.meldung_foto_lesen(sitzung, meldung_id, helfer.arbeitsordner())
    except ValueError as fehler:
        return helfer.fehlerteil(fehler)
    typ = "image/png" if inhalt.startswith(b"\x89PNG") else "image/jpeg"
    return Response(inhalt, media_type=typ, headers={"Content-Disposition": f'inline; filename="{name}"', "X-Content-Type-Options": "nosniff"})
