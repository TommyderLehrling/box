"""Kleinigkeiten, die mehrere Seiten brauchen: Fehlertext, Buchungsschlüssel, Arbeitsordner, Zeitangaben."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi.responses import HTMLResponse, Response

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


def dezimal(text: str) -> Decimal | None:
    """Eine Zahl mit Komma oder Punkt; leer ist `None`, alles andere ein Fehler mit Satzschlüssel."""
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError("web.zahl_ungueltig") from None


def zahl_text(wert: Decimal) -> str:
    """Eine Dezimalzahl ohne überflüssige Nullen und ohne Exponent (`1250.500` → `1250.5`)."""
    return f"{wert.normalize():f}"


def zaehler_hinweis(stand: str, letzter: str) -> str:
    """Der Satz „Zählerstand n liegt unter dem letzten Stand m“; leer, wenn die beiden Angaben keine Zahlen sind."""
    try:
        return t("inventar.pruefung.zaehler_unter", stand=zahl_text(Decimal(stand)), letzter=zahl_text(Decimal(letzter)))
    except (InvalidOperation, ValueError):
        return ""


def datum(text: str) -> dt.date | None:
    text = text.strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise ValueError("web.datum_ungueltig") from None


def datei_antwort(name: str, inhalt: bytes) -> Response:
    """Ein Foto zum Ansehen: im Browser (`inline`), der Typ aus dem Anfang der Datei, ohne Raten durch den Browser."""
    typ = "image/png" if inhalt.startswith(b"\x89PNG") else "image/jpeg"
    return Response(inhalt, media_type=typ, headers={"Content-Disposition": f'inline; filename="{name}"', "X-Content-Type-Options": "nosniff"})
