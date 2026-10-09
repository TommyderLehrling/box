"""Die Dienste `bestand` und `stueck` — Vertrag wörtlich `02_SCHNITTSTELLEN.md` (nur lesend, nur einfache Werte).

Rechte filtert der Anbieter über die Sitzung: `kostenstellen_fuer("inventar", "sehen")`. Kein Recht heißt leeres
Ergebnis bzw. `None`, nie ein Fehler. Preise, Kosten und Personen stehen nicht im Ergebnis.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from digiassistenz_kern import zeit
from digiassistenz_kern.texte import t

from . import modelle as m
from .dienstlogik import laden, pruefstand, sicht
from .rein import bestand as rein_bestand
from .rein.nummernformat import normalisiere

def stueck_infos(db: Session, sitzung: Any, stuecke: list[m.Stueck], heute: dt.date) -> dict[str, rein_bestand.StueckInfo]:
    mid = sitzung.kontext.mandant_id
    gruppen = {int(g.id): g for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    staende = pruefstand.staende(db, mid, stuecke, heute)
    return {
        s.inventarnummer: rein_bestand.StueckInfo(
            s.inventarnummer, s.bezeichnung, gruppen[int(s.gruppe_id)].schluessel, gruppen[int(s.gruppe_id)].bezeichnung,
            s.art, s.status, any(x.ampel == "rot" for x in staende.get(s.inventarnummer, [])), s.seriennummer, s.hersteller)
        for s in stuecke
    }


def _hinweis(zeilen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for z in zeilen:
        if z["hinweis"]:
            z["hinweis"] = t("inventar.code." + z["hinweis"])
    return zeilen


def bestand(db: Session, sitzung: Any, kostenstelle_id: int, tag: dt.date | None = None,
            gruppe: str | None = None) -> list[dict[str, Any]]:
    """Was steht am Tag X auf Kostenstelle Y — `[]` ohne Recht auf diese Kostenstelle."""
    erlaubt = sicht.erlaubte_kostenstellen(sitzung)
    if erlaubt is not None and kostenstelle_id not in erlaubt:
        return []
    heute = zeit.heute()
    kandidaten = list(db.execute(sicht.stuecke(sitzung)).scalars())
    infos = stueck_infos(db, sitzung, kandidaten, heute)
    zustaende = laden.lade_zustaende(db, sitzung.kontext.mandant_id, kandidaten)
    return _hinweis(rein_bestand.bestand(
        [(infos[n], zustaende[n]) for n in infos], kostenstelle_id, tag, heute, gruppe))


def stueck(db: Session, sitzung: Any, inventarnummer: str | None = None, seriennummer: str | None = None) -> dict[str, Any] | None:
    """Eine Nummer prüfen — `None`: unbekannt, nicht im Bestand oder kein Recht."""
    kandidaten = list(db.execute(sicht.stuecke(sitzung)).scalars())
    infos = stueck_infos(db, sitzung, kandidaten, zeit.heute())
    gesucht = inventarnummer if inventarnummer is not None else seriennummer or ""
    nach = "inventarnummer" if inventarnummer is not None else "seriennummer"
    info = rein_bestand.finde_stueck(infos.values(), gesucht, nach)
    if info is None or not normalisiere(gesucht):
        return None
    zeile = next(s for s in kandidaten if s.inventarnummer == info.inventarnummer)
    z = laden.lade_zustaende(db, sitzung.kontext.mandant_id, [zeile])[info.inventarnummer]
    return rein_bestand.stueck_auskunft(info, z)


#: AP-K2: in Modulbeschreibung.dienste eintragen, sobald der Kern das Feld hat (Steckbrief 11: noch nicht vorhanden)
DIENSTE = (("bestand", 1, bestand), ("stueck", 1, stueck))
