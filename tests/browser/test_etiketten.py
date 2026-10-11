"""Browserfälle 5 und 11 (INTEGRATION_VSC.md Abschnitt 4): Etiketten-PDF.

Der **Probedruck** auf Etikettenpapier 70 × 36 mm (Fall 11) bleibt Handarbeit; geprüft wird hier, was ohne Papier geht: ein A4-Hochformat-PDF zum Herunterladen,
die Zahl der Seiten nach der Zahl der Stücke und dass jede gedruckte Nummer über den QR-Weg `/inventar/s/<nummer>` aufgeht.
"""

from __future__ import annotations

import re
import zlib

from playwright.sync_api import Page


def _nummern(seite: Page, wie_viele: int) -> list[str]:
    seite.goto("/inventar?ansicht=liste")
    nummern = seite.locator("#inventar-liste table.liste tr td:first-child a").all_inner_texts()
    assert len(nummern) >= wie_viele, "zu wenig Stücke in der Box: der Seed fehlt?"
    return nummern[:wie_viele]


def _bogen(seite: Page, nummern: list[str]) -> bytes:
    seite.goto("/inventar/verwaltung/etiketten")
    seite.fill("#et-nummern", ", ".join(nummern))
    with seite.expect_download() as geladen:
        seite.click("form[action='/inventar/verwaltung/etiketten'] button.haupt")
    datei = geladen.value
    assert datei.suggested_filename.startswith("etiketten_") and datei.suggested_filename.endswith(".pdf")
    with open(datei.path(), "rb") as f:
        return f.read()


def _entpackt(pdf: bytes) -> bytes:
    """Alle Flate-Ströme des PDF entpackt (WeasyPrint legt den Seitenbaum in einen komprimierten Objektstrom)."""
    teile = [pdf]
    for strom in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, flags=re.S):
        try:
            teile.append(zlib.decompress(strom))
        except zlib.error:
            continue
    return b"\n".join(teile)


def _seiten(pdf: bytes) -> int:
    treffer = re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)|/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", _entpackt(pdf))
    assert treffer, "kein Seitenbaum gefunden"
    return max(int(a or b) for a, b in treffer)


def test_F05_zwanzig_etiketten_ein_bogen_dreissig_zwei(verwalter: Page) -> None:
    """Sollwert: 20 Stücke → 1 Seite; 30 Stücke (25–48) → 2 Seiten; A4 hoch (595 × 842 pt); jede Nummer geht über `/inventar/s/<nummer>` auf."""
    nummern = _nummern(verwalter, 30)
    zwanzig = _bogen(verwalter, nummern[:20])
    assert zwanzig.startswith(b"%PDF") and _seiten(zwanzig) == 1
    assert re.search(rb"/MediaBox\s*\[\s*0\s+0\s+59[45][\.\d]*\s+84[12][\.\d]*\s*\]", _entpackt(zwanzig)), "A4 hoch"
    assert _seiten(_bogen(verwalter, nummern)) == 2
    for nummer in nummern[:3]:
        antwort = verwalter.goto(f"/inventar/s/{nummer}")
        assert antwort.status == 200 and re.search(r"/inventar/stueck/\d+", verwalter.url), nummer


def test_F11_probedruck_format_a4_mit_dem_etikettenraster(verwalter: Page) -> None:
    """Sollwert (ohne Papier): das Raster ist 24 je A4 (70 × 36 mm); ein Bogen mit 24 Stücken füllt genau eine Seite, das 25. beginnt eine zweite.
    Das Auflegen auf Etikettenpapier und der Abgleich mit der Stanzung bleibt Handarbeit (Probedruck, Thomas/VSC)."""
    nummern = _nummern(verwalter, 25)
    assert _seiten(_bogen(verwalter, nummern[:24])) == 1
    assert _seiten(_bogen(verwalter, nummern)) == 2
