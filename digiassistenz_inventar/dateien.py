"""Pfade und Ablage der Dateien des Inventars — unter dem einen Arbeitsordner, nie ein fester Pfad.

`arbeitsordner / "inventar" / <mandant.ordnername> / "stamm" / <inventarnummer> / {bilder,pruefungen,meldungen}`
und `… / "export"`. Nachweise und Fotos sind unveränderlich: eine neue Datei statt Ersatz, der Hash steht im
Datensatz (Spec v0.2 Abschnitt 13).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

WURZEL = "inventar"
UNTERORDNER = ("bilder", "pruefungen", "meldungen")
_UNSICHER = re.compile(r"[^A-Za-z0-9._-]+")
FOTO_ENDUNGEN = {"image/jpeg": ".jpg", "image/png": ".png"}
FOTO_HOECHSTENS = 8 * 1024 * 1024


class DateiFehler(ValueError):
    """Der Text ist ein Schlüssel `dateien.<was>`, kein Satz."""


def modulordner(arbeitsordner: Path, ordnername: str) -> Path:
    return arbeitsordner / WURZEL / ordnername


def stammordner(arbeitsordner: Path, ordnername: str, inventarnummer: str, unter: str) -> Path:
    if unter not in UNTERORDNER:
        raise DateiFehler("dateien.unterordner_unbekannt")
    return modulordner(arbeitsordner, ordnername) / "stamm" / sauber(inventarnummer) / unter


def exportordner(arbeitsordner: Path, ordnername: str) -> Path:
    return modulordner(arbeitsordner, ordnername) / "export"


def importordner(arbeitsordner: Path, ordnername: str) -> Path:
    """Hochgeladene Importdateien — sie bleiben liegen (nichts wird gelöscht)."""
    return modulordner(arbeitsordner, ordnername) / "import"


def kostenstellenordner(arbeitsordner: Path, ordnername: str, nummer: str) -> Path:
    return modulordner(arbeitsordner, ordnername) / "kostenstellen" / sauber(nummer)


def sauber(name: str) -> str:
    """Ein Dateiname ohne Pfadtrenner und Sonderzeichen; leer ist nicht erlaubt."""
    rein = _UNSICHER.sub("_", name.strip()).strip("._")
    if not rein:
        raise DateiFehler("dateien.name_leer")
    return rein


def pruefsumme(inhalt: bytes) -> str:
    return hashlib.sha256(inhalt).hexdigest()


def speichern(ordner: Path, name: str, inhalt: bytes) -> tuple[Path, str]:
    """Legt eine Datei an, ohne eine vorhandene zu ersetzen (Zähler im Namen); liefert Pfad und SHA-256."""
    ordner.mkdir(parents=True, exist_ok=True)
    basis = sauber(name)
    stamm, punkt, endung = basis.rpartition(".")
    if not punkt:
        stamm, endung = basis, ""
    ziel = ordner / basis
    nr = 1
    while ziel.exists():
        nr += 1
        ziel = ordner / (f"{stamm}_{nr}" + (f".{endung}" if endung else ""))
    ziel.write_bytes(inhalt)
    return ziel, pruefsumme(inhalt)


KENNUNG = {".jpg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n"}


def foto_pruefen(inhalt_typ: str, groesse: int, inhalt: bytes | None = None) -> str:
    """Erlaubt sind jpg und png bis 8 MB; liefert die Endung. Mit `inhalt` zählt auch der Anfang der Datei, nicht nur die Angabe."""
    endung = FOTO_ENDUNGEN.get(inhalt_typ)
    if endung is None:
        raise DateiFehler("dateien.foto_typ")
    if groesse > FOTO_HOECHSTENS:
        raise DateiFehler("dateien.foto_gross")
    if inhalt is not None and not inhalt.startswith(KENNUNG[endung]):
        raise DateiFehler("dateien.foto_typ")
    return endung
