"""DOKON Inventar — Modul `inventar` (Schema `inventar`, Kette `i0001…`, Konto `inventar_nutzer`).

Das Paket ist leicht zu importieren: `SCHLUESSEL`, `VERSION` und `BESCHREIBUNG` werden erst beim ersten Zugriff
aus `modul` geholt, damit die reinen Module (`rein`) auch ohne den Kern laufen.
"""
from __future__ import annotations

from typing import Any

__all__ = ["BESCHREIBUNG", "SCHLUESSEL", "VERSION"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import modul

        return getattr(modul, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
