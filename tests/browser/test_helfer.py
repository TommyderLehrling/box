"""Kleine Hilfen für mehrere Dateien (kein Prüffall)."""

from __future__ import annotations

from playwright.sync_api import Page


def nummer_der_statuszeile(seite: Page, stueck_id: int) -> str:
    """Die Inventarnummer des Stücks: in der Statuszeile die Angabe nach der Bezeichnung."""
    seite.goto(f"/inventar/stueck/{stueck_id}")
    teile = [t.strip() for t in seite.locator("#statuszeile p").first.inner_text().split("·")]
    return teile[1]
