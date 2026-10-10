# L14 — Nachbesserung L13a (Auftrag 05, Abschnitte 1–4) und Werkstatt (G4)

Eine Lieferung für beide Teile (Auftrag 05, Abschnitt 6). Gebaut und geprüft mit **kern-0.15.4**; `kern_mindestens` bleibt `"0.15.3"`, `pyproject.toml` bleibt `>=0.15.3`.

```
python -m pytest -q -W error        # im Ordner Inventar; ohne Datenbank → 331 passed, skipped = 0
# mit Datenbank (Kern 0.15.4, PostgreSQL 16): tests/integration ohne test_t_i_6.py → 43 passed, skipped = 0   (Aufruf: tests/integration/laufen.md)
```

## Teil 1: L13a — die sechs Änderungen aus den Antworten (`FRAGEN_L13.md`)

| Nr. | Was | Wo | Geprüft in |
|---|---|---|---|
| 1 | Startstandort mit **`pflegen`**: Wahl aus `pflegen` auf der Kostenstelle, `stueck.anlegen` prüft `darf("inventar","pflegen",ks)`. **Im Import** dasselbe: Zeilen auf einer Kostenstelle ohne `pflegen` werden nicht angelegt und stehen im Bericht (`import.hinweis.kostenstelle_ohne_recht`). `buchen` bleibt für jede Bewegung danach | `dienstlogik/stueck.py`, `dienstlogik/import_lauf.py`, `web/stueck.py`, `web/verwaltung.py` | `test_l13a_db.py`: `buero` legt an (grün), `buero` bucht um und scannt (403); Import mit Kostenstelle ohne `pflegen` |
| 3 | Import ohne `kosten_pflegen`: Kaufdaten weiter übersprungen, der Prüfbericht sagt „Kaufpreis und Kaufdatum in n Zeilen übersprungen“ | `dienstlogik/import_lauf.py`, `vorlagen/inventar_verwaltung_import.html` | `test_pruefungen_db.py`, `test_vorlagen.py` |
| 4 | Zählerstand aus der Prüfung unter dem letzten Stand: bleibt an der Prüfung, **Hinweis nach dem Speichern** (an der Stück-Seite und in der Fällig-Liste) | `dienstlogik/pruefung.py`, `web/pruefungen.py`, `web/helfer.py` | `test_pruefungen_db.py` |
| 6 | Nachweis-Abruf **`inline`** statt `attachment`; `nosniff` und fester Typ bleiben | `web/pruefungen.py` | `test_pruefungen_db.py` |
| 9 | Kachel „Prüfungen fällig“ für `pruefen` **oder** `werkstatt`: `Kachel.rechte=(("inventar","pruefen"),("inventar","werkstatt"))` (Feld `rechte`, Tupel von Paaren) | `rein/kacheln.py`, `kacheln.py` | `tests/rein/test_kacheln.py`, `test_l13a_db.py` |
| 10 | `erinnern`: Uhrzeit gemerkt, vor ihr nur die Uhr (keine Sitzung), Einstellung höchstens einmal je Stunde neu gelesen; `hochlaufen(leise=False)` | `erinnern.py` | `tests/test_erinnern.py` (nachts 6 statt 72 Sitzungen) |

Abschnitte 2–4 des Auftrags: Wheel 0.15.4 eingesetzt, Steckbrief gelesen (neu 7.8: eine Logdatei je Prozess `log/digiassistenz-inventar-erinnern.log`, von Hand geprüft) ·
Pillow nicht gepinnt, `pydyf==0.12.1` und die Unterpaketliste in `INTEGRATION_VSC.md` korrigiert · `INTEGRATION_VSC.md` nachgeführt (Kern-Start und T-I-6 sind gefahren, Kern 0.15.4,
Dockerfile) · `docker/Dockerfile` kommt auf Drive als **`docker/Dockerfile.txt`** an (L10 hat dazu ein älteres `Dockerfile(1).txt`); VSC benennt beim Einbau um.

## Teil 2: L14 Werkstatt (G4)

`/inventar/werkstatt` (Recht `werkstatt`, neuer Menüpunkt „Werkstatt“):

* **Posteingang** der Meldungen: offen · angenommen · in Arbeit · erledigt (die letzten 30, mit wer/wann und Rückmeldung). Annehmen, Übernehmen, Erledigen (Rückmeldung Pflicht),
  Zurückziehen (Grund Pflicht). Das Foto der Meldung öffnet über `/inventar/meldung/<id>/foto` (inline, Prüfsumme geprüft).
* **Rückmeldung an den Melder** beim Erledigen: Mail über `mail.einreihen` (ohne aktives Konto oder Adresse bleibt es beim Vermerk) und **Vermerk am Stück** (Verlauf und
  Meldungen an der Stück-Seite).
* **Reparatur-Vorgang**: anlegen (aus einer Meldung oder von der Stück-Seite; intern/extern, Lieferant, Beschreibung), beginnen (Datum, geschätzte Kosten), abschließen (Datum, Kosten, Quelle
  `geschaetzt`/`rechnung`), Rechnungsbetrag nachtragen, zurückziehen mit Grund. Kosten trägt nur ein, wer `kosten_pflegen` hat, und sieht nur, wer `kosten_sehen` hat.
* **Status `in_reparatur`**: automatisch, solange eine Reparatur läuft, danach zurück auf `aktiv` (`rein.werkstatt.status_folge`); von Hand setzen/aufheben für `werkstatt` (nur zwischen `aktiv` und
  `in_reparatur`). Abgang und Eingang bleiben möglich; die Stück-Seite sagt es.
* Kacheln „Meldungen offen“ und „in Arbeit“ führen in die Werkstatt. Grundlage: `rein/werkstatt` (Automaten, unverändert bis auf „Abschließen ohne Kosten“).

Vorgesehen, nicht gebaut (Auftrag 05, Abschnitt 7): `etikett_code`. Die Scan-Auflösung steht jetzt an **einer** Stelle (`dienstlogik/sicht.aufloesen`).

## Geänderte und neue Dateien

| Pfad | Was |
|---|---|
| `dienstlogik/werkstatt.py` (neu), `web/werkstatt.py` (neu), `vorlagen/inventar_werkstatt.html` (neu) | Werkstatt |
| `rein/werkstatt.py`, `rein/kacheln.py`, `kacheln.py` | Abschließen ohne Kosten · `Kachel.rechte` · Kachel-Wege |
| `dienstlogik/stueck.py`, `import_lauf.py`, `pruefung.py`, `stueckseite.py`, `sicht.py` | Startstandort/`pflegen`, `status_setzen`, Import nach Rechten, Zählerhinweis, Meldungen mit Rückmeldung, `aufloesen` |
| `erinnern.py` | Merker, keine Sitzung vor der Uhrzeit, Log auf stdout |
| `modul.py`, `web/__init__.py`, `web/helfer.py`, `web/pruefungen.py`, `web/seiten.py`, `web/stueck.py`, `web/verwaltung.py` | Menüpunkt, Router, Hinweise, inline, Wege |
| `vorlagen/inventar_stueck.html`, `inventar_faellig.html`, `inventar_verwaltung_import.html` | Oberfläche |
| `texte/de.json` | **alle** Texte |
| `docker/Dockerfile` (auf Drive `Dockerfile.txt`), `INTEGRATION_VSC.md`, `README.md`, `tests/integration/laufen.md` | Anleitung |
| `tests/…` | neu: `integration/test_l13a_db.py`, `integration/test_werkstatt_db.py`; geändert: `test_vorlagen.py`, `test_modul.py`, `test_erinnern.py`, `rein/test_kacheln.py`, `rein/test_werkstatt.py`, `integration/test_pruefungen_db.py` |
