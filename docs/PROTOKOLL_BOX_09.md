# PROTOKOLL BOX 09 — Auftrag 06: Nachbesserung L14a und Lieferung L15 (Kosten G5), Stand 11.10.2026

Bezug: `BOX_AUFTRAG_06.md`; Antworten GER in `FRAGEN_L14.md`. Kern bleibt 0.15.4.

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | L14a Nr. 3 — eine Mailfunktion `benachrichtigen`, Mail an den Melder beim Erledigen und Zurückziehen, `erinnerungen.py` darüber | `tests/test_benachrichtigen.py`, `test_werkstatt_db.py` (Zeile `wartend`, `mandant_id`), `test_pruefungen_db.py` |
| 2 | L14a Nr. 5 — Hand bleibt Hand (`status_grund = "reparatur:<id>"`) | `tests/rein/test_werkstatt.py` (W9), `test_werkstatt_db.py` |
| 3 | L14a Nr. 6 — Pflichtangaben beim Abschließen, neue Spalten `arbeit`, `durchgefuehrt_von` in `i0001` | `test_werkstatt_db.py`, `test_migration_gegen_modelle.py`, `tests/rein/test_werkstatt.py` (W12, W13) |
| 4 | L14a Nr. 7 — Haken „Meldung damit erledigen“, Fehlerfall Mail | `test_werkstatt_db.py` (mit Haken, ohne Haken, Fehlerfall) |
| 5 | L14a Nr. 9 — Foto am Stück | `test_werkstatt_db.py` |
| 6 | Hilfetext der Werkstatt-Seite; `laufen.md`: „i0001 offen“ | `tests/test_texte.py` |
| 7 | L15 — Kostensätze (wirksamer Satz, je Stück überschreiben, Kalender-/Werktage) | `tests/rein/test_kosten_l15.py`, `test_kosten_db.py` |
| 8 | L15 — Seite `/inventar/kosten`: je Kostenstelle, je Stück, Miete gegen eigen, Export | `test_kosten_db.py`, `test_vorlagen.py` |
| 9 | L15 — Zählerstände (Quelle Werkstatt, Hinweis), Stück-Seite, Rechte (Polier sieht keine Preise) | `test_kosten_db.py` |
| 10 | L15 — Stichtags-Inventur (Vorschlag, nie automatisch) | `test_kosten_db.py` |
| 11 | Abschnitt 7 (Etikett-Code) weiter nur vorgesehen | — |

## Stand der Läufe

`python -m pytest -q -W error`: **360 passed**, `skipped = 0`. `tests/integration` (ohne T-I-6): **56 passed**, `skipped = 0` (Kern 0.15.4, PostgreSQL 16.15, Python 3.12.3).

## Nicht gefahren / offen

Docker-Bild, Browser und Kamera, Druck, T-I-6, der Prozess `erinnern` im Container (VSC); das Skript zum Vorfüllen der Rückmeldung (`statisch/inventar.js`) ist im Browser nicht gefahren.
Fragen in `docs/L15/FRAGEN_L15.md` (22).

Aufgefallen, nicht angefasst (nicht von diesem Auftrag): ungenutzte Importe in `web/kostenstelle.py`, `rein/bestand.py`, `dienstlogik/stueck.py`, `dienstlogik/laden.py` (pyflakes).
