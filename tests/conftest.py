"""Gemeinsames für die Prüffälle ohne Datenbank: das Modul wird beim Kern angemeldet, danach wieder abgemeldet."""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def angemeldet() -> Iterator[None]:
    """`inventar` im Prozess des Kerns anmelden (Texte, Vorlagen, Bausteine) und am Ende zurücknehmen."""
    from digiassistenz_kern import modul as kern_modul

    from digiassistenz_inventar.modul import BESCHREIBUNG

    kern_modul.anmelden(BESCHREIBUNG)
    yield
    kern_modul.abmelden(BESCHREIBUNG.schluessel)
