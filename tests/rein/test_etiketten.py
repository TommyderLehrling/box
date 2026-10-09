"""Prueffaelle fuer etiketten (E1-E10)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from html import unescape

import pytest

from digiassistenz_inventar.rein.etiketten import Etikett, Layout, bogen_html, kuerze, qr_inhalt, qr_svg

BASIS = "https://dokon.example.test"


def etiketten(n: int, nummer: str = "BM-{:05d}", bez: str = "Hydraulikbagger 21 t") -> list[Etikett]:
    return [Etikett(nummer.format(i + 1), bez, "Baumaschinen", "Muster-Bau GmbH") for i in range(n)]


def test_E1_vierundzwanzig_pro_bogen_und_25_ergeben_zwei_seiten():
    assert bogen_html(etiketten(24), BASIS).count('class="seite"') == 1
    assert bogen_html(etiketten(25), BASIS).count('class="seite"') == 2
    assert bogen_html(etiketten(48), BASIS).count('class="seite"') == 2
    assert bogen_html(etiketten(49), BASIS).count('class="seite"') == 3
    assert bogen_html(etiketten(25), BASIS).count('class="etikett"') == 25


def test_E2_jeder_qr_inhalt_enthaelt_die_nummer():
    html = bogen_html(etiketten(30), BASIS)
    inhalte = [unescape(x) for x in re.findall(r'data-qr="([^"]*)"', html)]
    assert len(inhalte) == 30
    for i, inhalt in enumerate(inhalte, start=1):
        assert inhalt == f"{BASIS}/inventar/s/BM-{i:05d}"


def test_E3_sonderzeichen_im_qr_inhalt_sind_kodiert():
    assert qr_inhalt(BASIS, "A/B 7") == f"{BASIS}/inventar/s/A%2FB%207"
    assert qr_inhalt(BASIS + "/", "G-2026-0001") == f"{BASIS}/inventar/s/G-2026-0001"
    assert qr_inhalt(BASIS, "ÄÖ#?") == f"{BASIS}/inventar/s/%C3%84%C3%96%23%3F"
    html = bogen_html([Etikett("A/B 7", "x", "g", "f")], BASIS)
    assert "A%2FB%207" in html
    with pytest.raises(ValueError, match="basis_url_ungueltig"):
        qr_inhalt("dokon.example", "X")


def test_E4_lange_bezeichnung_wird_gekuerzt():
    lang = "Hydraulikbagger " * 8  # 128 Zeichen
    kurz = kuerze(lang)
    assert len(kurz) <= 48 and kurz.endswith("…")
    assert kuerze("Nivelliergerät") == "Nivelliergerät"
    html = bogen_html(etiketten(1, bez="x" * 120), BASIS)
    assert "x" * 49 not in html and "…" in html


def test_E5_qr_svg_ist_gueltiges_svg_ohne_xml_kopf():
    svg = qr_svg("https://dokon.example.test/inventar/s/BM-00017")
    assert svg.startswith("<svg") and "<?xml" not in svg
    wurzel = ET.fromstring(svg)
    assert wurzel.tag.endswith("svg") and "viewBox" in wurzel.attrib
    assert qr_svg("a") != qr_svg("b")


def test_E6_css_seite_a4_ohne_rand_und_feste_mm_masse():
    html = bogen_html(etiketten(1), BASIS)
    assert "@page { size: A4; margin: 0 }" in html
    assert "width: 70mm" in html and "height: 36mm" in html
    assert "left:0mm;top:4.5mm" in html
    assert "left:70mm;top:4.5mm" in bogen_html(etiketten(2), BASIS)
    assert "left:0mm;top:40.5mm" in bogen_html(etiketten(4), BASIS)  # zweite Zeile
    assert "page-break-after: always" in html


def test_E7_nummer_gross_und_fett_mindestens_14_pt():
    html = bogen_html(etiketten(1), BASIS)
    regel = re.search(r"\.nr \{([^}]*)\}", html).group(1)
    assert float(re.search(r"font-size: ([0-9.]+)pt", regel).group(1)) >= 14
    assert "font-weight: bold" in regel


def test_E8_html_wird_maskiert():
    html = bogen_html([Etikett("X<1>", "<b>fett</b> & Co", "G<", "A&B")], BASIS)
    assert "<b>fett</b>" not in html and "&lt;b&gt;fett&lt;/b&gt; &amp; Co" in html
    assert "X&lt;1&gt;" in html


def test_E9_eigenes_layout():
    layout = Layout(spalten=2, zeilen=4, breite_mm=Decimal("90"), hoehe_mm=Decimal("60"), rand_oben_mm=Decimal("10"), rand_links_mm=Decimal("15"))
    html = bogen_html(etiketten(9), BASIS, layout)
    assert html.count('class="seite"') == 2
    assert "left:15mm;top:10mm" in html and "left:105mm;top:70mm" in html
    with pytest.raises(ValueError, match="layout_zu_gross"):
        bogen_html(etiketten(1), BASIS, Layout(spalten=4))
    with pytest.raises(ValueError, match="layout_zu_gross"):
        bogen_html(etiketten(1), BASIS, Layout(zeilen=9))


def test_E10_leere_liste_ist_fehler():
    with pytest.raises(ValueError, match="etiketten.leer"):
        bogen_html([], BASIS)


def test_E11_nummer_aus_scan_url_oder_getippt():
    from digiassistenz_inventar.rein.etiketten import inventarnummer_aus_scan as aus
    basis = "https://dokon.example"
    assert aus("https://dokon.example/inventar/s/BM-04711", basis) == "BM-04711"
    assert aus(" HTTPS://DOKON.EXAMPLE/inventar/s/bm-04711/?ref=x#a ", basis) == "BM-04711"
    assert aus(qr_inhalt(basis + "/", "AB 12/ä-ß"), basis) == "AB 12/Ä-ß"
    assert aus("  bm-04711 ", basis) == "BM-04711"
    assert aus("12345678", basis) == "12345678"               # reine Nummer eines gekauften Etiketts
    for ungueltig in ("", "   ", "https://fremd.example/inventar/s/BM-1", "https://dokon.example/inventar/s/",
                      "https://dokon.example/inventar/s/a/b", "BM<script>", "a;b", "x" * 65, "BM\n1\x00"):
        assert aus(ungueltig, basis) is None, ungueltig
    with pytest.raises(ValueError, match="basis_url_ungueltig"):
        aus("BM-1", "dokon.example")
