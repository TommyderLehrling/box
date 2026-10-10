"""Die Kosten-Seite (G5, Recht `kosten_sehen`): je Kostenstelle, je Stück, Miete gegen eigen und die CSV-Auszüge."""

from __future__ import annotations

import calendar
import datetime as dt
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.web import gemeinsam, wahlfeld

from .. import modelle as m
from .. import rechte
from ..dienstlogik import kostenrechnung, liste, sicht, zaehler
from . import helfer
from .stueck import _text, formular

router = APIRouter()
WEG = "/inventar/kosten"
FERTIG = ("export",)


def zeitraum(von: str, bis: str, heute: dt.date) -> tuple[dt.date, dt.date, bool]:
    """Der gewählte Zeitraum; ohne Angabe der laufende Monat. Das dritte Ergebnis sagt, ob eine Angabe ungültig war und ersetzt wurde."""
    standard = (heute.replace(day=1), heute.replace(day=calendar.monthrange(heute.year, heute.month)[1]))
    try:
        a, b = helfer.datum(von) or standard[0], helfer.datum(bis) or standard[1]
    except ValueError:
        return standard[0], standard[1], True
    return (a, b, False) if a <= b else (standard[0], standard[1], True)


def _filterweg(von: dt.date, bis: dt.date, kostenstelle: str, gruppe: str, vergleich: str) -> str:
    werte = {"von": von.isoformat(), "bis": bis.isoformat(), "kostenstelle": kostenstelle, "gruppe": gruppe, "vergleich": vergleich}
    return urlencode({k: v for k, v in werte.items() if v})


@router.get(WEG, response_class=HTMLResponse)
def kosten_seite(
    request: Request, von: str = "", bis: str = "", kostenstelle: str = "", gruppe: str = "", vergleich: str = "", stueck: str = "", fertig: str = "",
    sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "kosten_sehen")),
) -> HTMLResponse:
    heute = helfer.heute()
    anfang, ende, ersetzt = zeitraum(von, bis, heute)
    kostenstelle, gruppe, vergleich = kostenstelle.strip(), gruppe.strip(), vergleich.strip()
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    fehler = ""
    miete = None
    try:
        miete = kostenrechnung.miete_gegen_eigen(sitzung, anfang, ende, vergleich)
    except ValueError as ursache:
        sitzung.db.rollback()
        fehler = helfer.fehler_text(ursache)
    vorhaltung = kostenrechnung.vorhaltung_je_kostenstelle(sitzung, anfang, ende)
    stuecke, gesamt = kostenrechnung.stuecke_mit_filter(sitzung, kostenstelle, gruppe)
    rw = kostenrechnung.rechenwerte(db, mid)
    zeilen = kostenrechnung.stueck_kosten(db, mid, stuecke, heute, rw)
    summen = [{"name": vorhaltung.namen.get(int(s.schluessel), s.schluessel), "tage": s.tage, "betrag": s.betrag_vorhaltung}
              for s in vorhaltung.verrechnung.je_kostenstelle]
    einzeln = [{"ks": vorhaltung.namen.get(z.kostenstelle, str(z.kostenstelle)), "nummer": z.inventarnummer,
                "bezeichnung": vorhaltung.bezeichnungen.get(z.inventarnummer, ""), "tage": z.tage, "betrag": z.betrag_vorhaltung}
               for z in vorhaltung.verrechnung.zeilen]
    verlauf, gewaehlt = [], None
    if stueck.isdigit():
        gewaehlt = sitzung.db.execute(sicht.stuecke(sitzung, "kosten_sehen").where(m.Stueck.id == int(stueck))).scalars().first()
        if gewaehlt is not None:
            verlauf = zaehler.verlauf(sitzung, int(gewaehlt.id))
    wahl = wahlfeld.kostenstelle(sitzung, feld="kostenstelle", modul="inventar", aktion="kosten_sehen", gewaehlt=kostenstelle, leer="inventar.alle",
                                 leer_wert="", beschriftung="inventar.feld.kostenstelle", kennung="wahl-kosten-ks")
    return gemeinsam.seite(
        request, sitzung, "inventar_kosten.html", aktiv="inventar_kosten", von=anfang.isoformat(), bis=ende.isoformat(), zeitraum_ersetzt=ersetzt,
        kostenstelle=kostenstelle, gruppe=gruppe, vergleich=vergleich, gruppen=liste.gruppen_auswahl(sitzung), wahl_ks=wahl, summen=summen,
        einzeln=einzeln, ohne_satz=vorhaltung.ohne_satz, werktage=rw.werktage, tage_je_monat=rw.tage_je_monat, stuecke=zeilen, stuecke_gesamt=gesamt,
        miete=miete, miete_fehler=fehler, verlauf=verlauf, gewaehlt=gewaehlt, exporte=kostenrechnung.exportierte_dateien(sitzung, helfer.arbeitsordner()),
        fertig=fertig if fertig in FERTIG else "", filterweg=_filterweg(anfang, ende, kostenstelle, gruppe, vergleich), **rechte.darf_alle(sitzung))


@router.post(WEG + "/export", response_class=HTMLResponse)
def exportieren(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "kosten_sehen")),
) -> HTMLResponse:
    """Schreibt die CSV eines Blocks nach `export/`; zeigt danach wieder die Seite mit der Liste der Dateien."""
    anfang, ende, _ersetzt = zeitraum(_text(f, "von"), _text(f, "bis"), helfer.heute())
    block = _text(f, "block")
    try:
        kostenrechnung.exportieren(sitzung, block, anfang, ende, helfer.arbeitsordner(), _text(f, "kostenstelle"), _text(f, "gruppe"), _text(f, "vergleich"))
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    weg = _filterweg(anfang, ende, _text(f, "kostenstelle"), _text(f, "gruppe"), _text(f, "vergleich"))
    return gemeinsam.umleiten(f"{WEG}?fertig=export&{weg}#exporte", request)


__all__ = ["router"]
