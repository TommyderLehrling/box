# inventar_rein — Lieferung L1 (Kataloge, Nummernformat, Fristen)

Stand 08.10.2026 · Box für Auftrag 01 · Reine Python-Module, keine Datenbank, kein Web, kein Framework.

## Was drin ist

| Datei | Inhalt |
|---|---|
| `kataloge.py` | Datenklassen `Gruppe`, `Merkmal`, `Pruefart`; Lader `lade_gruppen/_merkmale/_pruefarten`; Prüfung `pruefe_kataloge` |
| `daten/gruppen.json` | 12 Gruppen (BM, FZ, AG, KG, WZ, EL, VM, CO, SR, HA, BA, IT) |
| `daten/merkmale.json` | 44 Merkmale, je Gruppe 3–5 |
| `daten/pruefarten.json` | 12 Prüfarten (Druckbehälter in zwei Prüfarten geteilt) |
| `nummernformat.py` | `Muster`, `pruefe_muster`, `zaehler_schluessel`, `naechste`, `entspricht`, `normalisiere` |
| `fristen.py` | `naechste_faelligkeit`, `ampel`, `tage_bis`, `faellig_nach_zaehler`, `naechste_nach_zaehler`, `werktage_zwischen`, `werktage_addieren` |
| `tests/test_*.py` | 34 Prüffälle; Namen `test_K<n>_…` (kataloge), `test_N<n>_…` (nummernformat), `test_F<n>_…` (fristen) |
| `requirements.txt` | `openpyxl`, `segno` (in L1 noch nicht gebraucht) |

## Aufruf (drei Zeilen)

```python
from datetime import date; from inventar_rein import kataloge, nummernformat as nf, fristen
nummer, stand = nf.naechste(nf.Muster("{gruppe}-{nr:5}"), {"BM": 16}, 2026, "BM")  # ("BM-00017", {"BM": 17})
print(nummer, fristen.naechste_faelligkeit(date(2026, 8, 31), 6), kataloge.pruefe_kataloge(kataloge.lade_gruppen(), kataloge.lade_merkmale(), kataloge.lade_pruefarten()))  # BM-00017 2027-02-28 []
```

(`print` steht nur in diesem Beispiel, nicht im Code der Module.)

## Prüflauf

```
python -m pytest -q        # im Ordner inventar_rein
34 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13.16, pytest 9.1.1)
python -c "import inventar_rein"   # ohne Ausgabe
```

Hinweis: Geprüft unter Python 3.12.3 und 3.13.16 (die Prüffälle von L1 laufen in beiden Versionen grün). VSC lässt sie bitte einmal in der Zielumgebung laufen.

## Fehlermeldungen sind Schlüssel

`pruefe_kataloge`, `pruefe_muster` und alle `ValueError` liefern **kurze Schlüssel** (z. B. `merkmal.gruppe_unbekannt:neu:xyz`, `muster.nr_fehlt`), keine deutschen Sätze. Die Texte dazu kommen mit `texte_de.json` in L5.

## Annahmen (vorläufig, siehe FRAGEN_L1.md)

1. Merkmal-Schlüssel sind **über alle Gruppen eindeutig** (damit die Importspalte `m:<schluessel>` in L4 nie mehrdeutig ist).
2. `{nr}` ohne Breite ist ein Fehler; Breite 1–12, ohne führende Null.
3. Monatsarithmetik kürzt nur auf den letzten Tag des Zielmonats (28.02.2027 + 12 → 28.02.2028, nicht 29.02.).
4. Ampel: genau `gelb_ab_tagen` Tage vor Fälligkeit ist noch gelb.
5. `werktage_zwischen` mit `bis <= von` ergibt 0. `faellig_nach_zaehler` bei kleinerem Zählerstand als bei der Prüfung ergibt `False`.
6. `normalisiere` lässt „ß“ stehen (statt „SS“) und fasst Leerraum zu einem Leerzeichen zusammen. `entspricht` normalisiert nicht selbst.
7. Gruppenzuordnung von `leitern_tritte`, `feuerloescher`, `druckbehaelter_*`, Durchführung von `anschlagmittel`/`uvv_fahrzeug`/`wartung_betriebsstunden` sind **meine Vorschläge**; Rechtsgrund mit „(prüfen)" dort, wo ich mir nicht sicher bin.

## Abweichungen vom Auftrag

- `tests/__init__.py` (nur ein Kommentar) zusätzlich, damit `pytest -q` im Ordner `inventar_rein` ohne weitere Einstellung `import inventar_rein` findet.
- Für Abschnitte 4–6 gibt der Auftrag keine Regelnummern. Ich habe K1–K10, N1–N12, F1–F12 selbst vergeben (Nummer im Testnamen).
- `pruefe_kataloge` prüft zusätzlich: Schlüsselform (`a-z0-9_`), leere Bezeichnung, unbekannte `oben`-Gruppe, doppelte Auswahlwerte, unbekannte `durchfuehrung`, `zaehler_intervall >= 1`.

## Offene Fragen

Siehe `FRAGEN_L1.md`.
