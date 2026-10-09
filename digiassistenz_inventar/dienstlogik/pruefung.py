"""Prüfung eintragen — mit Nachweis-Datei (SHA-256 im Datensatz, unveränderlich), Recht `pruefen`."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Mandant, protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import dateien
from .. import modelle as m
from ..rein import pruefung as rein
from . import pruefstand as staende
from .transfer import finde_stueck


def eintragen(
    sitzung: Any, inventarnummer: str, pruefart: str, durchgefuehrt_am: dt.date, ergebnis: str, durchfuehrung: str = "intern",
    pruefer_text: str = "", zaehlerstand: Decimal | None = None, bemerkung: str = "", nachweis: tuple[str, bytes] | None = None,
    arbeitsordner: Path | None = None, quelle: str = "web",
) -> m.Pruefung:
    if not sitzung.darf("inventar", "pruefen"):
        raise gemeinsam.KeinRecht("inventar", "pruefen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    zeile = finde_stueck(sitzung, inventarnummer, "pruefen")
    art = db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid, m.Pruefart.schluessel == pruefart)).scalar_one_or_none()
    if art is None:
        raise ValueError("pruefung.pruefart_unbekannt")
    if durchfuehrung not in m.PRUEF_DURCHFUEHRUNG:
        raise ValueError("pruefung.durchfuehrung_unbekannt")
    zu = next((z for z in _zuordnungen(sitzung, zeile) if z.pruefart == pruefart), None)
    if zu is None:
        raise ValueError("pruefung.nicht_zugeordnet")
    folge = rein.eintragen(zu, durchgefuehrt_am, ergebnis, zeit.heute(), zaehlerstand)
    pfad = pruefsumme = None
    if nachweis is not None:
        if arbeitsordner is None:
            raise ValueError("pruefung.arbeitsordner_fehlt")
        ordnername = db.execute(select(Mandant.ordnername).where(Mandant.id == mid)).scalar_one()
        ziel, pruefsumme = dateien.speichern(
            dateien.stammordner(arbeitsordner, ordnername, zeile.inventarnummer, "pruefungen"), nachweis[0], nachweis[1])
        pfad = str(ziel.relative_to(arbeitsordner))
    benutzer = None if sitzung.benutzer is None else int(sitzung.benutzer.id)
    satz = m.Pruefung(
        mandant_id=mid, stueck_id=zeile.id, pruefart_id=art.id, faellig_am=folge.naechste_am, durchgefuehrt_am=durchgefuehrt_am,
        ergebnis=ergebnis, durchfuehrung=durchfuehrung, pruefer_text=pruefer_text, pruefer_benutzer_id=benutzer,
        zaehlerstand=zaehlerstand, nachweis_pfad=pfad, nachweis_sha256=pruefsumme, bemerkung=bemerkung,
        naechste_am=folge.naechste_am, quelle=quelle, angelegt_von=benutzer)
    db.add(satz)
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.pruefung_eingetragen", objekt_typ="inventar.stueck",
                        objekt_id=int(zeile.id), neu_wert=f"{zeile.inventarnummer}: {pruefart} {ergebnis}, nächste {folge.naechste_am}",
                        benutzer_id=benutzer)
    return satz


def _zuordnungen(sitzung: Any, stueck: m.Stueck) -> list[rein.Zuordnung]:
    return staende.zuordnungen(sitzung.db, sitzung.kontext.mandant_id, [stueck]).get(stueck.inventarnummer, [])
