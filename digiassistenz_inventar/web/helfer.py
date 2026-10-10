"""Kleinigkeiten, die mehrere Seiten brauchen: Fehlertext, Buchungsschlüssel, Arbeitsordner, Zeitangaben."""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

from fastapi.responses import HTMLResponse

from digiassistenz_kern import zeit
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import einstellungen, gemeinsam

PRAEFIX = "inventar.code."


def fehler_text(fehler: Exception) -> str:
    """`ValueError("stueck.nummer_vergeben")` → der Satz unter `inventar.code.stueck.nummer_vergeben`."""
    schluessel = PRAEFIX + str(fehler)
    text = t(schluessel)
    return t("inventar.fehler_allgemein") if text == schluessel else text


def fehlerteil(fehler: Exception) -> HTMLResponse:
    return gemeinsam.fehlerteil(fehler_text(fehler))


def arbeitsordner() -> Path:
    return Path(einstellungen.konfiguration().arbeitsordner)


def neuer_schluessel() -> str:
    """Eine neue Buchung bekommt beim Aufbau der Seite ihren Schlüssel; zweimal absenden bucht einmal."""
    return str(uuid.uuid4())


def heute() -> dt.date:
    return zeit.heute()


def ganzzahl(text: str, standard: int | None = None) -> int | None:
    try:
        return int(str(text).strip())
    except ValueError:
        return standard


def datum(text: str) -> dt.date | None:
    text = text.strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise ValueError("web.datum_ungueltig") from None
