# PROTOKOLL BOX 03 — Auftrag 02 (L7, L9, L8)

Stand 09.10.2026 · Ergebnis: **215 passed / 0 failed / 0 skipped** (Python 3.12.3 und 3.13, auch mit `-W error`) · Git-Zweig `claude/inventar-modul-vorarbeit-oil35n`, Commit `147dba4`.

## Erledigt (Reihenfolge wie verlangt)

| Lieferung | Inhalt | Prüffälle |
|---|---|---|
| **L7** Korrekturen | `transfer`: Teilung erst beim Eingang, Teil-Eingang mit Fehlmenge, `beendet_am`, `quelle` beim Zurückziehen, `Quelle` +3 · `bestand`: Seriennummer/Hersteller, Suche nach Seriennummer · `pruefung`: Zustand `unbekannt`, Block „ohne Nachweis" · Prüfarten-Katalog nach B.5 (+Merkmal `fahrzeugklasse`) · Import: Beispielzeilen, Gruppe per Bezeichnung, Hinweis `abweichung` · Inventur: `mehr_gesehen` · Texte: Platzhalterregel · `testdaten`: Namen in JSON | +13 |
| **L9** Beispielbetrieb | 50 Stücke mit Geschichte, nachgespielt mit den echten Modulen; besteht den eigenen Import; Zustände nach Spec Abschnitt 16 | +9 |
| **L8** | `kacheln` · `verrechnung` (inkl. Miete gegen eigen, CSV) · Kostensatz-Standardwerte + `parameter_fuer` · `inventarnummer_aus_scan` · `mit_menge=True` als Standard | +13 |

Eigenschaftstests (L7): 500 + 150 + 120 + 80 zufällige Buchungsfolgen, Invarianten nach jedem Schritt; zwei absichtlich eingebaute Fehler wurden gefunden.

## Befund, den ich selbst gefunden habe

Ein erneut gesendeter Scan nach einem Teil-Eingang hätte den Fehlmengen-Transfer bestätigt, weil der Scan-Schlüssel nirgends gemerkt war. Behoben mit dem neuen Feld `Transfer.eingang_schluessel` (**VSC muss es speichern**).

## Wo liegen die Dateien

- **Git** (vollständig, maßgeblich): Zweig `claude/inventar-modul-vorarbeit-oil35n`, Ordner `inventar_rein/`, Doku in `docs/`.
- **Drive** `Gerate-App/box/lieferungen/`: `L7/` (README, FRAGEN), `L8/` (README, FRAGEN, `kacheln.py`, `verrechnung.py`, `daten/kostensaetze_standard.json`, `tests/test_kacheln.py`, `tests/test_verrechnung.py`), `L9/` (vollständig: README, FRAGEN, `beispielbetrieb.py`, `daten/beispielbetrieb.json`, `tests/test_beispielbetrieb.py`).
- **Nicht** nach Drive kopiert, nur in Git: die geänderten Bestandsdateien (`transfer.py`, `pruefung.py`, `bestand.py`, `inventur.py`, `import_vorlage.py`, `import_plan.py`, `testdaten.py`, `kosten.py`, `etiketten.py`, `daten/pruefarten.json`, `merkmale.json`, `texte_de.json`, `testdaten_namen.json` und die geänderten Prüffall-Dateien). Grund: Sparsamkeit mit dem Guthaben (etwa 250 KB Text). Sage Bescheid, dann lege ich sie ebenfalls ab.

## Fragen (Einzelheiten in `FRAGEN_L7/L8/L9.md`, keine blockiert)

1. Ampel-Reihenfolge `unbekannt` zwischen gelb und grün — richtig?
2. Fehlmenge erbt den Abgangszeitpunkt (sofort alt) — gewollt?
3. Teil-Eingang auch beim Überholen (dritter Ort)?
4. Neues Feld `eingang_schluessel` einverstanden?
5. `dguv_v3` heißt jetzt `dguv_v3_baustelle`/`dguv_v3_buero`; `pruefstand` ohne `ab`/`erstfaellig` — Migration durch VSC.
6. HU-Standard 12; soll `fahrzeugklasse` das Intervall setzen?
7. Kacheln: „Meldungen offen" nur Status `offen`? Weg-Namen sind meine; „an mich" über Kostenstellen der Person.
8. Miete gegen eigen: Mittelwert der eigenen Tagessätze der Gruppe — oder ein bestimmtes Stück?
9. Bagger heißt `BM-04711`; Prüfarten im Beispiel je Stück statt je Gruppe.
10. Kostensatz-Standardwerte (Zins 4 % überall) sind **meine Vorschläge**, Thomas prüft.

## Nicht geprüft

Kein WeasyPrint-Probedruck · Excel-Vorlage nie in Excel geöffnet · Fristen und Rechtsgründe der Prüfarten nicht fachlich geprüft („(prüfen)" bleibt) · Standardwerte der Kostensätze nicht fachlich geprüft · Kachel- und Weg-Namen nicht gegen den Kern geprüft (Kern-Dateien liegen mir noch nicht vor) · niemand außer mir hat den Code gelesen.
