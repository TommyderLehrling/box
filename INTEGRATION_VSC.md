# INTEGRATION_VSC — was VSC mit `digiassistenz_inventar` tut (L10–L14, Auftrag 05, Box, 10.10.2026)

Gebaut gegen **KERN_STECKBRIEF_kern-0.15.4**. Alles hier gilt als Entwurf, bis es auf dem echten Kern läuft. Schon gefahren (Auftrag 05, Abschnitt 5): Kern-Start
mit `prozesse` (GER am Kern ohne Docker, VSC im Container) und **T-I-6** nach L13 (VSC, 3 passed). Neu seit L13a/L14 ist nur, was in Abschnitt 1 steht.

## 1. Was Box schon gefahren hat (Python 3.12.3, Wheel 0.15.4 nicht editierbar, PostgreSQL 16.15, Superuser)

* `python -m pytest -q -W error`: 331 passed, 0 skipped.
* Kette `k0001…k0004` → `i0001`, Startdaten, zweiter Start ändert nichts.
* `tests/integration` (ohne `test_t_i_6.py`): 43 passed, 0 skipped — T-I-5 (8), Anwendungsfälle gegen die echte Datenbank (13), Modelle gegen Kette (2),
  Seiten L11/L12 (5), Prüfungen/Erinnerung/Kaufdaten/Scan-Quelle/Startstandort L13 (8), **L13a** (3), **Werkstatt L14** (4).
* Der Prozess `python -m digiassistenz_inventar.erinnern` von Hand gestartet und mit SIGTERM beendet: schreibt auf stdout und in
  `log/digiassistenz-inventar-erinnern.log` (Kern 0.15.4, eine Logdatei je Prozess), `inventar.erinnern_start` und `inventar.erinnern_ende`.
* Kern-Start mit `prozesse`: **ist gefahren** — GER am Kern 0.15.3/0.15.4 ohne Docker; VSC im Container (Prozess im Bild gefunden, `kill -9` → Neustart durch Docker,
  `docker stop` → `erinnern_ende`, Exit 0); **T-I-6 nach L13 grün (VSC)**. Box hat das nicht selbst gefahren.
* Nicht gefahren: Docker (`compose.yml`, `docker/Dockerfile`), Browser, Kamera, Druck.

## 2. Einbauen

```
pip install --no-deps digiassistenz_kern-0.15.4-py3-none-any.whl
pip install -r requirements.txt && pip install -r requirements-modul.txt      # Kern-Pakete + openpyxl, weasyprint
pip install --no-deps -e <pfad>/Inventar                                       # Einstiegspunkt digiassistenz.module → inventar
python -m digiassistenz_kern.start                                             # Ketten (Kern, dann i0001), Startdaten, Web, Prozesse der Module
```

* Nachzug: beim Start bekommen Konten, deren Vorlage einen Baustein trägt, die elf `inventar.*`-Rechte (Grund `nachzug:inventar_einbau`, einmal je Konto).
* Kern: **0.15.4** (einzige Änderung gegenüber 0.15.3: eine Logdatei je Prozess, `log/digiassistenz-<prozess>.log`). `Modulbeschreibung(kern_mindestens="0.15.3")` und
  `digiassistenz-kern>=0.15.3` in `pyproject.toml` bleiben; ein Kern unter 0.15.3 lässt das Modul aus (Satz im Log, `KernZuAlt`).
* `konfig.env`: `INVENTAR_ETIKETT_URL` (leer = aus der Anfrage). Die Kern-Schlüssel stehen in derselben Datei.
* **Erinnerungen sind ein Modulprozess, kein Cron.** `Modulbeschreibung.prozesse=("digiassistenz_inventar.erinnern",)`: der Kern startet
  `python -m digiassistenz_inventar.erinnern` neben dem Webserver und überwacht ihn. Der Prozess läuft dauerhaft und arbeitet einmal täglich
  zur Uhrzeit aus `inventar.einstellung` (Schlüssel `erinnern_um`, Standard `06:00` Ortszeit, in „Verwaltung › Einstellungen“ änderbar). Er schläft in
  Schritten von 1 s und prüft die Uhr alle 5 Minuten. **Ein Prozess, der wartet, öffnet keine Sitzung** (Steckbrief 10): die gelesene Uhrzeit wird gemerkt,
  vor ihr wird nur die Uhr geprüft, die Einstellung wird höchstens einmal je Stunde neu gelesen (eine geänderte Uhrzeit gilt also spätestens nach einer Stunde); ist der
  Tag erledigt, schaut er bis zum nächsten Datum nicht mehr in die Datenbank. SIGTERM beendet ihn sauber. Der letzte Lauf steht in `erinnern_letzter_lauf` (idempotent je Tag, ein
  verpasster Lauf holt am selben Tag nach). Je Lauf ein Protokolleintrag `inventar.erinnern_lauf` und eine Zeile im Log. Ein Fehler im Lauf steht im Log und
  beendet den Prozess nicht (fällt er, fällt der Container). `hochlaufen(leise=False)`: stdout ist das Log des Containers (`docker logs` zeigt den Tageslauf), die Datei das Log der Box.
  Der Lauf: überfällige Transfers → Mail an `disposition` und den Melder; fällige und überfällige Prüfungen → Mail an die Funktion `werkstatt` (nur bei Neuem, montags
  mit allen Überfälligen; Vorlauf `pruefung_erinnern_tage`, Standard 14).
* WeasyPrint braucht Pango/Cairo und eine Schrift im Bild (siehe `docker/Dockerfile`).
* **Rechte seit L13a:** Das Anlegen eines Stücks (Startstandort, auch im Import) braucht `pflegen` auf der gewählten Kostenstelle; jede Bewegung danach (Abgang, Eingang, Scan)
  braucht `buchen`. Kaufdaten ändert nur, wer `kosten_pflegen` hat. Reparaturkosten trägt nur ein, wer `kosten_pflegen` hat, und sieht nur, wer `kosten_sehen` hat.
* **Menü seit L14:** „Werkstatt“ (`/inventar/werkstatt`, Recht `werkstatt`, Reihenfolge 13); die Kacheln „Meldungen offen“ und „in Arbeit“ führen dorthin.

### Pakete (Auftrag 04 Abschnitt 4, Auftrag 05 Abschnitt 3)

* Regel: **eine Fassung je Paket je Box**, festgelegt in der `requirements.txt` des Kerns; Module nennen nur, was nur sie brauchen.
* Dieses Modul: `openpyxl==3.1.5`, `weasyprint==70.0` (`requirements-modul.txt`). **Pillow wird nicht gepinnt** — im gemeinsamen Bild gilt `Pillow==11.0.0` (Pin der Belegerfassung;
  WeasyPrint 70.0 läuft damit).
* Unterpakete von WeasyPrint, die mit dem Kern-Tausch in die Kern-`requirements.txt` gehen: `Pillow==11.0.0` (nicht 12.3.0), `pydyf==0.12.1` (ersetzt den Pin 0.10.0 der Belegerfassung),
  `tinycss2==1.5.1`, `tinyhtml5==2.1.0`, `cssselect2==0.10.1`, `pyphen==0.18.1`, `fonttools==4.66.1`, `webencodings==0.6.1`, `brotli==1.2.0`, `zopfli==0.4.3`, `et_xmlfile==2.0.0`.
* Die Belegerfassung geht mit dem Kern-Tausch auf WeasyPrint 70.0; `openpyxl` kommt ins gemeinsame Bild.
* Systempakete für WeasyPrint im Bild: `libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b fonts-dejavu-core` (stehen im Entwurf `docker/Dockerfile`).
* **Dockerfile:** Der Entwurf setzt auf das Kern-Prüfbild `digi-assistenz-kern:0.2.0` auf. Das gibt es, hat aber kein Pango/Cairo (darum die `apt`-Zeile) und ist kein Betriebsbild.
  Er bleibt Entwurf, bis Thomas entscheidet, wem das Bild gehört (vor AP-K2). Auf Drive heißt die Datei `docker/Dockerfile.txt` (aus L10 liegt ein älteres `Dockerfile(1).txt`);
  VSC benennt beim Einbau in `Dockerfile` um.

### Dateien im Arbeitsordner (Pfadliste)

Alles unter `<ARBEITSORDNER>/inventar/<mandant.ordnername>/`; nichts wird gelöscht, eine neue Datei ersetzt nie eine alte (Zähler im Namen).

| Pfad | Inhalt |
|---|---|
| `stamm/<nr>/bilder/` | Fotos des Stücks (jpg/png ≤ 8 MB; Hash am Stück) |
| `stamm/<nr>/pruefungen/` | Nachweise zu Prüfungen (PDF/JPG/PNG ≤ 10 MB; SHA-256 an der Prüfung; Abruf `/inventar/pruefung/<id>/nachweis` prüft die Summe und zeigt **inline**) |
| `stamm/<nr>/meldungen/` | Fotos zu Schadensmeldungen (Abruf `/inventar/meldung/<id>/foto`, inline, prüft die Summe) |
| `import/` | hochgeladene Excel-Importdateien (`<kennung>.xlsx`), bleiben liegen |
| `export/` | Etiketten-PDF (`etiketten_*.pdf`) |
| `kostenstellen/<nr>/` | reserviert für Kostenstellen-Unterlagen |
| `<ARBEITSORDNER>/log/digiassistenz-inventar-erinnern.log` | Log des Prozesses `erinnern` (vom Kern, 0.15.4) |

## 3. Läufe

| Lauf | Aufbau | Datei |
|---|---|---|
| T-I-5 | Kern + Inventar | `tests/integration/test_t_i_5.py` |
| Anwendungsfälle, Modelle gegen Kette | Kern + Inventar | `tests/integration/test_dienstlogik_db.py`, `test_migration_gegen_modelle.py` |
| Seiten L11/L12 durch die Anwendung | Kern + Inventar | `tests/integration/test_seiten_db.py` (5 Fälle) |
| Prüfungen, Erinnerung, Kaufdaten, Scan-Quelle, Startstandort (L13) | Kern + Inventar | `tests/integration/test_pruefungen_db.py` (8 Fälle) |
| Startstandort mit `pflegen`, Import nach Rechten, Kachel für `werkstatt` (L13a) | Kern + Inventar | `tests/integration/test_l13a_db.py` (3 Fälle) |
| Werkstatt: Posteingang, Rückmeldung, Reparatur, `in_reparatur` (L14) | Kern + Inventar | `tests/integration/test_werkstatt_db.py` (4 Fälle) |
| **T-I-6**, T-K-14 | Kern + Belegerfassung + Inventar | `tests/integration/test_t_i_6.py` (Muster T-I-4; von VSC nach L13 gefahren: 3 passed) |

Aufruf und Stolpersteine (auch Nicht-Superuser): `tests/integration/laufen.md`.

## 4. Browserfälle (Playwright, Chromium + Firefox, Zoom in WebKit) — Seiten aus L11–L14

1. Die Statuszeile ist das erste Element unter dem Seitenkopf der Stück-Seite (`#statuszeile`, vor allen `<details>`).
2. Die Tasten einer Reihe sind gleich hoch (`.tastenreihe`, auch `#haupttasten` und `#scan-tasten`).
3. Kein Link ohne Recht: `Polier.Eins` sieht weder Preise noch „Bearbeiten“, „Neues Stück“, „Prüfung eintragen“, „Werkstatt“ oder die Verwaltung; ohne `scannen` keine Taste „Ist angekommen“.
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
    und kehrt nach dem Speichern mit ✓ auf die Fällig-Liste zurück; liegt ein eingetragener Zählerstand unter dem letzten, steht der Hinweis dazu.
13. Prüfung mit PDF-Nachweis (und mit einem umbenannten Bild): „Nachweis ansehen“ zeigt die Datei **im Browser** (inline); eine Textdatei wird abgewiesen.
14. Neues Stück: das Startstandort-Feld ist Pflicht (Browser meldet „required“), ohne Wahl kein Absenden (`required` an der Kostenstellen-Wahl seit kern-0.15.3);
    ein Büro-Konto (`pflegen`, kein `buchen`) findet seine Kostenstellen in der Wahl und kann anlegen, aber nicht umbuchen.
15. Werkstatt (`/inventar/werkstatt`): Meldung eines Poliers mit Foto erscheint unter „Offen“, das Foto öffnet im Browser; Annehmen → Übernehmen → Erledigen mit Rückmeldung
    (ohne Text bleibt der Dialog offen und zeigt den Fehler); die Rückmeldung steht danach an der Stück-Seite; Zurückziehen verlangt einen Grund.
16. Reparatur: „Reparatur anlegen“ an einer Meldung öffnet den Dialog (`#reparatur-anlegen`) mit der Beschreibung der Meldung; „Beginnen“ → das Stück zeigt den Hinweis
    „In Reparatur“, Abgang und Eingang lassen sich weiter buchen; „Abschließen“ → wieder aktiv, sobald keine Reparatur mehr läuft. Ein Konto nur mit `werkstatt` sieht keine Kostenfelder.

## 5. Offen / bewusst nicht eingehängt (Steckbrief 11)

* `DIENSTE` (`bestand`, `stueck`) stehen in `dienste.py`; sie gehen in die Modulbeschreibung, sobald der Kern `dienste` hat (AP-K2).
* Kacheln stehen oben auf `/inventar` (`kacheln.py`); ein Kachel-Vertrag des Kerns gibt es noch nicht (Brücke 025). `Kachel.rechte` hat schon die Form des künftigen Vertrags:
  Tupel von Paaren `(Modul, Aktion)`, eines genügt (wie `Menueeintrag.rechte`).
* Startseite ist ein fester Weg (`/inventar`), weil der Callable-Weg die Beschriftung nicht findet.
* `Verbindung(braucht="baustelle", menuepunkte=())`: leer, bis APP den Weg nennt; der Schlüssel (`app` oder `baustelle`) steht nur als `MODUL_BAUSTELLE`.
* `app.modul` setzt das Inventar nicht; der Titel ist mit dem Inventar allein „DOKON“.
* Seiten: L11–L14 bringen Liste, Stück-Seite, Pflege, Verwaltung (Kataloge, Import, Etiketten, Testdaten), Hier-Seite, Buchungen, Scan, die Prüfungen
  (Fällig-Liste, Prüfung eintragen mit Nachweis, Prüfarten je Gruppe und Stück) und die Werkstatt (Posteingang, Reparatur-Vorgang). Kosten (L15) und die Browser-Prüffälle (L16) fehlen noch.
* **Vorgesehen, nicht gebaut (Thomas, Auftrag 05 Abschnitt 7):** vorgedruckte QR-Etiketten. Spec E24: Feld `etikett_code` je Stück (eindeutig je Mandant), der Scan löst zuerst die
  Inventarnummer, dann den Etikett-Code auf, „Etikett zuordnen“ an der Stück-Seite, Protokoll `inventar.etikett_zugeordnet`. Vorbereitet: die Auflösung steht an **einer** Stelle
  (`dienstlogik/sicht.aufloesen`), der Etikett-Code kommt dort als weiterer Schritt dazu, ohne dass sich Wege oder Seiten ändern.
* `DIENSTE` sind `Dienst`-Objekte (lokale Klasse, gleiche Felder wie der künftige Kern-Typ).
* Der Zeitplan „täglich um …“ gehört dem Modul, bis der Kern einen hat (Steckbrief 11, AP-K2): `erinnern` schläft und wacht selbst.
