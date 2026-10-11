"""Verwaltung (L16): Feiertage und eigene freie Tage in den Einstellungen; Zählerstand-Spalte im Excel-Import."""

from __future__ import annotations

import re
import uuid

from openpyxl import load_workbook
from playwright.sync_api import Page, expect


def test_feiertage_bundesland_und_eigene_tage(verwalter: Page) -> None:
    """Sollwert: Standard ohne Bundesland zeigt „keine Feiertage“; mit Sachsen steht der Buß- und Bettag 18.11.2026 in der Liste (Fronleichnam nicht);
    ein eigener Tag lässt sich eintragen, abschalten und wieder einschalten; ein ungültiges Datum wird mit einem Satz abgewiesen."""
    verwalter.goto("/inventar/verwaltung/einstellungen?jahr=2026")
    assert verwalter.input_value("#e-bundesland") in ("", "SN")
    verwalter.select_option("#e-bundesland", "SN")
    with verwalter.expect_navigation(url=re.compile(r"fertig=")):
        verwalter.click("form[action='/inventar/verwaltung/einstellungen'] button.haupt")
    verwalter.goto("/inventar/verwaltung/einstellungen?jahr=2026")
    liste = verwalter.locator("#freie-tage-liste")
    expect(liste).to_contain_text("Buß- und Bettag")
    expect(liste.locator("tr", has_text="Buß- und Bettag")).to_contain_text("18.11.2026")
    expect(liste).not_to_contain_text("Fronleichnam")
    expect(liste).to_contain_text("Tag der Deutschen Einheit")

    name = "Betriebsausflug"
    verwalter.fill("#t-datum", "2026-06-12")
    verwalter.fill("#t-bez", name)
    with verwalter.expect_navigation(url=re.compile(r"fertig=")):
        verwalter.click("form[action='/inventar/verwaltung/einstellungen/tage']:has(#t-datum) button.haupt")
    verwalter.goto("/inventar/verwaltung/einstellungen?jahr=2026")
    expect(verwalter.locator("#eigene-tage")).to_contain_text(name)
    expect(verwalter.locator("#freie-tage-liste")).to_contain_text("12.06.2026")
    zeile = verwalter.locator("#eigene-tage tr", has_text=name)
    with verwalter.expect_navigation(url=re.compile(r"fertig=")):
        zeile.locator("button").click()
    verwalter.goto("/inventar/verwaltung/einstellungen?jahr=2026")
    expect(verwalter.locator("#freie-tage-liste")).not_to_contain_text("12.06.2026")
    expect(verwalter.locator("#eigene-tage tr", has_text=name)).to_have_class(re.compile("leise"))
    with verwalter.expect_navigation(url=re.compile(r"fertig=")):
        verwalter.locator("#eigene-tage tr", has_text=name).locator("button").click()
    verwalter.goto("/inventar/verwaltung/einstellungen?jahr=2026")
    expect(verwalter.locator("#freie-tage-liste")).to_contain_text("12.06.2026")
    # zurück auf „keines“: danach zählen wieder nur Montag bis Freitag (der eigene Tag bleibt)
    verwalter.select_option("#e-bundesland", "")
    with verwalter.expect_navigation(url=re.compile(r"fertig=")):
        verwalter.click("form[action='/inventar/verwaltung/einstellungen'] button.haupt")
    verwalter.goto("/inventar/verwaltung/einstellungen?jahr=2026")
    expect(verwalter.locator("#freie-tage-liste")).not_to_contain_text("Buß- und Bettag")


def test_import_zaehlerstand_spalte(verwalter: Page, tmp_path) -> None:
    """Sollwert: die Vorlage hat die Spalte „Zählerstand“; ein Stand in der Datei erscheint im Prüfbericht („Zählerstände aus der Datei: 1“), für ein Stück
    ohne Zähler steht der Hinweis „keinen Zähler“; nach dem Einspielen steht der Stand an der Stück-Seite."""
    verwalter.goto("/inventar/verwaltung/import")
    with verwalter.expect_download() as geladen:
        verwalter.click("a[href='/inventar/verwaltung/import/vorlage']")
    vorlage = tmp_path / "vorlage.xlsx"
    geladen.value.save_as(vorlage)
    mappe = load_workbook(vorlage)
    blatt = mappe["Inventar"]
    kopf = [z.value for z in blatt[1]]
    assert "Zählerstand" in kopf
    blatt.delete_rows(2, blatt.max_row)
    zahl = 10_000 + uuid.uuid4().int % 80_000  # eine Nummer, die es in dieser Box noch nicht gibt
    gross, klein = f"BM-{zahl:05d}", f"KG-{zahl:05d}"
    for z in ({"Inventarnummer": gross, "Bezeichnung": "Import Bagger", "Gruppe": "baumaschine", "Art": "gross", "Kostenstelle": 70101, "Zählerstand": 1234},
              {"Inventarnummer": klein, "Bezeichnung": "Import Klein", "Gruppe": "kleingeraet", "Art": "klein", "Kostenstelle": 70101, "Zählerstand": 5}):
        blatt.append([z.get(name) for name in kopf])
    datei = tmp_path / "zaehler.xlsx"
    mappe.save(datei)
    verwalter.set_input_files("#import-datei", str(datei))
    verwalter.click("main form[enctype='multipart/form-data'] button.haupt")
    expect(verwalter.locator("#import-zaehlerstaende")).to_contain_text("1")
    expect(verwalter.locator("main")).to_contain_text("keinen Zähler")
    verwalter.click("main form:has(input[value=einspielen]) button.haupt")
    expect(verwalter.locator("p.gut[role=status]")).to_be_visible()
    verwalter.goto("/inventar?ansicht=liste")
    verwalter.locator("#inv-q").press_sequentially(gross, delay=15)
    verwalter.locator("#inventar-liste a", has_text=gross).click()
    verwalter.locator("summary", has_text=re.compile("Zähler")).first.click()
    expect(verwalter.locator("main")).to_contain_text("1234")
    expect(verwalter.locator("main")).to_contain_text("Import")
