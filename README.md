# DOKON Inventar — `digiassistenz_inventar` (Modul `inventar`, Entwurf L14)

Geräteverwaltung einer Baufirma als Modul des Kerns `digiassistenz_kern` ≥ 0.15.3 (gebaut und geprüft mit 0.15.4): Schema `inventar`, Konto `inventar_nutzer`,
Kette `i0001…`, Bausteine `inventar.*`. Die Fachlogik liegt in `digiassistenz_inventar/rein/` (reine Module, keine Datenbank).
**Entwurf**, bis VSC das Modul auf dem echten Kern fährt (Aufträge 01–03, Lieferungen L1–L14, Aufträge 04 und 05).

## Prüfen

```
python -m pytest -q                    # im Ordner Inventar; ohne Datenbank; erwartet: 331 passed, skipped = 0
```

Mit Datenbank (Kern 0.15.4 als Wheel, PostgreSQL 16 mit contrib, `pg_dump` 16; Anleitung `tests/integration/laufen.md`):

```
cd <wurzel mit konfig.env> && DIGIASSISTENZ_WURZEL=$PWD python -m pytest <pfad>/tests/integration/test_t_i_5.py \
    <pfad>/tests/integration/test_dienstlogik_db.py <pfad>/tests/integration/test_migration_gegen_modelle.py \
    <pfad>/tests/integration/test_seiten_db.py <pfad>/tests/integration/test_pruefungen_db.py \
    <pfad>/tests/integration/test_l13a_db.py <pfad>/tests/integration/test_werkstatt_db.py
```

Stand Box (Python 3.12.3, Kern-Wheel 0.15.4, PostgreSQL 16.15): `tests` 331 passed, `tests/integration` 43 passed (T-I-5, Anwendungsfälle,
Modelle gegen Kette, Seiten, Prüfungen, L13a, Werkstatt), jeweils `skipped = 0`. **T-I-6** (mit Belegerfassung) hat Box nicht gefahren — sie fehlt ihr;
VSC hat es nach L13 mit 0.15.3 gefahren (3 passed).

## Aufbau

| Ort | Inhalt |
|---|---|
| `pyproject.toml` | Einstiegspunkt `digiassistenz.module` → `inventar`, `digiassistenz-kern>=0.15.3` |
| `digiassistenz_inventar/modul.py` | die Modulbeschreibung (Menü, Erweiterungen, Ereignis, Suche, Verbindung) |
| `rechte.py`, `modelle.py` | elf Bausteine, Vorlagen-Ergänzung, Nachzug · 18 Tabellen |
| `migration.py`, `migrationen/` | Kette `i0001_grundlinie` (Rolle, Schema, alle Tabellen), Kern zuerst |
| `startdaten.py` | Kataloge, Kostensatz-Vorschläge, Einstellungen — wiederholbar, ohne Stücke |
| `dienstlogik/` | Anwendungsfälle: Nummer, Stück, Transfer, Import, Testdaten, Etiketten, Prüfung, Erinnerung, Werkstatt |
| `dienste.py`, `kacheln.py` | Dienste `bestand` und `stueck` (noch nicht beim Kern angemeldet), Kacheln |
| `erinnern.py` | Modulprozess (`prozesse`): der Kern startet ihn neben dem Webserver; arbeitet einmal täglich zur Uhrzeit `erinnern_um` |
| `web/`, `vorlagen/`, `statisch/` | Seiten Liste, Stück, Verwaltung, Hier, Scan, Transfer, Fällig-Liste und Prüfungen (L11–L13), Werkstatt (L14), Reiter an Kern-Seiten |
| `texte/de.json` | alle Texte; `app.modul` setzt das Inventar nicht (Steckbrief 11) |
| `rein/` | die reinen Module mit Katalogen (`rein/daten`) — Prüffälle in `tests/rein` |
| `compose.yml`, `docker/`, `konfig.env.beispiel` | Aufbau mit Docker (von Box nicht gebaut). `docker/Dockerfile` ist ein Entwurf; auf Drive liegt er als `docker/Dockerfile.txt` (VSC benennt beim Einbau um) |
| `INTEGRATION_VSC.md` | was VSC tut |
| `docs/` | README und `FRAGEN_L<n>.md` je Lieferung, Protokolle |

Regeln: nur öffentliche Kern-Namen, kein anderes Modul, keine Löschung, keine deutschen Sätze im Code (Texte in `de.json`).
Die Wörter `beleg…` kommen im Code nicht vor (T-K-12d): Reparaturkosten aus einer Rechnung heißen `rechnung`.
