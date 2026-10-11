"""Zoom (Steckbrief 10, in WebKit gefahren): bei 200 % und 400 % Zoom (Seitenbreite 640 bzw. 320 CSS-Pixel) bleiben die Hauptseiten benutzbar:
kein Querlauf der ganzen Seite, die Tasten der Stück-Seite stehen sichtbar da."""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser

from conftest import BASIS, VERWALTER, anmelden, eindeutig, stueck_anlegen

SEITEN = ("/inventar", "/inventar/hier", "/inventar/faellig", "/inventar/werkstatt", "/inventar/kosten", "/inventar/verwaltung/inventur")


@pytest.mark.parametrize("breite", [640, 320])
def test_zoom_kein_querlauf_der_ganzen_seite(browser: Browser, _aufbau, breite: int) -> None:
    kontext = browser.new_context(base_url=BASIS, viewport={"width": breite, "height": 900}, locale="de-DE")
    kontext.set_default_timeout(10_000)
    try:
        seite = anmelden(kontext, VERWALTER)
        sid = stueck_anlegen(seite, eindeutig("Zoom"))
        zu_breit = []
        for weg in (*SEITEN, f"/inventar/stueck/{sid}"):
            seite.goto(weg)
            ueberlauf = seite.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if ueberlauf > 1:
                zu_breit.append((weg, ueberlauf))
        assert zu_breit == [], zu_breit
        seite.goto(f"/inventar/stueck/{sid}")
        assert seite.locator("#statuszeile").is_visible() and seite.locator("#haupttasten").is_visible()
    finally:
        kontext.close()
