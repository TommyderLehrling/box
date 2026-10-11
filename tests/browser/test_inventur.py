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
    assert verwalter.locator("#zaehl-abfrage").count() == 0, "schon gesehen: kein zweites Mal fragen"
    expect(verwalter.locator("#statuszeile p").first).to_contain_text("seit")  # gebucht ist nichts: das Stück steht wie vorher

    verwalter.goto("/inventar/verwaltung/inventur")
    zeile = _zeile(verwalter, menge, ks)
    expect(zeile).to_have_count(1)
    expect(zeile.locator("td").nth(2)).to_have_text("10")
    expect(zeile.locator("td").nth(3)).to_have_text("7")
    expect(zeile.locator("td").nth(4)).to_contain_text("Teilweise gesehen")

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
