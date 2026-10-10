# PROTOKOLL BOX 05 — Auftrag 03, Lieferung L11 (Seiten G1), Stand 10.10.2026

Bezug: `BOX_AUFTRAG_03.md` Abschnitte 5, 6, 9, 10; `KERN_STECKBRIEF_kern-0.15.2.md`. L11 und L12 wurden in einem Zug gebaut und geprüft.

## Was erledigt ist

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | Inventarliste: Umschalter Ordner/Liste, Filter (Status, Gruppe, Kostenstelle über die Kern-Wahl, nur angekündigt, nur fällig), Suche mit `hx-get` nach 250 ms (Nummer, Name, Seriennummer, Kennzeichen-Merkmal, Ort), Sortierpfeile, Seiten ab 200 Treffern | `test_seiten_db` (Suche, Filter, Sortierung, Ordner), `test_vorlagen` |
| 2 | Stück-Seite: Statuszeile (Lage, Prüfstand-Ampel, Haupttasten je Lage), darunter Stamm, Merkmale, Zubehör/Bauteile, Standort-Verlauf, Transfers, Prüfungen, Meldungen/Reparaturen, Zählerstände, Kosten (nur `kosten_sehen`), Verlauf über `protokoll.verlauf` | `test_seiten_db`, `test_vorlagen` (ohne Rechte: keine Tasten, keine Preise) |
| 3 | Stück anlegen/ändern mit Merkmalsfeldern je Gruppe, Nummernvorschlag (ohne den Zähler zu verbrauchen), Lieferant und Startstandort über die Kern-Wahl, Foto (jpg/png ≤ 8 MB, Anfang der Datei geprüft) | `test_seiten_db` |
| 4 | Status ändern mit Grund; Zubehör und Bauteile anlegen/lösen (nie löschen); Zählerstand (nie zurück); „Schaden melden“ (idempotent über die Buchung) | `test_seiten_db` |
| 5 | Verwaltung → Inventar: Kacheln nach Rechten; Gruppen, Merkmale, Prüfarten (mit Tabelle Intervall je Merkmal), Bauteile, Kostensätze (neuer Satz, alter bleibt), Einstellungen, Import (Vorlage, Prüfbericht, Einspielen nur ohne Fehler, idempotent), Etiketten-PDF, Testdaten (nur bis `auslieferung_am`) | `test_seiten_db` |
| 6 | 165 neue Texte; 10 Vorlagen mit vier Hilfeschlüsseln | `test_texte`, T-HI-Nachbau |

## Stand der Läufe

`python -m pytest -q -W error`: **280 passed, 0 skipped**. `tests/integration` mit Kern 0.15.2 und PostgreSQL 16: **28 passed, 0 skipped** (T-I-6 braucht die Belegerfassung, hier nicht installiert: Fehler „falscher Aufbau“, wie vorgesehen).

## Fehler gefunden und behoben

* `gemeinsam.seite` bekam `darf_pflegen` doppelt (Route und `darf_alle`): nur noch aus `darf_alle`.
* Foto-Prüfung glaubte der Angabe des Browsers: jetzt zählt auch der Dateianfang.
* Import: eine Nicht-Excel-Datei ergab 500; jetzt ein Satz (409). Größe höchstens 10 MB.
* Kern-Befund `teil_wahl.html` (`requiredaria-label`) umgangen und in `FRAGEN_L11.md` Nr. 3 gemeldet.

## Offen

Browserfälle (Liste in `INTEGRATION_VSC.md`), Kamera-Scan, T-I-6, Docker; Fragen in `docs/L11/FRAGEN_L11.md`. L13 (Fälligkeit, Prüfung eintragen) nur auf Zuruf.
