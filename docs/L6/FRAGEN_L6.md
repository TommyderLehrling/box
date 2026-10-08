# FRAGEN_L6 — Box an GER/Thomas

Stand 08.10.2026. Nichts blockiert; jede Annahme ist eingebaut und getestet. **Korrigiert:** Frage 1 aus `FRAGEN_L5` (Seite `bauteile` = Zubehör) war falsch — `bauteile` ist der Bauteilkatalog (Spec Abschnitt 2). Die Texte sind angepasst.

| Nr. | Frage | Vorschlag / vorläufig angenommen |
|---|---|---|
| 1 | Bauteilkatalog: Soll der Startkatalog leer sein (nur die Form), wie Spec Abschnitt 14 es verlangt („Bauteile-Form")? | **Vorläufig: leer.** Bauteilnummern sind Lieferantennummern; erfinden würde falsche Daten liefern. |
| 2 | Prüfung: Wie zählt das Ergebnis „bestanden mit Mängeln" (`maengel`) für die nächste Frist? | **Vorläufig: wie bestanden** (normales Intervall). „Nicht bestanden" ist sofort wieder fällig (rot) bis zur nächsten bestandenen Prüfung. |
| 3 | Prüfung: Ein Stück, das noch nie geprüft wurde — ab wann fällig? | **Vorläufig: Startdatum + Intervall** (`erstfaellig="intervall"`). Alternative `"sofort"`: dann wären nach dem Import von 2.000 Stücken alle rot. Welches Startdatum nimmt VSC (Anlage- oder Kaufdatum)? |
| 4 | Zähler-Fälligkeit (z. B. Wartung alle 500 h): Ab wann „gelb"? | **Vorläufig: 10 % des Zählerintervalls vor Erreichen.** Der Zählerstand der letzten Prüfung muss bekannt sein, sonst gilt nur die Datumsfrist. Wer zuerst eintritt, bestimmt die Ampel. |
| 5 | Vorhaltung in Werktagen: Gilt dieselbe Regel (Eingangstag zählt zum Ziel, Abgangstag nicht zur Quelle)? Wer liefert die Feiertage? | **Vorläufig: ja, gleiche Regel**; VSC übergibt die Feiertage (Bundesland ist Einstellung des Betriebs). |
| 6 | Stückstatus: Rückkehr aus „vermisst" ohne Grund erlaubt (Stück ist wieder aufgetaucht)? Wechsel zwischen zwei Endzuständen? | **Vorläufig:** aus „vermisst" zurück ohne Grund; stillgelegt → verkauft/verschrottet mit Grund erlaubt; verkauft/verschrottet → anderer Endzustand **nicht**. Nur wer Rechte hat (`inventar.stilllegen`) darf das — das prüft VSC. |
| 7 | Meldung: Darf „angenommen" direkt auf „erledigt" (Sofortreparatur)? Pflichtfelder? | **Vorläufig: ja; „erledigt" braucht eine Rückmeldung (Spec: Rückmeldung an den Melder), „zurückgezogen" einen Grund.** |
| 8 | Reparatur: Zählen nur **erledigte** Reparaturen in die Gesamtkosten? Beleg ersetzt Schätzung? | **Vorläufig: ja; `reparaturkosten` liefert getrennt (Summe aus Belegen, Summe aus Schätzungen).** |
| 9 | Import: Eine Zeile, deren Inventarnummer es schon gibt, aber mit anderen Werten — überschreiben? | **Vorläufig: nein, nur melden** („zweiter Lauf ändert nichts", Spec Abschnitt 12). Kostenstelle und Menge werden nicht verglichen, weil Transfers sie ändern. |
| 10 | Inventur: Eine Fehlmenge bei Mengenartikeln ist **nicht** „vermisst"; Mehrmenge zählt als gefunden. Was soll bei Mehrmenge geschehen? | **Vorläufig: nichts** (nur „gefunden"). Vorschlag: Hinweis „mehr gesehen als erwartet". |
| 11 | `bestand` (Dienst): Hinweise sind Schlüssel (`stueck_status.hinweis_in_reparatur` …), nicht Text; je Stück und Status eine Zeile; angekündigt nur für heute. Darf VSC `transfer.status_auf` weiter nutzen? | **Vorläufig:** für den Dienst `bestand` die Funktion `bestand.bestand` nutzen. `status_auf` (L2) zeigt auch vergangene Tage mit angekündigtem Eingang und passt zu B2, nicht zur Dienst-Regel. |
| 12 | `Quelle`: Die Spec Abschnitt 4 nennt für das Protokoll `baustelle`, `pruefung`, `werkstatt`; der Auftrag nur vier Werte. | **Vorläufig: vier Werte in `transfer`.** Vorschlag: Literal um die drei erweitern (reine Ergänzung). |
| 13 | Prüffall-Kennung `T-R-…` (Spec Abschnitt 18) statt meiner Kürzel? | **Vorläufig: Kürzel + mechanische Zuordnung in der README.** Ich benenne um, falls gewünscht. |
| 14 | Paketname: `inventar_rein` (Auftrag) oder `digiassistenz_inventar.rein` (Spec Abschnitt 14)? | **Vorläufig: `inventar_rein`.** |
