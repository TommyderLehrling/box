"""Die Inventarliste, ihr HTMX-Teil, das QR-Ziel und die Fällig-Seite (L13 füllt sie)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func

from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import gemeinsam, wahlfeld

from .. import kacheln as modul_kacheln
from .. import modelle as m
from .. import rechte
from ..dienstlogik import liste
from ..dienstlogik import sicht
from ..rein.nummernformat import normalisiere

router = APIRouter()
LISTE = "inventar_liste"


def _filter(q: str, status: str, gruppe: str, kostenstelle: str, angekuendigt: str, faellig: str) -> liste.Filter:
    return liste.Filter(q=q.strip(), status=status, gruppe=gruppe, kostenstelle=kostenstelle.strip(),
                        angekuendigt=angekuendigt == "1", faellig=faellig == "1")


def _teil_werte(request: Request, sitzung: Sitzung, f: liste.Filter, seite: int, sortieren: str, richtung: str) -> dict[str, Any]:
    if sortieren in liste.SORTIERBAR:
        spalte, absteigend = sortieren, richtung == "ab"
    else:
        spalte, absteigend = gemeinsam.sortierung_lesen(request, LISTE, liste.SORTIERBAR, "nummer", standard_absteigend=False)
    ergebnis = liste.seite(sitzung, f, spalte, absteigend, seite)
    grundweg = "/inventar?" + f.als_weg() + ("&" if f.als_weg() else "") + "ansicht=liste"
    return dict(seite_inhalt=ergebnis, spalte=spalte, absteigend=absteigend, grundweg=grundweg, filterweg=f.als_weg())


@router.get("/inventar", response_class=HTMLResponse)
def uebersicht(
    request: Request, q: str = "", status: str = "", gruppe: str = "", kostenstelle: str = "", angekuendigt: str = "",
    faellig: str = "", ansicht: str = "liste", seite: int = 1, sortieren: str = "", richtung: str = "auf",
    sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> HTMLResponse:
    f = _filter(q, status, gruppe, kostenstelle, angekuendigt, faellig)
    ordner = ansicht == "ordner"
    werte = _teil_werte(request, sitzung, f, seite, sortieren, richtung) if not ordner else dict(
        seite_inhalt=None, spalte="nummer", absteigend=False, grundweg="", filterweg=f.als_weg())
    karten = [{"text": k.text_schluessel, "zahl": k.zahl, "weg": k.weg} for k in modul_kacheln.kacheln(sitzung.db, sitzung)]
    wahl = wahlfeld.kostenstelle(sitzung, feld="kostenstelle", modul="inventar", aktion="sehen", gewaehlt=f.kostenstelle,
                                 leer="inventar.alle", leer_wert="", beschriftung="inventar.feld.kostenstelle", kennung="wahl-filter-ks")
    antwort = gemeinsam.seite(
        request, sitzung, "inventar_uebersicht.html", aktiv="inventar", filter=f, ordner=liste.ordner(sitzung, f) if ordner else [],
        ansicht="ordner" if ordner else "liste", kacheln=karten, gruppen=liste.gruppen_auswahl(sitzung), wahl_ks=wahl,
        stati=list(m.STATUS), **werte, **rechte.darf_alle(sitzung))
    if not ordner:
        gemeinsam.sortierung_merken(antwort, LISTE, werte["spalte"], werte["absteigend"])
    return antwort


@router.get("/inventar/liste", response_class=HTMLResponse)
def liste_teil(
    request: Request, q: str = "", status: str = "", gruppe: str = "", kostenstelle: str = "", angekuendigt: str = "",
    faellig: str = "", seite: int = 1, sortieren: str = "", richtung: str = "auf",
    sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> HTMLResponse:
    """Nur die Tabelle samt Seitenwahl — das holt HTMX beim Tippen und beim Sortieren."""
    f = _filter(q, status, gruppe, kostenstelle, angekuendigt, faellig)
    werte = _teil_werte(request, sitzung, f, seite, sortieren, richtung)
    antwort = gemeinsam.teil("teil_inventar_liste.html", filter=f, **werte)
    return gemeinsam.sortierung_merken(antwort, LISTE, werte["spalte"], werte["absteigend"])


def _ziel(sitzung: Sitzung, text: str, ks: str) -> RedirectResponse:
    nummer = normalisiere(text)
    zeile = sitzung.db.execute(sicht.stuecke(sitzung).where(func.upper(m.Stueck.inventarnummer) == nummer)).scalars().first()
    if zeile is None:
        zeile = sitzung.db.execute(sicht.stuecke(sitzung).where(
            func.upper(m.Stueck.seriennummer) == nummer).order_by(m.Stueck.inventarnummer)).scalars().first()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "sehen")
    return RedirectResponse(f"/inventar/stueck/{int(zeile.id)}" + (f"?ks={ks}" if ks.isdigit() else ""), status_code=303)


@router.get("/inventar/s")
def scan_eingabe(
    nummer: str = "", ks: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> RedirectResponse:
    """Der Rückfall ohne Skript: das Eingabefeld der Scan-Seite schickt die Nummer hierher."""
    return _ziel(sitzung, nummer, ks)


@router.get("/inventar/s/{inventarnummer}")
def qr_ziel(
    inventarnummer: str, ks: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> RedirectResponse:
    """Das Ziel des QR-Codes: Nummer (oder Seriennummer) → Stück-Seite; was es nicht gibt, ist „kein Recht“ (N7)."""
    return _ziel(sitzung, inventarnummer, ks)


@router.get("/inventar/faellig", response_class=HTMLResponse)
def faellig_seite(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "pruefen"), ("inventar", "werkstatt"))),
) -> HTMLResponse:
    return gemeinsam.seite(request, sitzung, "inventar_faellig.html", aktiv="inventar_faellig", hinweis=t("inventar.kommt_mit_g3"))
