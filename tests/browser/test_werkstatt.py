"""Werkstatt (G4, L14/L14a): Posteingang, Foto der Meldung, Abschluss-Dialog mit Haken und Vorfüll-Skript, Rückmeldung an der Stück-Seite (INTEGRATION_VSC.md Abschnitt 4, Fälle 15–17)."""

from __future__ import annotations

import re

from playwright.sync_api import Browser, Page, expect

from conftest import BASIS, PNG, anmelden, eindeutig, ks_id, stueck_anlegen, POLIER


def _klick(seite: Page, ziel) -> None:
    """Klick auf eine Taste, die über HTMX bucht und die Seite neu lädt: auf die neue Seite warten, dann auf ✓."""
    with seite.expect_navigation(url=re.compile(r"fertig=")):
        ziel.click()
    expect(seite.locator("#werkstatt-fertig")).to_contain_text("✓")


def _schaden_melden(browser: Browser, sid: int, text: str):
    """Ein Polier meldet einen Schaden mit Foto (Handy-Breite)."""
    kontext = browser.new_context(base_url=BASIS, viewport={"width": 390, "height": 800}, locale="de-DE")
    kontext.set_default_timeout(10_000)
    seite = anmelden(kontext, POLIER)
    seite.goto(f"/inventar/stueck/{sid}?ks={ks_id(seite, '70101')}")
    seite.click("#dialog-meldung > summary")
    seite.fill("#meldung-text", text)
    seite.set_input_files("#meldung-foto", {"name": "schaden.png", "mimeType": "image/png", "buffer": PNG})
    seite.click("#dialog-meldung button.haupt")
    expect(seite.locator("p.gut[role=status]")).to_contain_text("✓")
    kontext.close()


def test_werkstatt_titel_ist_text_und_menue_fuehrt_hin(verwalter: Page) -> None:
    """Sollwert: der Tab-Titel ist reiner Text (kein `<script>` im Titel); der Menüpunkt „Werkstatt“ führt auf die Seite."""
    verwalter.goto("/inventar")
    verwalter.click("header a[href='/inventar/werkstatt']")
    verwalter.wait_for_url(re.compile(r"/inventar/werkstatt$"))
    titel = verwalter.title()
    assert "<" not in titel and titel.startswith("Werkstatt"), titel


def test_werkstatt_meldung_bis_rueckmeldung(verwalter: Page, browser: Browser) -> None:
    """Sollwert: Meldung (mit Foto) → Annehmen → Übernehmen → Reparatur anlegen (Beschreibung vorbelegt) → Beginnen → Abschließen oben in einem
    Dialog: Haken „Meldung damit erledigen“ an, Rückmeldung wird aus „Was gemacht wurde“ vorgefüllt, solange man sie nicht selbst ändert → Meldung erledigt,
    die Rückmeldung steht an der Stück-Seite, das Stück ist wieder aktiv."""
    name = eindeutig("Werkstatt")
    sid = stueck_anlegen(verwalter, name)
    beschreibung = eindeutig("Hydraulikschlauch undicht")
    _schaden_melden(browser, sid, beschreibung)

    verwalter.goto("/inventar/werkstatt")
    zeile = verwalter.locator("#werkstatt-offen tr[id^=meldung-]", has_text=beschreibung)
    expect(zeile).to_have_count(1)
    foto = zeile.locator("a[href$='/foto']").get_attribute("href")
    kopf = verwalter.evaluate("async (w) => { const r = await fetch(w); return [r.status, r.headers.get('content-type')]; }", foto)
    assert kopf == [200, "image/png"], kopf
    _klick(verwalter, zeile.locator("form.inline button.haupt"))

    zeile = verwalter.locator("#werkstatt-angenommen tr[id^=meldung-]", has_text=beschreibung)
    _klick(verwalter, zeile.locator("form.inline button.haupt"))
    zeile = verwalter.locator("#werkstatt-in-arbeit tr[id^=meldung-]", has_text=beschreibung)
    zeile.locator("a", has_text="Reparatur anlegen").click()
    expect(verwalter.locator("#reparatur-anlegen")).to_have_attribute("open", "")
    assert beschreibung in verwalter.input_value("#rp-text"), "die Beschreibung der Meldung ist vorbelegt"
    _klick(verwalter, verwalter.locator("#reparatur-anlegen button.haupt"))

    reparatur = verwalter.locator("#werkstatt-reparaturen tr[id^=reparatur-]", has_text=name)
    reparatur.locator("details[id^=beginnen-] > summary").click()
    _klick(verwalter, reparatur.locator("details[id^=beginnen-] button.haupt"))
    verwalter.goto(f"/inventar/stueck/{sid}")
    expect(verwalter.locator("#hinweis-in-reparatur")).to_be_visible()

    verwalter.goto("/inventar/werkstatt")
    verwalter.locator("#werkstatt-reparaturen tr[id^=reparatur-]", has_text=name).locator("a[id^=abschluss-]").click()
    dialog = verwalter.locator("#reparatur-abschliessen")
    expect(dialog).to_have_attribute("open", "")
    expect(dialog.locator("input[name=meldung_erledigen]")).to_be_checked()
    # Vorfüll-Skript: die Rückmeldung folgt „Was gemacht wurde“, bis jemand sie selbst anfasst
    verwalter.fill("#ab-arbeit", "Schlauch")
    assert verwalter.input_value("#ab-rueck") == "Schlauch"
    verwalter.fill("#ab-arbeit", "Schlauch getauscht")
    assert verwalter.input_value("#ab-rueck") == "Schlauch getauscht"
    verwalter.fill("#ab-rueck", "Eigener Text für den Melder")
    verwalter.fill("#ab-arbeit", "Schlauch getauscht und Öl nachgefüllt")
    assert verwalter.input_value("#ab-rueck") == "Eigener Text für den Melder", "ein selbst geänderter Text bleibt"
    assert verwalter.input_value("#ab-durch") != "", "intern: die abschließende Person ist vorbelegt"
    if verwalter.locator("#ab-zaehler").count():
        verwalter.fill("#ab-zaehler", "1234")
    _klick(verwalter, dialog.locator("button.haupt"))
    erledigt = verwalter.locator("#werkstatt-erledigt tr[id^=meldung-]", has_text=beschreibung)
    expect(erledigt).to_contain_text("Eigener Text für den Melder")
    verwalter.goto(f"/inventar/stueck/{sid}")
    expect(verwalter.locator("main")).to_contain_text("Eigener Text für den Melder")
    expect(verwalter.locator("#hinweis-in-reparatur")).to_have_count(0)


def test_werkstatt_zurueckziehen_verlangt_einen_grund(verwalter: Page, browser: Browser) -> None:
    """Sollwert: „Zurückziehen“ ohne Grund wird vom Browser nicht abgeschickt; mit Grund verschwindet die Meldung aus „Offen“."""
    sid = stueck_anlegen(verwalter, eindeutig("Zurueck"))
    beschreibung = eindeutig("Kratzer im Lack")
    _schaden_melden(browser, sid, beschreibung)
    verwalter.goto("/inventar/werkstatt")
    zeile = verwalter.locator("#werkstatt-offen tr[id^=meldung-]", has_text=beschreibung)
    zeile.locator("details[id^=zurueck-] > summary").click()
    zeile.locator("details[id^=zurueck-] button.haupt").click()
    assert verwalter.evaluate("() => document.querySelector('#werkstatt-offen details[open] form').checkValidity()") is False
    zeile.locator("details[id^=zurueck-] input[name=grund]").fill("Doppelt gemeldet")
    _klick(verwalter, zeile.locator("details[id^=zurueck-] button.haupt"))
    expect(verwalter.locator("#werkstatt-offen tr[id^=meldung-]", has_text=beschreibung)).to_have_count(0)
