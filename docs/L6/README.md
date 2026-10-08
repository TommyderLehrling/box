# inventar_rein — Lieferung L6 (Korrekturen nach Spec v0.2 und Vorarbeit für G2 bis G5)

Stand 08.10.2026 · gehört in denselben Ordner `inventar_rein/` wie L1 bis L5. **Dateien dieser Lieferung ersetzen gleichnamige Dateien aus früheren Lieferungen** (Liste unten).

## Anlass
Nach dem Lesen von `SPEC_Geraete_v0.2.md` und `02_SCHNITTSTELLEN.md` habe ich meine eigenen Fehler korrigiert (Begriffe, Bauteilkatalog, Werktage) und die Module ergänzt, die die Spec Box zuweist oder die sich ohne Datenbank prüfen lassen.

## Ersetzt (gleicher Name, neuer Inhalt)
| Datei | Änderung |
|---|---|
| `kataloge.py` | neu: `Bauteil`, `lade_bauteile`, `passende_bauteile`, `pruefe_bauteile` |
| `kosten.py` | `vorhaltung` mit `werktage=True` und `feiertage` (Spec-Frage 3: Kalender- oder Werktage als Einstellung) |
| `daten/texte_de.json` | Begriffe nach Spec Abschnitt 7 (Prüfergebnis, Meldungsart/-status, Reparaturstatus), Seite `bauteile` = Bauteilkatalog, Texte für alle neuen Schlüssel (384 Einträge) |
| `tests/test_kataloge.py` (K1–K12), `tests/test_kosten.py` (C1–C14), `tests/test_texte.py` | erweitert |

## Neu
| Datei | Inhalt | Prüffälle |
|---|---|---|
| `daten/bauteile.json` | Startkatalog Bauteile: leer (nur die Form) | — |
| `pruefung.py` | Zuordnung Prüfart ↔ Stück, Eintragen, Stand nach Datum **und** Zähler, Ampel, Faellig-Liste | 12 (R1–R12) |
| `stueck_status.py` | Status eines Stücks, Wechselregeln, Grundpflicht, Buchbarkeit | 8 (S1–S8) |
| `werkstatt.py` | Statusautomaten für Meldung und Reparatur, Folge für den Stückstatus, Reparaturkosten | 11 (W1–W11) |
| `import_plan.py` | idempotenter Import: neu / unverändert / abweichend, Bericht je Gruppe und Art | 6 (M1–M6) |
| `inventur.py` | Stichtagslauf: gefunden, woanders, Fehlmengen, „vermisst" vorschlagen | 7 (V1–V7) |
| `bestand.py` | die Dienste `bestand` und `stueck` nach `02_SCHNITTSTELLEN.md` als reine Funktionen | 9 (D1–D9) |
| `tests/test_transfer_eigenschaften.py` | zufällige Buchungsfolgen (Eigenschaftstests) für `transfer` | 5 (P1–P4) |

## Aufruf (drei Zeilen)
```python
from datetime import date; from inventar_rein.pruefung import Zuordnung, Eintrag, pruefstand
stand = pruefstand(Zuordnung("dguv_v3", 12, None), Eintrag("dguv_v3", date(2025, 10, 20), "bestanden"), date(2026, 10, 8), ab=date(2025, 1, 1))
print(stand.faellig_am, stand.tage, stand.ampel)  # 2026-10-20 12 gelb
```

## Prüflauf
```
python -m pytest -q        # im Ordner inventar_rein (L1 bis L6)
180 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13.16, pytest 9.1.1; auch mit -W error)
```

## Wie die Eigenschaftstests arbeiten
Je Lauf zufällige Folgen aus Abgang, Scan, Eingang, Zurückziehen und Erinnern (feste Startwerte, Einzelstück und Menge 40). Nach **jedem** Schritt gilt: Menge bleibt erhalten (offene Standorte + abgespaltene, noch schwebende Menge), höchstens ein offener Standort je Kostenstelle, keine leeren Standorte, Ids eindeutig, Eingang nur bei „bestätigt", angekündigte Ganz-Transfers haben noch ihre Quelle. Zusätzlich: Wiederholung mit gleichem Buchungsschlüssel ändert nichts (P2), und die `Aenderung`-Liste allein reicht, um den Zustand nachzubauen (P3) — das ist genau das, was VSC in die Datenbank schreibt. Gegenprobe: zwei absichtlich eingebaute Fehler in `transfer.py` (Menge am Ziel nicht zusammengeführt, Teilmenge beim Zurückziehen nicht zurückgegeben) wurden von den Tests gefunden; die Datei ist wiederhergestellt. **In `transfer.py` selbst haben die Eigenschaftstests keinen Fehler gefunden.** Den einzigen Fehler dieser Runde hat der Prüffall V5 in meinem neuen Modul `inventur.py` gefunden (ein Mengenartikel auf zwei Kostenstellen wurde als „woanders gesehen" gewertet) — behoben.

## Prüffall-Namen und die Spec-Kennung `T-R-…`
Spec Abschnitt 18 kennt für Box-Module `T-R-…`. Die Zuordnung ist mechanisch: `T-R-<MODUL>-<KÜRZEL><NR>`, z. B. `test_B7_…` = `T-R-TRANSFER-B7`.

| Modul | Kürzel | Modul | Kürzel |
|---|---|---|---|
| kataloge | K | kosten | C |
| nummernformat | N | import_vorlage | I |
| fristen | F | testdaten | T |
| transfer | B (Regeln), Z (Zusatz), P (Eigenschaften) | etiketten | E |
| pruefung | R | texte_de.json | X |
| stueck_status | S | werkstatt | W |
| import_plan | M | inventur | V |
| bestand | D | | |

## Abweichungen und Ergänzungen
- Der Auftrag nennt das Paket `inventar_rein`, die Spec Abschnitt 14 noch `digiassistenz_inventar.rein`. Ich bleibe beim Auftrag (neuer).
- `Quelle` in `transfer` kennt nur die vier Werte des Auftrags (`web`, `handy`, `import`, `system`); die Spec Abschnitt 4 nennt für das Protokoll weitere (`baustelle`, `pruefung`, `werkstatt`). Siehe Frage 12.
- Meldungen, Prüfungen und Reparaturen sind einfache Datenklassen **ohne** Stück-Bezug, weil das Modul „ein Stück" nicht kennt; die Zuordnung macht VSC.

## Offene Fragen
Siehe `FRAGEN_L6.md`.
