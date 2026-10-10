# L12 — Seiten G2 (Auftrag 03)

Hier-Seite des Poliers („angekündigt — ist angekommen?“, „vor Ort“), Abgang buchen, Eingang bestätigen (auch Teilmenge), Scan „ist hier“,
Zurückziehen, Scan-Seite im Browser (`BarcodeDetector`, Rückfall Eingabe), QR-Ziel `/inventar/s/{nummer}`, Reiter an der Kostenstelle mit
Link zur gefilterten Liste, Dienste-Adapter mit lokaler Klasse `Dienst`. Die Transfer-Erinnerungen (Kacheln, Mail über
`python -m digiassistenz_inventar.erinnern`) stehen seit L10 und sind unverändert; die Verbindungs-Taste „Baustelle“ bleibt leer, bis APP den
Weg nennt (`FRAGEN_L12.md` Nr. 4).

```
python -m pytest -q        # im Ordner Inventar → 280 passed, skipped = 0
```

Mit Datenbank: 28 passed, 0 skipped (`test_seiten_db.py` fährt Abgang → Eingang → Teil-Eingang → Zurückziehen → Scan durch die Anwendung).

## Dateien in diesem Ordner (alle vollständig)

| Pfad | Was |
|---|---|
| `web/hier.py`, `web/transfer.py`, `web/__init__.py`, `web/kostenstelle.py` | Hier, Scan-Seite, Buchungswege, Reiter |
| `vorlagen/inventar_hier.html`, `inventar_scannen.html`, `teil_inventar_kostenstelle.html` | Seiten |
| `statisch/inventar.js` | Kamera-Scan mit Eingabe-Rückfall |
| `dienste.py` | `Dienst` (gleiche Felder wie der künftige Kern-Typ), `DIENSTE` |
| `texte/de.json` | **alle** Texte (L10 + L11 + L12) |
| `tests/rein/test_texte.py`, `tests/integration/test_seiten_db.py`, `test_dienstlogik_db.py`, `laufen.md` | Prüffälle |
| `INTEGRATION_VSC.md`, `README.md`, `docs/…` | Anleitung, Protokolle, Fragen |
