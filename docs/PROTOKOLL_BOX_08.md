# PROTOKOLL BOX 08 — Auftrag 05: Nachbesserung L13a und Lieferung L14 (Werkstatt G4), Stand 10.10.2026

Bezug: `BOX_AUFTRAG_05.md`; `KERN_STECKBRIEF_kern-0.15.4.md`; Antworten GER in `FRAGEN_L13.md`.

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | Wheel 0.15.4 eingesetzt, Steckbrief gelesen; `kern_mindestens` bleibt `0.15.3` | alle Läufe mit 0.15.4; `tests/test_modul.py` |
| 2 | L13a Nr. 1 — Startstandort und Import mit `pflegen` | `test_l13a_db.py` (`buero` legt an, bucht nicht um; Import) |
| 3 | L13a Nr. 3, 4, 6 — Importhinweis, Zählerhinweis, Nachweis inline | `test_pruefungen_db.py`, `test_vorlagen.py` |
| 4 | L13a Nr. 9 — Kachel `rechte` für `pruefen` oder `werkstatt` | `tests/rein/test_kacheln.py`, `test_l13a_db.py` |
| 5 | L13a Nr. 10 — `erinnern` ohne Sitzung vor der Uhrzeit, `hochlaufen(leise=False)` | `tests/test_erinnern.py`, von Hand gestartet (stdout + `digiassistenz-inventar-erinnern.log`), SIGTERM |
| 6 | Pakete und `INTEGRATION_VSC.md` nachgeführt (Pillow nicht gepinnt, `pydyf==0.12.1`, Dockerfile.txt) | Anleitungen |
| 7 | L14 Werkstatt: Posteingang, Rückmeldung (Mail + Vermerk), Reparatur-Vorgang, `in_reparatur`, Zurückziehen mit Grund, Kacheln | `test_werkstatt_db.py` (4 Fälle), `test_vorlagen.py`, `tests/rein/test_werkstatt.py` |
| 8 | Abschnitt 7 nur vorgesehen: Scan-Auflösung an einer Stelle | bestehende Fälle für `/inventar/s/…` in `test_seiten_db.py`, `test_pruefungen_db.py` |

## Stand der Läufe

`python -m pytest -q -W error`: **331 passed**, `skipped = 0`. `tests/integration` (ohne T-I-6): **43 passed**, `skipped = 0` (Kern 0.15.4, PostgreSQL 16.15).

## Nicht gefahren / offen

Docker-Bild, Browser und Kamera, Druck, T-I-6 (VSC); Fragen in `docs/L14/FRAGEN_L14.md`.
