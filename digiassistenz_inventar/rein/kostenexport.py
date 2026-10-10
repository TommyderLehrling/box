"""CSV-Auszüge der Kosten-Seite und der Inventur — reine Texte, geschrieben wird in der Dienstlogik.

Standard für deutsches Excel: Semikolon, Dezimalkomma, Zeilenende CRLF; die Datei bekommt beim Schreiben ein BOM (utf-8-sig).
Die Kopfzeilen sind Schlüssel (`kostenstelle`, `betrag` …), keine Sätze; die Seite zeigt ihre eigenen Texte.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal

BLOECKE = ("kostenstelle", "stueck", "miete", "anlagenbuch")

KOPF = {
    "kostenstelle": ("kostenstelle", "inventarnummer", "tage", "betrag_vorhaltung"),
    "stueck": ("inventarnummer", "bezeichnung", "gruppe", "kaufdatum", "kaufpreis", "satz_tag", "satz_monat", "kalkulatorisch_bis_heute",
               "reparaturen_belegt", "reparaturen_geschaetzt", "gesamtkosten", "satzquelle"),
    "miete": ("inventarnummer", "gruppe", "miettage", "miete", "eigen", "differenz"),
    "anlagenbuch": ("inventarnummer", "bezeichnung", "gruppe", "kaufdatum", "kaufpreis", "lieferant", "buchwert_extern", "afa_hinweis"),
    "inventur": ("kostenstelle", "inventarnummer", "bezeichnung", "erwartet", "gesehen", "ergebnis"),
}


def _zelle(wert: object) -> str:
    if wert is None:
        return ""
    if isinstance(wert, Decimal):
        return f"{wert:f}".replace(".", ",")
    if isinstance(wert, datetime):
        return wert.isoformat(timespec="seconds")
    if isinstance(wert, date):
        return wert.isoformat()
    return str(wert)


def csv_text(block: str, zeilen: Iterable[Sequence[object]]) -> str:
    """Die CSV eines Blocks mit Kopfzeile; jede Zeile muss so viele Zellen haben wie der Kopf."""
    kopf = KOPF[block]
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    schreiber.writerow(kopf)
    for z in zeilen:
        if len(z) != len(kopf):
            raise ValueError("kosten.spaltenzahl")
        schreiber.writerow([_zelle(x) for x in z])
    return puffer.getvalue()


def dateiname(block: str, zeitpunkt: datetime) -> str:
    """`kosten_<block>_<JJJJMMTT-HHMMSS>.csv` — der Zeitstempel macht den Namen eindeutig, überschrieben wird nie (siehe `dateien.speichern`)."""
    if block not in KOPF:
        raise ValueError("kosten.block_unbekannt")
    praefix = "inventur" if block == "inventur" else f"kosten_{block}"
    return f"{praefix}_{zeitpunkt.strftime('%Y%m%d-%H%M%S')}.csv"
