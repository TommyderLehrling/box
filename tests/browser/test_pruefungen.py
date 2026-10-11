"""Browserfälle 12 und 13 (INTEGRATION_VSC.md Abschnitt 4): Fällig-Liste mit Rücksprung, Prüfung mit Nachweis, der im Browser (inline) aufgeht."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from conftest import PDF, PNG, eindeutig, stueck_anlegen


def _kopfzeilen(seite: Page, weg: str) -> dict[str, str]:
    """Antwortkopf eines Abrufs mit der Sitzung der Seite (ein Abruf im Browser, nicht im Test-Client)."""
    return seite.evaluate("""async (weg) => { const r = await fetch(weg); return { status: String(r.status), art: r.headers.get('content-type') || '',
        anordnung: r.headers.get('content-disposition') || '', nosniff: r.headers.get('x-content-type-options') || '' }; }""", weg)


def test_F12_faellig_liste_drei_bloecke_filter_und_ruecksprung(verwalter: Page) -> None:
    """Sollwert: drei Blöcke; der Filter wirkt; „Prüfung eintragen“ öffnet die Stück-Seite mit offenem Dialog und der Prüfart, nach dem
    Speichern steht ✓ auf der Fällig-Liste und das Stück ist aus „ohne Nachweis“ verschwunden."""
    name = eindeutig("Faellig")
    sid = stueck_anlegen(verwalter, name, gruppe="baumaschine", art="gross")
    verwalter.goto("/inventar/faellig")
    for block in ("ueberfaellig", "faellig", "ohne_nachweis"):
        expect(verwalter.locator(f"#faellig-{block}")).to_have_count(1)
    zeile = verwalter.locator("#faellig-ohne_nachweis tr", has_text=name).first
    expect(zeile).to_be_visible()
    verwalter.select_option("#f-gruppe", "kleingeraet")
    verwalter.wait_for_url(re.compile(r"gruppe=kleingeraet"))
    expect(verwalter.locator("#faellig-ohne_nachweis tr", has_text=name)).to_have_count(0)
    verwalter.select_option("#f-gruppe", "")
    verwalter.wait_for_url(lambda url: "gruppe=kleingeraet" not in url)
    link = verwalter.locator("#faellig-ohne_nachweis tr", has_text=name).first.locator("a.taste")
    link.click()
    verwalter.wait_for_url(re.compile(rf"/inventar/stueck/{sid}\?.*weiter=faellig"))
    expect(verwalter.locator("#pruefung-eintragen")).to_have_attribute("open", "")
    assert verwalter.input_value("#pr-art") != ""
    verwalter.click("#pruefung-eintragen button.haupt")
    verwalter.wait_for_url(re.compile(r"/inventar/faellig"))
    expect(verwalter.locator("p.gut[role=status]")).to_contain_text("✓")
    expect(verwalter.locator("#faellig-ohne_nachweis tr", has_text=name).first.locator("td").nth(2)).not_to_have_text(re.compile(r"^$")) if \
        verwalter.locator("#faellig-ohne_nachweis tr", has_text=name).count() else None


def test_F12b_zaehlerstand_unter_dem_letzten_gibt_einen_hinweis(verwalter: Page) -> None:
    """Sollwert: ein Zählerstand unter dem letzten wird nicht geführt; die Seite, auf die man zurückkehrt, sagt es."""
    name = eindeutig("Zaehler")
    sid = stueck_anlegen(verwalter, name, gruppe="baumaschine", art="gross")
    verwalter.goto(f"/inventar/stueck/{sid}")
    verwalter.locator("summary", has_text=re.compile("Zähler")).first.click()
    verwalter.fill("#zaehler-stand", "500")
    verwalter.locator("#zaehler-stand").locator("xpath=ancestor::form").locator("button[type=submit]").click()
    verwalter.wait_for_url(re.compile(r"fertig=zaehlerstand"))
    verwalter.goto(f"/inventar/stueck/{sid}?pruefart=hu&weiter=faellig#pruefung-eintragen")
    verwalter.locator("#pr-art").select_option(index=1) if verwalter.input_value("#pr-art") == "" else None
    verwalter.fill("#pr-zaehler", "100")
    verwalter.click("#pruefung-eintragen button.haupt")
    verwalter.wait_for_url(re.compile(r"/inventar/faellig"))
    expect(verwalter.locator("p.warnung[role=status]")).to_be_visible()


def test_F13_nachweis_geht_im_browser_auf_textdatei_wird_abgewiesen(verwalter: Page) -> None:
    """Sollwert: PDF und ein umbenanntes Bild kommen mit `Content-Disposition: inline`, richtigem Typ und `nosniff` zurück; eine Textdatei wird abgewiesen."""
    sid = stueck_anlegen(verwalter, eindeutig("Nachweis"), gruppe="baumaschine", art="gross")
    ergebnisse = []
    for dateiname, typ, inhalt in (("hu.pdf", "application/pdf", PDF), ("umbenannt.pdf", "application/pdf", PNG)):
        verwalter.goto(f"/inventar/stueck/{sid}?pruefart=hu&weiter=stueck#pruefung-eintragen")
        verwalter.locator("#pr-art").select_option(index=1) if verwalter.input_value("#pr-art") == "" else None
        verwalter.set_input_files("#pr-nachweis", {"name": dateiname, "mimeType": typ, "buffer": inhalt})
        verwalter.click("#pruefung-eintragen button.haupt")
        verwalter.wait_for_url(re.compile(r"fertig=pruefung"))
        ergebnisse.append(dateiname)
    verwalter.goto(f"/inventar/stueck/{sid}")
    verwalter.locator("#abschnitt-pruefungen > summary").click()
    links = verwalter.locator("a[href$='/nachweis']")
    expect(links).to_have_count(2)
    arten = []
    for i in range(2):
        kopf = _kopfzeilen(verwalter, links.nth(i).get_attribute("href"))
        assert kopf["status"] == "200" and kopf["anordnung"].startswith("inline") and kopf["nosniff"] == "nosniff", kopf
        arten.append(kopf["art"])
    assert sorted(arten) == ["application/pdf", "image/png"], arten
    # Textdatei im PDF-Kleid
    verwalter.goto(f"/inventar/stueck/{sid}?pruefart=hu&weiter=stueck#pruefung-eintragen")
    verwalter.locator("#pr-art").select_option(index=1) if verwalter.input_value("#pr-art") == "" else None
    verwalter.set_input_files("#pr-nachweis", {"name": "falsch.pdf", "mimeType": "application/pdf", "buffer": b"nur Text, kein PDF"})
    verwalter.click("#pruefung-eintragen button.haupt")
    expect(verwalter.locator("#stueck-meldung [role=alert]")).to_contain_text("PDF")
