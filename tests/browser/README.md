# Browser-Prüffälle (Playwright) — `tests/browser/`

Die Fälle sprechen mit einer **laufenden Box** im echten Browser. Sie stehen nicht im gewöhnlichen Lauf (`pytest.ini`: `norecursedirs`). Fehlt die Box, ist jeder Fall **rot**, nie übersprungen.
VSC fährt sie auf Chromium und Firefox; der Zoom-Fall auch in WebKit. Box hat **Chromium (headless, Playwright 1.56)** selbst gefahren — Firefox und WebKit sind in der Box nicht eingebaut.

## Aufbau

```
pip install playwright==1.56.0            # oder die Fassung, zu der die Browser auf dem Rechner passen
python -m playwright install chromium firefox webkit     # nur dort, wo das Netz es erlaubt (in der Box: Chromium liegt schon da)

# frische, leere Prüfdatenbank in DB_URL (konfig.env im Arbeitsverzeichnis); Kern 0.15.4 und das Inventar sind eingebaut
DIGIASSISTENZ_WURZEL=$PWD python <pfad>/tests/browser/box_starten.py --port 8765        # baut Ketten, Startdaten, Kostenstellen, vier Konten und startet den Server
```

* `box_starten.py` löscht nichts: ist das Schema `kern` schon da, bricht es ab (`--weiter` startet nur den Server auf einer schon aufgebauten Datenbank).
* Konten (Passwort `Browser-Inventar-2026!`): `verwalter@browser.invalid`, `polier@browser.invalid` (Kostenstellen 70101, 70102), `polier2@browser.invalid` (70102), `buero@browser.invalid` (Vorlage `buero`, alle fünf).
* Kostenstellen `1000 79795 80010 70101 70102`. Die Testdaten (Seed 11, 60 Stück) spielt der erste Fall über Verwaltung → Testdaten ein (`conftest.py`, `_aufbau`).
* Die Sitzung des Kerns ist ein **Secure-Cookie**: darum arbeiten alle Fälle im Browser (nicht mit einem reinen HTTP-Client). Für eine https-Box `BROWSER_BASIS_URL=https://…` setzen; ein selbst signiertes Zertifikat braucht `ignore_https_errors` (in `conftest.py` ergänzen).

## Lauf

```
BROWSER_BASIS_URL=http://127.0.0.1:8765 BROWSER_ENGINES=chromium python -m pytest -q <pfad>/tests/browser -p no:cacheprovider --rootdir=<pfad>/tests/browser -c /dev/null
BROWSER_ENGINES=firefox ...                         # ebenso
BROWSER_ENGINES=webkit ... test_zoom.py             # in WebKit zählt der Zoom-Fall
```

`BROWSER_ENGINES` nimmt eine Liste (`chromium,firefox`). Immer die Zeile `passed/failed/skipped` lesen: `skipped` muss 0 sein. **Eine Fahrt braucht eine frische Box**: `test_zz_import_gross.py` legt 2.500 Stücke an und steht darum zuletzt; die Inventur
(`test_inventur.py`) setzt einen Stichtag.

## Fälle

| Datei | Fall (Nummer aus `INTEGRATION_VSC.md` Abschnitt 4) | Sollwert in Kürze |
|---|---|---|
| `test_oberflaeche.py` | 1 Statuszeile · 2 Tasten gleich hoch · 3 kein Link ohne Recht · 7 Suchfeld 250 ms · 8 Dialoge · 9 Merkmale/Nummernvorschlag · 10 Foto · 14 Startstandort/Büro | je Docstring |
| `test_scan_transfer.py` | 6 Scan-Weg (Eingabe, **Kamera-Attrappe**), Abgang → „Ist hier“ → Eingang, Hier-Seite | Quelle `handy` nur nach Kamera |
| `test_etiketten.py` | 5 Etiketten-PDF (1 Bogen bei 20, 2 bei 25–48) · 11 Probedruck (ohne Papier: A4, 24 je Bogen) | der Druck auf 70 × 36 mm bleibt Handarbeit |
| `test_pruefungen.py` | 12 Fällig-Liste mit Rücksprung (und Hinweis bei zu niedrigem Zählerstand) · 13 Nachweis inline, Textdatei abgewiesen | `Content-Disposition: inline`, `nosniff` |
| `test_werkstatt.py` | Posteingang, Foto der Meldung, Abschluss-Dialog mit Haken und Vorfüll-Skript, Rückmeldung an der Stück-Seite, Zurückziehen mit Grund | Titel ohne Markup |
| `test_kosten.py` | Polier sieht keine Preise · Export und Download (BOM, Anhang, `nosniff`, nur `export/`) · Kostensatz überschreiben · Vergleichszeile | |
| `test_inventur.py` | Stichtag · Mengenabfrage (vorbelegt, nichts gebucht) · „als vermisst“ nur mit Grund | |
| `test_verwaltung.py` | Feiertage und eigene Tage · Zählerstand-Spalte im Import | |
| `test_zoom.py` | 200 % und 400 % Zoom (640/320 px): kein Querlauf der Seiten | in WebKit |
| `test_zz_import_gross.py` | 4 Import mit 2.500 Stücken, danach `/inventar` in unter 1 s | |

**Kamera-Attrappe:** Chromium startet mit `--use-fake-device-for-media-stream --use-fake-ui-for-media-stream` (`conftest.py`). Weil ein `BarcodeDetector` nicht überall da ist, bekommt der Fall einen Ersatz, der den QR-Text liefert. Geprüft wird der Weg
„Bild → Nummer → Stück-Seite mit `art=kamera`“; das echte Erkennen eines Etiketts bleibt ein Versuch am Handy. Firefox und WebKit haben keinen `BarcodeDetector`: dort wird der Rückfall (Eingabefeld, Hinweistext) geprüft.
