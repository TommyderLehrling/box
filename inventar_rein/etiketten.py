"""Etikettenbogen als HTML mit CSS (WeasyPrint macht spaeter das PDF); QR mit segno."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from urllib.parse import quote

import segno

MAX_BEZEICHNUNG = 48  # zwei Zeilen zu je etwa 24 Zeichen bei 8 pt
NUMMER_PT = 14


@dataclass(frozen=True)
class Etikett:
    inventarnummer: str
    bezeichnung: str
    gruppe_text: str
    firma: str


@dataclass(frozen=True)
class Layout:
    spalten: int = 3
    zeilen: int = 8
    breite_mm: Decimal = Decimal("70")
    hoehe_mm: Decimal = Decimal("36")
    rand_oben_mm: Decimal = Decimal("4.5")
    rand_links_mm: Decimal = Decimal("0")  # A4, 24 je Bogen (Standard-Bogen 70 x 36)


def qr_inhalt(basis_url: str, inventarnummer: str) -> str:
    """Baut die Adresse hinter dem QR-Code; die Nummer wird URL-sicher kodiert."""
    if not basis_url.startswith(("http://", "https://")):
        raise ValueError("etiketten.basis_url_ungueltig")
    return f"{basis_url.rstrip('/')}/inventar/s/{quote(inventarnummer, safe='')}"


def qr_svg(inhalt: str) -> str:
    """Erzeugt den QR-Code als SVG-Zeichenkette (Fehlerkorrektur M, ohne XML-Kopf)."""
    return segno.make(inhalt, error="m").svg_inline(scale=1, omitsize=True)


def kuerze(text: str, grenze: int = MAX_BEZEICHNUNG) -> str:
    """Kuerzt auf grenze Zeichen und haengt bei Bedarf eine Ellipse an."""
    text = " ".join(text.split())
    return text if len(text) <= grenze else text[: grenze - 1].rstrip() + "…"


def _mm(x: Decimal) -> str:
    return f"{x.normalize():f}mm"


def _css(layout: Layout) -> str:
    inhalt_h = layout.hoehe_mm - 4
    return (
        "@page { size: A4; margin: 0 }\n"
        "html, body { margin: 0; padding: 0; font-family: Arial, Helvetica, sans-serif; }\n"
        ".seite { position: relative; width: 210mm; height: 297mm; overflow: hidden; page-break-after: always; }\n"
        ".seite:last-child { page-break-after: auto; }\n"
        f".etikett {{ position: absolute; box-sizing: border-box; width: {_mm(layout.breite_mm)}; "
        f"height: {_mm(layout.hoehe_mm)}; padding: 2mm; display: flex; overflow: hidden; }}\n"
        f".qr {{ flex: 0 0 {_mm(inhalt_h)}; width: {_mm(inhalt_h)}; height: {_mm(inhalt_h)}; }}\n"
        ".qr svg { width: 100%; height: 100%; display: block; }\n"
        ".text { flex: 1 1 auto; min-width: 0; padding-left: 2mm; display: flex; flex-direction: column; }\n"
        f".nr {{ font-size: {NUMMER_PT}pt; font-weight: bold; line-height: 1.1; overflow-wrap: anywhere; }}\n"
        ".bez { font-size: 8pt; line-height: 1.2; max-height: 2.4em; overflow: hidden; margin-top: 1mm; }\n"
        ".klein { font-size: 6pt; color: #333; margin-top: auto; }\n"
    )


def bogen_html(etiketten: Iterable[Etikett], basis_url: str, layout: Layout = Layout()) -> str:
    """Setzt alle Etiketten auf A4-Boegen; nach jedem vollen Bogen folgt ein Seitenumbruch."""
    liste = list(etiketten)
    if not liste:
        raise ValueError("etiketten.leer")
    if (layout.spalten < 1 or layout.zeilen < 1
            or layout.rand_links_mm + layout.spalten * layout.breite_mm > 210
            or layout.rand_oben_mm + layout.zeilen * layout.hoehe_mm > 297):
        raise ValueError("etiketten.layout_zu_gross")
    je_seite = layout.spalten * layout.zeilen
    seiten: list[str] = []
    for start in range(0, len(liste), je_seite):
        zellen: list[str] = []
        for i, e in enumerate(liste[start:start + je_seite]):
            zeile, spalte = divmod(i, layout.spalten)
            links = layout.rand_links_mm + spalte * layout.breite_mm
            oben = layout.rand_oben_mm + zeile * layout.hoehe_mm
            inhalt = qr_inhalt(basis_url, e.inventarnummer)
            zellen.append(
                f'<div class="etikett" style="left:{_mm(links)};top:{_mm(oben)}" data-qr="{escape(inhalt, quote=True)}">'
                f'<div class="qr">{qr_svg(inhalt)}</div>'
                f'<div class="text"><div class="nr">{escape(e.inventarnummer)}</div>'
                f'<div class="bez">{escape(kuerze(e.bezeichnung))}</div>'
                f'<div class="klein">{escape(e.gruppe_text)} · {escape(e.firma)}</div></div></div>'
            )
        seiten.append('<div class="seite">' + "".join(zellen) + "</div>")
    return (
        '<!DOCTYPE html>\n<html lang="de"><head><meta charset="utf-8"><title>Etiketten</title>'
        f"<style>\n{_css(layout)}</style></head><body>\n" + "\n".join(seiten) + "\n</body></html>\n"
    )
