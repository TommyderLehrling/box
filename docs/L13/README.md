# L13 — Umstellung auf kern-0.15.3 (Auftrag 04, Abschnitt 1–4) und Prüfungen (G3)

## Teil 1: Auftrag 04, Abschnitt 1–4

| Was | Stand |
|---|---|
| Kern 0.15.3 | `digiassistenz-kern>=0.15.3`, `Modulbeschreibung(kern_mindestens="0.15.3")` aus `KERN_MINDESTFASSUNG`; Steckbrief 0.15.3 gilt |
| Antworten L10–L12 | Prüfung-eintragen-Dialog an der Stück-Seite · Kaufdaten ändern nur mit `kosten_pflegen` (Vorlage `einkauf` bekommt es) · Scan-Quelle `handy` nur aus der Kamera (`art=kamera`) · Startstandort beim Anlegen Pflicht (`required` an der Wahl) · `werktage` mit Hinweistext · `import/` in der Pfadliste |
| `erinnern` als Prozess | `prozesse=("digiassistenz_inventar.erinnern",)`; läuft dauerhaft, einmal täglich zu `erinnern_um` (Standard 06:00 Ortszeit), SIGTERM sauber, idempotent je Tag, Uhr/Schlaf einhängbar |
| Pakete | `INTEGRATION_VSC.md` (eine Fassung je Paket je Box, Systempakete), Kommentar im `docker/Dockerfile` |
| `laufen.md` | Nicht-Superuser-Satz übernommen |

## Teil 2: L13 Prüfungen

`/inventar/faellig` mit den Blöcken überfällig · fällig (gelb) · ohne Nachweis, Filter nach Prüfart, Gruppe, Kostenstelle; je Zeile „Prüfung eintragen“.
Der Dialog liegt an der Stück-Seite (Datum, Ergebnis, intern/extern, Prüfer als Benutzer, Name oder Lieferant, Zählerstand, Nachweis PDF/JPG/PNG, Bemerkung).
Nachweise liegen unter `stamm/<nr>/pruefungen/`, die SHA-256 steht an der Prüfung, der Abruf prüft sie. Prüfarten je Gruppe (Intervall überschreibbar, Verwaltung) und je Stück
(überschreiben, abschalten, hinzunehmen; Stück-Seite). Erinnerung „Prüfung fällig in n Tagen / überfällig“ an die Funktion `werkstatt` im Prozess.

```
python -m pytest -q -W error        # im Ordner Inventar; ohne Datenbank → 317 passed, skipped = 0
# mit Datenbank (Kern 0.15.3, PostgreSQL 16): tests/integration ohne test_t_i_6.py → 36 passed, skipped = 0
```

## Geänderte und neue Dateien

| Pfad | Was |
|---|---|
| `pyproject.toml`, `modul.py`, `rechte.py`, `startdaten.py` | 0.15.3, `kern_mindestens`, `prozesse`, `einkauf` + `kosten_pflegen`, neue Einstellungen |
| `erinnern.py`, `rein/zeitplan.py`, `dienstlogik/erinnerungen.py` | Modulprozess, Tagesplan, Erinnerung Prüfungen |
| `dateien.py`, `dienstlogik/pruefung.py`, `dienstlogik/faellig.py` | Nachweis, Prüfung eintragen/lesen, Prüfarten je Stück, Fällig-Liste |
| `dienstlogik/stueck.py`, `pflege.py`, `import_lauf.py`, `katalogpflege.py`, `stueckseite.py` | Kaufdaten-Recht, Import ohne Kaufdaten, Gruppen-Intervall, Uhrzeit, Prüferanzeige |
| `web/pruefungen.py`, `web/pruefdialog.py`, `web/__init__.py`, `web/seiten.py`, `web/stueck.py`, `web/transfer.py`, `web/verwaltung.py` | Seiten und Wege |
| `vorlagen/inventar_faellig.html`, `inventar_stueck.html`, `inventar_stueck_form.html`, `inventar_verwaltung_pruefarten.html`, `inventar_verwaltung_einstellungen.html`, `statisch/inventar.js` | Oberfläche |
| `texte/de.json` | **alle** Texte |
| `docker/Dockerfile`, `INTEGRATION_VSC.md`, `README.md`, `tests/integration/laufen.md` | Anleitung |
| `tests/…` | `test_vorlagen.py`, `test_modul.py`, `test_erinnern.py`, `test_dateien.py`, `rein/test_zeitplan.py`, `rein/test_texte.py`, `integration/test_pruefungen_db.py`, `test_seiten_db.py`, `test_t_i_5.py` |
