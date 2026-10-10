"""Prüfungen: die Fällig-Liste, „Prüfung eintragen“ mit Nachweis, Prüfarten je Stück und der Nachweis zum Ansehen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.web import gemeinsam, wahlfeld

from .. import dateien
from .. import modelle as m
from .. import rechte
from ..dienstlogik import faellig, liste, pruefung, stueckseite
from . import helfer
from .stueck import _text, formular

router = APIRouter()


def _nachweis(f: dict[str, Any]) -> tuple[str, bytes] | None:
    wert = f.get("nachweis")
    if wert is None or isinstance(wert, str) or not getattr(wert, "filename", ""):
        return None
    inhalt = wert.file.read(dateien.NACHWEIS_HOECHSTENS + 1)
    return (wert.filename, inhalt) if inhalt else None


_zahl = helfer.dezimal


@router.get("/inventar/faellig", response_class=HTMLResponse)
def faellig_seite(
    request: Request, pruefart: str = "", kostenstelle: str = "", gruppe: str = "", fertig: str = "", stand: str = "", letzter: str = "",
    sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "pruefen"), ("inventar", "werkstatt"))),
) -> HTMLResponse:
    f = faellig.Filter(pruefart=pruefart.strip(), kostenstelle=kostenstelle.strip(), gruppe=gruppe.strip())
    mid = sitzung.kontext.mandant_id
    arten = [(p.schluessel, p.bezeichnung) for p in sitzung.db.execute(
        select(m.Pruefart).where(m.Pruefart.mandant_id == mid, m.Pruefart.aktiv).order_by(m.Pruefart.bezeichnung)).scalars()]
    wahl = wahlfeld.kostenstelle(sitzung, feld="kostenstelle", modul="inventar", aktion="sehen", gewaehlt=f.kostenstelle,
                                 leer="inventar.alle", leer_wert="", beschriftung="inventar.feld.kostenstelle", kennung="wahl-faellig-ks")
    return gemeinsam.seite(
        request, sitzung, "inventar_faellig.html", aktiv="inventar_faellig", filter=f, uebersicht=faellig.uebersicht(sitzung, f),
        arten=arten, gruppen=liste.gruppen_auswahl(sitzung), wahl_ks=wahl, fertig=fertig == "pruefung",
        zaehler_hinweis=helfer.zaehler_hinweis(stand, letzter) if fertig == "pruefung" else "", **rechte.darf_alle(sitzung))


@router.post("/inventar/stueck/{stueck_id}/pruefung", response_class=HTMLResponse)
def pruefung_eintragen(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pruefen")),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        datum = helfer.datum(_text(f, "durchgefuehrt_am"))
        if datum is None:
            raise ValueError("pruefung.datum_fehlt")
        satz = pruefung.eintragen(
            sitzung, zeile.inventarnummer, _text(f, "pruefart"), datum, _text(f, "ergebnis"), _text(f, "durchfuehrung") or "intern",
            pruefer_text=_text(f, "pruefer_text"), zaehlerstand=_zahl(_text(f, "zaehlerstand")), bemerkung=_text(f, "bemerkung"),
            nachweis=_nachweis(f), arbeitsordner=helfer.arbeitsordner(), quelle="web",
            pruefer_benutzer_id=None if _text(f, "pruefer_text") else helfer.ganzzahl(_text(f, "pruefer_benutzer_id")),  # ein Name geht vor
            pruefer_lieferant_id=helfer.ganzzahl(_text(f, "pruefer_lieferant_id")))
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    unter = getattr(satz, "zaehler_unter", None)
    hinweis = "" if unter is None or satz.zaehlerstand is None else f"&stand={helfer.zahl_text(satz.zaehlerstand)}&letzter={helfer.zahl_text(unter)}"
    if _text(f, "weiter") == "faellig":
        return gemeinsam.umleiten(f"/inventar/faellig?fertig=pruefung{hinweis}", request)
    return gemeinsam.umleiten(f"/inventar/stueck/{stueck_id}?fertig=pruefung{hinweis}", request)


@router.post("/inventar/stueck/{stueck_id}/pruefart", response_class=HTMLResponse)
def pruefart_setzen(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        pruefung.pruefart_setzen(sitzung, zeile.inventarnummer, _text(f, "pruefart"), _text(f, "intervall_monate"), "aktiv" in f)
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return gemeinsam.umleiten(f"/inventar/stueck/{stueck_id}?fertig=pruefart", request)


@router.get("/inventar/pruefung/{pruefung_id}/nachweis")
def nachweis(
    pruefung_id: int, sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> Response:
    """Der Nachweis zum Ansehen: nur für Stücke, die man sehen darf; die Prüfsumme muss zum Datensatz passen."""
    try:
        name, inhalt = pruefung.nachweis_lesen(sitzung, pruefung_id, helfer.arbeitsordner())
    except ValueError as fehler:
        return helfer.fehlerteil(fehler)
    typ = "application/pdf" if inhalt.startswith(b"%PDF-") else "image/png" if inhalt.startswith(b"\x89PNG") else "image/jpeg"
    # inline: der Prüfer will ansehen (Browser zeigt PDF und Bilder direkt); speichern geht weiter. Fester Typ und nosniff bleiben.
    return Response(inhalt, media_type=typ, headers={"Content-Disposition": f'inline; filename="{name}"', "X-Content-Type-Options": "nosniff"})
