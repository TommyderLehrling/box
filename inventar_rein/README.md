# inventar_rein — Vorarbeit „Inventar" (Box, Auftrag 01, Lieferungen L1 bis L5)

Stand 08.10.2026 · Reine Python-Module mit Prüffällen: keine Datenbank, kein Web, kein Framework. Abhängigkeiten: `openpyxl`, `segno` (`requirements.txt`).

## Was drin ist

| Lieferung | Module | Prüffälle |
|---|---|---|
| L1 | `kataloge` (+ `daten/gruppen.json`, `merkmale.json`, `pruefarten.json`) · `nummernformat` · `fristen` | 34 |
| L2 | `transfer` (Zustandsautomat der Buchung, Regeln B1–B13) | 23 |
| L3 | `kosten` (kalkulatorische Kosten, Sollwerte Bagger) | 14 |
| L4 | `import_vorlage` (Excel-Vorlage erzeugen, lesen, prüfen) · `testdaten` (Generator) | 31 |
| L5 | `etiketten` (QR-Bogen als HTML) · `daten/texte_de.json` (Oberflächentexte) | 17 |

Je Lieferung gibt es eine eigene README und eine `FRAGEN_L<n>.md` (im Ablageordner `lieferungen/L<n>/`).

## Aufruf (drei Zeilen)

```python
from datetime import date; from inventar_rein import kataloge, nummernformat as nf, fristen
nummer, stand = nf.naechste(nf.Muster("{gruppe}-{nr:5}"), {"BM": 16}, 2026, "BM")  # ("BM-00017", {"BM": 17})
print(nummer, fristen.naechste_faelligkeit(date(2026, 8, 31), 6), kataloge.pruefe_kataloge(kataloge.lade_gruppen(), kataloge.lade_merkmale(), kataloge.lade_pruefarten()))  # BM-00017 2027-02-28 []
```

## Prüflauf

```
python -m pytest -q        # im Ordner inventar_rein
119 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13.16, pytest 9.1.1)
python -c "import inventar_rein"   # ohne Ausgabe
```

## Regeln, die alle Module einhalten

- Typangaben und ein Docstring je öffentlicher Funktion; kein `print`, kein globaler Zustand (Nachschlagetabellen sind unveränderlich).
- Keine deutschen Sätze im Code: Fehler und Protokoll sind **Schlüssel** (`transfer.menge_zu_gross`, `import.fehler.gruppe_unbekannt` …). Der Text zu jedem Schlüssel steht in `daten/texte_de.json` (`inventar.code.<schlüssel>`, bei Import-Fehlern `inventar.import.fehler.<name>`); ein Prüffall vergleicht Datei und Quelltext.
- Nichts wird gelöscht: Zustände werden geschlossen, überholt oder zurückgezogen.
- Geld ist `Decimal`, Zeiten sind zeitzonenbewusst, die Module kennen weder Rechte noch Datenbank.

## Annahmen, Abweichungen, Fragen

Stehen je Lieferung in der README und in `FRAGEN_L1.md` bis `FRAGEN_L5.md`; zusammengefasst im `PROTOKOLL_BOX_01.md`.
