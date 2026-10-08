# PROTOKOLL — Box, Auftrag 01 (Vorarbeit Inventar), Lieferungen L1 bis L5

Stand 08.10.2026 · Box. Alles aus `BOX_AUFTRAG_01.md` (Drive: Gerate-App/box) bearbeitet; Abgabeform: Ordner `inventar_rein/` je Lieferung, README mit pytest-Zeile, `FRAGEN_L<n>.md`.

## 1. Ergebnis in einer Zeile

L1–L5 vollständig geliefert. `pytest -q`: **119 passed / 0 failed / 0 skipped**, geprüft unter **Python 3.12.3** und 3.13.16, auch mit `-W error`. `python -c "import inventar_rein"` ohne Ausgabe.

## 2. Was erledigt ist und wie

| Lieferung | Erledigt | Wie geprüft |
|---|---|---|
| **L1** kataloge, nummernformat, fristen | 12 Gruppen, 44 Merkmale, 12 Prüfarten als JSON; Lader und `pruefe_kataloge`; Nummernmuster `{nr:N}`, `{jahr}`, `{jahr2}`, `{gruppe}` mit Zählern je Schlüssel, `entspricht`, `normalisiere`; Fristen mit Monatsende-Regel, Ampel, Zählerfälligkeit, Werktage | 34 Prüffälle; alle Beispiele aus dem Auftrag (15.03.2026+12, 31.08.2026+6, 29.02.2028+12, `BM-00017`, Überlauf `1000`, `normalisiere(" bm-00017 ")`) |
| **L2** transfer | Zustandsautomat: Abgang, Scan (bestätigen / gesehen / überholen / System-Abgang / Erstanlage), Eingang, Zurückziehen, Überfällige, Erinnern, `status_auf`, Zubehör folgt; Teilmengen; Idempotenz über `eintrag_schluessel` | 23 Prüffälle: B1–B13 je mit Nummer im Namen, dazu Z1–Z8 (Teilmenge zurückziehen/überholen, Zusammenführen am Ziel, Fehlerfälle, Eingabe bleibt unverändert) |
| **L3** kosten | Kostensatz, Vorhaltung je Kostenstelle, Gesamtkosten, kalkulatorisch bis heute, Miete gegen Eigen, Restbuchwert | 14 Prüffälle; `test_bagger` trifft alle sechs Sollwerte (1.406,25 · 250,00 · 1.500,00 · 3.156,25 · 105,21 · 736,46) |
| **L4** import_vorlage, testdaten | Excel-Vorlage (Kopf, 2 Beispielzeilen, Dropdowns, Kommentare); `lies` mit allen Prüfregeln und Teil-Import; Generator mit Seed (2.500 Stück: 125 Transfers, 5.075 Prüfungen, 850 Zählerstände) | 31 Prüffälle: jede Prüfregel mit selbst erzeugter Datei (I16 stellt sicher, dass jeder Fehlerschlüssel erreichbar ist); erzeugte Stücke bestehen den eigenen Import (T5); Determinismus, Verteilung ±2 %, Eindeutigkeit der Nummern |
| **L5** etiketten, texte_de.json | HTML-Bogen 70 × 36 mm, 24 je A4, QR als SVG; 305 Texte (63 Hilfetexte, Begriffe, 22 Import-Fehler, Text zu jedem der 100 Meldungsschlüssel) | 17 Prüffälle: 25 Etiketten → 2 Seiten, QR-Inhalt, Kodierung, Kürzung, SVG parsebar; Textdatei wird gegen den Quelltext abgeglichen (fehlender oder verwaister Schlüssel bricht den Test) |

Abnahmekriterien aus Abschnitt 12: pytest grün mit `skipped = 0` ✓ · `import` ohne Nebenwirkung ✓ · Typangaben und Docstring an allen öffentlichen Funktionen, kein `print`, kein veränderlicher Modulzustand (per Skript geprüft) ✓ · jede Regel mit Nummer im Testnamen ✓ (für Abschnitte 4–6 habe ich K/N/F, für 8 C, 9 I/T, 10 E/X selbst vergeben) · `requirements.txt` genau zwei Zeilen ✓ · Dateien vollständig ✓.

## 3. Fehler, die beim Bauen aufgetreten sind (ehrlich)

- Mein von Hand gerechneter Sollwert für den 21,67-Tage-Satz war falsch (145,6429 statt 145,6507). Der Code war richtig; der Test wurde mit einer unabhängigen Decimal-Rechnung korrigiert (Woche 1.019,55).
- Zwei Prüffälle (I3, I16) hatten Fehler im Testaufbau (doppelte Nummern, falsche Gruppe für ein Merkmal), nicht im Modul. Behoben.
- `openpyxl` meldete eine Deprecation-Warnung (`font.copy`); ersetzt, damit `-W error` grün bleibt.
- Die Nachschlagetabellen in `testdaten.py` waren veränderlich; jetzt unveränderlich.

## 4. Was **nicht** geprüft ist

- WeasyPrint/PDF: nicht ausprobiert (laut Auftrag nur HTML als Text). Schriftgrößen, Kürzungslänge und Bogenränder brauchen einen Probedruck.
- Excel selbst: die Vorlage wurde nur mit `openpyxl` gelesen, nicht in Excel/LibreOffice geöffnet (Dropdowns, Kommentare, verstecktes Blatt).
- Rechtsgrundlagen und Fristen der Prüfarten sind nicht fachlich geprüft (siehe Fragen).
- Kein zweites Augenpaar: kein anderer hat den Code gelesen. Empfehlung: GER lässt `transfer.py` gegen die Regeln B1–B13 gegenlesen.

## 5. Wichtigste offene Fragen (vollständige Listen: `FRAGEN_L1.md` bis `FRAGEN_L5.md`)

| Nr. | Frage | Warum wichtig | Vorläufig |
|---|---|---|---|
| 1 | DGUV V3: 12 Monate richtig, oder kürzer für ortsveränderliche Betriebsmittel auf Baustellen (Fachperson fragen)? Auch die „(prüfen)"-Rechtsgründe | Falsche Frist ist eine Haftungsfrage | 12 Monate, „(prüfen)" |
| 2 | Mengenartikel: gilt Preis/Tagessatz je Stück oder je Zeile? | Wirkt auf Kosten, Testdaten, Import | je Stück; `vorhaltung(..., mit_menge=False)` |
| 3 | Teilmenge (B8): soll die abgehende Menge auf A bis zum Eingang noch „vor Ort" zählen? | Anzeige „Was steht wo" | wie B8 wörtlich: nein |
| 4 | B13 erster Abgang: Transfer mit `von_kostenstelle = None` (wie Auftrag) oder mit der genannten Quelle? | Konflikt im Auftragstext | erster Scan: `None`; erster Abgang: Quelle = `von_ks` |
| 5 | Merkmal-Schlüssel global eindeutig? | Importspalten `m:<schluessel>` | ja |
| 6 | Beispielzeilen der Vorlage beim Import ignorieren? | Sonst Geisterdatensätze bei Kostenstelle 1000 | nein (VSC warnt) |
| 7 | Zusatzfeld `Transfer.abgespalten`, Transfer-Id `t:<eintrag_schluessel>`, `quelle` bei `zurueckziehen` | Berührt Datenmodell von VSC | wie in L2-README |
| 8 | Texte: wie füllt VSC die Platzhalter (`str.format`?) — einige Texte enthalten wörtliche `{…}` | Sonst Laufzeitfehler | siehe FRAGEN_L5 Nr. 4 |
| 9 | Seite `bauteile` = Zubehör? Etikettenbogen 70 × 36 bestätigt? | Texte / Layout | ja / ja |

## 6. Nächste Schritte (Vorschlag)

1. Thomas → GER: Fragen 1–9 beantworten; GER gegenlesen `transfer.py`.
2. VSC: `inventar_rein/` in das Produkt einbauen, `pytest -q` einmal in der Zielumgebung (Python 3.12) laufen lassen, Probedruck der Etiketten.
3. Box: bei Antworten die Annahmen umstellen (je Frage ein kleiner, isolierter Eingriff) und neue Prüffälle ergänzen.

## 7. Wo liegt was

- Drive: `Gerate-App/box/lieferungen/` → `L1` … `L5` (je `inventar_rein/` mit den **neuen** Dateien der Lieferung, `README.md`, daneben `FRAGEN_L<n>.md`), `PROTOKOLL_BOX_01.md`. Die Ordner `inventar_rein/` werden zu einem Ordner zusammengelegt (gleiche Pfade, nichts überschneidet sich).
- Git: Zweig `claude/inventar-modul-vorarbeit-oil35n` im Repository `tommyderlehrling/box`: das vollständige, zusammengelegte Paket `inventar_rein/` plus Dokumente.
