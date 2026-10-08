# inventar_rein — Lieferung L4 (import_vorlage, testdaten)

Stand 08.10.2026 · gehört in denselben Ordner `inventar_rein/` wie L1 bis L3. Braucht `openpyxl` (siehe `requirements.txt` aus L1).

## Neu
| Datei | Inhalt |
|---|---|
| `import_vorlage.py` | `erzeuge_vorlage`, `lies`, `ImportZeile`, `ImportFehler`, Konstanten `SPALTEN` und `FEHLER_SCHLUESSEL` (alle Fehlerschlüssel des Imports) |
| `testdaten.py` | `erzeuge(seed, anzahl, …)` → `Testdaten`; `STANDARD_ANZAHL = 2500` |
| `tests/test_import_vorlage.py` | 16 Prüffälle I1–I16, jede Prüfregel mit selbst erzeugter Datei |
| `tests/test_testdaten.py` | 15 Prüffälle T1–T12 (T3 läuft für vier Nummernmuster) |

## Aufruf (drei Zeilen)
```python
from datetime import date; from inventar_rein import kataloge as k, testdaten as t, nummernformat as nf
d = t.erzeuge(1, 2500, k.lade_gruppen(), k.lade_merkmale(), k.lade_pruefarten(), [100, 200, 300], nf.Muster("{gruppe}-{nr:5}"), date(2026, 10, 8))
print(len(d.stuecke), len(d.transfers), len(d.pruefungen), len(d.zaehlerstaende))  # 2500 125 5075 850
```

## Prüflauf
```
python -m pytest -q        # im Ordner inventar_rein (L1 bis L4)
102 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13.16, pytest 9.1.1)
```

## So ist es gebaut
- **Vorlage:** Blatt „Inventar" (Kopfzeile fest, 14 Spalten, danach `m:<schluessel>` für jedes Merkmal des Katalogs), zwei Beispielzeilen, Dropdowns für Gruppe und Art (Listen auf verstecktem Blatt „Listen"), je Merkmalsspalte ein Kommentar in Zeile 1 (`gruppe=…; typ=…; einheit=…; pflicht=…; auswahl=…`).
- **Lesen:** Fehlerfreie Zeilen kommen zurück, fehlerhafte nur in die Fehlerliste (Teil-Import). Doppelte Inventarnummern (nach `normalisiere`) → Fehler für **alle** beteiligten Zeilen. Leere Zeilen werden übersprungen. Zeilennummern sind Excel-Zeilen.
- **Testdaten:** `random.Random(seed)`, keine Uhr. Verteilung der Gruppen nach dem Verfahren „größter Rest" (Summe stimmt immer): 8 % Baumaschinen, 6 % Fahrzeuge, 50 % KG/WZ/EL, 10 % CO/SR, 20 % BA/IT, 6 % Rest. Genau 5 % der Stücke haben einen angekündigten Transfer, genau 20 % eine Besonderheit; bei den Prüfungen sind 8 % rot und 10 % gelb (Ampel, Stichtag), Fälligkeit immer = `naechste_faelligkeit(durchgefuehrt, Intervall)`, nie vor dem Kaufdatum. Seriennummern sind sichtbar künstlich (`TEST-…`).
- Test T5 schreibt 400 erzeugte Stücke in eine Excel-Datei und liest sie mit `lies` ohne Fehler zurück.

## Abweichungen und Ergänzungen
- `lies` hat einen zusätzlichen optionalen Parameter `heute: date | None = None` (Obergrenze des Baujahrs); ohne Angabe gilt das heutige Datum. Grund: Prüffälle dürfen nicht von der Uhr abhängen.
- `vorlage`-Spalten `m:…` stehen für **alle** Merkmale; welche zu welcher Gruppe gehören, steht im Kommentar.

## Offene Fragen
Siehe `FRAGEN_L4.md`.
