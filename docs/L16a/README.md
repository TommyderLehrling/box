# L16a — Feiertagsregion aus dem Kern, Inventur abschließen, Ablesedatum, Playwright 1.49.1 (Auftrag 08)

Letzte Lieferung von Box. Gebaut und geprüft mit **kern-0.15.5** (Wheel und Steckbrief aus `kern_fuer_box`); `kern_mindestens = "0.15.5"`, `pyproject.toml` `>=0.15.5`. Entwurf, bis VSC es fährt.
**Abschnitt 4 (Nachtrag 08b) ist umgesetzt** — siehe die Zeile „4 kern-0.15.5“ unten. Die Abschnitte 1–3 und 17 sind unverändert aus dem ersten Stand.

```
python -m pytest -q -W error        # im Ordner Inventar; ohne Datenbank → 418 passed, skipped = 0
# mit Datenbank (Kern 0.15.5, PostgreSQL 16): tests/integration ohne test_t_i_6.py → 70 passed, skipped = 0   (Aufruf: tests/integration/laufen.md)
# Browser (Chromium 141 headless, Playwright 1.49.1, Prüf-Box aus tests/browser/box_starten.py) → 31 Fälle, skipped = 0 (Zeitfall siehe unten)   (Aufruf: tests/browser/README.md)
```

Einmal vorher: `pip install -e <pfad>/Inventar[pruefung]` (pytest, httpx, pyflakes, `playwright==1.49.1`) und `python -m playwright install chromium`.

## Was neu ist

| Nr. (Auftrag) | Was | Wo | Geprüft in |
|---|---|---|---|
| 1 Feiertagsregion | Die Region kommt aus dem Kern: `mandant.feiertagsregion` (`<Land>[-<Teil>]`; `DE` bundesweit, `DE-NI` Niedersachsen, leer = keine Feiertage). Die Einstellung `bundesland` ist weg (der Assistent fragt nicht, `startdaten` setzt nichts); Einstellungen zeigt die Region nur an, mit dem Hilfetext, dass die Verwaltung des Betriebs sie im Kern einstellt. Leer: Hinweis `feiertagsregion_fehlt` auf **Einstellungen** und **Kosten** (dort nur im Werktage-Modus, FRAGEN Nr. 4); unbekannt: `feiertagsregion_unbekannt` | `dienstlogik/feiertage.py` (`region`, `hinweis`), `web/verwaltung.py`, `web/kosten.py`, Vorlagen | `test_feiertage_db.py`, `tests/test_vorlagen.py`, Browser `test_verwaltung.py` |
| Rechner | `rein/feiertage.py` ist ein dünner Umschlag um `holidays.country_holidays(land, subdiv=teil or None, years=[…], language="de")`; `holidays==0.60` in `requirements-modul.txt` und `pyproject.toml`. Land und Teil werden getrennt an das Paket gegeben, kein eigenes Kürzel. Die 32 Sollwerte (16 Länder × 2026/2027) laufen jetzt **gegen das Paket**. `ostern()`, `buss_und_bettag()` und die eigenen Tabellen sind weg | `rein/feiertage.py`, `tests/rein/test_feiertage.py` | `tests/rein/test_feiertage.py` (FRAGEN Nr. 2: Brandenburg) |
| Eigene Tage | neue Spalte `inventar.feiertag.jaehrlich` (bool, in `i0001`, die Grundlinie ist offen): ein jährlicher Tag gilt ab seinem Datum in jedem Jahr; abgeschaltet statt gelöscht | `modelle.py`, `migrationen/versions/i0001_grundlinie.py`, `dienstlogik/feiertage.py`, `katalogpflege.py` | `test_feiertage_db.py`, Browser |
| Zählregel | an beiden Stellen im Docstring: `rein.fristen.werktage_zwischen` zählt `(von, bis]`, `dienstlogik.feiertage.werktage` zählt `[von, bis]` | `rein/fristen.py`, `dienstlogik/feiertage.py` | `test_L16_werktage_ohne_und_mit_feiertag` |
| 12 Mehrmenge | Mehr gezählt als gebucht ist erlaubt: Hinweis „n vor Ort, m gebucht — Überschuss nicht gebucht; bitte im Büro klären“ (`#hinweis-mehrmenge`), gebucht wird nichts | `web/transfer.py`, `web/stueck.py`, `web/helfer.py`, `inventar_stueck.html` | `test_inventur_menge_db.py`, Browser `test_inventur.py` |
| 13 Zweiter Scan | Das Mengenfeld wird bei laufender Inventur wieder angeboten (vorbelegt mit der zuletzt gezählten Menge); ein zweiter Scan mit Zahl überschreibt die letzte Sichtung, einer ohne Zahl lässt sie stehen | `dienstlogik/inventur.py` (`zaehlen_abfragen`) | `test_inventur_menge_db.py`, Browser |
| 14 Inventur abschließen | Recht `einstellen`: CSV `export/inventur_<stichtag>_<zeitstempel>.csv` (je Kostenstelle gesehen / nicht gesehen, dazu Vermisst-Vorschlag), Einstellung `inventur_letzte` (`<Stichtag>\|<Pfad>`), Stichtag geleert, Protokoll `inventar.inventur_abgeschlossen`, Download über die Auszug-Route. Der Status `vermisst` wird nicht gesetzt | `dienstlogik/inventur.py` (`abschliessen`, `letzte`), `rein/kostenexport.py`, `dienstlogik/kostenrechnung.py`, `web/inventur.py`, `inventar_verwaltung_inventur.html` | `test_inventur_menge_db.py`, Browser `test_inventur.py` |
| 17 Ablesedatum | optionale 16. Spalte „Ablesedatum“ im Excel-Import (Dateien mit 14 und 15 Spalten werden weiter gelesen): leer = Zeitpunkt des Imports, Vergangenheit erlaubt, Zukunft abgewiesen (`import.fehler.ablesedatum_zukunft`, nicht lesbar: `…_ungueltig`); der Tag gilt als Mittag UTC des Zählerstands | `rein/import_vorlage.py`, `dienstlogik/import_lauf.py`, `dienstlogik/zaehler.py` | `tests/rein/test_import_vorlage.py`, `test_import_zaehler_db.py` |
| 4 kern-0.15.5 | `kern_mindestens`/`pyproject` auf 0.15.5; `Modulbeschreibung.reihenfolge = 30` (`modul.REIHENFOLGE`); `personen_auswahl` fragt `rechte.wer_darf(db, mandant_id=…, baustein="inventar.werkstatt")` — die eigene Rechte-Auswertung ist raus (`BenutzerRecht`-Import mit); **409-Ziele**: alle `hx-target` der Formulare sind kleine Meldezeilen (`#stueck-meldung`, `#katalog-meldung`, `#inventur-meldung`, `#kosten-meldung`, `#werkstatt-meldung`, `#hier-meldung`), kein `HX-Retarget` nötig; die Umgehung in `statisch/inventar.js` ist entfernt (sie hätte doppelt getauscht) | `modul.py`, `dienstlogik/werkstatt.py`, `statisch/inventar.js`, `pyproject.toml` | `tests/test_modul.py` (`kern_mindestens`, `reihenfolge == 30`), `test_werkstatt_db.py` (Vertretungssatz ohne eigenen Baustein), Browser `test_inventur.py` (409 → roter Satz, Seite bleibt) |
| H1 | `pip install -e <Inventar>[pruefung]` in `tests/integration/laufen.md` und `INTEGRATION_VSC.md` | — | — |
| Playwright | `playwright==1.49.1` (Extra `pruefung`, `tests/browser/README.md`) | — | Browser, 31 Fälle |

Nebenbei: Texte `inventar.aktion.inventur_gesehen` und `…inventur_abgeschlossen` ergänzt (der Verlauf des Stücks zeigte für die Sichtung den rohen Schlüssel). `rein/feiertage.py` unterdrückt beim Import die Zukunftswarnung von `holidays` 0.x (die Fassung ist festgelegt, wie die Warnung es empfiehlt) — sonst bricht `pytest -W error` schon beim Import.

## Stand der Läufe

| Lauf | Ergebnis |
|---|---|
| `python -m pytest -q -W error` (ohne Datenbank) | **418 passed**, `skipped = 0` |
| `tests/integration` ohne `test_t_i_6.py` (PostgreSQL 16, Kern 0.15.5) | **70 passed**, `skipped = 0` |
| `tests/browser` (Chromium 141 headless, Treiber Playwright 1.49.1, frische Box) | **31 Fälle**, `skipped = 0` — 30 in der Gesamtfahrt; `test_zz_import_gross` (Liste mit 2.500 Stücken unter 1 s) war darin einmal mit 1,18 s knapp darüber, einzeln auf frischer Box bestanden (38 s) |
| T-I-6 | nicht gefahren (Belegerfassung fehlt Box) |

Playwright 1.49.1: `playwright install chromium` scheitert in der Box (Download von Chromium 131 nicht möglich). Fahrweise: 1.49.1 installiert, `PLAYWRIGHT_BROWSERS_PATH` auf einen Ordner mit `chromium-1148` und `chromium_headless_shell-1148` als Verweise auf das vorhandene Chromium 141. Es lief also der **1.49.1-Treiber mit Chromium 141**, nicht mit dem zu 1.49.1 gehörigen Chromium 131. Firefox und WebKit hat Box nicht gefahren.
