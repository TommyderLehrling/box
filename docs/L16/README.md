# L16 — Nachbesserung L15a, Feiertage, Mengenabfrage, Zählerstand im Import, Browser-Prüffälle, Abschluss (Auftrag 07)

Letzte Lieferung der Vorarbeit. Gebaut und geprüft mit **kern-0.15.4**; `kern_mindestens` bleibt `"0.15.3"`, `pyproject.toml` bleibt `>=0.15.3`. Entwurf, bis VSC es fährt.
Mit L16 kommen **alle Dateien, die seit L10 je geändert wurden** (200), noch einmal flach mit Sortiertabelle (`00_INFO_FUER_GER.md`), damit nichts am Git hängt.

```
python -m pytest -q -W error        # im Ordner Inventar; ohne Datenbank → 412 passed, skipped = 0
# mit Datenbank (Kern 0.15.4, PostgreSQL 16): tests/integration ohne test_t_i_6.py → 66 passed, skipped = 0   (Aufruf: tests/integration/laufen.md)
# Browser (Chromium headless, Playwright 1.56, Prüf-Box aus tests/browser/box_starten.py) → 29 passed, skipped = 0   (Aufruf: tests/browser/README.md)
```

## Teil 1: L15a — die Antworten zu `FRAGEN_L15.md`

| Nr. | Was | Wo | Geprüft in |
|---|---|---|---|
| 3 | Werkstatt-Seite: am Vorgang „✉ nicht zugestellt (keine Adresse)“ bzw. „… (nicht eingereiht)“, wenn der **letzte** Vermerk `mail_ohne_adresse` oder `mail_nicht_eingereiht` ist (eine Protokollabfrage für alle Zeilen) | `dienstlogik/werkstatt.py` (`_nicht_zugestellt`), `vorlagen/inventar_werkstatt.html` | `test_werkstatt_db.py` |
| 6 | Personen-Auswahl im Abschluss-Dialog: zuerst Konten mit Baustein `inventar.werkstatt` (Entzug schlägt Gewährung), dann die übrigen aktiven, je Gruppe nach Name — eine Abfrage | `dienstlogik/werkstatt.py` (`personen_auswahl`) | `test_werkstatt_db.py` |
| 11 | Beschriftung „Stand der Parameter“ statt „Gerechnet am“ | `texte/de.json` | `test_kosten_db.py` |
| 15 | Vergleichszeile „Reparaturen: geplant / angefallen“ (geplant = Monate seit Kauf × Reparaturanteil je Monat; angefallen = Σ `reparatur.kosten`) auf der Stück-Seite und im Block je Stück; „echt“ und „kalkulatorisch“ bleiben getrennt, keine Summe | `rein/kosten.reparatur_geplant`, `dienstlogik/kostenrechnung.py`, `stueckseite.py`, Vorlagen | `tests/rein/test_kosten_l15.py`, `test_kosten_db.py` |
| 17 | **Download der Auszüge** `/inventar/kosten/auszug/<dateiname>` (`kosten_sehen`, nur `.csv` direkt in `export/`, `attachment`, `nosniff`; die Datei bleibt im Ordner; Pfade mit `..`, Unterordner, Punkt am Anfang → „unbekannt“) | `dienstlogik/kostenrechnung.auszug_lesen`, `web/kosten.py`, `web/helfer.csv_download` | `test_kosten_db.py`, Browser `test_kosten.py` |
| pyflakes | ungenutzte Importe in `web/kostenstelle.py`, `rein/bestand.py`, `dienstlogik/stueck.py`, `dienstlogik/laden.py` entfernt; **`tests/test_regeln.py` fährt pyflakes über das ganze Paket** (rot bei ungenutzten Importen); `pyproject.toml` nennt `pyflakes` unter `pruefung` | — | `tests/test_regeln.py` |

## Teil 2: L16

| Teil | Was | Wo |
|---|---|---|
| **Feiertage** (Nr. 13) | Einstellung `bundesland` (16 Länder; leer = keine Feiertage), `rein/feiertage.py` (feste Tage + Ostern-Tage, Buß- und Bettag; nur **landesweite** Feiertage), Sollwert-Prüffälle 2026/2027 **je Land** von Hand aus dem Kalender. **Eigene Tage** in der neuen Tabelle `inventar.feiertag` (`i0001`, 19 Tabellen), Verwaltung → Einstellungen zeigt die freien Tage des Jahres (Land + eigene) und erlaubt Eintragen, Abschalten, Einschalten. **Ein Datenzugriff** `dienstlogik/feiertage.py` (`werktage(db, von, bis, mandant_id)` zählt beide Tage mit). Wirkung: Vorhaltung und Miete-gegen-eigen **bei Werktage-Rechnung** (`werktage` > 0), Transfer-Frist (`transfer_frist_werktage`), Kachel „Transfers überfällig“, Erinnerung | `rein/feiertage.py`, `dienstlogik/feiertage.py`, `kostenrechnung.py`, `erinnerungen.py`, `kacheln.py`, `katalogpflege.py`, `web/verwaltung.py`, `modelle.py`, `migrationen/versions/i0001_grundlinie.py`, `vorlagen/inventar_verwaltung_einstellungen.html` |
| **Mengenabfrage** (Nr. 21) | Läuft eine Inventur (Stichtag gesetzt) und ist das Stück ein Mengenartikel, der auf der Kostenstelle steht und dort seit dem Stichtag noch nicht gesehen wurde, zeigt der Scan „Ist hier“ das Feld „Menge vor Ort“ (vorbelegt mit der Buchmenge). Gesehen = genannte Menge, Fehlmenge = Rest, **nichts wird gebucht**; `inventar.inventur_gesehen` trägt die Menge (`alt_wert = ks:<id>;menge:<n>`). Ohne Inventur wie bisher. Mehrere Sichtungen derselben Kostenstelle ergeben **eine** (die jüngste); ein gewöhnlicher Scan macht eine genannte Menge nicht rückgängig | `dienstlogik/inventur.py` (`zaehlen_abfragen`), `dienstlogik/transfer.py`, `web/transfer.py`, `web/stueck.py`, `vorlagen/inventar_stueck.html` |
| **Zählerstand im Import** (Nr. 19) | Spalte „Zählerstand“ (15., optional) in der Vorlage; alte 14-Spalten-Dateien werden weiter gelesen. Quelle `import`; gleich oder höher als der letzte → eingetragen; **zu niedrig** oder **Stück ohne Zähler** → nur ein Hinweis im Bericht. Der Prüfbericht zeigt die Zahl, die Vorschau schreibt nichts | `rein/import_vorlage.py`, `dienstlogik/import_lauf.py`, `web/verwaltung.py`, `vorlagen/inventar_verwaltung_import.html` |
| **Browser-Prüffälle** | `tests/browser/`: Aufbau (`box_starten.py`, Seed der Testdaten), 29 Fälle — die 14 aus `INTEGRATION_VSC.md` Abschnitt 4 plus Werkstatt, Kosten, Inventur, Fällig-Liste mit Rücksprung, Nachweis inline, Feiertage, Zählerstand-Import, Zoom; Kamera-Attrappe für den Scan-Weg. Chromium headless selbst gefahren: **29 passed** | `tests/browser/*` |
| **Funde aus dem Browser** | (1) htmx 2 tauscht 409 nicht ein: der Fehlersatz einer abgewiesenen Handlung blieb unsichtbar → `inventar.js` tauscht 409 ein, jede Vorlage mit `hx-post` lädt es (Test in `test_vorlagen.py`); (2) `<script>` im Titelblock der Werkstatt erschien als Text im Tab (Test: im Titelblock steht kein Markup); (3) der Export-Knopf der Kosten leitete auf dieselbe Adresse mit `#exporte` um, ein zweiter Klick lud nichts neu; (4) schmale Bildschirme: Tabellen und Wahlfelder liefen über die Seite hinaus → Klasse `inventar-seite`, Regeln in `statisch/stil.css` | `statisch/inventar.js`, `statisch/stil.css`, alle Vorlagen, `web/kosten.py` |
| **Abschluss** | `README.md` (Wurzel) als Gesamtübersicht L10–L16, `INTEGRATION_VSC.md` final, `tests/integration/laufen.md` final (Stand „i0001 offen“), diese Datei, `FRAGEN_L16.md`, `PROTOKOLL_BOX_10.md` | — |

## Neue und geänderte Dateien seit L15

| Pfad | Was |
|---|---|
| `rein/feiertage.py`, `dienstlogik/feiertage.py` (neu) | Feiertage, ein Datenzugriff |
| `rein/kosten.py`, `rein/import_vorlage.py`, `rein/beispielbetrieb.py` | `reparatur_geplant` · Spalte Zählerstand · Zeile mit Zählerstand |
| `dienstlogik/` — `werkstatt`, `kostenrechnung`, `stueckseite`, `inventur`, `transfer`, `import_lauf`, `katalogpflege`, `erinnerungen`, `laden`, `stueck` | Anpassungen |
| `web/` — `kosten`, `helfer`, `werkstatt`, `stueck`, `transfer`, `verwaltung`, `kostenstelle` | Routen |
| `vorlagen/` (alle Seiten des Inventars), `statisch/inventar.js`, `statisch/stil.css` | Oberfläche |
| `modelle.py`, `migrationen/versions/i0001_grundlinie.py`, `kacheln.py`, `rein/bestand.py` | Tabelle `feiertag`, Kacheln mit Feiertagen |
| `texte/de.json` | **alle** Texte (933 Schlüssel) |
| `tests/rein/test_feiertage.py` (neu), `tests/integration/test_feiertage_db.py`, `test_inventur_menge_db.py`, `test_import_zaehler_db.py` (neu), `tests/browser/*` (neu) | Prüffälle |
| `tests/test_regeln.py` (pyflakes), `tests/test_vorlagen.py`, `tests/rein/test_texte.py`, `tests/rein/test_import_vorlage.py`, `tests/rein/test_testdaten.py`, `tests/integration/test_t_i_5.py` (19 Tabellen), `test_kosten_db.py`, `test_werkstatt_db.py` | angepasst |
| `README.md`, `INTEGRATION_VSC.md`, `tests/integration/laufen.md`, `pytest.ini` (ohne `browser`), `pyproject.toml` | Anleitung |
| `docs/L15/FRAGEN_L15.md` | **ersetzt** durch die Fassung mit den Antworten GER |
| `docs/L16/*`, `docs/PROTOKOLL_BOX_10.md` | diese Lieferung |

Vorgesehen, nicht gebaut (Auftrag 05, Abschnitt 7): `etikett_code`. Die Scan-Auflösung steht an **einer** Stelle (`dienstlogik/sicht.aufloesen`).
