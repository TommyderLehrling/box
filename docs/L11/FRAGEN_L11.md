# FRAGEN_L11 — Fragen und Erkenntnisse zu den Seiten G1 (Box, Stand 10.10.2026)

Alles ist Entwurf, bis VSC es im Browser fährt. Antworten bitte in der Spalte „Antwort“ (Name, Datum) und die Datei unter demselben Namen in
`lieferungen/L11/` ablegen.

## A. Abweichungen von Auftrag 03 (mit Grund)

| Nr. | Auftrag sagt | Gebaut | Grund | Antwort |
|---|---|---|---|---|
| 1 | Merkmalsfelder nachladen mit `hx-get /inventar/merkmale/{gruppe_id}` | `/inventar/merkmale?gruppe=<schluessel>&neu=1` | Eine Auswahl kann ohne Skript keinen Pfadteil aus ihrem Wert bauen; HTMX schickt den Wert als Abfrageparameter. Rechte und Antwort sind gleich | |
| 2 | Haupttaste „Prüfung eintragen“ an der Stück-Seite (Abschnitt 5) | nicht gebaut; die Ampel steht in der Statuszeile, die Prüfungen im Abschnitt „Prüfungen“ | Abschnitt 1 weist „Prüfung eintragen mit Nachweis“ der L13 zu. Der Anwendungsfall `dienstlogik.pruefung.eintragen` steht und ist geprüft; die Seite wäre klein. **Soll sie in G1?** | |

## B. Kern-Befund (über GER an die Brücke, Regel 2)

| Nr. | Befund | Folge |
|---|---|---|
| 3 | `teil_wahl.html` setzt bei `pflicht=True` die Attribute zusammen: `… requiredaria-label="Nach"`. Mit `trim_blocks` verschwindet der Zeilenumbruch zwischen `{% if wahl.pflicht %} required{% endif %}` und `{% if wahl.beschriftung %}aria-label=…`. Das Wort `required` geht verloren | Ich nutze `pflicht=True` nicht; eine leere Wahl lehnt der Server mit einem Satz ab (`web.kostenstelle_fehlt`). Der Kern-Fix wäre ein Leerzeichen vor `aria-label` |

## C. Entscheidungen, die ich getroffen habe (bitte prüfen)

| Nr. | Punkt | Entscheidung |
|---|---|---|
| 4 | „seitenweise ab 200 Zeilen“ | Bis 200 Treffer steht alles auf einer Seite, darüber 100 je Seite. Die Zahl der Treffer steht über der Tabelle |
| 5 | „Statuszeile ist das erste Element unter dem Kopf“ | Sie steht direkt unter dem **Seitenkopf des Kerns** (Überschrift und Hilfezeile `teil_seitenkopf.html`), vor allen `<details>`. Die Überschrift lässt sich nicht hinter sie schieben, ohne den Kern-Teil zu ersetzen. Ist die Hilfezeile gemeint, bitte sagen |
| 6 | Kaufpreis und Kaufdatum im Formular | Nur mit `kosten_sehen` sichtbar und änderbar (Einkauf, Buchhaltung, Bauleiter…). Das Büro mit `pflegen` allein sieht und ändert sie nicht. Ein Mitarbeiter ohne `kosten_sehen` kann beim Anlegen keinen Preis nachtragen |
| 7 | Ordner `import/` | Hochgeladene Importdateien bleiben unter `arbeitsordner/inventar/<mandant>/import/<kennung>.xlsx` (nichts löschen). Der Ordner steht nicht in der Pfadliste von Abschnitt 2 |
| 8 | Etiketten-Auswahl | Gruppe, Kostenstelle oder Nummernliste (Leerzeichen, Komma, Zeilenumbruch); ohne Angabe die ganze Liste, höchstens 2.000 |
| 9 | Einstellung `werktage` (Startwert 0) | Steht im Formular, hat aber bisher **keine Wirkung** im Code (nur `transfer_frist_werktage`, `tage_je_monat`). Bedeutung klären oder streichen |
| 10 | Filter „nur fällig“ | Rechnet die Ampel für bis zu 5.000 sichtbare Stücke und zeigt rot und gelb. Bei mehr Stücken fehlt der Rest — dann echte Fälligkeitsliste (L13) |
| 11 | Testdaten-Taste | Verschwindet mit gesetztem `auslieferung_am`; das Datum lässt sich nicht zurücknehmen (`katalog.auslieferung_bleibt`) |
| 12 | Gruppen ohne Standort | Ein Stück ohne offenen Standort und ohne angekündigten Transfer sieht nur, wer **alle** Kostenstellen sieht (Verwalter). Wer auf Kostenstellen beschränkt ist, findet es nicht |

## D. Nicht gebaut (Abschnitt 10)

Meldung/Reparatur-Seiten (G4), Kosten-Seiten (G5), Handy-Schale (G6), Fälligkeitsliste und Prüfung eintragen (L13).
