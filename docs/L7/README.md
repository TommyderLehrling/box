# L7 — Korrekturen nach Auftrag 02

Geänderte Dateien (ersetzen gleichnamige aus L1–L6): `transfer.py`, `pruefung.py`, `bestand.py`, `inventur.py`, `import_vorlage.py`, `import_plan.py`, `testdaten.py`, `daten/pruefarten.json`, `daten/merkmale.json`, `daten/texte_de.json`; neu `daten/testdaten_namen.json`; Prüffälle `test_transfer`, `test_transfer_eigenschaften`, `test_pruefung`, `test_bestand`, `test_kataloge`, `test_import_vorlage`, `test_import_plan`, `test_inventur`, `test_texte`, `test_testdaten`. Unverändert, nicht neu geliefert: alle übrigen Dateien.

```
python -m pytest -q        # im Ordner inventar_rein
193 passed / 0 failed / 0 skipped   (Python 3.12.3, auch mit -W error)
```

## Was sich ändert (Nummern wie Auftrag 02, Abschnitt B)

| B | Änderung |
|---|---|
| 1 | `transfer`: Abgang spaltet nichts mehr ab, die Menge bleibt auf A `vor_ort` (reserviert über `belegt`), Teilung beim Eingang. `Transfer.abgespalten` entfällt. Neu `beendet_am` (bei `ueberholt`/`zurueckgezogen`; `status_auf` nutzt es), `zurueckziehen(..., quelle="web")`, `Quelle` um `baustelle`, `pruefung`, `werkstatt` erweitert. |
| 2 | Teil-Eingang: `eingang_bestaetigen(..., menge=8)` bei 10 angekündigt bestätigt 8 und kündigt die Fehlmenge 2 als neuen Transfer an (Grund `transfer.fehlmenge`, `abgang_am` übernommen, daher bald in `ueberfaellige`); `scan_ist_hier(menge=…)` ebenso; Mehrmenge → `ValueError(transfer.menge_zu_gross)`. Prüffälle B14–B16, Z9. |
| 3 | `bestand`: `StueckInfo.seriennummer/hersteller`, `stueck_auskunft` liefert beides, `finde_stueck(..., nach="inventarnummer"\|"seriennummer")`. |
| 4 | `pruefung`: nie geprüft → Ampel `unbekannt` (Datum und Tage `None`), Erstfälligkeit erst nach der ersten Prüfung (Parameter `ab` und `erstfaellig` entfallen), `ohne_nachweis(...)` als eigener Block neben `faellig_liste`. |
| 5 | Prüfarten: `dguv_v3` → `dguv_v3_baustelle` (3) und `dguv_v3_buero` (24); `uvv_erdbau`, `hebezeuge` Rechtsgrund; neu `kran`, `druckbehaelter_aussen`, `sp_sicherheitspruefung`, `hubarbeitsbuehne`, `verbandkasten`, `baustromverteiler`; Druckbehälter 60/120/24; `hu` 12; Merkmal `fahrzeugklasse`. „(prüfen)" steht überall, wo Fachperson bestätigt. |
| 6 | Texte: `{name}`-Platzhalter, wörtliche Klammern als `{{ }}` (zwei Texte angepasst); neue Texte für `unbekannt`, `fehlmenge`, `mehr_gesehen`, `beispiel_uebersprungen`, `abweichung`. Prüffall X8: jeder Text lässt sich mit Dummy-Mapping formatieren. |
| 7 | `testdaten`: Namenslisten in `daten/testdaten_namen.json`, Lader `lade_namen()`. |
| A | Import: Beispielzeilen (`Besonderheiten` beginnt mit `BEISPIEL`) werden übersprungen, Hinweis `import.hinweis.beispiel_uebersprungen` über `lies_mit_hinweisen` (`lies` bleibt gleich); Gruppe als Schlüssel oder Bezeichnung; `plane(...).hinweise` mit `import.hinweis.abweichung` je Feld; `inventur.mehr_gesehen` als Hinweis mit Differenz. |

## Eigenschaftstests

P1 prüft 500 zufällige Buchungsfolgen zu je 30 Schritten (Gesamtmenge 1 und 40), P2 150, P3 120, P4 80 Folgen; Invarianten nach jedem Schritt: Menge bleibt erhalten, höchstens ein offener Standort je Kostenstelle, angekündigte Mengen liegen noch im Bestand, Änderungen beschreiben den Zustandswechsel vollständig. Kein Fehler in `transfer.py` gefunden. Gegenprobe: zwei absichtlich eingebaute Fehler (falsche Restmenge bei der Teilung, fehlende Mehrmengen-Prüfung) wurden gefunden, Datei danach wiederhergestellt.

## Ein Fund beim Umbau

Ein erneut gesendeter Scan (Handy offline, gleicher `eintrag_schluessel`) hätte nach einem Teil-Eingang den Fehlmengen-Transfer ungewollt bestätigt, weil der Scan-Schlüssel nirgends gemerkt war. Neu: `Transfer.eingang_schluessel`; `scan_ist_hier` meldet bei bekanntem Schlüssel `transfer.doppelt`. **VSC muss das Feld mit speichern.**
