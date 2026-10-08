# inventar_rein — Lieferung L2 (transfer)

Stand 08.10.2026 · gehört in denselben Ordner `inventar_rein/` wie L1 (neue Dateien ergänzen, nichts ersetzen).

## Neu
| Datei | Inhalt |
|---|---|
| `transfer.py` | Zustandsautomat der Buchung: `abgang_buchen`, `scan_ist_hier`, `eingang_bestaetigen`, `zurueckziehen`, `ueberfaellige`, `erinnert`, `status_auf`, `zubehoer_folgt` und die Datenklassen aus dem Auftrag |
| `tests/test_transfer.py` | 23 Prüffälle: B1–B13 (Nummer im Namen) und Z1–Z8 für Teilmengen, Zusammenführung, Fehlerfälle |

## Aufruf (drei Zeilen)
```python
from datetime import datetime, timezone; from inventar_rein.transfer import Standort, Zustand, abgang_buchen, scan_ist_hier
z = Zustand((Standort("BM-00017", 100, 1, datetime(2026, 10, 1, tzinfo=timezone.utc), None, None, "web", "anna"),), ())
z = abgang_buchen(z, "BM-00017", 100, 200, 1, "bernd", datetime(2026, 10, 8, tzinfo=timezone.utc), "handy", "uuid-1").zustand; print(scan_ist_hier(z, "BM-00017", 200, "carla", datetime(2026, 10, 9, tzinfo=timezone.utc), "handy", "uuid-2").protokoll)  # ('transfer.eingang',)
```

## Prüflauf
```
python -m pytest -q        # im Ordner inventar_rein (L1 + L2)
57 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13.16, pytest 9.1.1)
```

## So ist es gebaut
- Reine Funktionen: `Zustand` rein, `Ergebnis(zustand, aenderungen, protokoll)` raus; die Eingabe wird nie verändert. Keine Zufallszahlen, keine Uhr: Transfer-Id ist `"t:" + eintrag_schluessel`.
- Jede `Aenderung.daten` enthält `person`, `zeit`, `quelle`. Naive `datetime` → `ValueError("transfer.zeit_naiv")`.
- Fehler und Protokoll sind Schlüssel (`transfer.menge_zu_gross`, `transfer.abgang_system` …), keine Sätze.
- Scan-Reihenfolge: offener Transfer hierher → bestätigen (B3) · Stück schon hier → `inventur.gesehen` (B5) · offener Transfer woandershin → überholen und neu (B6) · Stück woanders → System-Abgang (B4) · gar kein Standort → Erstanlage (B13).

## Abweichungen und Ergänzungen (Begründung)
- `Transfer` hat ein zusätzliches Feld `abgespalten: bool = False`. Grund: bei Teilmengen (B8) wird der Rest beim Abgang abgespalten; ohne Merker wüsste das Modul beim Eingang, Zurückziehen oder Überholen nicht, ob die Quelle noch zu schließen ist. Mit Vorgabewert, die Konstruktion nach Auftrag funktioniert unverändert.
- Überholter Transfer: `grund` ist der Schlüssel `transfer.gesehen_auf:<kostenstelle>` (kein deutscher Satz im Code); der Text steht in `texte_de.json` (L5).
- `zurueckziehen` hat laut Auftrag keinen Parameter `quelle`; die Änderung trägt deshalb `quelle = "web"`.
- `Aenderung.art = "meldung"` ist im Typ enthalten, wird aber in L2 nicht erzeugt.

## Offene Fragen
Siehe `FRAGEN_L2.md`.
