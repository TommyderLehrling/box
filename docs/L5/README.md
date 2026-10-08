# inventar_rein — Lieferung L5 (etiketten, texte_de.json)

Stand 08.10.2026 · gehört in denselben Ordner `inventar_rein/` wie L1 bis L4. Braucht `segno`.

## Neu
| Datei | Inhalt |
|---|---|
| `etiketten.py` | `Etikett`, `Layout`, `qr_inhalt`, `qr_svg`, `bogen_html` (und die Hilfe `kuerze`) |
| `daten/texte_de.json` | 305 Oberflächentexte (flach, `schluessel → Text`) |
| `tests/test_etiketten.py` | 10 Prüffälle E1–E10 |
| `tests/test_texte.py` | 7 Prüffälle X1–X7 |

## Aufruf (drei Zeilen)
```python
from inventar_rein.etiketten import Etikett, bogen_html
html = bogen_html([Etikett("BM-00017", "Hydraulikbagger 21 t", "Baumaschinen", "Muster-Bau GmbH")], "https://dokon.example.test")
print(html.count('class="etikett"'), "data-qr=\"https://dokon.example.test/inventar/s/BM-00017\"" in html)  # 1 True
```

## Prüflauf
```
python -m pytest -q        # im Ordner inventar_rein (L1 bis L5, vollständig)
119 passed / 0 failed / 0 skipped   (Python 3.12.3 und 3.13.16, pytest 9.1.1)
python -c "import inventar_rein"   # ohne Ausgabe
```

## So ist es gebaut
- **Etiketten:** A4, 3 × 8 = 24 je Bogen, 70 × 36 mm, absolut positioniert in mm; `@page { size: A4; margin: 0 }`; Seitenumbruch nach jedem vollen Bogen. Links QR (`segno`, Fehlerkorrektur M, ohne XML-Kopf), rechts Inventarnummer (14 pt, fett), Bezeichnung (8 pt, höchstens 48 Zeichen, sonst mit „…" gekürzt), darunter Gruppe und Firma klein. Jedes Etikett trägt `data-qr="<Adresse>"`, damit sich der QR-Inhalt im HTML prüfen lässt. Texte werden HTML-maskiert.
- **QR-Adresse:** `<basis_url>/inventar/s/<Nummer>`, die Nummer URL-kodiert (`/` → `%2F`, Leerzeichen → `%20`).
- **Texte:** 63 Hilfetexte (21 Seiten × `liegt` / `tasten` / `danach`), Begriffe `inventar.<bereich>.<name>`, alle 22 Import-Fehler `inventar.import.fehler.<name>` und zu **jedem** Meldungsschlüssel der Module ein Text `inventar.code.<schlüssel>`. Zwei Prüffälle vergleichen die Datei mit dem Quelltext: Fehlt für einen neuen Schlüssel der Text (oder bleibt einer übrig), schlägt der Test an. Angehängte Einzelheiten (`gruppe.kuerzel_doppelt:BM`) werden als `{detail}` eingesetzt.

## Grenzen
- WeasyPrint ist **nicht** getestet (laut Auftrag nur HTML als Text). Die Textlänge (48 Zeichen) und der Rand sind rechnerisch gewählt; ein Probedruck mit echtem Bogen steht aus.
- Die Wortlaute sind ein Entwurf; Thomas/GER prüfen sie.

## Offene Fragen
Siehe `FRAGEN_L5.md`.
