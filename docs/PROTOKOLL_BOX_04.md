# PROTOKOLL BOX 04 — Auftrag 03, Lieferung L10 (Gerüst), Stand 09.10.2026

Bezug: `BOX_AUFTRAG_03.md`, `KERN_STECKBRIEF_kern-0.15.2.md`, `VON_VSC_01_antwort.md`, Kern-Wheel 0.15.2.

## Was erledigt ist

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | Paket `inventar_rein` vollständig auf Drive (`lieferungen/PAKET_inventar_rein/`, 48 Dateien) | Größen verglichen |
| 2 | `inventar_rein` → `digiassistenz_inventar/rein`, Tests → `tests/rein` (Importpfade, Texte nach `texte/de.json`) | 220 → 257 Prüffälle grün |
| 3 | Antworten aus Abschnitt 0: Intervall je Merkmal (HU), `gruppe_pruefart`, Kachel „in Arbeit“, echte Wege, `vergleichsstueck`, Mietkosten 4.200,00 € im Beispiel | je ein Prüffall (R13, K13, H5, G8, E10) |
| 4 | Modulbeschreibung, Rechte (11 Bausteine, 9 Ergänzungen, Nachzug als Paare), Suche, Erweiterungen, Ereignis | `test_modul`, T-I-5 |
| 5 | 18 Tabellen: `modelle.py` und Kette `i0001` (explizit, aus den Modellen geschrieben, dann geprüft) | `test_migration_gegen_modelle`: Spalten, Nullbarkeit, Eindeutigkeit, Fremdschlüssel, Prüfungen, Indizes gleich |
| 6 | Startdaten (12 Gruppen, 45 Merkmale, 19 Prüfarten, 30 Zuordnungen, 12 Kostensatz-Vorschläge, 8 Einstellungen), wiederholbar | zweiter Start ändert nichts |
| 7 | Anwendungsfälle: Nummer (Zähler unter `FOR UPDATE`), Stück anlegen/Status, Transfer (Abgang, Eingang, Scan, Zurückziehen, Teil-Eingang, Zubehör folgt), Import (idempotent), Testdaten, Etiketten-PDF, Prüfung mit Nachweis, Erinnerung | 13 Fälle gegen PostgreSQL |
| 8 | Dienste `bestand`, `stueck` (Vertrag wörtlich), Kacheln, Gerüst-Seiten, Reiter, Übersichtszeile, Suche | T-I-5 (8 Fälle) |
| 9 | Prüfregeln des Kerns nachgebaut: T-K-10d, T-K-12/12d, T-AP02-10/11/13, T-Z-1, T-T-2, T-HI-1, T-K-14 (Modelle) | `test_regeln`, `test_texte`, `test_vorlagen` |
| 10 | `compose.yml`, `docker/`, `konfig.env.beispiel`, `INTEGRATION_VSC.md`, `tests/integration/laufen.md`, `test_t_i_6.py` | nur gelesen, nicht gebaut/gefahren |

## Stand der Läufe

`python -m pytest -q`: **257 passed, 0 skipped** (auch `-W error`). `tests/integration` mit Kern 0.15.2 und PostgreSQL 16.15: **23 passed, 0 skipped**.

## Fehler gefunden und behoben

* T-K-12d verlangte neue Namen (`beleg…`): `kosten_quelle`, `rechnung_verweis`, `kosten_aus_rechnung`.
* `rein.import_vorlage` nutzte `date.today()`: jetzt ohne Obergrenze, wenn kein Stichtag kommt.
* Zweiter Importlauf meldete jede Zeile als abweichend (Lieferant unbekannt): Namen werden gemeldet, nicht verglichen.
* Meine Erwartung „Polier darf nicht buchen“ war falsch (er darf auf seiner Kostenstelle); der Prüffall prüft jetzt die fremde Kostenstelle.
* Die Verwaltungsübersicht des Kerns zeigt die Zeile des Moduls (`verwaltung.uebersicht`) auf `/verwaltung`, die Spalte je Kostenstelle auf `/verwaltung/uebersicht`.

## Offen

L11, L12 (Seiten), L13 nur auf Zuruf; T-I-6 ungefahren; Docker ungebaut; Weg ohne Superuser ungeprüft; Dienste/Kacheln/Startseite wie `INTEGRATION_VSC.md` Abschnitt 5; Fragen D7–D16 in `FRAGEN_L10.md` (Abschnitt H).
