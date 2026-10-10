# PROTOKOLL BOX 06 — Auftrag 03, Lieferung L12 (Seiten G2), Stand 10.10.2026

Bezug: `BOX_AUFTRAG_03.md` Abschnitte 5, 8, 9; `KERN_STECKBRIEF_kern-0.15.2.md`.

## Was erledigt ist

| Nr. | Was | Wie geprüft |
|---|---|---|
| 1 | Hier-Seite: Kostenstelle aus `kostenstellen_fuer("inventar","scannen")` (Wahl bei mehreren, Cookie), Block „angekündigt — ist angekommen?“ mit Taste je Zeile und Mengenfeld bei Mengenartikeln, Block „vor Ort“ mit Tasten nach Recht, Taste „Scannen“ | `test_seiten_db`, `test_vorlagen` |
| 2 | Abgang buchen (Von/Nach/Menge/Grund; zweimal absenden bucht einmal), Eingang bestätigen (auch Teilmenge), Scan „ist hier“, Zurückziehen mit Grund (nur von der Herkunft) | `test_seiten_db`: Verwalter bucht, Polier am Ziel bestätigt, Fremder wird abgewiesen |
| 3 | Scan-Seite `/inventar/scannen` mit `BarcodeDetector` und Eingabe-Rückfall; QR-Ziel `/inventar/s/{nr}` (auch Seriennummer), Rückfall `/inventar/s?nummer=`; auf der Stück-Seite mit `?ks=` die großen Tasten | `test_seiten_db`; die Kamera ist **nicht** geprüft |
| 4 | Reiter an der Kostenstelle mit Link zur gefilterten Liste | T-I-5, `test_vorlagen` |
| 5 | `Dienst`-Klasse (lokal), `DIENSTE` | `test_dienstlogik_db` |
| 6 | Suche zeigt auf `/inventar/s/<nr>` | T-I-5 |

## Stand der Läufe

Wie PROTOKOLL 05: **280 passed**, Integration **28 passed**, `skipped = 0`.

## Nicht gebaut

Verbindungs-Taste Baustelle (kein Weg von APP), Fälligkeitsliste und Prüfung eintragen (L13), Meldung/Reparatur-Seiten (G4).

## Offen

Kamera auf Handy und Tablet (Chromium, https), Browserfälle, Fragen in `docs/L12/FRAGEN_L12.md`.
