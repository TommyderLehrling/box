# L9 — Beispielbetrieb

Neu: `beispielbetrieb.py`, `daten/beispielbetrieb.json`, `tests/test_beispielbetrieb.py` (E1–E9); geändert: `tests/test_texte.py` (Präfix, .json-Namen), `daten/texte_de.json` (5 Schlüssel).

```
python -m pytest -q        # im Ordner inventar_rein
202 passed / 0 failed / 0 skipped   (auch mit -W error)
```

**Stichtag 09.10.2026.** 50 Stücke, fünf Kostenstellen (1000 Bauhof · 79795 · 80010 · 2000 Werkstatt · 3000 Büro), Personen `polier.eins` (79795), `polier.zwei` (80010), `dispo`, `werkstatt`.
Die Geschichte (Buchungen, Prüfungen, Zählerstände, Meldungen, Reparaturen) steht in der JSON-Datei und wird mit den echten Modulen `transfer`, `pruefung`, `werkstatt` nachgespielt: `zustaende(b)`, `pruefstaende(b, katalog)`. `schreibe_importdatei(b, pfad, merkmale)` schreibt die Stücke im Importformat; E2 liest sie mit `lies` ohne Fehler zurück, ein zweiter Lauf von `plane` ändert nichts.

Der Bagger heißt `BM-04711` (Muster `{gruppe}-{nr:5}`, Nummer 4711).

## Welches Stück zeigt welchen Fall

| Nummer | Bezeichnung | Start-KS | Fall |
|---|---|---|---|
| BM-04711 | Hydraulikbagger 21 t | 1000 | Bagger 4711: Bauhof, Abgang nach 79795 angekuendigt, Tieflöffel folgt |
| BM-00002 | Minibagger 1,8 t | 1000 | Abgang und Scan bestaetigt, Grabenloeffel folgt |
| BM-00003 | Radlader 8 t | 80010 | Wartung nach Betriebsstunden gelb durch Zaehler |
| BM-00004 | Tandemwalze 12 t | 79795 | Pruefung ohne Nachweis (unbekannt) |
| BM-00005 | Teleskoplader 3,5 t | 79795 | Mietgeraet mit Zeitraum |
| BM-00006 | Planierraupe 18 t | 2000 | in der Werkstatt, ohne Meldung |
| BM-00007 | Mobilbagger 14 t | 79795 | Pruefung gruen |
| AG-00001 | Tieflöffel 600 mm | 1000 | Zubehoer zu BM-04711 (folgt dem Bagger) |
| AG-00002 | Hydraulikhammer 800 kg | 1000 | Zubehoer ohne Hauptstueck, frei |
| AG-00003 | Grabenlöffel 400 mm | 1000 | Zubehoer zu BM-00002 |
| KG-00001 | Rüttelplatte 400 kg | 1000 | DGUV-V3-Pruefung ueberfaellig (rot), per Scan system-seitig umgebucht |
| KG-00002 | Stromerzeuger 8 kVA | 79795 | Pruefung gruen |
| KG-00003 | Trennschleifer 400 mm | 79795 | Pruefung gelb (6 Tage) |
| KG-00004 | Tauchpumpe 2 Zoll | 2000 | in_reparatur mit Meldung in Arbeit und interner Reparatur |
| KG-00005 | Bautrockner | 80010 | offene Meldung (noch niemand angenommen) |
| KG-00006 | Nassschneider | 1000 | vermisst |
| KG-00007 | Kompressor 10 bar | 80010 | ohne Pruefart |
| KG-00008 | Stampfer 70 kg | 1000 | steht auf dem Bauhof |
| WZ-00001 | Schaufel | 1000 | Mengenartikel: Teil-Eingang 8 von 10, Fehlmenge 2 angekuendigt |
| WZ-00002 | Schubkarre | 1000 | Mengenartikel ohne Bewegung |
| WZ-00003 | Bohrhammer | 79795 | Einzelstueck Werkzeug |
| WZ-00004 | Wasserwaage 2 m | 80010 | Einzelstueck Werkzeug |
| EL-00001 | Kabeltrommel 50 m | 1000 | Transfer ueberfaellig: Abgang vor mehr als 3 Werktagen nicht bestaetigt |
| EL-00002 | Baustromverteiler | 79795 | Baustromverteiler-Pruefung gruen |
| EL-00003 | Flutlichtstrahler | 80010 | ohne Pruefart |
| EL-00004 | Handlampe | 1000 | ohne Pruefart |
| EL-00005 | Kabelbrücke | 79795 | Mengenartikel Elektro |
| VM-00001 | Nivelliergerät | 1000 | Vermessung |
| VM-00002 | Rotationslaser | 79795 | Vermessung |
| VM-00003 | Messlatte 5 m | 80010 | Vermessung |
| CO-00001 | Bürocontainer 20 ft | 79795 | Container auf 79795 |
| CO-00002 | Mannschaftscontainer 20 ft | 80010 | Container auf 80010 |
| SR-00001 | Schalungsstütze | 79795 | 40 Stuetzen auf zwei Kostenstellen (25 auf 79795, 15 auf 80010) |
| SR-00002 | Schaltafel 50 x 250 | 1000 | Mengenartikel auf dem Bauhof |
| SR-00003 | Gerüstrahmen 2 m | 80010 | Mengenartikel auf 80010 |
| HZ-00001 | Kettenzug 2 t | 1000 | Hebezeug-Pruefung gruen |
| HZ-00002 | Rundschlinge 3 t | 1000 | Mengenartikel Anschlagmittel |
| HZ-00003 | Traverse 4 m | 79795 | ohne Nachweis (Hebezeug-Pruefung nie eingetragen) |
| BA-00001 | Schreibtisch 160×80 | 3000 | Schreibtisch im Buero |
| BA-00002 | Bürostuhl | 3000 | Mengenartikel Buero |
| BA-00003 | Aktenschrank | 3000 | Buero |
| BA-00004 | Besprechungstisch | 3000 | Buero |
| IT-00001 | Laptop 15 Zoll | 3000 | DGUV-V3 Buero gruen |
| IT-00002 | Laptop 15 Zoll | 79795 | Laptop auf der Baustelle |
| IT-00003 | Tablet 10 Zoll | 79795 | Tablet |
| IT-00004 | Drucker A3 | 3000 | Drucker |
| IT-00005 | Monitor 27 Zoll | 3000 | Monitor |
| FZ-00001 | Kipper 3-Achs | 1000 | HU in 27 Tagen faellig (gelb) |
| FZ-00002 | Transporter 3,5 t | 1000 | HU ueberfaellig (rot) |
| FZ-00003 | Pritschenwagen | 1000 | HU gruen |

## Zustände nach Spec Abschnitt 16 (in E3 bis E5 geprüft)

- Bagger `BM-04711`: Bauhof `vor_ort`, 79795 `angekuendigt`, Tieflöffel `AG-00001` folgt (Quelle `system`); `bestand` auf 79795 führt ihn nur als `angekuendigt`.
- `polier.eins` scannt auf 79795: Transfer bestätigt, Bauhof-Standort geschlossen. `polier.zwei` scannt auf 80010: neuer Transfer 79795→80010, Abgang Quelle `system`.
- Überfällig bei Frist 3 Werktage: nur `EL-00001` (Abgang 02.10.).
- Ampeln: rot 2 (Rüttelplatte DGUV, Transporter HU), gelb 3 (Trennschleifer, Radlader durch Zähler, Kipper HU), unbekannt 3.
