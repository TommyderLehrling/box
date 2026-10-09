# L8 — Posteingang-Kacheln, Verrechnung, Standardwerte, Scan

Neu: `kacheln.py`, `verrechnung.py`, `daten/kostensaetze_standard.json`, `tests/test_kacheln.py` (H1–H4), `tests/test_verrechnung.py` (G1–G7). Geändert: `kosten.py` (Standardwerte, `parameter_fuer`, `mit_menge=True` als Standard), `etiketten.py` (`inventarnummer_aus_scan`), `tests/test_kosten.py` (C8 angepasst, C15), `tests/test_etiketten.py` (E11), `tests/test_texte.py`, `daten/texte_de.json`.

```
python -m pytest -q        # im Ordner inventar_rein
215 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13, auch mit -W error)
```

| Teil | Inhalt |
|---|---|
| `kacheln(stuecke, pruefstaende, meldungen, heute, reparaturen=(), meine_kostenstellen=(), frist_werktage=3, feiertage=())` | `Kachel(text_schluessel, zahl, weg_schluessel, recht)` in fester Reihenfolge: fällig/überfällig (`inventar.pruefen`) · ohne Nachweis (`inventar.pruefen`) · angekündigt an mich (`inventar.scannen`) · Transfers überfällig (`inventar.buchen`) · Meldungen offen (`inventar.werkstatt`) · Reparaturen in Arbeit (`inventar.werkstatt`). Zahl 0 entfällt. Rechte filtert VSC vor dem Aufruf (nur erlaubte Stücke übergeben). Endzustände zählen nicht. |
| `verrechne(stuecke, stunden, von, bis, werktage=False, feiertage=())` | je Kostenstelle und Stück: Tage, Vorhaltung (mit Menge), Stunden × `satz_stunde`, Summe; Summen je Kostenstelle und je Stück; Stunden außerhalb des Zeitraums zählen nicht; fehlender Stundensatz: 0 und Hinweis `verrechnung.satz_stunde_fehlt:<Nr>`. Eingabe der Stunden wie Dienst `maschinenstunden`: `(tag, kostenstelle, inventarnummer, maschinen_std)`. |
| `miete_gegen_eigen(stuecke, von, bis, ...)` | je Mietstück (`miete=True`): Mietkosten gegen den **mittleren** `satz_tag` der eigenen Stücke derselben Gruppe × Miettage im Zeitraum; ohne Vergleichsstück `eigen = None`. |
| `csv_text` / `schreibe_csv` | Semikolon, Dezimalkomma, Windows-Zeilenende, Datei mit BOM; beides einstellbar. |
| `lade_standardwerte()` / `parameter_fuer(gruppe, standardwerte, kaufpreis)` | Vorschlagswerte je Gruppe (Nutzungsdauer, Reparatur %/Jahr, Restwert %, Zins %), überall `"quelle": "vorschlag_box"`. Die Werte sind **meine Vorschläge**, aus keiner Tabelle abgeschrieben. |
| `inventarnummer_aus_scan(text, basis_url)` | versteht unsere QR-Adresse (Groß/Klein egal, mit `?`/`#`/Schrägstrich am Ende) **und** eine getippte oder aufgedruckte reine Nummer; fremde Adressen, leer, Steuerzeichen, `<>"';?#%&=|{}`, über 64 Zeichen → `None`. |
