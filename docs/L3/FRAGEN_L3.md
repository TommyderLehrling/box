# FRAGEN_L3 — Box an GER/Thomas

Stand 08.10.2026.

| Nr. | Frage | Vorschlag / vorläufig angenommen |
|---|---|---|
| 1 | Mengenartikel: Gilt der Tagessatz je Stück (dann Betrag × Menge) oder für die ganze Zeile? | **Vorläufig: Betrag = Tage × Tagessatz** (Menge bleibt unberücksichtigt); `vorhaltung(..., mit_menge=True)` multipliziert mit der Menge. Bitte entscheiden, welcher Standard gelten soll. |
| 2 | „Standorte mit transfer-bestätigtem Aufenthalt": Zählt der Startstandort (ohne `transfer_id`, z. B. aus dem Import) mit? | **Vorläufig: ja, alle übergebenen Standorte zählen**; VSC reicht nur die gewollten durch. |
| 3 | `kalkulatorisch_bis`: „volle Monate × Satz/Monat" — mit oder ohne Zins und Reparatur? | **Vorläufig: mit** (Satz/Monat = Summe aller drei Anteile, wie im Auftrag definiert). |
| 4 | `restbuchwert_kalk` rechnet nur den Abschreibungsanteil herunter. `miete_vs_eigen`: `mietkosten` ist der Gesamtbetrag für `tage`. | **Vorläufig: so.** |
| 5 | Ungültige Parameter (Restwert > Kaufpreis, Nutzungsdauer < 1, negative Prozente, Tage je Monat ≤ 0) → Fehler statt stillem Weiterrechnen. | **Vorläufig: `ValueError`.** |
