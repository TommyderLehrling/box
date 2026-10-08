# FRAGEN_L4 — Box an GER/Thomas

Stand 08.10.2026.

| Nr. | Frage | Vorschlag / vorläufig angenommen |
|---|---|---|
| 1 | Die zwei Beispielzeilen der Vorlage sind gültige Daten (Kostenstelle 1000, Nummern `<Kürzel>-00001`). Hat der Betrieb Kostenstelle 1000, würden sie beim Import mitkommen. | **Vorläufig: so.** Vorschlag: Beispielzeilen nach dem Muster `BEISPIEL` in „Besonderheiten" markieren und von `lies` ignorieren — oder VSC weist beim Hochladen darauf hin. |
| 2 | Spalte „Gruppe": Schlüssel (`baumaschine`) oder Bezeichnung („Baumaschinen")? | **Vorläufig: Schlüssel** (das liefert das Dropdown). |
| 3 | Merkmalswerte kommen als Text zurück: Zahl mit Punkt (`21.5`), Datum als ISO, `ja`/`nein`. Inventarnummern werden beim Lesen normalisiert (Großbuchstaben). | **Vorläufig: so.** |
| 4 | Testdaten: `{jahr}` in der Nummer ist das Kaufjahr; Nummern steigen mit dem Kaufdatum. Prüfungen gibt es für **jedes** Stück je zugeordneter Prüfart (auch Mengenartikel); die Wartung nach Betriebsstunden hat zusätzlich eine Datumsfrist. | **Vorläufig: so.** |
| 5 | Mengenartikel in den Testdaten: Kaufpreis gilt je Stück (nicht für die ganze Zeile) — passend zu Frage 1 aus L3. | **Vorläufig: je Stück.** |
| 6 | Die DGUV-V3-Frist (Frage 5 aus L1) bestimmt die Fälligkeiten in den Testdaten. | Bei Änderung des Katalogs ändern sich die Testdaten automatisch. |
| 7 | Transfers der Testdaten tragen Zeitstempel in UTC (08:00), Quelle `import`, Person `testdaten`. | **Vorläufig: so.** |
