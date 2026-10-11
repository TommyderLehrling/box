"""Browserfall 6 (Scan-Weg mit Kamera-Attrappe und Eingabe) und die Buchungen Abgang / Eingang / „Ist hier“ (INTEGRATION_VSC.md Abschnitt 4).

Kamera-Attrappe: Chromium mit `--use-fake-device-for-media-stream` (steht in `conftest.py`). Weil `BarcodeDetector` in einem Chromium unter Linux fehlen kann, bekommt der Fall
einen Ersatz, der den QR-Text liefert — so wird der Weg „Kamera → Nummer → Stück-Seite“ geprüft, nicht das Erkennen selbst (das bleibt ein Versuch am Handy).
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from conftest import POLIER_ZWEI, anmelden, eindeutig, ks_id, stueck_anlegen, wahl_waehlen
from test_helfer import nummer_der_statuszeile


def _abgang(verwalter: Page, sid: int, nach: str) -> None:
    verwalter.goto(f"/inventar/stueck/{sid}")
    verwalter.click("#dialog-abgang > summary")
    wahl_waehlen(verwalter, "wahl-abgang-nach", nach)
    verwalter.click("#dialog-abgang button.haupt")
    expect(verwalter.locator("p.gut[role=status]")).to_contain_text("✓")


def test_F06a_scan_ueber_eingabe_fuehrt_auf_die_stueck_seite(verwalter: Page) -> None:
    """Sollwert: Nummer getippt → Stück-Seite mit `?ks=`, ohne `art=kamera` (Quelle `web`); „Ist hier“ meldet ✓."""
    sid = stueck_anlegen(verwalter, eindeutig("Scan Eingabe"))
    nummer = nummer_der_statuszeile(verwalter, sid)
    ks = ks_id(verwalter, "70101")
    verwalter.goto(f"/inventar/scannen?ks={ks}")
    verwalter.fill("#scan-nummer", nummer)
    verwalter.press("#scan-nummer", "Enter")
    verwalter.wait_for_url(re.compile(rf"/inventar/stueck/{sid}\?.*ks={ks}"))
    assert "art=kamera" not in verwalter.url
    verwalter.click("#scan-tasten form button.haupt")
    expect(verwalter.locator("p.gut[role=status]")).to_contain_text("✓")


def test_F06b_scan_ueber_kamera_attrappe(verwalter: Page, engine: str) -> None:
    """Sollwert (Chromium): die Attrappe liefert ein Bild, `#scan-kamera` erscheint, der Treffer führt mit `art=kamera` auf die Stück-Seite.
    Firefox und WebKit haben keinen `BarcodeDetector`: der Text „Kamera nicht verfügbar“ steht da, das Eingabefeld bleibt."""
    sid = stueck_anlegen(verwalter, eindeutig("Scan Kamera"))
    nummer = nummer_der_statuszeile(verwalter, sid)
    ks = ks_id(verwalter, "70101")
    if engine != "chromium":
        verwalter.goto(f"/inventar/scannen?ks={ks}")
        expect(verwalter.locator("#scan-status")).not_to_be_empty()
        expect(verwalter.locator("#scan-nummer")).to_be_visible()
        return
    verwalter.context.grant_permissions(["camera"])
    verwalter.context.add_init_script(
        "window.BarcodeDetector = class { constructor() {} async detect() { return [{ rawValue: 'https://box.invalid/inventar/s/%s' }]; } };" % nummer)
    verwalter.goto(f"/inventar/scannen?ks={ks}")
    verwalter.wait_for_url(re.compile(rf"/inventar/stueck/{sid}\?.*art=kamera"), timeout=15_000)
    expect(verwalter.locator("#scan-tasten")).to_be_visible()


def test_F06c_ist_hier_bestaetigt_den_angekuendigten_transfer(verwalter: Page, browser) -> None:
    """Sollwert: Abgang von 70101 nach 70102 (Verwalter); `Polier.Zwei` scannt auf 70102 „Ist hier“ → Transfer bestätigt, das Stück steht auf 70102."""
    sid = stueck_anlegen(verwalter, eindeutig("Transfer Scan"))
    _abgang(verwalter, sid, "70102")
    polier = browser.new_context(base_url=verwalter.url.split("/inventar")[0], viewport={"width": 390, "height": 800})
    try:
        seite = anmelden(polier, POLIER_ZWEI)
        ks = ks_id(seite, "70102")
        seite.goto(f"/inventar/stueck/{sid}?ks={ks}")
        expect(seite.locator("#statuszeile")).to_contain_text("angekündigt")
        seite.click("#scan-tasten form button.haupt")
        expect(seite.locator("p.gut[role=status]")).to_contain_text("✓")
        seite.goto(f"/inventar/stueck/{sid}")
        expect(seite.locator("#statuszeile")).to_contain_text("Baustelle 70102")
    finally:
        polier.close()


def test_hier_seite_ist_angekommen(verwalter: Page, browser) -> None:
    """Sollwert: auf `/inventar/hier` steht der angekündigte Transfer; „Ist angekommen“ bucht den Eingang."""
    name = eindeutig("Transfer Hier")
    sid = stueck_anlegen(verwalter, name)
    _abgang(verwalter, sid, "70102")
    polier = browser.new_context(base_url=verwalter.url.split("/inventar")[0], viewport={"width": 390, "height": 800})
    try:
        seite = anmelden(polier, POLIER_ZWEI)
        seite.goto("/inventar/hier")
        zeile = seite.locator("#hier-angekuendigt tr", has_text=name)
        expect(zeile).to_have_count(1)
        zeile.locator("button.haupt").click()
        expect(seite.locator("p.gut[role=status]")).to_contain_text("✓")
        seite.goto("/inventar/hier")
        expect(seite.locator("#hier-vor-ort")).to_contain_text(name)
    finally:
        polier.close()
