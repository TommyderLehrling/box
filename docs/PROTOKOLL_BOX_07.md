# PROTOKOLL BOX 07 — Auftrag 04 (Abschnitt 1–4) und Lieferung L13 (Prüfungen G3), Stand 10.10.2026

Bezug: `BOX_AUFTRAG_04.md`; `KERN_STECKBRIEF_kern-0.15.3.md`; Antworten GER in `FRAGEN_L10…L12`.

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | Umstellung auf Wheel 0.15.3, `kern_mindestens` | `tests/test_modul.py`; alle Läufe mit 0.15.3 |
| 2 | Antworten L10–L12 umgesetzt (Dialog, `kosten_pflegen`, Scan-Quelle, Startstandort, Pfadliste, `werktage`-Hinweis) | `test_pruefungen_db.py`, `test_vorlagen.py` |
| 3 | `erinnern` als Modulprozess | `test_erinnern.py` (ohne DB), Tick gegen die Datenbank, von Hand gestartet und mit SIGTERM beendet |
| 4 | Pakete/Systempakete/Nicht-Superuser-Satz | Anleitungen, `docker/Dockerfile` (nicht gebaut) |
| 5 | L13: fällig-Liste, Prüfung eintragen mit Nachweis, Prüfarten je Gruppe/Stück, Erinnerung, Ampel | `test_pruefungen_db.py` (8 Fälle), `test_vorlagen.py` |

## Stand der Läufe

`python -m pytest -q -W error`: **317 passed**, `skipped = 0`. `tests/integration` (ohne T-I-6): **36 passed**, `skipped = 0` (Kern 0.15.3, PostgreSQL 16.15).

## Nicht gefahren / offen

Docker-Bild, `digiassistenz_kern.start` mit `prozesse`, Browser und Kamera, Druck; Fragen in `docs/L13/FRAGEN_L13.md` (vor allem Nr. 1).
