# Bericht an GER — L16a, Abschnitte 1–4 (Box, 11.10.2026)

Alles ist Entwurf, bis VSC es fährt. Gebaut und geprüft mit **kern-0.15.5** (`kern_mindestens = "0.15.5"`, `pyproject.toml` `>=0.15.5`).

## Abgabe

| Was | Wert |
|---|---|
| Drive-Ordner | `alles_neue_von_box_L16a_komplett` (ID `1Whg1HDHP5TP4fyYSYaC0l6JFcmNfSe4r`) |
| Inhalt | 203 Dateien plus `00_INFO_FUER_GER.md` (Sortiertabelle Dateiname → Zielpfad), komplett flach |
| Zielordner im Repo | `lieferungen/L16a/Inventar/` |
| Git-Stand | Branch `claude/inventar-modul-vorarbeit-oil35n`, letzter Commit `d2e45bd`, kein PR |

Jede Datei lief einzeln durch den Drive-Upload; nach jedem Upload habe ich die Größe gegen die lokale Datei verglichen, alle 203 stimmen. Eine Gegenprobe über den ganzen Ordner war über die Drive-Suche nicht kostengünstig möglich. Empfehlung: GER prüft vor dem Ablegen von `PAKET_inventar_vollstaendig` mit Prüfsummen.

## Teststand

Die drei Läufe sind getrennt; keiner deckt einen anderen ab.

| Lauf | Ergebnis |
|---|---|
| Ohne Datenbank (`python -m pytest -q -W error`) | **418 passed**, skipped = 0 |
| Integration mit Datenbank (PostgreSQL 16, Kern-Wheel 0.15.5, ohne `test_t_i_6.py`) | **70 passed**, skipped = 0 |
| Browser (Chromium 141 headless, Treiber Playwright 1.49.1, frische Prüf-Box) | **31 Fälle**, skipped = 0 (30 in der Gesamtfahrt) |

Der Zeitfall `test_zz_import_gross` (Liste mit 2.500 Stücken unter 1 s) riss in der Gesamtfahrt einmal die Grenze mit 1,18 s. Einzeln auf frischer Box bestand er in 38 s. Das werte ich als Zeitgrenze auf geteilter Hardware, nicht als Logikfehler.

Die Zahlen weichen von GERs Lauf (412/66/29) ab, weil L16a dazugekommen ist (Feiertage, Ablesedatum, Inventur abschließen, Browserfall für den 409).

**Nicht gefahren:** T-I-6 (Belegerfassung fehlt Box), Firefox, WebKit, Docker-Bild, Prozess `erinnern` im Container, QR-Etikett mit Handykamera, Probedruck.

Chromium 131 lässt sich in der Box nicht laden. Es lief der 1.49.1-Treiber gegen das vorhandene Chromium 141 (Verweise `chromium-1148`). Das ist nicht das Paar, das 1.49.1 mitbringt.

## Umgesetzt

| Nr. | Was |
|---|---|
| 4 | `kern_mindestens` und `pyproject` auf 0.15.5; `Modulbeschreibung.reihenfolge = 30`; `personen_auswahl` über `rechte.wer_darf` (eigene Rechte-Auswertung raus); alle `hx-target` der Formulare sind kleine Meldezeilen, kein `HX-Retarget` nötig; Umgehung des 409 in `statisch/inventar.js` entfernt (hätte doppelt getauscht); Browserfall prüft, dass der rote Satz erscheint und die Seite bleibt |
| 1 | Feiertagsregion aus `mandant.feiertagsregion`; Einstellung `bundesland` entfernt; Hinweise bei leerer oder unbekannter Region |
| 2 | Rechner `rein/feiertage.py` als Umschlag um `holidays==0.60`; 32 Sollwerte laufen gegen das Paket |
| 3 | Eigene Tage mit Haken "jährlich" (Spalte `inventar.feiertag.jaehrlich` in `i0001`) |
| 12 / 13 | Mehrmenge-Hinweis ohne Buchung; zweiter Scan mit Zahl überschreibt die letzte Sichtung |
| 14 | "Inventur abschließen": CSV, Einstellung `inventur_letzte`, Stichtag geleert, Protokoll, Download |
| 17 | Optionale 16. Importspalte "Ablesedatum" |
| H1 | `pip install -e <Inventar>[pruefung]`, Playwright 1.49.1 |

## Funde

1. Brandenburg: `holidays==0.60` führt Ostersonntag und Pfingstsonntag; meine Handwerte hatten sie nicht. Keine Wirkung auf Werktage.
2. Die Auszugsliste der Kosten-Seite führt auch die Inventur-CSVs.
3. Zeitfall im Browser auf geteilter Hardware unsicher.
4. Playwright: Treiber 1.49.1 gegen Chromium 141 statt 131.
5. Eine alte `bundesland`-Zeile in `inventar.einstellung` bleibt ungenutzt liegen (nichts wird gelöscht); Region dort im Kern setzen.

## Offene Fragen (`FRAGEN_L16a.md`, 10 Punkte)

Am dringendsten:

- **Nr. 1:** Sollen künftige Routen immer auf eine Meldezeile zielen (Regel), oder plant der Kern ein Hilfsmittel?
- **Nr. 2:** Stimmen die übrigen 15 Länder mit der Erwartung der Verwaltung überein?
- **Nr. 9:** Zeitgrenze für den 2.500-Stücke-Fall lassen oder auf 2 s heben?

## Guthaben

Zu Beginn von L16a rund 14,9 Mio. Tokens, am Ende rund 13,8 Mio.
