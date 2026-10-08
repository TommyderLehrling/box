# FRAGEN_L1 — Box an GER/Thomas

Stand 08.10.2026. Nichts davon blockiert; ich habe jeweils die **vorläufige Annahme** eingebaut (steht auch in der README).

| Nr. | Frage | Vorschlag / vorläufig angenommen |
|---|---|---|
| 1 | Dürfen Merkmal-Schlüssel in zwei Gruppen gleich heißen (z. B. `gewicht`)? | **Vorläufig: nein, global eindeutig** — dann ist die Importspalte `m:<schluessel>` (L4) nie mehrdeutig. Alternative: je Gruppe eindeutig und Importspalte mit Gruppe. |
| 2 | Ist `{nr}` ohne Breite erlaubt? | **Vorläufig: Fehler** (`muster.nr_breite_fehlt`); Breite 1–12. |
| 3 | Monatsende-Regel: Bleibt ein Monatsende ein Monatsende (28.02.2027 + 12 → 29.02.2028) oder wird nur gekürzt (→ 28.02.2028)? | **Vorläufig: nur kürzen** (30.04. + 1 → 30.05.); passt zu allen drei Beispielen im Auftrag. |
| 4 | Ampel: Ist genau 30 Tage vor Fälligkeit schon gelb? | **Vorläufig: ja** (gelb, wenn `tage_bis <= gelb_ab_tagen`). |
| 5 | DGUV V3: Der Auftrag nennt 12 Monate. Ich vermute, dass für ortsveränderliche Betriebsmittel auf Baustellen kürzere Richtwerte üblich sind (z. B. 6 Monate) — nicht sicher. Eine oder mehrere Prüfarten (ortsfest / ortsveränderlich)? | **Vorläufig: eine Prüfart, 12 Monate**, Rechtsgrund mit „(prüfen)". Bitte Fachperson/Prüfer fragen. |
| 6 | Gruppen der Prüfarten, die der Auftrag offenlässt: `leitern_tritte`, `feuerloescher`, `druckbehaelter_*`; Durchführung von `anschlagmittel`, `uvv_fahrzeug`, `wartung_betriebsstunden`. | **Vorläufig:** `leitern_tritte` → werkzeug, kleingeraet · `feuerloescher` → baumaschine, fahrzeug, container · `druckbehaelter_*` → baumaschine, kleingeraet · alle drei Durchführungen `beides`. |
| 7 | Rechtsgrund bei `anschlagmittel` („DGUV Regel 100-500 (prüfen)"), `wartung_betriebsstunden` („Herstellervorgabe (prüfen)"), `uvv_erdbau` und `druckbehaelter_*` („(prüfen)"): Wer bestätigt die Vorschriften? | Vorläufig mit „(prüfen)" gekennzeichnet; ich rate keine Paragrafen. |
| 8 | `werktage_zwischen` mit `bis` vor `von`: 0 oder Fehler? Zähler kleiner als bei der Prüfung (z. B. Zählertausch): `False` oder Fehler? | **Vorläufig: 0 bzw. `False`**; kein Fehler. |
| 9 | `normalisiere`: „ß" stehen lassen oder zu „SS"? | **Vorläufig: „ß" bleibt.** |
| 10 | Die Fehlerschlüssel von `pruefe_kataloge`/`pruefe_muster` brauchen deutsche Texte. | Ich nehme sie in `texte_de.json` (L5) auf, sofern nichts dagegen spricht. |
