# PROTOKOLL BOX 11 — Auftrag 08: Lieferung L16a (Feiertagsregion aus dem Kern, Inventur abschließen, Ablesedatum), Stand 11.10.2026

Bezug: `BOX_AUFTRAG_08.md`; Antworten GER in `FRAGEN_L15.md` und `FRAGEN_L16.md`. Kern bleibt 0.15.4. Abschnitt 4 (kern-0.15.5) nicht umgesetzt, weil 0.15.5 nicht in `kern_fuer_box` lag.

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | Feiertagsregion aus `mandant.feiertagsregion`; Einstellung `bundesland` entfernt; Hinweis `feiertagsregion_fehlt` / `_unbekannt` auf Einstellungen und Kosten | `test_feiertage_db.py`, `tests/test_vorlagen.py`, Browser `test_verwaltung.py` |
| 2 | Rechner: `rein/feiertage.py` = Umschlag um `holidays==0.60`; 32 Sollwerte gegen das Paket; BB mit Oster-/Pfingstsonntag | `tests/rein/test_feiertage.py` |
| 3 | `inventar.feiertag.jaehrlich` (`i0001`), Haken in den Einstellungen | `test_feiertage_db.py`, Browser |
| 4 | Zählregeln an beiden Stellen dokumentiert | `test_L16_werktage_ohne_und_mit_feiertag` |
| 5 | Nr. 12 Mehrmenge-Hinweis, Nr. 13 zweiter Scan überschreibt | `test_inventur_menge_db.py`, Browser |
| 6 | Nr. 14 „Inventur abschließen“ (CSV, `inventur_letzte`, Stichtag leer, Protokoll, Download) | `test_inventur_menge_db.py`, Browser |
| 7 | Nr. 17 Ablesedatum (16. Spalte) | `test_import_vorlage.py`, `test_import_zaehler_db.py` |
| 8 | H1 `pip install -e <Inventar>[pruefung]`; Playwright 1.49.1 | `laufen.md`, `INTEGRATION_VSC.md`, `tests/browser/README.md` |
| 9 | Abschnitt 4 nicht umgesetzt (kern-0.15.5 fehlt) | `FRAGEN_L16a.md` Nr. 1 |
| 10 | Abschluss: `README.md`, `INTEGRATION_VSC.md`, `laufen.md`, `docs/L16a/*`, dieses Protokoll; Lieferung „komplett“ flach | `00_INFO_FUER_GER.md` |

## Stand der Läufe

| Lauf | Ergebnis |
|---|---|
| `python -m pytest -q -W error` (ohne Datenbank) | **417 passed**, `skipped = 0` |
| `tests/integration` ohne `test_t_i_6.py` | **69 passed**, `skipped = 0` |
| `tests/browser` (Chromium 141, Treiber Playwright 1.49.1) | **30 passed**, `skipped = 0` |

Guthaben: zu Beginn von L16a rund 14,9 Mio. Tokens, jetzt rund 14,6 Mio.
