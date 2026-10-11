"""Inventur (E10, L15/L16): Stichtag setzen, Mengenabfrage beim Scan, „als vermisst“ mit Grund — nichts geschieht von selbst."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from conftest import eindeutig, ks_id, stueck_anlegen


def _zeile(seite: Page, sid: int, ks: int):
    return seite.locator(f"#inventur-{sid}-{ks}")


def test_inventur_stichtag_mengenabfrage_und_vermisst_mit_grund(verwalter: Page) -> None:
    """Sollwert:
    1. Ohne Stichtag fragt der Scan eines Mengenartikels keine Menge.
    2. Mit Stichtag steht auf der Stück-Seite „Menge vor Ort“, vorbelegt mit der Buchmenge; 7 von 10 gezählt → „Teilweise gesehen“ (7 von 10), gebucht wird nichts.
    2a. Ein zweiter Scan mit Zahl überschreibt die letzte Sichtung; mehr als gebucht wird nicht gebucht und mit Hinweis gemeldet.
    3. Ein nicht gescanntes Stück ist „Nicht gesehen“; „Als vermisst vorschlagen“ öffnet die Zeile, ohne Grund geht es nicht ab; erst mit Grund (von Hand) wird es vermisst."""
    menge = stueck_anlegen(verwalter, eindeutig("Inventur Menge"), gruppe="schalung_ruestung", art="menge", menge="10")
    klein = stueck_anlegen(verwalter, eindeutig("Inventur klein"), gruppe="kleingeraet", art="klein")
    ks = ks_id(verwalter, "70101")

    verwalter.goto("/inventar/verwaltung/inventur")
    heute = verwalter.get_attribute("#inv-tag", "max")
    if verwalter.locator("#inventur-leer").count() == 0:  # ein Stichtag aus einer früheren Fahrt: zurücknehmen (leer lassen)
        verwalter.fill("#inv-tag", "")
        with verwalter.expect_navigation(url=re.compile(r"fertig=stichtag")):
            verwalter.click("#inventur-stichtag button.haupt")
        verwalter.goto("/inventar/verwaltung/inventur")
    expect(verwalter.locator("#inventur-leer")).to_be_visible()
    verwalter.goto(f"/inventar/stueck/{menge}?ks={ks}")
    assert verwalter.locator("#zaehl-abfrage").count() == 0, "ohne Stichtag keine Mengenabfrage"
    verwalter.goto("/inventar/verwaltung/inventur")
    verwalter.fill("#inv-tag", heute)
    with verwalter.expect_navigation(url=re.compile(r"fertig=stichtag")):
        verwalter.click("#inventur-stichtag button.haupt")
    expect(verwalter.locator("#inventur-fertig")).to_contain_text("✓")

    verwalter.goto(f"/inventar/stueck/{menge}?ks={ks}")
    expect(verwalter.locator("#zaehl-abfrage")).to_be_visible()
    assert verwalter.input_value("#zaehl-menge") == "10", "vorbelegt mit der Buchmenge"
    assert verwalter.evaluate("() => document.getElementById('zaehl-menge').min") == "1"
    verwalter.fill("#zaehl-menge", "7")
    verwalter.click("#scan-tasten form button.haupt")
    expect(verwalter.locator("p.gut[role=status]")).to_contain_text("✓")
    verwalter.goto(f"/inventar/stueck/{menge}?ks={ks}")
    expect(verwalter.locator("#zaehl-abfrage")).to_be_visible()  # L16a: ein zweiter Scan mit Zahl darf die erste überschreiben
    assert verwalter.input_value("#zaehl-menge") == "7", "vorbelegt mit der zuletzt gezählten Menge"
    expect(verwalter.locator("#statuszeile p").first).to_contain_text("seit")  # gebucht ist nichts: das Stück steht wie vorher

    verwalter.goto("/inventar/verwaltung/inventur")
    zeile = _zeile(verwalter, menge, ks)
    expect(zeile).to_have_count(1)
    expect(zeile.locator("td").nth(2)).to_have_text("10")
    expect(zeile.locator("td").nth(3)).to_have_text("7")
    expect(zeile.locator("td").nth(4)).to_contain_text("Teilweise gesehen")

    verwalter.goto(f"/inventar/stueck/{menge}?ks={ks}")
    verwalter.fill("#zaehl-menge", "12")
    verwalter.click("#scan-tasten form button.haupt")
    expect(verwalter.locator("#hinweis-mehrmenge")).to_contain_text("12 vor Ort, 10 gebucht — Überschuss nicht gebucht; bitte im Büro klären")
    verwalter.goto(f"/inventar/stueck/{menge}?ks={ks}")
    expect(verwalter.locator("#hinweis-mehrmenge")).to_have_count(0)
    verwalter.goto("/inventar/verwaltung/inventur")
    expect(_zeile(verwalter, menge, ks).locator("td").nth(3)).to_have_text("12")

    zeile = _zeile(verwalter, klein, ks)
    expect(zeile.locator("td").nth(4)).to_contain_text("Nicht gesehen")
    verwalter.click(f"#vermisst-{klein} > summary")
    verwalter.click(f"#vermisst-{klein} button.haupt")
    assert verwalter.evaluate(f"() => document.querySelector('#vermisst-{klein} form').checkValidity()") is False, "ohne Grund nicht"
    verwalter.goto(f"/inventar/stueck/{klein}")
    assert verwalter.locator("#statuszeile .warnung").count() == 0, "bis hierher ist nichts von selbst vermisst"
    verwalter.goto("/inventar/verwaltung/inventur")
    verwalter.click(f"#vermisst-{klein} > summary")
    verwalter.fill(f"#grund-{klein}", "Nicht auffindbar")
    with verwalter.expect_navigation(url=re.compile(r"fertig=vermisst")):
        verwalter.click(f"#vermisst-{klein} button.haupt")
    expect(verwalter.locator("#inventur-fertig")).to_contain_text("✓")
    expect(_zeile(verwalter, klein, ks).locator("td").nth(4)).to_contain_text("vermisst")
    verwalter.goto(f"/inventar/stueck/{klein}")
    expect(verwalter.locator("main")).to_contain_text("Nicht auffindbar")


def test_inventur_abschliessen_schreibt_csv_und_loescht_den_stichtag(verwalter: Page) -> None:
    """Sollwert (L16a): „Inventur abschließen“ steht in einem aufklappbaren Block; danach steht „Letzte Inventur: Stichtag …“ mit Download der CSV,
    der Stichtag ist gelöscht (die Seite zeigt wieder die leere Inventur) und die Datei lässt sich laden."""
    verwalter.goto("/inventar/verwaltung/inventur")
    if verwalter.locator("#inventur-leer").count() == 1:  # läuft der Fall allein: einen Stichtag setzen
        verwalter.fill("#inv-tag", verwalter.get_attribute("#inv-tag", "max"))
        with verwalter.expect_navigation(url=re.compile(r"fertig=stichtag")):
            verwalter.click("#inventur-stichtag button.haupt")
    verwalter.click("#inventur-abschliessen > summary")
    with verwalter.expect_navigation(url=re.compile(r"fertig=abgeschlossen")):
        verwalter.click("#inventur-abschliessen button.haupt")
    expect(verwalter.locator("#inventur-fertig")).to_contain_text("✓")
    expect(verwalter.locator("#inventur-letzte")).to_contain_text("Letzte Inventur")
    expect(verwalter.locator("#inventur-leer")).to_be_visible()
    with verwalter.expect_download() as geladen:
        verwalter.click("#inventur-letzte a")
    assert re.fullmatch(r"inventur_\d{4}-\d{2}-\d{2}_\d{8}-\d{6}\.csv", geladen.value.suggested_filename), geladen.value.suggested_filename
