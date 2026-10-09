"""Übersicht, Hier und Fällig — die drei Seiten im Kopf (L10: Gerüst, L11/L12/L13 füllen sie)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import or_, select

from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import gemeinsam

from .. import kacheln as modul_kacheln
from .. import modelle as m
from .. import rechte
from ..dienstlogik import pruefstand, sicht
from ..rein.pruefung import gesamt_ampel

router = APIRouter()
SEITE = 100  # Zeilen je Seite (Auftrag 03, Abschnitt 5: seitenweise ab 200)
AMPEL = {"gruen": "✓", "gelb": "⚠", "rot": "✗", "unbekannt": "◌"}


def _liste(sitzung: Sitzung, q: str, seite: int) -> tuple[list[dict[str, Any]], bool]:
    db = sitzung.db
    abfrage = sicht.stuecke(sitzung)
    wort = " ".join(q.split())
    if wort:
        muster = "%" + wort.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        abfrage = abfrage.where(or_(
            m.Stueck.inventarnummer.ilike(muster, escape="\\"), m.Stueck.bezeichnung.ilike(muster, escape="\\"),
            m.Stueck.seriennummer.ilike(muster, escape="\\")))
    zeilen = list(db.execute(abfrage.order_by(m.Stueck.inventarnummer).offset((seite - 1) * SEITE).limit(SEITE + 1)).scalars())
    mehr = len(zeilen) > SEITE
    zeilen = zeilen[:SEITE]
    gruppen = {int(g.id): g.bezeichnung for g in db.execute(
        select(m.Gruppe).where(m.Gruppe.mandant_id == sitzung.kontext.mandant_id)).scalars()}
    orte = sicht.standorte_offen(sitzung, [int(z.id) for z in zeilen])
    namen = sicht.kostenstellen_namen(sitzung, {k for liste in orte.values() for k, _ in liste})
    staende = pruefstand.staende(db, sitzung.kontext.mandant_id, zeilen, _heute())
    return [{
        "id": int(z.id), "nummer": z.inventarnummer, "bezeichnung": z.bezeichnung, "gruppe": gruppen.get(int(z.gruppe_id), ""),
        "steht_auf": ", ".join(namen.get(k, "") for k, _ in orte.get(int(z.id), [])),
        "status": z.status, "ampel": AMPEL[gesamt_ampel(staende.get(z.inventarnummer, []))],
    } for z in zeilen], mehr


def _heute():  # Kern-Uhr, damit Prüfläufe die gestellte Zeit sehen
    from digiassistenz_kern import zeit

    return zeit.heute()


@router.get("/inventar", response_class=HTMLResponse)
def uebersicht(
    request: Request, q: str = "", seite: int = 1,
    sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> HTMLResponse:
    zeilen, mehr = _liste(sitzung, q, max(seite, 1))
    karten = [{"text": k.text_schluessel, "zahl": k.zahl, "weg": k.weg} for k in modul_kacheln.kacheln(sitzung.db, sitzung)]
    return gemeinsam.seite(request, sitzung, "inventar_uebersicht.html", aktiv="inventar", zeilen=zeilen, mehr=mehr,
                           seite_nr=max(seite, 1), q=q, kacheln=karten, **rechte.darf_alle(sitzung))


@router.get("/inventar/hier", response_class=HTMLResponse)
def hier(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "scannen"), ("inventar", "sehen"))),
) -> HTMLResponse:
    orte = sitzung.db.execute(
        sitzung.abfrage(m.Standort).where(m.Standort.bis.is_(None)).order_by(m.Standort.kostenstelle_id, m.Standort.stueck_id).limit(SEITE)
    ).scalars().all()
    nummern = {int(s.id): s.inventarnummer for s in sitzung.db.execute(
        sicht.stuecke(sitzung).where(m.Stueck.id.in_([int(o.stueck_id) for o in orte]))).scalars()} if orte else {}
    ks = sicht.kostenstellen_namen(sitzung, {int(o.kostenstelle_id) for o in orte})
    zeilen = [{"kostenstelle": ks.get(int(o.kostenstelle_id), ""), "nummer": nummern.get(int(o.stueck_id), ""), "menge": int(o.menge)}
              for o in orte if int(o.stueck_id) in nummern]
    return gemeinsam.seite(request, sitzung, "inventar_hier.html", aktiv="inventar_hier", zeilen=zeilen, **rechte.darf_alle(sitzung))


@router.get("/inventar/faellig", response_class=HTMLResponse)
def faellig(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "pruefen"), ("inventar", "werkstatt"))),
) -> HTMLResponse:
    return gemeinsam.seite(request, sitzung, "inventar_faellig.html", aktiv="inventar_faellig", hinweis=t("inventar.kommt_mit_g3"))
