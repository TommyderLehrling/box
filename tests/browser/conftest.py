"""Browser-Prüffälle (Playwright, synchron) gegen eine laufende Prüf-Box — Aufbau siehe `README.md` in diesem Ordner.

Gebraucht wird eine Box, die `box_starten.py` (oder ein gleichwertiger Aufbau) bereitstellt, mit den Konten
`verwalter@browser.invalid`, `polier@browser.invalid`, `polier2@browser.invalid`, `buero@browser.invalid`. Die Adresse steht in `BROWSER_BASIS_URL`
(Standard `http://127.0.0.1:8765`), die Engines in `BROWSER_ENGINES` (Standard `chromium`; `chromium,firefox,webkit`). Fehlt die Box, wird jeder Fall **rot** — nichts wird übersprungen.

Der Aufbau (Seed): die Testdaten des Moduls mit festem Seed (`SEED`, `ANZAHL`) — einmal je Lauf, ein zweites Mal ändert sich nichts.
Jeder Fall legt seine eigenen Stücke mit einer eindeutigen Bezeichnung an und räumt nichts weg (es wird nichts gelöscht).
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

BASIS = os.environ.get("BROWSER_BASIS_URL", "http://127.0.0.1:8765").rstrip("/")
ENGINES = [e.strip() for e in os.environ.get("BROWSER_ENGINES", "chromium").split(",") if e.strip()]
PASSWORT = os.environ.get("BROWSER_PASSWORT", "Browser-Inventar-2026!")
VERWALTER = "verwalter@browser.invalid"
POLIER = "polier@browser.invalid"
POLIER_ZWEI = "polier2@browser.invalid"
BUERO = "buero@browser.invalid"
KOSTENSTELLEN = ("1000", "79795", "80010", "70101", "70102")
SEED, ANZAHL = 11, 60
KAMERA_ARGUMENTE = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "engine" in metafunc.fixturenames:
        metafunc.parametrize("engine", ENGINES, scope="session")


@pytest.fixture(scope="session")
def pw() -> Iterator[Playwright]:
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(pw: Playwright, engine: str) -> Iterator[Browser]:
    start = getattr(pw, engine)
    argumente = KAMERA_ARGUMENTE if engine == "chromium" else []
    b = start.launch(args=argumente) if argumente else start.launch()
    yield b
    b.close()


@pytest.fixture(scope="session", autouse=True)
def _box_laeuft(pw: Playwright) -> None:
    """Ohne laufende Box ist jeder Fall rot (nicht übersprungen)."""
    antwort = pw.request.new_context().get(f"{BASIS}/anmelden")
    assert antwort.ok, f"Keine Box unter {BASIS} (BROWSER_BASIS_URL) — erst `box_starten.py` starten, siehe tests/browser/README.md"


def anmelden(kontext: BrowserContext, name: str) -> Page:
    seite = kontext.new_page()
    seite.goto(f"{BASIS}/anmelden")
    seite.fill("input[name=anmeldename]", name)
    seite.fill("input[name=passwort]", PASSWORT)
    seite.click("button[type=submit]")
    seite.wait_for_load_state("networkidle")
    assert "/anmelden" not in seite.url, f"Anmeldung von {name} fehlgeschlagen"
    return seite


@pytest.fixture(scope="session")
def _aufbau(pw: Playwright) -> None:
    """Die Testdaten mit festem Seed (Verwaltung → Testdaten); wiederholbar. Kostenstellen und Konten legt `box_starten.py` an.

    Mit dem Browser selbst (die Sitzung ist ein Secure-Cookie, ein reiner HTTP-Client nähme sie nicht mit).
    """
    b = pw.chromium.launch()
    k = b.new_context(base_url=BASIS, locale="de-DE")
    k.set_default_timeout(30_000)
    seite = anmelden(k, VERWALTER)
    seite.goto("/inventar/verwaltung/testdaten")
    if seite.locator("#td-seed").count():
        seite.fill("#td-seed", str(SEED))
        seite.fill("#td-anzahl", str(ANZAHL))
        seite.locator("main form button[type=submit]").click()
        seite.wait_for_selector("#katalog-meldung :text-matches('.+')", timeout=120_000)
    b.close()


@pytest.fixture
def kontext(browser: Browser, _aufbau: None) -> Iterator[BrowserContext]:
    k = browser.new_context(base_url=BASIS, viewport={"width": 1280, "height": 900}, accept_downloads=True, locale="de-DE")
    k.set_default_timeout(10_000)
    yield k
    k.close()


@pytest.fixture
def verwalter(kontext: BrowserContext) -> Page:
    return anmelden(kontext, VERWALTER)


@pytest.fixture
def polier(browser: Browser, _aufbau: None) -> Iterator[Page]:
    k = browser.new_context(base_url=BASIS, viewport={"width": 390, "height": 800}, locale="de-DE")  # Handy
    k.set_default_timeout(10_000)
    yield anmelden(k, POLIER)
    k.close()


@pytest.fixture
def buero(kontext: BrowserContext) -> Page:
    return anmelden(kontext, BUERO)


def eindeutig(vorsilbe: str = "Fall") -> str:
    return f"{vorsilbe} {uuid.uuid4().hex[:8]}"


def wahl_waehlen(seite: Page, kennung: str, text: str) -> None:
    """Das Such-Wahlfeld des Kerns (`#<kennung>-suche`, Auswahl `#<kennung>`): tippen, auf den Treffer warten, wählen."""
    seite.fill(f"#{kennung}-suche", text)
    seite.wait_for_function(
        "([k, t]) => Array.from(document.querySelectorAll('#' + k + ' option')).some(o => o.value && o.textContent.includes(t))", arg=[kennung, text])
    wert = seite.evaluate(
        "([k, t]) => Array.from(document.querySelectorAll('#' + k + ' option')).find(o => o.value && o.textContent.includes(t)).value", [kennung, text])
    seite.select_option(f"#{kennung}", wert)


def stueck_anlegen(seite: Page, bezeichnung: str, gruppe: str = "baumaschine", art: str = "gross", kostenstelle: str = "70101", menge: str = "1",
                   kaufpreis: str = "") -> int:
    """Legt ein Stück über das Formular `/inventar/stueck/neu` an (wie ein Mensch) und liefert seine Id."""
    seite.goto("/inventar/stueck/neu")
    seite.fill("#inv-bezeichnung", bezeichnung)
    seite.select_option("#inv-gruppe-form", gruppe)
    seite.select_option("#inv-art", art)
    if menge != "1":
        seite.fill("#inv-menge", menge)
    if kaufpreis:
        seite.fill("#inv-kaufpreis", kaufpreis)
    wahl_waehlen(seite, "wahl-start-ks", kostenstelle)
    seite.click("#stueck-form button[type=submit]")
    seite.wait_for_url(re.compile(r"/inventar/stueck/\d+\?fertig=angelegt"))
    return int(re.search(r"/inventar/stueck/(\d+)", seite.url).group(1))


def ks_id(seite: Page, nummer: str) -> int:
    """Die Id der Kostenstelle mit dieser Nummer (aus der Wahl auf `/inventar/hier`; das Konto braucht `scannen` auf ihr)."""
    seite.goto("/inventar/hier")
    for option in seite.locator("#hier-ks option").all():
        if option.inner_text().startswith(nummer):
            return int(option.get_attribute("value"))
    if seite.locator("#hier-ks").count() == 0:  # nur eine Kostenstelle: ohne Wahl, der Scan-Link trägt die Id
        if nummer in seite.locator("main strong").first.inner_text():
            return int(re.search(r"ks=(\d+)", seite.locator("a[href*='/inventar/scannen?ks=']").first.get_attribute("href")).group(1))
    raise AssertionError(f"Kostenstelle {nummer} fehlt in der Wahl")


def nummer_von(seite: Page, stueck_id: int) -> str:
    """Die Inventarnummer des Stücks (zweite Angabe der Statuszeile)."""
    seite.goto(f"/inventar/stueck/{stueck_id}")
    return seite.locator("#statuszeile strong + *").first.evaluate("e => e.parentElement.textContent").split("·")[1].strip()


def ist_chromium(engine: str) -> bool:
    return engine == "chromium"


ARBEITSORDNER_HINWEIS = Path(__file__).with_name("README.md")
