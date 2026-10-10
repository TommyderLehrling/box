# L15 — Nachbesserung L14a (Auftrag 06, Abschnitt 1) und Kosten (G5, Abschnitt 4)

Eine Lieferung für beide Teile (Auftrag 06, Abschnitt 5). Gebaut und geprüft mit **kern-0.15.4**; `kern_mindestens` bleibt `"0.15.3"`, `pyproject.toml` bleibt `>=0.15.3`. Entwurf, bis VSC es fährt.

```
python -m pytest -q -W error        # im Ordner Inventar; ohne Datenbank → 360 passed, skipped = 0
# mit Datenbank (Kern 0.15.4, PostgreSQL 16): tests/integration ohne test_t_i_6.py → 56 passed, skipped = 0   (Aufruf: tests/integration/laufen.md)
```

## Teil 1: L14a — die fünf Änderungen aus den Antworten (`FRAGEN_L14.md`, „Antworten GER“)

| Nr. | Was | Wo | Geprüft in |
|---|---|---|---|
| 3 | **Eine** Mailfunktion `benachrichtigen(db, benutzer, schluessel, *, mandant_id, von=None, objekt_id=None, **felder)`; sie ruft `mail.einreihen(db, an=[adresse], betreff=…, text=…, mandant_id=…, benutzer_id=…)` (nur Schlüsselwörter, `mandant_id` immer). Adresse `benachrichtigung_email`, sonst `email`; **ohne Adresse nicht einreihen, sondern vermerken**. Beim **Erledigen und Zurückziehen** (mit Grund) geht die Mail an den Melder, beim Annehmen/Übernehmen keine. **Alle** Mails des Moduls laufen darüber — auch `erinnerungen.py` (Transfers an Disposition und Melder, Prüfungen an `werkstatt`), jetzt eine Mail je Person. Versendet wird nichts: die Zeile steht in `kern.mail_ausgang` mit Status `wartend` | `dienstlogik/benachrichtigen.py` (neu), `dienstlogik/werkstatt.py`, `dienstlogik/erinnerungen.py`, `texte/de.json` (`inventar.mail.*`) | `tests/test_benachrichtigen.py` (6, ohne Datenbank, darunter: nur diese Datei ruft `mail.einreihen`), `test_werkstatt_db.py` (Zeile `wartend`, Mandant gesetzt), `test_pruefungen_db.py` |
| 5 | **Hand bleibt Hand**: setzt die Automatik `in_reparatur`, schreibt sie `status_grund = "reparatur:<id>"`; endet die letzte laufende Reparatur, wird nur dann `aktiv`, wenn der Grund so beginnt — sonst bleibt `in_reparatur`, bis die Werkstatt es von Hand aufhebt | `rein/werkstatt.status_folge(…, status_grund)`, `dienstlogik/werkstatt._status_folgen` | `tests/rein/test_werkstatt.py` (W9), `test_werkstatt_db.py` (von Hand gesperrt, kleiner Vorgang → bleibt gesperrt; Automatik hebt ihre eigene Sperre auf) |
| 6 | **Beim Abschließen Pflicht — wer, wo, was, wann**: extern `lieferant_id`, intern **neu `durchgefuehrt_von`** (vorbelegt mit der Abschließenden; benannter Fremdschlüssel `fk_reparatur_durchgefuehrt_von` auf `kern.benutzer`), **neu `arbeit`**, `beendet_am`. Beim Anlegen bleibt alles freiwillig. Beide Spalten in **`i0001`**. Posteingang und Stück-Seite zeigen wer/was | `modelle.py`, `migrationen/versions/i0001_grundlinie.py`, `rein/werkstatt.py`, `dienstlogik/werkstatt.py`, `dienstlogik/stueckseite.py`, Vorlagen | `tests/rein/test_werkstatt.py` (W12, W13), `test_werkstatt_db.py`, `test_migration_gegen_modelle.py` |
| 7 | **Haken „Meldung damit erledigen“** im Abschluss-Dialog (an, wenn eine nicht erledigte Meldung dranhängt), darunter die Rückmeldung, **vorgefüllt mit `arbeit`**. Haken an → Abschluss + Meldung erledigt (`bearbeitet_von`, `erledigt_am`, `rueckmeldung`) + Benachrichtigung in **einer** Transaktion. Scheitert das Einreihen: Abschluss und Erledigung gelten, Vermerk „Mail nicht eingereiht“. Der Dialog steht jetzt **oben** auf der Seite (`?abschluss=<id>`) | `dienstlogik/werkstatt.reparatur_abschliessen`, `web/werkstatt.py`, `vorlagen/inventar_werkstatt.html`, `statisch/inventar.js` | `test_werkstatt_db.py`: mit Haken, ohne Haken, Fehlerfall, bereits erledigte Meldung, offene Meldung |
| 9 | **Foto am Stück abrufbar**: `/inventar/stueck/<id>/foto` (Recht `sehen` am Stück, Prüfsumme, inline, `nosniff`); die Stück-Seite zeigt es | `dienstlogik/pflege.foto_lesen`, `web/stueck.py`, `web/helfer.datei_antwort`, `vorlagen/inventar_stueck.html` | `test_werkstatt_db.py` (Abruf, ohne Foto, fremdes Stück, verändert, fehlt, kein Recht) |
| Hilfe | Hilfetext der Werkstatt-Seite nennt die eigene Vorlage „Werkstatt“ (keine Vorlage im Modul) | `texte/de.json` (`hilfe.inventar_werkstatt.danach`) | `tests/test_texte.py` |
| Grundlinie | `tests/integration/laufen.md`: **„i0001 offen“** | `tests/integration/laufen.md` | — |

## Teil 2: L15 Kosten (G5) — kalkulatorisch, nicht steuerlich

| Teil | Was | Wo |
|---|---|---|
| **Kostensätze** | wirksamer Satz je Stück: eigene Zeile vor der der Gruppe vor der der übergeordneten Gruppe; Parameter Kaufpreis(basis), Nutzungsdauer, Restwert, Zins, Reparaturanteil/Jahr → Monats-, Tages-, Wochensatz (`rein.kosten`); Quelle `gerechnet` / `manuell` / `bgl`, jede Zeile mit „Gerechnet am“. Je Stück überschreiben (`kosten_pflegen`, Stück-Seite), je Gruppe in Verwaltung → Kostensätze (Kaufpreisbasis neu). Kalendertage (30) oder Werktage (Einstellung `werktage`, z. B. 21,67) | `dienstlogik/kostenrechnung.py`, `dienstlogik/katalogpflege.py`, `web/stueck.py`, `web/verwaltung.py` |
| **Seite `/inventar/kosten`** | Menüpunkt „Kosten“ (`kosten_sehen`, Reihenfolge 14): **je Kostenstelle** (Σ Standorttage × Tagessatz × Menge, nur vor Ort, Zeitraum wählbar, Standard laufender Monat), **je Stück** (Kaufpreis, kalkulatorische Kosten bis heute, Reparaturen nach Quelle, Gesamtkosten, Zählerstand-Verlauf), **Miete gegen eigen**, **Anlagenbuch** (Kaufdaten) | `web/kosten.py`, `vorlagen/inventar_kosten.html`, `modul.py` |
| **Export** | CSV je Block nach `export/` (`kosten_<block>_<Zeitstempel>.csv`, BOM, Semikolon, Dezimalkomma), nichts überschrieben; die Seite listet die Pfade | `rein/kostenexport.py`, `dienstlogik/kostenrechnung.exportieren` |
| **Stück-Seite** | Abschnitt „Kosten“ (nur `kosten_sehen`): Tagessatz, Kosten bis heute, Reparaturen, Gesamt, Herkunft des Satzes; „Kostensatz überschreiben“ und „Miete eintragen“ (`kosten_pflegen`); Foto (L14a) | `dienstlogik/stueckseite.py`, `vorlagen/inventar_stueck.html` |
| **Zählerstände** | Verlauf mit Quelle (Eingabe, Prüfung, **Werkstatt neu**, Import, Baustelle erst später) und wer; ein zu niedriger Stand in Prüfung und Werkstatt: nur vermerkt, mit Hinweis | `dienstlogik/zaehler.py` (neu), `dienstlogik/pflege.py`, `dienstlogik/pruefung.py`, `dienstlogik/werkstatt.py` |
| **Stichtags-Inventur** (E10) | Verwaltung → Inventur: Stichtag setzen, je Kostenstelle „gesehen / nicht gesehen“, Vermisst **vorschlagen** (Taste je Zeile, Grund Pflicht, nie automatisch), CSV | `dienstlogik/inventur.py`, `web/inventur.py`, `vorlagen/inventar_verwaltung_inventur.html` |
| **Rechte** | alles nur mit `kosten_sehen` (auf den Kostenstellen, für die der Baustein gilt); ändern nur mit `kosten_pflegen`; Poliere sehen keine Preise | `dienstlogik/kostenrechnung.py`, Routen |
| **Nicht in L15** | Einsatzstunden aus der Baustelle, Rechnungen aus den Belegen (nach AP-K2), steuerliche AfA — vorgehalten sind `buchwert_extern`, `afa_hinweis` und der Auszug „Anlagenbuch“ | — |

Prüffälle: `tests/rein/test_kosten_l15.py` (13: Sätze mit Sollwerten je Größe, Mengenartikel × Menge, Kalender- gegen Werktage, Teil-Eingang, Miete, CSV), `tests/integration/test_kosten_db.py` (7: Vorhaltung je
Kostenstelle über Transfer mit Teil-Eingang, Miete gegen eigen, Export liegt und wird nicht überschrieben, Polier sieht keine Preise, Kostensatz je Stück, Inventur setzt nichts von selbst, Zählerstand aus der
Werkstatt), `tests/test_vorlagen.py`.

Vorgesehen, nicht gebaut (Auftrag 05, Abschnitt 7): `etikett_code`. Die Scan-Auflösung steht an **einer** Stelle (`dienstlogik/sicht.aufloesen`).

## Neue und geänderte Dateien

| Pfad | Was |
|---|---|
| `dienstlogik/benachrichtigen.py`, `kostenrechnung.py`, `inventur.py`, `zaehler.py` (neu) | Mailstelle, Kostenrechnung, Inventur, Zählerstände |
| `rein/kostenexport.py` (neu), `rein/kosten.py`, `rein/werkstatt.py` | CSV-Texte · zwei Hilfsfunktionen · Hand bleibt Hand, Pflichtangaben |
| `web/kosten.py`, `web/inventur.py` (neu), `web/__init__.py`, `web/werkstatt.py`, `web/stueck.py`, `web/verwaltung.py`, `web/helfer.py` | Seiten und Routen |
| `vorlagen/inventar_kosten.html`, `inventar_verwaltung_inventur.html` (neu); `inventar_werkstatt.html`, `inventar_stueck.html`, `inventar_verwaltung_kostensaetze.html` | Oberfläche |
| `dienstlogik/werkstatt.py`, `erinnerungen.py`, `stueckseite.py`, `pflege.py`, `pruefung.py`, `sicht.py`, `transfer.py`, `katalogpflege.py` | Anpassungen (`transfer.py`: der Ort einer Inventur-Sichtung steht jetzt in `alt_wert`) |
| `modelle.py`, `migrationen/versions/i0001_grundlinie.py`, `modul.py`, `statisch/inventar.js`, `statisch/stil.css` | Spalten, Menüpunkt, Skript, Stil |
| `texte/de.json` | **alle** Texte |
| `INTEGRATION_VSC.md`, `README.md`, `tests/integration/laufen.md`, `docs/L15/*`, `docs/PROTOKOLL_BOX_09.md` | Anleitung |
| `tests/…` | neu: `test_benachrichtigen.py`, `rein/test_kosten_l15.py`, `integration/test_kosten_db.py`; geändert: `test_vorlagen.py`, `test_modul.py`, `rein/test_werkstatt.py`, `rein/test_texte.py`, `integration/test_werkstatt_db.py`, `integration/test_pruefungen_db.py` |
