"""Kosten (G5, L15/L15a): Polier sieht keine Preise, Export und Download der CSV-Auszüge, Kostensatz je Stück überschreiben, Vergleichszeile geplant/angefallen."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from conftest import eindeutig, stueck_anlegen


def test_polier_sieht_keine_preise_und_keine_kosten(polier: Page, verwalter: Page) -> None:
    """Sollwert: der Polier hat keinen Menüpunkt „Kosten“, die Seite antwortet 403, auf der Stück-Seite steht kein Preis und kein Kostenabschnitt;
    das Konto mit `kosten_sehen` (Verwalter) sieht beides."""
    sid = stueck_anlegen(verwalter, eindeutig("Preis"), kaufpreis="98765")
    polier.goto("/inventar")
    assert polier.locator("header a[href='/inventar/kosten']").count() == 0
    assert polier.goto("/inventar/kosten").status == 403
    polier.goto(f"/inventar/stueck/{sid}")
    assert polier.locator("#abschnitt-kosten").count() == 0 and "98.765" not in polier.content() and "98765" not in polier.content()
    verwalter.goto(f"/inventar/stueck/{sid}")
    verwalter.locator("#abschnitt-kosten > summary").click()
    expect(verwalter.locator("#abschnitt-kosten")).to_contain_text("98.765")


def test_kosten_export_und_download(verwalter: Page) -> None:
    """Sollwert: „Als CSV exportieren“ meldet ✓ und nennt die Datei; der Download kommt als Anhang (UTF-8 mit BOM, Semikolon) zurück; ein zweiter Export
    legt eine zweite Datei an (nichts wird überschrieben); die Datei bleibt im Ordner."""
    verwalter.goto("/inventar/kosten")
    vorher = verwalter.locator("a[href^='/inventar/kosten/auszug/']").count()
    for i in range(2):
        anzahl = verwalter.locator("a[href^='/inventar/kosten/auszug/']").count()
        verwalter.locator("#kosten-kostenstelle form.inline button").click()
        expect(verwalter.locator("a[href^='/inventar/kosten/auszug/']")).to_have_count(anzahl + 1, timeout=15_000)
        expect(verwalter.locator("#kosten-fertig")).to_contain_text("✓")
        verwalter.wait_for_timeout(1100)  # der Name trägt den Zeitstempel auf die Sekunde
    links = verwalter.locator("a[href^='/inventar/kosten/auszug/']")
    expect(links).to_have_count(vorher + 2, timeout=15_000)
    with verwalter.expect_download() as geladen:
        links.last.click()
    datei = geladen.value
    assert datei.suggested_filename.startswith("kosten_kostenstelle_") and datei.suggested_filename.endswith(".csv")
    inhalt = open(datei.path(), "rb").read()
    assert inhalt.startswith(b"\xef\xbb\xbf") and b";" in inhalt.splitlines()[0]
    assert verwalter.locator("a[href^='/inventar/kosten/auszug/']").count() == vorher + 2, "die Datei bleibt im Ordner"
    kopf = verwalter.evaluate("async (w) => { const r = await fetch(w); return [r.status, r.headers.get('content-disposition'), r.headers.get('x-content-type-options')]; }",
                              links.first.get_attribute("href"))
    assert kopf[0] == 200 and kopf[1].startswith("attachment") and kopf[2] == "nosniff"
    fremd = verwalter.evaluate("async () => (await fetch('/inventar/kosten/auszug/..%2Fkonfig.env')).status")
    assert fremd in (400, 404, 409), "nur Dateien aus export/"


def test_kostensatz_je_stueck_ueberschreiben_und_vergleichszeile(verwalter: Page) -> None:
    """Sollwert: mit `kosten_pflegen` ersetzt „Kostensatz überschreiben“ den Satz der Gruppe für dieses Stück (Herkunft „Stück“);
    die Zeile „Reparaturen: geplant / angefallen“ steht da, ohne Summe."""
    sid = stueck_anlegen(verwalter, eindeutig("Satz"), gruppe="schalung_ruestung", art="menge", menge="5", kaufpreis="1000")
    verwalter.goto(f"/inventar/stueck/{sid}")
    verwalter.locator("#abschnitt-kosten > summary").click()
    expect(verwalter.locator("#kosten-reparaturen-vergleich")).to_contain_text("/")
    assert "Gruppe" in verwalter.locator("#abschnitt-kosten > p.klein").first.inner_text()
    verwalter.click("#dialog-kostensatz > summary")
    verwalter.fill("#ks-dauer", "48")
    verwalter.fill("#ks-zins", "5")
    verwalter.fill("#ks-rep", "3")
    with verwalter.expect_navigation(url=re.compile(r"fertig=")):
        verwalter.click("#dialog-kostensatz button.haupt")
    verwalter.locator("#abschnitt-kosten > summary").click()
    assert "Stück" in verwalter.locator("#abschnitt-kosten > p.klein").first.inner_text()
