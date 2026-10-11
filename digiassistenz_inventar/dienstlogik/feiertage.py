"""Werktage und freie Tage des Mandanten — der **eine** Datenzugriff für Feiertage.

Frei sind die Feiertage der Region des Mandanten (`kern.mandant.feiertagsregion`, Format `<Land>[-<Teil>]`, leer = keine Feiertage)
und die eigenen Tage des Betriebs (`inventar.feiertag`, nur aktive; `jaehrlich` gilt in jedem Jahr am selben Tag und Monat).
Alle Stellen, die Werktage zählen (Vorhaltung, Fristen, Kacheln, Erinnerungen), fragen hier. Die Liste kann später unverändert in den
Kern wandern: nur diese Datei kennt Tabelle und Mandant.

**Zählregel, an beiden Stellen dokumentiert:** `werktage()` hier zählt `[von, bis]` (beide Enden, für Zeiträume);
`rein.fristen.werktage_zwischen()` zählt `(von, bis]` (für Fristen). Nie eine Funktion mit zwei Regeln.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Mandant, zeit

from .. import modelle as m
from ..rein import feiertage as rein_feiertage
from ..rein.fristen import werktage_zwischen

HINWEIS_FEHLT = "feiertagsregion_fehlt"
HINWEIS_UNBEKANNT = "feiertagsregion_unbekannt"


def region(db: Any, mandant_id: int) -> str:
    """Die Feiertagsregion des Mandanten, wie sie im Kern steht (`DE`, `DE-NI`, leer)."""
    return (db.execute(select(Mandant.feiertagsregion).where(Mandant.id == mandant_id)).scalar_one_or_none() or "").strip()


def _tage_der_region(von: dt.date, bis: dt.date, text: str) -> set[dt.date]:
    try:
        return rein_feiertage.feiertage_zwischen(von, bis, text)
    except ValueError:
        return set()  # unbekannte Region: keine Feiertage, `hinweis()` sagt es


def hinweis(db: Any, mandant_id: int) -> str:
    """`feiertagsregion_fehlt` (leer), `feiertagsregion_unbekannt` (das Paket kennt sie nicht) oder leer, wenn alles in Ordnung ist."""
    text = region(db, mandant_id)
    if not text:
        return HINWEIS_FEHLT
    try:
        rein_feiertage.feiertage(zeit.heute().year, text)
    except ValueError:
        return HINWEIS_UNBEKANNT
    return ""


def _jaehrlich(datum: dt.date, jahre: range) -> set[dt.date]:
    tage: set[dt.date] = set()
    for jahr in jahre:
        try:
            tage.add(dt.date(jahr, datum.month, datum.day))
        except ValueError:
            continue  # der 29. Februar gibt es nicht in jedem Jahr
    return tage


def eigene_tage(db: Any, mandant_id: int, von: dt.date | None = None, bis: dt.date | None = None) -> set[dt.date]:
    """Die aktiven eigenen Tage des Betriebs, auf Wunsch nur im Zeitraum [von, bis]; jährliche Tage zählen in jedem Jahr des Zeitraums."""
    zeilen = list(db.execute(select(m.Feiertag).where(m.Feiertag.mandant_id == mandant_id, m.Feiertag.aktiv)).scalars())
    tage: set[dt.date] = set()
    for z in zeilen:
        if z.jaehrlich:
            jahre = range(von.year if von else z.datum.year, (bis.year if bis else z.datum.year) + 1)
            tage |= {t for t in _jaehrlich(z.datum, jahre) if t >= z.datum}
        else:
            tage.add(z.datum)
    return {t for t in tage if (von is None or t >= von) and (bis is None or t <= bis)}


def freie_tage(db: Any, mandant_id: int, von: dt.date, bis: dt.date) -> frozenset[dt.date]:
    """Feiertage der Region und eigene Tage im Zeitraum [von, bis]."""
    if bis < von:
        return frozenset()
    return frozenset(_tage_der_region(von, bis, region(db, mandant_id)) | eigene_tage(db, mandant_id, von, bis))


def werktage(db: Any, von: dt.date, bis: dt.date, mandant_id: int) -> int:
    """Werktage von `von` bis `bis`, **beide Tage eingeschlossen** `[von, bis]`: Montag bis Freitag ohne freie Tage des Mandanten.

    (`rein.fristen.werktage_zwischen` zählt dagegen `(von, bis]` — das ist die Regel der Fristen, nicht dieser Zeiträume.)
    """
    if bis < von:
        return 0
    return werktage_zwischen(von - dt.timedelta(days=1), bis, freie_tage(db, mandant_id, von, bis))


def frei_ab(db: Any, mandant_id: int, ab: dt.date, bis: dt.date) -> frozenset[dt.date]:
    """Freie Tage von `ab` (z. B. dem ältesten Abgang) bis `bis` — für Fristen, die in der Vergangenheit beginnen."""
    return freie_tage(db, mandant_id, ab, bis)


def frei_fuer_transfers(db: Any, mandant_id: int, zustaende: Any, heute: dt.date) -> frozenset[dt.date]:
    """Freie Tage vom ältesten offenen Abgang bis heute (die Frist der Transfers zählt Werktage ab dem Abgang)."""
    abgaenge = [t.abgang_am.date() for z in zustaende for t in z.transfers if t.status == "angekuendigt" and t.abgang_am is not None]
    return frozenset() if not abgaenge else frei_ab(db, mandant_id, min(abgaenge), heute)


def liste(db: Any, mandant_id: int) -> list[m.Feiertag]:
    """Alle eigenen Tage (auch abgeschaltete), neueste Tage zuerst."""
    return list(db.execute(select(m.Feiertag).where(m.Feiertag.mandant_id == mandant_id).order_by(m.Feiertag.datum.desc())).scalars())


def eigene_im_jahr(db: Any, mandant_id: int, jahr: int) -> list[m.Feiertag]:
    """Die eigenen Tage, die in diesem Jahr stehen: die mit Datum im Jahr und die jährlichen, die schon begonnen haben."""
    return [z for z in liste(db, mandant_id) if z.datum.year == jahr or (z.jaehrlich and z.datum.year < jahr)]


def benannt(db: Any, mandant_id: int, jahr: int) -> list[tuple[dt.date, str, bool]]:
    """Alle freien Tage eines Jahres als (Tag, Name, eigen?) — für die Anzeige in den Einstellungen. Eigene Tage ersetzen gleichdatierte Feiertage."""
    try:
        land = rein_feiertage.feiertage_benannt(jahr, region(db, mandant_id))
    except ValueError:
        land = {}
    zeilen: dict[dt.date, tuple[str, bool]] = {tag: (name, False) for tag, name in land.items()}
    for z in db.execute(select(m.Feiertag).where(m.Feiertag.mandant_id == mandant_id, m.Feiertag.aktiv)).scalars():
        if z.jaehrlich:
            for tag in _jaehrlich(z.datum, range(jahr, jahr + 1)):
                if tag >= z.datum:
                    zeilen[tag] = (z.bezeichnung, True)
        elif z.datum.year == jahr:
            zeilen[z.datum] = (z.bezeichnung, True)
    return [(t, name, eigen) for t, (name, eigen) in sorted(zeilen.items())]
