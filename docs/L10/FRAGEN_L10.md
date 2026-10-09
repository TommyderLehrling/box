# FRAGEN_L10 — Fragen und Erkenntnisse (Box, Stand 09.10.2026)

**Zum Antworten:** Abschnitt G ist die gemeinsame Antwortliste für Thomas, GER und CC/VSC. Bitte die Spalte „Antwort“ ausfüllen (Name, Datum, ja/nein/anderer Weg) und die Datei unter demselben Namen in `lieferungen/L10/` ablegen; Box liest sie beim nächsten Lauf. Fragen an den Kern gehen über GER an die Brücke (Regel 2).

Gebaut wird gegen **KERN_STECKBRIEF_kern-0.15.2** (ersetzt die Fassung 0.13.2 vollständig). Alles hier ist Entwurf, bis VSC es auf dem echten Kern laufen lässt.

## A. Entscheidung nötig (Vorschlag steht dabei)

| Nr. | Frage | Vorschlag Box | Folge, wenn nichts gesagt wird |
|---|---|---|---|
| 1 | **`app.modul`**: Auftrag 03 sagt „liefern wir", Steckbrief Abschnitt 11 sagt „ein zweites Modul setzt es nicht" (bis zu den Modulreitern). | Nicht setzen. `bezeichnung="inventar.modul"` mit Text „Inventar" (auch Überschrift der Suchgruppe). | Wie Vorschlag. Der Titel heißt mit Inventar allein „DOKON" statt „DOKON Inventar". |
| 2 | **Nachzug**: Bausteine werden Konten beim Anlegen kopiert. Auf einer Box mit bestehenden Konten erreicht das neue Modul den Verwalter nicht von selbst. Auftrag 03 sagt „nachzug leer". | Nachzug mit Paaren für alle 11 Bausteine, Grund `nachzug:inventar_einbau`. Wirkt nur bei Konten, deren Vorlage den Baustein trägt, einmal je Konto, wiederholbar. | Nachzug bleibt leer wie im Auftrag; der Verwalter bekommt die Rechte von Hand. |

## B. Kleinere Punkte (Standard, wenn niemand widerspricht)

| Nr. | Punkt | Standard |
|---|---|---|
| 3 | Steckbrief widerspricht sich bei der Anmelde-Richtung: Abschnitt 1.4 sagt `modul.anmelden` ruft `rechte.anmelden`, Abschnitt 3.1 sagt `rechte.anmelden` ruft `modul.anmelden`. Vermutlich ein Kern-Fehler. | Bitte über GER an die Brücke. Mein Modul ruft keins von beiden auf, ohne Folge. |
| 4 | Die Modulbeschreibung hat kein Feld für die Kern-Mindestfassung. | `digiassistenz-kern>=0.15.2` in `pyproject.toml` und Konstante `KERN_MINDESTFASSUNG`; keine Laufzeitprüfung. |
| 5 | `aehnlichkeit.rang` steht im Steckbrief (2.7), aber ohne Importpfad, nicht in Anhang A und nicht in der Liste der öffentlichen Namen aus Auftrag 03. | `from digiassistenz_kern import aehnlichkeit`. Ist das nicht öffentlich, baue ich eine einfache eigene Suche mit `ilike`. |
| 6 | Die Suche ist neu im Kern (0.15.0) und stand nicht in Auftrag 03. | Ich baue `suche=_suche` (Rahmen-Baustein `inventar.sehen`) und in T-I-5 einen Fall für Suchfeld und `/suche`. Ohne suchendes Modul ist `/suche` 404. |
| 7 | `sitzung.db.begin_nested()` je Modulsuche macht der Kern. | Ich rufe es nicht selbst auf. |

## C. Erkenntnisse aus dem Steckbrief 0.15.2

- **Verlauf**: `protokoll.verlauf(db, mandant_id, objekt_typ, objekt_id)` ersetzt für die Stück-Seite `zu_objekten`. Ob jemand den Verlauf sehen darf, prüft der Aufrufer. Meine Objekttypen: `inventar.stueck`.
- **Nachzug** darf Paare `(baustein, grund)` tragen (0.14.0); `rechte.nachzug_paare()` normalisiert.
- **Vertretungen** gehören nicht zur Zuordnung. Ich nehme für Kostenstellen nur `sitzung.kostenstellen_fuer(...)`, nie eigene Zuordnungslogik.
- **Noch nicht im Kern** (Abschnitt 11): `Dienst`/`dienste`, Kacheln-Vertrag, Modulreiter, Posteingang als Kern-Seite, Verteil-Dialog, Callable-Weg bei der Startseite, Erweiterungsstelle `akte.teil`. Ich erfinde nichts davon: `DIENSTE` und die Kacheln bleiben Modulkonstanten mit Kommentar, die Startseite ist ein fester Weg.
- **T-HI-1** prüft nur Kern-Vorlagen; die Hilfe-Prüfung für meine Vorlagen (vier Schlüssel je Seite) baue ich selbst nach.
- Der Kern-Prüffall T-K-STECK betrifft nur den Kern.

## D. Entscheidungen im Datenmodell (zum Prüfen)

1. **Nummernzähler**: eigene Tabelle `zaehler` (Auftrag 03, Abschnitt 6) mit `SELECT … FOR UPDATE`; die Variante „`nummer_zaehler:` in `einstellung`" entfällt.
2. **`transfer.eintrag_schluessel`** ist Text, nicht UUID: der Zustandsautomat bildet abgeleitete Schlüssel wie `<uuid>|fehlmenge`. Eindeutig je Mandant (nicht global).
3. **`kostensatz`** trägt für Startwerte je Gruppe die Parameter (Nutzungsdauer, Restwert in Prozent, Zins, Reparaturanteil); die gerechneten Sätze (`satz_monat/tag/woche`) sind nullbar und kommen mit G5 je Stück. Quelle der Startwerte: `vorschlag_box`.
4. **Mengenartikel**: die Menge steht je Kostenstelle in `standort`, nicht am Stück.
5. **`transfer`-Id im Zustandsautomaten** ist `t:<eintrag_schluessel>`; sie braucht keine eigene Spalte.
6. **`standort.von_person`** ist die Benutzer-ID (null = System), nicht `angelegt_von`.

## E. Umgesetzt aus Auftrag 03, Abschnitt 0 (Commit `fdb23c6`, 220 Prüffälle grün)

- `Pruefart.intervall_je_merkmal` (HU nach Fahrzeugklasse); kürzestes passendes Intervall gilt, die Überschreibung am Stück geht vor; der Katalog prüft Merkmal, Werte und Monate.
- `gruppe_pruefart` als Startwert aus dem Katalog.
- Kachel „in Arbeit" zählt Stücke mit angenommener oder in Arbeit befindlicher Meldung oder Reparatur in Arbeit, jedes Stück einmal. „Meldungen offen" zählt nur `offen`.
- Echte Wege in den Kacheln: `/inventar`, `/inventar/hier`, `/inventar/faellig`, `/inventar/verwaltung`.
- `miete_gegen_eigen(…, vergleichsstueck=…)`: eine Nummer für alle oder eine Zuordnung je Mietstück; unbekannt oder Mietstück als Vergleich gibt `verrechnung.vergleichsstueck_unbekannt`.
- Beispielbetrieb: Mietkosten 4.200,00 € am Teleskoplader BM-00005; `miete_gegen_eigen` zeigt dort einen Wert.
- Die Hilfe hat jetzt vier Schlüssel je Seite (`hilfe.inventar_<seite>` plus `.liegt/.tasten/.danach`), dazu die Seite `scannen`.

## F. Grenzen

- Ich kann nichts gegen den echten Kern ausführen. Der Kern in `kern_fuer_box` ist ohne `modelle.py` nicht importierbar. Ich teste gegen einen eigenen, kleinen Ersatz des Kerns (nur in `tests/`) und gegen eine lokale PostgreSQL ohne Kern.
- Der Stand ist **Entwurf**, bis VSC T-I-5 und T-I-6 auf dem echten Kern fährt.

## G. Antwortliste (Adressat, Frage, Antwort)

Adressaten: **Thomas** (Fachentscheidung) · **GER** (Auftrag, Spec, Brücke) · **CC/VSC** (Kern, baut das Modul in den Kern ein) · **Belegerfassung** (nur Info).

| Nr. | Adressat | Frage | Vorschlag Box | Antwort (bitte eintragen) |
|---|---|---|---|---|
| A1 | GER, dann Thomas | `app.modul` setzen (Auftrag 03) oder nicht (Steckbrief 11)? | Nicht setzen; `bezeichnung="inventar.modul"` | **Nicht setzen** (GER, laut CC-Meldung 09.10.) — umgesetzt |
| A2 | GER, dann Thomas | Nachzug der 11 Bausteine an bestehende Konten (Auftrag 03: „leer“)? | Ja, Grund `nachzug:inventar_einbau` | **Ja, Paare für alle Bausteine** (GER: „du hattest recht“) — umgesetzt |
| 6 | GER | Suche (`suche=_suche`, Seite `/suche`) in L10 aufnehmen? Sie stand nicht in Auftrag 03. | Ja, sonst wird ein Prüffall „jeder GET-Weg 200“ für `/suche` rot | |
| D1–D6 | GER | Datenmodell wie in Abschnitt D (Tabelle `zaehler`, Text-Schlüssel, Kostensatz-Startwerte, Menge in `standort`)? | Ja | |
| 3 | CC/VSC (über GER) | Steckbrief 1.4 und 3.1 nennen die Richtung `modul.anmelden` ↔ `rechte.anmelden` gegensätzlich. Welche gilt im Quelltext? | Keine Folge für `inventar`; Kern oder Steckbrief korrigieren | **Erratum VSC:** `modul.anmelden` ruft `rechte.anmelden`; 3.1 war falsch, Korrektur mit dem nächsten Kern-Tag |
| 4 | CC/VSC (über GER) | Gibt es einen Weg, die Kern-Mindestfassung in der Modulbeschreibung zu nennen? Ein Feld fehlt. | Nur `pyproject.toml` und Konstante `KERN_MINDESTFASSUNG`; Kern-Wunsch: Feld | |
| 5 | CC/VSC (über GER) | Ist `from digiassistenz_kern import aehnlichkeit` (`rang`, `HOECHSTENS`) für Module erlaubt? Importpfad nicht im Steckbrief. | Ja; sonst eigene Suche mit `ilike` | **Ja, erlaubt** (VSC) — genutzt in `dienstlogik/sicht.py` |
| 7 | CC/VSC | Nur Info: Ich rufe `sitzung.db.begin_nested()` nicht selbst auf, die Suche läuft im Sicherungspunkt des Kerns. | Bitte bestätigen | |
| I1 | Belegerfassung | Nur Info: Die Belegerfassung kennt `inventar` nur als Modul mit eigenem Schema und Konto; kein Fremdschlüssel in ihr Schema (T-K-14), keine Wege oder Bausteine von ihr im Code. | — | |
| I2 | CC/VSC, Belegerfassung | Nur Info: Mit Kern 0.15 und einem Modul mit `suche` ist `/suche` für `inventar` 200. Prüffälle, die jeden GET-Weg erwarten, sehen dann `/suche`. | — | |

## H. Stand nach dem Bau (L10, Box, 09.10.2026) — neue Fragen und Abweichungen

Die Antworten von VSC (`VON_VSC_01_antwort.md`) habe ich gelesen und umgesetzt. GERs Datei mit der Antwort auf diese Liste habe ich nicht gesehen; A1 und A2 kenne ich aus der Meldung von CC. Alle übrigen Vorschläge (Nr. 4, 6, 7, D1–D6) habe ich wie vorgeschlagen gebaut — **bitte bestätigen oder korrigieren.**

| Nr. | Adressat | Frage / Abweichung | Was Box getan hat | Antwort (bitte eintragen) |
|---|---|---|---|---|
| D7 | GER | **Zubehör und Passung (`beziehung`)**: Auftrag 03 verlangt „genau eines von `zu_stueck_id`, `bauteil_id`, `gruppe_id`“. Eine Passung „Bauteil passt zu Gruppe“ braucht aber das Bauteil **und** die Gruppe. | `gehoert_zu`: `von_stueck_id` und `zu_stueck_id`, sonst nichts. `passt_zu`: `bauteil_id` plus genau eines von `zu_stueck_id` und `gruppe_id`, `von_stueck_id` leer. Zwei Prüfungen in der Datenbank. | |
| D8 | GER | **Wörter `beleg…` (T-K-12d)**: Spec v0.2 nennt `reparatur.kosten_quelle ∈ geschaetzt\|beleg` und `beleg_verweis`. Beides verletzt die Regel. | `kosten_quelle ∈ geschaetzt\|rechnung`, Spalte `rechnung_verweis`, Funktion `kosten_aus_rechnung`. Bei `dienste`/G5 gilt später derselbe Name. | |
| D9 | GER | **`test_dienstlogik.py` ohne Datenbank (Auftrag 03, Abschnitt 9)**: mit dem echten Kern und einer PostgreSQL geht ein stärkerer Nachweis. | Die Anwendungsfälle laufen gegen die echte Datenbank in `tests/integration/test_dienstlogik_db.py` (13 Fälle, echte Sitzung, echte Rechte). Eine Fake-Sitzung gibt es nicht. `pytest -q` ohne Datenbank braucht den **installierten Kern**, aber keine Datenbank. | |
| D10 | GER | **Import mit unbekanntem Lieferanten**: der Kern gehört die Lieferanten, das Inventar legt keine an. | Das Stück bekommt keinen Lieferanten; der Bericht nennt die Namen (`lieferanten_unbekannt`); die Abweichungsprüfung ignoriert den Namen, damit ein zweiter Lauf nichts ändert. | |
| D11 | GER | **Ohne Stichtag keine Baujahr-Obergrenze** im Excel-Import (`rein.import_vorlage.lies(heute=None)`); vorher `date.today()` (Wanduhr, T-K-Regel). | Aufrufer im Modul übergeben immer `zeit.heute()`. | |
| D12 | CC/VSC | **Seiten unter „Verwaltung“**: `aktiv="verwaltung"` rendert die zweite Kopfzeile, die Seite `/inventar/verwaltung` nutzt es. Stimmt das als Muster für Modul-Verwaltungsseiten? | T-I-5 prüft: `/verwaltung` zeigt `/inventar/verwaltung` in der zweiten Zeile, kein toter Link. | |
| D13 | CC/VSC | **Zustand des Kern-Bilds** (`digi-assistenz-kern:0.2.0`), das `docker/Dockerfile` als Basis nimmt, und die Pfade `KERN_DOCKER`/`docker/wheels` in `compose.yml`. | Entwurf, nicht gebaut. | |
| D14 | CC/VSC | **Rückmeldung zu `LAUFEN_OHNE_DOCKER.md`**: der Weg als Superuser stimmt wie beschrieben (Wheel 0.15.2 nicht editierbar, Python 3.12.3, PostgreSQL 16.15, `pg_dump` 16, `pg_trgm`). Der Weg **ohne** Superuser ist von Box **nicht** gefahren. | Nur der Superuser-Weg ist geprüft. Der Aufruf der Läufe braucht `--rootdir=<Ordner des Inventars>`, wenn man aus der Wurzel mit `konfig.env` startet. | |
| D15 | CC/VSC | **T-I-6** (Kern + Belegerfassung + Inventar) ist geschrieben nach dem Muster T-I-4, aber **nicht gefahren**. | Bitte fahren und Befund melden. | |
| D16 | Thomas | **L11/L12**: siehe Abschätzung im Bericht. | — | |
