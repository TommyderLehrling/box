# PROTOKOLL BOX 10 — Auftrag 07: Nachbesserung L15a und Lieferung L16 (Feiertage, Mengenabfrage, Zählerstand-Import, Browser-Prüffälle), Stand 11.10.2026

Bezug: `BOX_AUFTRAG_07.md`; Antworten GER in `FRAGEN_L15.md` („Antworten GER“). Kern bleibt 0.15.4. Die mit ⏳ markierten Punkte (CD/VSC lesen gegen) sind gebaut wie angegeben; Korrekturen kämen als Nachtrag 07b.

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | L15a Nr. 3 — „✉ nicht zugestellt“ an der Werkstatt-Zeile | `test_werkstatt_db.py` |
| 2 | L15a Nr. 6 — Personen-Auswahl: Konten mit `inventar.werkstatt` zuerst, eine Abfrage | `test_werkstatt_db.py` |
| 3 | L15a Nr. 11 — „Stand der Parameter“ | `test_kosten_db.py` |
| 4 | L15a Nr. 15 — Vergleichszeile geplant / angefallen | `tests/rein/test_kosten_l15.py`, `test_kosten_db.py` |
| 5 | L15a Nr. 17 — Download der Auszüge | `test_kosten_db.py` (inkl. Pfadangriffe), Browser `test_kosten.py` |
| 6 | pyflakes: Importe aufgeräumt, Test in `tests/test_regeln.py` | `tests/test_regeln.py` |
| 7 | L16 Feiertage — `rein/feiertage.py`, Tabelle `inventar.feiertag` (`i0001`), `dienstlogik/feiertage.py`, Einstellung `bundesland`, eigene Tage, Wirkung auf Vorhaltung, Transfer-Frist, Kachel, Erinnerung | `tests/rein/test_feiertage.py` (32 Sollwerte: 16 Länder × 2026/2027, Ostern, Buß- und Bettag), `test_feiertage_db.py` (3), Browser `test_verwaltung.py` |
| 8 | L16 Mengenabfrage bei laufender Inventur | `test_inventur_menge_db.py` (3), `tests/test_vorlagen.py`, Browser `test_inventur.py` |
| 9 | L16 Zählerstand im Excel-Import | `tests/rein/test_import_vorlage.py` (3 neu), `test_import_zaehler_db.py` (2), Browser `test_verwaltung.py` |
| 10 | L16 Browser-Prüffälle unter `tests/browser/` (29), `box_starten.py`, `README.md` | Chromium headless selbst gefahren: 29 passed |
| 11 | Funde im Browser behoben: 409 wird nicht getauscht · `<script>` im Titelblock der Werkstatt · Export-Weiterleitung mit Fragment · schmale Bildschirme | `tests/test_vorlagen.py` (2 neu), Browser `test_werkstatt.py`, `test_kosten.py`, `test_zoom.py` |
| 12 | Abschluss: `README.md` (Wurzel), `INTEGRATION_VSC.md` final, `laufen.md` final, `docs/L16/*`, dieses Protokoll | — |
| 13 | Lieferung „komplett“: alle 197 Dateien, die seit L10 geändert wurden, flach mit Sortiertabelle | `00_INFO_FUER_GER.md` |
| 14 | Abschnitt 7 (Etikett-Code) weiter nur vorgesehen | — |

## Stand der Läufe

`python -m pytest -q -W error`: **412 passed**, `skipped = 0`. `tests/integration` (ohne T-I-6): **66 passed**, `skipped = 0`. `tests/browser` (Chromium 141 headless, Playwright 1.56, frische Prüf-Box): **29 passed**, `skipped = 0`
(Kern 0.15.4, PostgreSQL 16.15, Python 3.12.3).

## Nicht gefahren / offen

Docker-Bild, Firefox und WebKit, das Erkennen eines echten QR-Etiketts mit der Handykamera, Probedruck auf Etikettenpapier, T-I-6 (Belegerfassung fehlt Box), der Prozess `erinnern` im Container (VSC); die Browser-Fälle auf Firefox/WebKit (VSC).
Fragen und Funde in `docs/L16/FRAGEN_L16.md`.

Verbraucht: rund 0,7 Mio. Tokens dieses Auftrags (L15a, Feiertage, Mengenabfrage, Zählerstand-Import, Browser-Fälle, Abschluss); Rest beim Abschluss rund 14,3 Mio.
