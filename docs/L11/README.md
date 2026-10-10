# L11 — Seiten G1 (Auftrag 03)

Inventarliste (Ordner/Liste, Filter, Suche, seitenweise), Stück-Seite mit Statuszeile, Stück anlegen/ändern, Merkmale, Zubehör/Bauteile,
Zählerstand, Foto, „Schaden melden“, Verwaltung → Inventar (Gruppen, Merkmale, Prüfarten, Bauteile, Kostensätze, Einstellungen, Import,
Etiketten, Testdaten). L11 und L12 sind **zusammen** gebaut und gegeneinander geprüft; die Drive-Ordner trennen die Dateien nach
Zuständigkeit (Liste unten), maßgeblich ist L10 + L11 + L12, spätere Dateien ersetzen frühere.

```
python -m pytest -q        # im Ordner Inventar → 280 passed, skipped = 0
```

Mit Datenbank (Kern 0.15.2, PostgreSQL 16, `tests/integration/laufen.md`): `test_t_i_5.py`, `test_dienstlogik_db.py`,
`test_migration_gegen_modelle.py`, **neu** `test_seiten_db.py` (5 Fälle durch die echte Anwendung) → 28 passed, 0 skipped.

## Dateien in diesem Ordner (alle vollständig)

| Pfad | Was |
|---|---|
| `dienstlogik/liste.py` | Filter, Suche (Nummer, Name, Seriennummer, Kennzeichen-Merkmal, Ort), Sortierung, Seiten, Ordner |
| `dienstlogik/stueckseite.py` | Alles für die Stück-Seite, nur lesend; Kosten nur mit `kosten_sehen` |
| `dienstlogik/pflege.py` | Stück ändern, Foto, Zubehör, Bauteil, Zählerstand, Schaden melden |
| `dienstlogik/katalogpflege.py` | Gruppen, Merkmale, Prüfarten (mit Intervall je Merkmal), Bauteile, Kostensätze, Einstellungen |
| `dienstlogik/sicht.py`, `nummer.py`, `dateien.py`, `modul.py` | kleine Ergänzungen (angekündigte Transfers, Nummernvorschlag, Foto-Anfang prüfen, Suchtreffer → `/inventar/s/<nr>`) |
| `web/helfer.py`, `web/stueck.py`, `web/verwaltung.py`, `web/seiten.py` | die Routen |
| `vorlagen/inventar_uebersicht.html`, `teil_inventar_liste.html`, `inventar_stueck.html`, `inventar_stueck_form.html`, `teil_inventar_merkmale.html`, `teil_inventar_fertig.html`, `inventar_verwaltung*.html` (10) | Seiten |
| `tests/test_vorlagen.py` | alle Vorlagen mit Fake-Kontext, dazu 11 Inhaltsfälle |

Die geänderten Dateien `texte/de.json` (165 neue Schlüssel), `tests/rein/test_texte.py` und die Tests mit Datenbank liegen in `lieferungen/L12/`.

## Wege (Abweichung von Abschnitt 5 siehe `FRAGEN_L11.md` Nr. 1)

`/inventar` · `/inventar/liste` · `/inventar/stueck/{id}` · `/inventar/stueck/neu` · `/inventar/stueck/{id}/aendern|status|zubehoer|bauteil|zaehlerstand|meldung` ·
`/inventar/merkmale?gruppe=` · `/inventar/verwaltung[/gruppen|merkmale|pruefarten|bauteile|kostensaetze|einstellungen|import|import/vorlage|etiketten|testdaten]`.
