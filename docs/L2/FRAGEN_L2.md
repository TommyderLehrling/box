# FRAGEN_L2 — Box an GER/Thomas

Stand 08.10.2026. Nichts blockiert; jede Annahme ist eingebaut und getestet.

| Nr. | Frage | Vorschlag / vorläufig angenommen |
|---|---|---|
| 1 | Teilmenge (B8): Beim Abgang von 10 aus 40 wird A(40) geschlossen und A(30) geöffnet. Damit zählt die abgehende Teilmenge in `status_auf(A)` nicht mehr als „vor Ort", sondern nur auf B als „angekündigt". Bei Einzelstücken (B2) zählt A dagegen weiter „vor Ort". Gewollt? | **Vorläufig: so wie B8 es beschreibt.** Alternative: Teilmenge bis zum Eingang auf A als „vor Ort" weiterzählen. |
| 2 | Zusatzfeld `Transfer.abgespalten` (Vorgabewert `False`) — in Ordnung? | **Vorläufig: ja** (Begründung in der README). |
| 3 | Transfer-Id = `"t:" + eintrag_schluessel` (damit das Modul ohne Zufall und Datenbank auskommt). Vergibt VSC lieber eigene Ids? | **Vorläufig: so.** VSC darf die Id beim Speichern ersetzen, solange `transfer_id` in Standort und Aenderung mitgeführt wird. |
| 4 | B13 erster Abgang: Der Auftrag sagt „Transfer mit `von_kostenstelle = None`". Beim Abgang kennt der Aufrufer aber `von_ks`. | **Vorläufig:** erster **Scan** → `von_kostenstelle = None` (wie B13). Erster **Abgang** → Standort wird auf `von_ks` angelegt (Menge = Abgangsmenge), der Transfer trägt `von_kostenstelle = von_ks`. |
| 5 | `eingang_bestaetigen` auf einen schon bestätigten Transfer: Fehler oder still ohne Wirkung? Überholt/zurückgezogen? | **Vorläufig:** bestätigt → keine Änderung, Protokoll `transfer.schon_bestaetigt`; überholt/zurückgezogen → `ValueError(transfer.nicht_offen)`. (Doppelter Handy-Scan bleibt so harmlos.) |
| 6 | `zurueckziehen` hat keinen Parameter `quelle`. | **Vorläufig:** `quelle = "web"`. Vorschlag: Parameter `quelle` ergänzen. |
| 7 | Für überholte und zurückgezogene Transfers gibt es keinen Zeitstempel. `status_auf` kann deshalb für Tage in der Vergangenheit nur bestätigte und noch offene Transfers als „angekündigt" zeigen. | **Vorläufig: überholte/zurückgezogene zählen nie als angekündigt.** Vorschlag: Feld `beendet_am` ergänzen. |
| 8 | Mehrere gleichzeitig offene Teilmengen-Transfers oder ein Mengenartikel auf mehreren Kostenstellen: Ein Scan ohne eindeutigen Bezug kann nicht entscheiden. | **Vorläufig: `ValueError(transfer.mehrdeutig)`**; VSC lässt dann auswählen (Taste „Ist angekommen" am konkreten Transfer). |
| 9 | Zeitzone: `ueberfaellige` zählt ab `abgang_am.date()` in der Zeitzone der übergebenen `datetime`. | Vorschlag: VSC liefert durchgehend Betriebszeit (Europe/Berlin). |
| 10 | `zubehoer_folgt`: Zubehör wird mit seiner **ganzen** Menge gebucht und übersprungen (`zubehoer.nicht_am_ort`), wenn es nicht auf der Quell-Kostenstelle steht. | **Vorläufig: so.** |
