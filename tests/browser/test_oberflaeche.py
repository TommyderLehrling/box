"""Browserfälle 1–3, 7–10 und 14 (INTEGRATION_VSC.md Abschnitt 4): Stück-Seite, Tasten, Rechte, Liste, Dialoge, Merkmale, Foto, Startstandort.

Aufbau: die Box aus `conftest.py` (Seed: Kostenstellen und Testdaten); jeder Fall legt sein Stück mit eindeutiger Bezeichnung an.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from conftest import PNG, eindeutig, ks_id, stueck_anlegen, wahl_waehlen


def test_F01_statuszeile_steht_vor_allen_aufklappern(verwalter: Page) -> None:
    """Sollwert: `#statuszeile` ist das erste Element unter dem Seitenkopf; kein `<details>` steht davor."""
    sid = stueck_anlegen(verwalter, eindeutig("Statuszeile"))
    verwalter.goto(f"/inventar/stueck/{sid}")
    davor = verwalter.evaluate("""() => {
        const z = document.getElementById('statuszeile');
        const alle = Array.from(document.querySelectorAll('main details:not(.hilfe-mehr)'));  // die Hilfe im Seitenkopf zählt nicht
        return alle.filter(d => (d.compareDocumentPosition(z) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0).length;
    }""")
    assert davor == 0
    erstes = verwalter.evaluate("""() => {
        const z = document.getElementById('statuszeile');
        let v = z.previousElementSibling;
        return v ? v.tagName + '#' + (v.id || v.className) : '';
    }""")
    assert "DETAILS" not in erstes
    expect(verwalter.locator("#statuszeile")).to_contain_text("Baustelle 70101")


def test_F02_tasten_einer_reihe_sind_gleich_hoch(verwalter: Page) -> None:
    """Sollwert: in `#haupttasten` und `#scan-tasten` haben alle Tasten die gleiche Höhe (± 1 px)."""
    sid = stueck_anlegen(verwalter, eindeutig("Tasten"))
    ks = ks_id(verwalter, "70101")
    verwalter.goto(f"/inventar/stueck/{sid}?ks={ks}")
    for reihe in ("#haupttasten", "#scan-tasten"):
        hoehen = verwalter.locator(f"{reihe} > a, {reihe} > button, {reihe} > form button, {reihe} > details > summary").evaluate_all(
            "els => els.filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().height))")
        assert hoehen, reihe
        assert max(hoehen) - min(hoehen) <= 1, (reihe, hoehen)


def test_F03_polier_sieht_keine_links_ohne_recht(polier: Page, verwalter: Page) -> None:
    """Sollwert: `Polier.Eins` sieht weder Preise noch Bearbeiten, Neues Stück, Prüfung eintragen, Werkstatt, Kosten oder Verwaltung."""
    sid = stueck_anlegen(verwalter, eindeutig("Rechte"), kaufpreis="1234")
    polier.goto(f"/inventar/stueck/{sid}")
    html = polier.content()
    for spur in ("/aendern", "/inventar/werkstatt", "/inventar/kosten", "/inventar/verwaltung", "/inventar/stueck/neu", "1.234", "1234,00"):
        assert spur not in html, spur
    assert polier.locator("#abschnitt-kosten").count() == 0
    assert polier.locator("#pruefung-eintragen").count() == 0
    for gesperrt in ("/inventar/werkstatt", "/inventar/kosten", "/inventar/verwaltung", "/inventar/stueck/neu"):
        assert polier.goto(gesperrt).status == 403, gesperrt


def test_F07_suchfeld_wartet_250_ms_und_aendert_nur_die_liste(verwalter: Page) -> None:
    """Sollwert: nach dem Tippen ändert sich nur `#inventar-liste`; Seitenwahl und Sortierung behalten den Filter."""
    name = eindeutig("Suchbar")
    stueck_anlegen(verwalter, name)
    verwalter.goto("/inventar?ansicht=liste")
    verwalter.evaluate("() => { window.__merker = document.getElementById('inventar-filter'); }")
    anfragen: list[str] = []
    verwalter.on("request", lambda a: anfragen.append(a.url) if "/inventar/liste" in a.url else None)
    verwalter.locator("#inv-q").press_sequentially(name, delay=15)
    verwalter.wait_for_timeout(100)
    assert anfragen == [], "vor Ablauf der 250 ms geht keine Anfrage hinaus"
    expect(verwalter.locator("#inventar-liste table.liste tr:has(td)")).to_have_count(1)
    expect(verwalter.locator("#inventar-liste")).to_contain_text(name)
    assert len(anfragen) == 1
    assert verwalter.evaluate("() => window.__merker === document.getElementById('inventar-filter')"), "das Formular bleibt, nur die Liste wird ersetzt"
    verwalter.click("#inventar-liste th a >> nth=0")
    assert "q=" in verwalter.url and name.split()[0] in verwalter.url.replace("+", " ").replace("%20", " ")


def test_F08_dialoge_klappen_zu_und_setzen_zurueck(verwalter: Page) -> None:
    """Sollwert: „Abbrechen“ und Esc klappen den Dialog zu und leeren das Formular; nach dem Speichern steht ✓ und die Seite bleibt."""
    sid = stueck_anlegen(verwalter, eindeutig("Dialog"))
    verwalter.goto(f"/inventar/stueck/{sid}?ks={ks_id(verwalter, '70101')}")
    verwalter.click("#dialog-meldung > summary")
    assert verwalter.evaluate("() => document.getElementById('dialog-meldung').open")
    verwalter.fill("#meldung-text", "Riss im Schlauch")
    verwalter.click("#dialog-meldung [data-abbrechen]")
    assert not verwalter.evaluate("() => document.getElementById('dialog-meldung').open")
    assert verwalter.input_value("#meldung-text") == ""
    verwalter.click("#dialog-meldung > summary")
    verwalter.fill("#meldung-text", "Zweiter Versuch")
    verwalter.keyboard.press("Escape")
    assert not verwalter.evaluate("() => document.getElementById('dialog-meldung').open")
    verwalter.click("#dialog-meldung > summary")
    verwalter.fill("#meldung-text", "Riss im Schlauch")
    verwalter.click("#dialog-meldung button.haupt")
    expect(verwalter.locator("#stueck-meldung, [role=status]").first).to_contain_text("✓")
    assert re.search(rf"/inventar/stueck/{sid}", verwalter.url)


def test_F09_merkmalsfelder_und_nummernvorschlag_wechseln_mit_der_gruppe(verwalter: Page) -> None:
    """Sollwert: Gruppenwechsel tauscht die Merkmalsfelder und den Platzhalter des Nummernfeldes (Kürzel der Gruppe)."""
    verwalter.goto("/inventar/stueck/neu")
    verwalter.select_option("#inv-gruppe-form", "baumaschine")
    expect(verwalter.locator("#inv-nummer")).to_have_attribute("placeholder", re.compile(r"^BM-"))
    vorher = verwalter.locator("#merkmal-felder").inner_html()
    verwalter.select_option("#inv-gruppe-form", "fahrzeug")
    expect(verwalter.locator("#inv-nummer")).to_have_attribute("placeholder", re.compile(r"^FZ-"))
    assert verwalter.locator("#merkmal-felder").inner_html() != vorher
    assert verwalter.locator("#m-kennzeichen").count() == 1 and verwalter.locator("#m-betriebsgewicht").count() == 0


def test_F10_foto_jpg_png_wird_genommen_textdatei_abgewiesen(verwalter: Page) -> None:
    """Sollwert: ein PNG am Stück erscheint auf der Stück-Seite; eine umbenannte Textdatei wird abgewiesen."""
    verwalter.goto("/inventar/stueck/neu")
    verwalter.fill("#inv-bezeichnung", eindeutig("Foto"))
    verwalter.select_option("#inv-gruppe-form", "baumaschine")
    verwalter.select_option("#inv-art", "gross")
    wahl_waehlen(verwalter, "wahl-start-ks", "70101")
    verwalter.set_input_files("#inv-foto", {"name": "bild.png", "mimeType": "image/png", "buffer": PNG})
    verwalter.click("#stueck-form button[type=submit]")
    verwalter.wait_for_url(re.compile(r"/inventar/stueck/\d+"))
    expect(verwalter.locator("#stueck-foto")).to_be_visible()
    sid = int(re.search(r"/stueck/(\d+)", verwalter.url).group(1))
    verwalter.goto(f"/inventar/stueck/{sid}/aendern")
    verwalter.set_input_files("#inv-foto", {"name": "tarnung.png", "mimeType": "image/png", "buffer": b"das ist kein bild"})
    verwalter.click("#stueck-form button[type=submit]")
    expect(verwalter.locator("#stueck-meldung [role=alert]")).to_be_visible()


def test_F14_neues_stueck_verlangt_startstandort_buero_kann_anlegen_nicht_umbuchen(buero: Page) -> None:
    """Sollwert: das Startstandort-Feld ist Pflicht; ein Büro-Konto findet seine Kostenstellen, legt an, hat aber keine Taste zum Umbuchen."""
    buero.goto("/inventar/stueck/neu")
    assert buero.evaluate("() => document.getElementById('wahl-start-ks').required") is True
    buero.fill("#inv-bezeichnung", eindeutig("Buero"))
    buero.select_option("#inv-gruppe-form", "kleingeraet")
    buero.select_option("#inv-art", "klein")
    assert buero.evaluate("() => document.getElementById('stueck-form').checkValidity()") is False, "ohne Startstandort kein Absenden"
    wahl_waehlen(buero, "wahl-start-ks", "70101")
    assert buero.evaluate("() => document.getElementById('stueck-form').checkValidity()") is True
    buero.click("#stueck-form button[type=submit]")
    buero.wait_for_url(re.compile(r"/inventar/stueck/\d+"))
    assert buero.locator("#dialog-abgang").count() == 0, "pflegen ist nicht buchen"
