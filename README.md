# DOKON Inventar — `digiassistenz_inventar` (Modul `inventar`, Gesamtübersicht L10–L16a, Entwurf)

Geräteverwaltung einer Baufirma als Modul des Kerns `digiassistenz_kern` ≥ 0.15.3 (gebaut und geprüft mit 0.15.4): Schema `inventar`, Konto `inventar_nutzer`,
Kette `i0001…`, Bausteine `inventar.*`. Die Fachlogik liegt in `digiassistenz_inventar/rein/` (reine Module, keine Datenbank).
**Entwurf**, bis VSC das Modul auf dem echten Kern fährt (Aufträge 01–03, Lieferungen L1–L16a, Aufträge 04 bis 08). L16a ist die letzte Lieferung von Box.

## Prüfen

```
python -m pytest -q                    # im Ordner Inventar; ohne Datenbank; erwartet: 417 passed, skipped = 0
```

Mit Datenbank (Kern 0.15.4 als Wheel, PostgreSQL 16 mit contrib, `pg_dump` 16; Anleitung `tests/integration/laufen.md`) — alle Dateien außer T-I-6:

```
cd <wurzel mit konfig.env> && DIGIASSISTENZ_WURZEL=$PWD python -m pytest --rootdir=<pfad> $(ls <pfad>/tests/integration/test_*.py | grep -v test_t_i_6)
```

Einmal die Prüfpakete: `pip install -e <pfad>/Inventar[pruefung]` (pytest, httpx, pyflakes, **playwright==1.49.1**); danach `python -m playwright install chromium`.

Browser (Playwright 1.49.1, **von VSC zu fahren**; Anleitung `tests/browser/README.md`): `python -m pytest tests/browser` gegen eine laufende Box, `BROWSER_BASIS_URL` setzen.

Stand Box (Python 3.12.3, Kern-Wheel 0.15.4, PostgreSQL 16.15): `tests` **417 passed**, `tests/integration` **69 passed** (T-I-5, Anwendungsfälle, Modelle gegen Kette, Seiten, Prüfungen, L13a, Werkstatt,
Kosten und Inventur, Feiertage, Mengenabfrage, Zählerstand-Import), jeweils `skipped = 0`. **T-I-6** (mit Belegerfassung) hat Box nicht gefahren — sie fehlt ihr; VSC hat es nach L13 mit 0.15.3 gefahren (3 passed).
Browserfälle: **30 passed** (Chromium 141 headless, Playwright 1.49.1-Treiber); siehe `docs/L16a/README.md` (Stand der Läufe).

## Was das Modul kann (nach Lieferung)

| Lieferung | Inhalt |
|---|---|
| L1–L9 | reine Module: Kataloge, Nummernformat, Fristen und Ampel, Transfer-Automat, Kosten, Import, Testdaten, Etiketten, Kacheln, Verrechnung, Beispielbetrieb |
| L10 | Gerüst: Modulbeschreibung, elf Bausteine, Modelle, Kette `i0001`, Startdaten, Dienste, Kacheln |
| L11 | Inventarliste (Ordner/Liste, Filter, Suche), Stück-Seite, Anlegen/Ändern, Merkmale, Zubehör und Bauteile, Zählerstand, Foto, „Schaden melden“, Verwaltung (Kataloge, Import, Etiketten, Testdaten) |
| L12 | Hier-Seite des Poliers, Abgang, Eingang (auch Teilmenge), Scan „Ist hier“, Zurückziehen, Scan-Seite mit Kamera, QR-Ziel, Reiter an der Kostenstelle |
| L13 / L13a | kern-0.15.3; Prüfungen und Fällig-Liste, Nachweis, Erinnerungen als Modulprozess; Startstandort Pflicht, Rechte `pflegen`/`buchen` getrennt |
| L14 / L14a | Werkstatt: Posteingang, Reparatur-Vorgang, Pflichtangaben beim Abschließen, Haken „Meldung erledigen“, eine Mailstelle, Foto am Stück |
| L15 / L15a | Kosten (Sätze, Seite, CSV-Auszüge mit Download, Vergleichszeile geplant/angefallen), Zählerstände, Stichtags-Inventur |
| **L16a** | Feiertagsregion aus dem Kern, Rechner auf `holidays==0.60`, „jährlich“ für eigene Tage, Mehrmenge-Hinweis und zweiter Scan mit Zahl bei der Inventur, **Inventur abschließen** (CSV), Spalte „Ablesedatum“ im Excel-Import, Playwright 1.49.1 |
| **L16** | **Feiertage** (Region, eigene Tage, ein Datenzugriff), **Mengenabfrage** bei laufender Inventur, **Zählerstand** im Excel-Import, Browser-Prüffälle (`tests/browser/`), diese Übersicht |

## Seiten, Wege, Rechte

| Menüpunkt / Seite | Weg | Recht (eines genügt) |
|---|---|---|
| Inventar (Liste, Kacheln) | `/inventar`, `/inventar/liste`, `/inventar/kostenstelle/{id}` | `sehen` |
| Stück-Seite, Anlegen, Ändern | `/inventar/stueck/{id}`, `/neu`, `/{id}/aendern` | `sehen` · Anlegen/Ändern `pflegen` |
| Hier | `/inventar/hier` | `scannen` oder `sehen` |
| Scannen | `/inventar/scannen`, `/inventar/s`, `/inventar/s/{nummer}` | `scannen` |
| Fällig | `/inventar/faellig` | `pruefen` oder `werkstatt` |
| Werkstatt | `/inventar/werkstatt` | `werkstatt` |
| Kosten | `/inventar/kosten`, `/inventar/kosten/auszug/{datei}` | `kosten_sehen` |
| Verwaltung | `/inventar/verwaltung` mit Gruppen, Merkmale, Prüfarten, Bauteile, Kostensätze (`kosten_pflegen`), Einstellungen, Import, Etiketten, Testdaten, Inventur | `einstellen` oder `pflegen` |
| Dateien | `…/stueck/{id}/foto`, `…/meldung/{id}/foto`, `…/pruefung/{id}/nachweis` | `sehen` am Stück |

Die elf Bausteine: `sehen`, `scannen`, `buchen`, `melden`, `pflegen`, `pruefen`, `werkstatt`, `stilllegen`, `kosten_sehen`, `kosten_pflegen`, `einstellen`. Startwerte je Systemvorlage in `rechte.py`
(Polier: sehen, scannen, buchen, melden; Preise sieht nur, wer `kosten_sehen` hat).

## Einstellungen (Verwaltung → Einstellungen, je Mandant)

| Schlüssel | Standard | Wirkung |
|---|---|---|
| `nummernmuster` | `{gruppe}-{nr:5}` | Inventarnummer |
| `transfer_frist_werktage` | 3 | ab wann ein Transfer „überfällig“ ist (Werktage **ohne Feiertage**) |
| `tage_je_monat` / `werktage` | 30 / 0 | Tagessatz aus Monatssatz; `werktage` > 0 (z. B. 21,67) rechnet nach Werktagen |
| `gelb_ab_tagen`, `zaehler_gelb_prozent`, `pruefung_erinnern_tage` | 30, 10, 14 | Ampel und Vorlauf der Erinnerung |
| `zins_prozent`, `etikett_layout`, `erinnern_um` | 4.0, `70x36_3x8`, `06:00` | Kosten, Etikettenbogen, Uhrzeit des Tageslaufs |
| **Feiertagsregion** (L16a) | – | keine Einstellung des Moduls: sie steht im Kern am Mandanten (`mandant.feiertagsregion`, `DE`, `DE-NI` …; leer = keine Feiertage, mit Hinweis); die Tage kommen aus `holidays==0.60` |
| **eigene freie Tage** (L16, L16a) | – | Tabelle `inventar.feiertag`; je Datum ein Tag, ein- und abschaltbar, nie gelöscht; Haken „jährlich“ (`jaehrlich`) |
| `inventur_letzte` (L16a) | leer | `<Stichtag>\|<CSV>` der zuletzt abgeschlossenen Inventur (Verwaltung → Inventur → „Inventur abschließen“) |
| `inventur_stichtag` | leer | gesetzt in Verwaltung → Inventur; bei laufender Inventur fragt der Scan eines Mengenartikels die Menge |
| `auslieferung_am` | leer | ab dem Datum verschwinden die Testdaten für immer |

## Prozesse

* `digiassistenz_inventar.erinnern` (Modulprozess, vom Kern gestartet): einmal täglich zur Uhrzeit `erinnern_um` — überfällige Transfers an `disposition` und den Melder, fällige Prüfungen an `werkstatt`. Alle Mails
  gehen durch **eine** Funktion (`dienstlogik/benachrichtigen.py`), die nur einreiht (`kern.mail_ausgang`, `wartend`).
* Feiertage: **ein** Datenzugriff (`dienstlogik/feiertage.py`, `werktage(db, von, bis, mandant_id)`); Vorhaltung nach Werktagen, Transfer-Frist, Kachel „Transfers überfällig“ und Erinnerung fragen dort.

## Dateien im Arbeitsordner (Pfadliste)

Alles unter `<ARBEITSORDNER>/inventar/<mandant.ordnername>/`; nichts wird gelöscht, eine neue Datei ersetzt nie eine alte.

| Pfad | Inhalt |
|---|---|
| `stamm/<nr>/bilder/`, `…/pruefungen/`, `…/meldungen/` | Foto des Stücks, Nachweise, Fotos der Meldungen (Abruf mit Prüfsumme, inline) |
| `import/` | hochgeladene Excel-Dateien |
| `export/` | Etiketten-PDF, CSV-Auszüge `kosten_<block>_<Zeitstempel>.csv`, `inventur_<…>.csv` (BOM, Semikolon, Dezimalkomma); Download über `/inventar/kosten/auszug/<datei>` |
| `<ARBEITSORDNER>/log/digiassistenz-inventar-erinnern.log` | Log des Prozesses (vom Kern) |

## Aufbau

| Ort | Inhalt |
|---|---|
| `pyproject.toml` | Einstiegspunkt `digiassistenz.module` → `inventar`, `digiassistenz-kern>=0.15.3` |
| `digiassistenz_inventar/modul.py` | die Modulbeschreibung (Menü, Erweiterungen, Ereignis, Suche, Verbindung) |
| `rechte.py`, `modelle.py` | elf Bausteine, Vorlagen-Ergänzung, Nachzug · **19 Tabellen** |
| `migration.py`, `migrationen/` | Kette `i0001_grundlinie` (Rolle, Schema, alle Tabellen), Kern zuerst |
| `startdaten.py` | Kataloge, Kostensatz-Vorschläge, Einstellungen — wiederholbar, ohne Stücke |
| `dienstlogik/` | Anwendungsfälle: Nummer, Stück, Transfer, Import, Testdaten, Etiketten, Prüfung, Erinnerung, Werkstatt, Mailstelle, Kostenrechnung, Inventur, Zählerstände, **Feiertage** |
| `dienste.py`, `kacheln.py` | Dienste `bestand` und `stueck` (noch nicht beim Kern angemeldet), Kacheln |
| `erinnern.py` | Modulprozess `erinnern` |
| `web/`, `vorlagen/`, `statisch/` | Seiten und Routen |
| `texte/de.json` | alle Texte (keine deutschen Sätze im Code) |
| `rein/` | die reinen Module mit Katalogen (`rein/daten`), darunter `rein/feiertage.py` |
| `tests/` | `rein/` und Dateien im Wurzelordner ohne Datenbank; `integration/` mit Datenbank; **`browser/`** mit Playwright |
| `compose.yml`, `docker/`, `konfig.env.beispiel` | Aufbau mit Docker (von Box nicht gebaut; `docker/Dockerfile` ist ein Entwurf, auf Drive `Dockerfile.txt`) |
| `INTEGRATION_VSC.md` | was VSC tut |
| `docs/` | README und `FRAGEN_L<n>.md` je Lieferung, Protokolle `PROTOKOLL_BOX_<nn>.md` |

## Prüffälle (Überblick)

| Bereich | Wo |
|---|---|
| reine Module (Sollwerte von Hand) | `tests/rein/` — u. a. `test_feiertage.py` (alle 16 Länder, 2026 und 2027), `test_kosten_l15.py`, `test_verrechnung.py`, `test_import_vorlage.py` |
| Regeln des Moduls | `tests/test_regeln.py` (T-K-10d, T-K-12d, T-AP02-10/11/13, T-Z-1, **pyflakes** über das ganze Paket), `tests/rein/test_texte.py` (X1–X9), `tests/test_vorlagen.py` (jede Vorlage rendert mit `StrictUndefined`) |
| mit Datenbank | `tests/integration/` — T-I-5, `test_dienstlogik_db`, `test_migration_gegen_modelle`, `test_seiten_db`, `test_pruefungen_db`, `test_l13a_db`, `test_werkstatt_db`, `test_kosten_db`, **`test_feiertage_db`**, **`test_inventur_menge_db`**, **`test_import_zaehler_db`** |
| Belegerfassung dazu | `tests/integration/test_t_i_6.py` (T-I-6, T-K-14; Box kann es nicht fahren) |
| Browser | `tests/browser/` (Playwright; VSC) |

## Offen (nicht in Box’ Hand)

* Docker-Bild und Druck (Etikettenpapier 70 × 36 mm) — VSC/Thomas; Browserfälle auf allen drei Engines (Chromium hat Box headless gefahren, Firefox und WebKit nicht).
* `DIENSTE` (`bestand`, `stueck`) gehen in die Modulbeschreibung, sobald der Kern `dienste` hat (AP-K2); Kachel-Vertrag des Kerns fehlt (Brücke 025).
* **Vorgesehen, nicht gebaut:** vorgedruckte QR-Etiketten (`etikett_code`, Spec E24); die Auflösung steht an einer Stelle (`dienstlogik/sicht.aufloesen`).
* Einsatzstunden aus der Baustelle, Rechnungen aus den Belegen (nach AP-K2), steuerliche AfA.
* Grundlinie `i0001` ist **offen** (Stand „i0001 offen“, `tests/integration/laufen.md`): sie bleibt änderbar bis zur ersten Box mit Inventar-Daten. L16 hat sie um `inventar.feiertag` ergänzt.

Regeln: nur öffentliche Kern-Namen, kein anderes Modul, keine Löschung, keine deutschen Sätze im Code (Texte in `de.json`).
Die Wörter `beleg…` kommen im Code nicht vor (T-K-12d): Reparaturkosten aus einer Rechnung heißen `rechnung`.
