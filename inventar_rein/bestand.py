"""Die Dienste bestand und stueck des Inventars als reine Funktionen (Rechte filtert VSC vorher)."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from .nummernformat import normalisiere
from .stueck_status import hinweis as status_hinweis
from .stueck_status import im_bestand
from .transfer import Zustand


@dataclass(frozen=True)
class StueckInfo:
    inventarnummer: str
    bezeichnung: str
    gruppe: str
    gruppe_text: str
    art: str
    status: str
    pruefung_ueberfaellig: bool = False
    seriennummer: str = ""
    hersteller: str = ""


def finde_stueck(
    stuecke: Iterable[StueckInfo], eingabe: str, nach: Literal["inventarnummer", "seriennummer"] = "inventarnummer"
) -> StueckInfo | None:
    """Sucht eine getippte Nummer: getrimmt und unabhaengig von Gross- und Kleinschreibung.

    Bei nach="seriennummer" gilt die Hersteller-Seriennummer; leere Seriennummern treffen nie.
    """
    if nach not in ("inventarnummer", "seriennummer"):
        raise ValueError("bestand.suche_unbekannt")
    gesucht = normalisiere(eingabe)
    if not gesucht:
        return None
    return next((s for s in stuecke if normalisiere(getattr(s, nach)) == gesucht), None)


def _hinweis(info: StueckInfo) -> str:
    return status_hinweis(info.status) or ("bestand.hinweis_pruefung_ueberfaellig" if info.pruefung_ueberfaellig else "")


def bestand(
    stuecke: Iterable[tuple[StueckInfo, Zustand]], kostenstelle: int, tag: date | None, heute: date,
    gruppe: str | None = None,
) -> list[dict[str, Any]]:
    """Was steht am Tag auf der Kostenstelle: angekuendigt nur fuer heute, Mengen als Summe, ohne Endzustaende."""
    stichtag = tag or heute
    zeilen: list[dict[str, Any]] = []
    for info, z in stuecke:
        if gruppe is not None and info.gruppe != gruppe:
            continue
        if not im_bestand(info.status):
            continue
        hier = [s for s in z.standorte if s.kostenstelle == kostenstelle and s.von.date() <= stichtag
                and (s.bis is None or stichtag < s.bis.date())]
        angekuendigt = [t for t in z.transfers if stichtag == heute and t.status == "angekuendigt"
                        and t.nach_kostenstelle == kostenstelle]
        for status, mengen, seit in (
            ("vor_ort", [s.menge for s in hier], [s.von.date() for s in hier]),
            ("angekuendigt", [t.menge for t in angekuendigt],
             [t.abgang_am.date() for t in angekuendigt if t.abgang_am is not None]),
        ):
            if not mengen:
                continue
            zeilen.append({
                "inventarnummer": info.inventarnummer, "bezeichnung": info.bezeichnung, "gruppe": info.gruppe,
                "gruppe_text": info.gruppe_text, "art": info.art,
                "menge": sum(mengen) if info.art == "menge" else 1,
                "seit": min(seit) if seit else None, "status": status, "hinweis": _hinweis(info),
            })
    return sorted(zeilen, key=lambda r: (r["gruppe_text"], r["bezeichnung"], r["inventarnummer"], r["status"]))


def stueck_auskunft(info: StueckInfo, z: Zustand) -> dict[str, Any] | None:
    """Antwort des Dienstes stueck: None, wenn das Stueck in einem Endzustand ist; sonst Stammangaben und Standort."""
    if not im_bestand(info.status):
        return None
    offen = sorted((s for s in z.standorte if s.bis is None), key=lambda s: (-s.menge, s.kostenstelle))
    standort = offen[0] if offen else None
    return {
        "inventarnummer": info.inventarnummer, "bezeichnung": info.bezeichnung, "gruppe": info.gruppe,
        "gruppe_text": info.gruppe_text, "art": info.art, "status": info.status,
        "seriennummer": info.seriennummer, "hersteller": info.hersteller,
        "standort_kostenstelle_id": standort.kostenstelle if standort else None,
        "standort_seit": standort.von.date() if standort else None,
    }
