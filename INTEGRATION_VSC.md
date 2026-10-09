# INTEGRATION_VSC — was VSC mit `digiassistenz_inventar` tut (L10, Box, 09.10.2026)

Gebaut gegen **KERN_STECKBRIEF_kern-0.15.2**. Alles hier gilt als Entwurf, bis es auf dem echten Kern läuft.

## 1. Was Box schon gefahren hat (Python 3.12.3, Wheel 0.15.2 nicht editierbar, PostgreSQL 16.15, Superuser)

* `python -m pytest -q`: 257 passed, 0 skipped (auch mit `-W error`).
* Kette `k0001…k0004` → `i0001`, Startdaten, zweiter Start ändert nichts.
* `tests/integration`: T-I-5 (8), Anwendungsfälle gegen die echte Datenbank (13), Modelle gegen Kette (2) — 23 passed.
* Nicht gefahren: **T-I-6** (keine Belegerfassung), Docker (`compose.yml`, `docker/Dockerfile`), Konto ohne Superuser, Browser.

## 2. Einbauen

```
pip install --no-deps digiassistenz_kern-0.15.2-py3-none-any.whl
pip install -r requirements.txt && pip install -r requirements-modul.txt      # Kern-Pakete + openpyxl, weasyprint
pip install --no-deps -e <pfad>/Inventar                                       # Einstiegspunkt digiassistenz.module → inventar
python -m digiassistenz_kern.start                                             # Ketten (Kern, dann i0001), Startdaten, Web
```

* Nachzug: beim Start bekommen Konten, deren Vorlage einen Baustein trägt, die elf `inventar.*`-Rechte (Grund `nachzug:inventar_einbau`, einmal je Konto).
* `konfig.env`: `INVENTAR_ETIKETT_URL` (leer = aus der Anfrage). Die Kern-Schlüssel stehen in derselben Datei.
* Cron einmal täglich: `python -m digiassistenz_inventar.erinnern` (Transfer-Erinnerung an `disposition` und den Melder).
* WeasyPrint braucht Pango/Cairo und eine Schrift im Bild (siehe `docker/Dockerfile`).

## 3. Läufe

| Lauf | Aufbau | Datei |
|---|---|---|
| T-I-5 | Kern + Inventar | `tests/integration/test_t_i_5.py` |
| Anwendungsfälle, Modelle gegen Kette | Kern + Inventar | `tests/integration/test_dienstlogik_db.py`, `test_migration_gegen_modelle.py` |
| **T-I-6**, T-K-14 | Kern + Belegerfassung + Inventar | `tests/integration/test_t_i_6.py` (Muster T-I-4; **ungefahren**) |

Aufruf und Stolpersteine: `tests/integration/laufen.md`.

## 4. Browserfälle (Playwright, Chromium + Firefox, Zoom in WebKit) — erst mit L11/L12

1. Die Statuszeile ist das erste Element unter dem Kopf der Stück-Seite.
2. Die Tasten einer Reihe sind gleich hoch.
3. Kein Link ohne Recht: `Polier.Eins` sieht weder Preise noch „Pflegen“.
4. Import mit 2.500 Stücken → die Liste öffnet in < 1 s.
5. Etiketten-PDF für 20 Stücke: 1 Bogen, 2 Seiten bei 25–48 Stücken; jeder QR führt auf `/inventar/s/<nummer>`.
6. Scan-Weg: `/inventar/scannen` mit Kamera-Attrappe und mit Eingabe von Hand; „Ist hier“ bestätigt den angekündigten Transfer.
7. Probedruck eines Bogens auf Etikettenpapier 70 × 36 mm (24 je A4).

## 5. Offen / bewusst nicht eingehängt (Steckbrief 11)

* `DIENSTE` (`bestand`, `stueck`) stehen in `dienste.py`; sie gehen in die Modulbeschreibung, sobald der Kern `dienste` hat (AP-K2).
* Kacheln stehen oben auf `/inventar` (`kacheln.py`); Posteingang-Kachel erst mit Vertrag (Brücke 025).
* Startseite ist ein fester Weg (`/inventar`), weil der Callable-Weg die Beschriftung nicht findet.
* `Verbindung(braucht="baustelle", menuepunkte=())`: leer, bis APP den Weg nennt; der Schlüssel (`app` oder `baustelle`) steht nur als `MODUL_BAUSTELLE`.
* `app.modul` setzt das Inventar nicht; der Titel ist mit dem Inventar allein „DOKON“.
* Seiten: L10 hat Übersicht, Hier, Fällig (Hinweis), Verwaltung (Zahlen), Reiter an der Kostenstelle, Zeile in der Verwaltungsübersicht, Suche. Der Rest (Stück-Seite, Pflege, Import/Etiketten-Seiten, Hier-Buchungen, Scan) kommt mit L11/L12, die Anwendungsfälle dahinter stehen und sind geprüft.
