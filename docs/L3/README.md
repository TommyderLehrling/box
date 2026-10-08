# inventar_rein — Lieferung L3 (kosten)

Stand 08.10.2026 · gehört in denselben Ordner `inventar_rein/` wie L1 und L2.

## Neu
| Datei | Inhalt |
|---|---|
| `kosten.py` | `Kostenparameter`, `Kostensatz`, `Vorhaltung`, `kostensatz`, `vorhaltung`, `gesamtkosten`, `kalkulatorisch_bis`, `miete_vs_eigen`, `restbuchwert_kalk` |
| `tests/test_kosten.py` | 14 Prüffälle: `test_bagger` mit allen Sollwerten, C1–C13 |

## Aufruf (drei Zeilen)
```python
from decimal import Decimal as D; from inventar_rein.kosten import Kostenparameter, kostensatz
satz = kostensatz(Kostenparameter(D("150000"), D("15000"), 96, D("4.0"), D("12.0")))
print(satz.satz_monat, satz.satz_tag, satz.satz_woche)  # 3156.25 105.21 736.46
```

## Prüflauf
```
python -m pytest -q        # im Ordner inventar_rein (L1 bis L3)
71 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13.16, pytest 9.1.1)
```
`test_bagger` bestätigt die Sollwerte aus dem Auftrag: Abschreibung 1.406,25 · Zins 250,00 · Reparatur 1.500,00 · Monat 3.156,25 · Tag 105,21 · Woche 736,46.

## So ist es gebaut
- Alles `Decimal`; Rundung kaufmännisch (`ROUND_HALF_UP`) auf 2 Stellen erst am Ende jeder Größe. Darum ist die Woche **736,46** (aus dem ungerundeten Tagessatz) und nicht 105,21 × 7 = 736,47.
- `vorhaltung`: Der Eingangstag zählt zum Ziel, der Abgangstag nicht mehr zur Quelle (Standort `[von, bis)` in Kalendertagen, geschnitten mit dem Zeitraum `[von, bis]`).
- `kalkulatorisch_bis` und `restbuchwert_kalk` zählen volle Monate mit derselben Monatsende-Regel wie `fristen`.
- Ungültige Parameter → `ValueError` mit Schlüssel (`kosten.preis_ungueltig` …).

## Abweichungen und Ergänzungen
- `vorhaltung` hat einen zusätzlichen Parameter `mit_menge: bool = False` (siehe Frage 1).
- Steuerliche AfA wird nicht gerechnet (wie im Auftrag).

## Offene Fragen
Siehe `FRAGEN_L3.md`.
