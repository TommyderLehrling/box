# INTEGRATION_VSC — was VSC mit `digiassistenz_inventar` tut (L10–L13, Auftrag 04, Box, 10.10.2026)

Gebaut gegen **KERN_STECKBRIEF_kern-0.15.3**. Alles hier gilt als Entwurf, bis es auf dem echten Kern läuft (T-I-6 hat VSC mit 0.15.3 gefahren: 3 passed).

## 1. Was Box schon gefahren hat (Python 3.12.3, Wheel 0.15.3 nicht editierbar, PostgreSQL 16.15, Superuser)

* `python -m pytest -q -W error`: 317 passed, 0 skipped.
* Kette `k0001…k0004` → `i0001`, Startdaten, zweiter Start ändert nichts.
* `tests/integration` (ohne `test_t_i_6.py`): 36 passed, 0 skipped — T-I-5 (8), Anwendungsfälle gegen die echte Datenbank (13), Modelle gegen Kette (2),
  Seiten L11/L12 (5), Prüfungen/Erinnerung/Kaufdaten/Scan-Quelle/Startstandort L13 (8).
* Der Prozess `python -m digiassistenz_inventar.erinnern` wurde von Hand gestartet und mit SIGTERM beendet (Lauf des Tages, sauberes Ende nach < 1 s).
* Nicht gefahren: **T-I-6** (keine Belegerfassung — VSC hat es mit 0.15.3 gefahren), Docker (`compose.yml`, `docker/Dockerfile`), Kern-Start
  mit `prozesse` (`digiassistenz_kern.start`), Browser, Kamera, Druck.

## 2. Einbauen

```
pip install --no-deps digiassistenz_kern-0.15.3-py3-none-any.whl
pip install -r requirements.txt && pip install -r requirements-modul.txt      # Kern-Pakete + openpyxl, weasyprint
pip install --no-deps -e <pfad>/Inventar                                       # Einstiegspunkt digiassistenz.module → inventar
python -m digiassistenz_kern.start                                             # Ketten (Kern, dann i0001), Startdaten, Web, Prozesse der Module
```

* Nachzug: beim Start bekommen Konten, deren Vorlage einen Baustein trägt, die elf `inventar.*`-Rechte (Grund `nachzug:inventar_einbau`, einmal je Konto).
* Kern-Mindestfassung: `Modulbeschreibung(kern_mindestens="0.15.3")`, dazu `digiassistenz-kern>=0.15.3` in `pyproject.toml`. Ein älterer Kern lässt das Modul aus
  (Satz im Log, `KernZuAlt`).
* `konfig.env`: `INVENTAR_ETIKETT_URL` (leer = aus der Anfrage). Die Kern-Schlüssel stehen in derselben Datei.
* **Erinnerungen sind ein Modulprozess, kein Cron.** `Modulbeschreibung.prozesse=("digiassistenz_inventar.erinnern",)`: der Kern startet
  `python -m digiassistenz_inventar.erinnern` neben dem Webserver und überwacht ihn. Der Prozess läuft dauerhaft und arbeitet einmal täglich
  zur Uhrzeit aus `inventar.einstellung` (Schlüssel `erinnern_um`, Standard `06:00` Ortszeit, in „Verwaltung › Einstellungen“ änderbar). Er schläft in
  Schritten von 1 s und prüft die Uhr alle 5 Minuten (ist der Tag erledigt, schaut er bis zum nächsten Datum nicht mehr in die Datenbank); SIGTERM beendet ihn sauber. Der letzte Lauf steht in `erinnern_letzter_lauf` (idempotent je Tag, ein
  verpasster Lauf holt am selben Tag nach). Je Lauf ein Protokolleintrag `inventar.erinnern_lauf` und eine Zeile im Log. Ein Fehler im Lauf steht im Log und
  beendet den Prozess nicht (fällt er, fällt der Container). Der Lauf: überfällige Transfers → Mail an `disposition` und den Melder; fällige und überfällige
  Prüfungen → Mail an die Funktion `werkstatt` (nur bei Neuem, montags mit allen Überfälligen; Vorlauf `pruefung_erinnern_tage`, Standard 14).
* WeasyPrint braucht Pango/Cairo und eine Schrift im Bild (siehe `docker/Dockerfile`).

### Pakete (Auftrag 04, Abschnitt 4)

* Regel: **eine Fassung je Paket je Box**, festgelegt in der `requirements.txt` des Kerns; Module nennen nur, was nur sie brauchen.
* Dieses Modul: `openpyxl==3.1.5`, `weasyprint==70.0` (`requirements-modul.txt`).
* Die Belegerfassung geht mit dem Kern-Tausch auf WeasyPrint 70.0; `openpyxl` kommt ins gemeinsame Bild.
* Systempakete für WeasyPrint im Bild: `libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b fonts-dejavu-core` (stehen im `docker/Dockerfile`;
  das Bild bleibt Entwurf — wem es gehört, entscheidet Thomas vor AP-K2).

### Dateien im Arbeitsordner (Pfadliste)

Alles unter `<ARBEITSORDNER>/inventar/<mandant.ordnername>/`; nichts wird gelöscht, eine neue Datei ersetzt nie eine alte (Zähler im Namen).

| Pfad | Inhalt |
|---|---|
| `stamm/<nr>/bilder/` | Fotos des Stücks (jpg/png ≤ 8 MB; Hash am Stück) |
| `stamm/<nr>/pruefungen/` | Nachweise zu Prüfungen (PDF/JPG/PNG ≤ 10 MB; SHA-256 an der Prüfung; Abruf `/inventar/pruefung/<id>/nachweis` prüft die Summe) |
| `stamm/<nr>/meldungen/` | Fotos zu Schadensmeldungen |
| `import/` | hochgeladene Excel-Importdateien (`<kennung>.xlsx`), bleiben liegen |
| `export/` | Etiketten-PDF (`etiketten_*.pdf`) |
| `kostenstellen/<nr>/` | reserviert für Kostenstellen-Unterlagen |

## 3. Läufe

| Lauf | Aufbau | Datei |
|---|---|---|
| T-I-5 | Kern + Inventar | `tests/integration/test_t_i_5.py` |
| Anwendungsfälle, Modelle gegen Kette | Kern + Inventar | `tests/integration/test_dienstlogik_db.py`, `test_migration_gegen_modelle.py` |
| Seiten L11/L12 durch die Anwendung | Kern + Inventar | `tests/integration/test_seiten_db.py` (5 Fälle) |
| Prüfungen, Erinnerung, Kaufdaten, Scan-Quelle, Startstandort (L13) | Kern + Inventar | `tests/integration/test_pruefungen_db.py` (8 Fälle) |
| **T-I-6**, T-K-14 | Kern + Belegerfassung + Inventar | `tests/integration/test_t_i_6.py` (Muster T-I-4; von VSC mit 0.15.3 gefahren) |

Aufruf und Stolpersteine (auch Nicht-Superuser): `tests/integration/laufen.md`.

## 4. Browserfälle (Playwright, Chromium + Firefox, Zoom in WebKit) — Seiten aus L11–L13

1. Die Statuszeile ist das erste Element unter dem Seitenkopf der Stück-Seite (`#statuszeile`, vor allen `<details>`).
2. Die Tasten einer Reihe sind gleich hoch (`.tastenreihe`, auch `#haupttasten` und `#scan-tasten`).
3. Kein Link ohne Recht: `Polier.Eins` sieht weder Preise noch „Bearbeiten“, „Neues Stück“, „Prüfung eintragen“ oder die Verwaltung; ohne `scannen` keine Taste „Ist angekommen“.
4. Import mit 2.500 Stücken (Excel-Vorlage) → danach öffnet `/inventar` in < 1 s (Seiten à 100).
5. Etiketten-PDF für 20 Stücke: 1 Bogen, 2 Seiten bei 25–48 Stücken; jeder QR führt auf `/inventar/s/<nummer>`.
6. Scan-Weg: `/inventar/scannen` mit Kamera-Attrappe (Chromium `--use-fake-device-for-media-stream`) und mit Eingabe von Hand; „Ist hier“ bestätigt den angekündigten
   Transfer; `BarcodeDetector` fehlt in Firefox/WebKit → nur das Eingabefeld. Quelle `handy` nur nach Kamera (`art=kamera`), getippt gilt `web`.
7. Suchfeld der Liste: 250 ms nach dem Tippen ändert sich nur `#inventar-liste`; Sortierpfeil und Seitenwahl behalten die Filter.
8. Dialoge (`<details>`): „Abbrechen“ und Esc klappen zu und setzen das Formular zurück; nach „fertig“ steht ✓ und die Seite bleibt.
9. Merkmalsfelder wechseln mit der Gruppe, der Nummernvorschlag im Nummernfeld mit (`hx-swap-oob`).
10. Foto-Upload jpg/png ≤ 8 MB; eine umbenannte Textdatei wird abgewiesen.
11. Probedruck eines Bogens auf Etikettenpapier 70 × 36 mm (24 je A4).
12. Fällig-Liste: drei Blöcke (überfällig · fällig gelb · ohne Nachweis), Filter wirken, „Prüfung eintragen“ springt auf die Stück-Seite, öffnet den Dialog mit der Prüfart
    und kehrt nach dem Speichern mit ✓ auf die Fällig-Liste zurück.
13. Prüfung mit PDF-Nachweis (und mit einem umbenannten Bild): Datei erscheint unter „Nachweis ansehen“, öffnet/lädt als PDF; eine Textdatei wird abgewiesen.
14. Neues Stück: das Startstandort-Feld ist Pflicht (Browser meldet „required“), ohne Wahl kein Absenden (`required` an der Kostenstellen-Wahl seit kern-0.15.3).

## 5. Offen / bewusst nicht eingehängt (Steckbrief 11)

* `DIENSTE` (`bestand`, `stueck`) stehen in `dienste.py`; sie gehen in die Modulbeschreibung, sobald der Kern `dienste` hat (AP-K2).
* Kacheln stehen oben auf `/inventar` (`kacheln.py`); Posteingang-Kachel erst mit Vertrag (Brücke 025).
* Startseite ist ein fester Weg (`/inventar`), weil der Callable-Weg die Beschriftung nicht findet.
* `Verbindung(braucht="baustelle", menuepunkte=())`: leer, bis APP den Weg nennt; der Schlüssel (`app` oder `baustelle`) steht nur als `MODUL_BAUSTELLE`.
* `app.modul` setzt das Inventar nicht; der Titel ist mit dem Inventar allein „DOKON“.
* Seiten: L11–L13 bringen Liste, Stück-Seite, Pflege, Verwaltung (Kataloge, Import, Etiketten, Testdaten), Hier-Seite, Buchungen, Scan und die Prüfungen
  (Fällig-Liste, Prüfung eintragen mit Nachweis, Prüfarten je Gruppe und Stück). Werkstatt (L14), Kosten (L15) und die Browser-Prüffälle (L16) fehlen noch.
* `DIENSTE` sind `Dienst`-Objekte (lokale Klasse, gleiche Felder wie der künftige Kern-Typ).
* Der Zeitplan „täglich um …“ gehört dem Modul, bis der Kern einen hat (Steckbrief 11, AP-K2): `erinnern` schläft und wacht selbst.
