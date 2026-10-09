# FRAGEN_L10 — Fragen und Erkenntnisse (Box, Stand 09.10.2026)

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
