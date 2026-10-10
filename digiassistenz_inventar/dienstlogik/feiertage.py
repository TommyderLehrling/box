"""Werktage und freie Tage des Mandanten — der **eine** Datenzugriff für Feiertage.

Frei sind die Feiertage des eingestellten Bundeslandes (`bundesland`, leer = keine) und die eigenen Tage des Betriebs
(`inventar.feiertag`, nur aktive). Alle Stellen, die Werktage zählen (Vorhaltung, Fristen, Kacheln, Erinnerungen), fragen
hier. Die Liste kann später unverändert in den Kern wandern: nur diese Datei kennt Tabelle und Einstellung.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select

from .. import modelle as m
from ..rein import feiertage as rein_feiertage
from ..rein.fristen import werktage_zwischen
from . import katalog

EINSTELLUNG_LAND = "bundesland"


def bundesland(db: Any, mandant_id: int) -> str:
    return katalog.einstellung(db, mandant_id, EINSTELLUNG_LAND).strip().upper()


def eigene_tage(db: Any, mandant_id: int, von: dt.date | None = None, bis: dt.date | None = None) -> set[dt.date]:
    """Die aktiven eigenen Tage des Betriebs, auf Wunsch nur im Zeitraum [von, bis]."""
    q = select(m.Feiertag.datum).where(m.Feiertag.mandant_id == mandant_id, m.Feiertag.aktiv)
    if von is not None:
        q = q.where(m.Feiertag.datum >= von)
    if bis is not None:
        q = q.where(m.Feiertag.datum <= bis)
    return set(db.execute(q).scalars())


def freie_tage(db: Any, mandant_id: int, von: dt.date, bis: dt.date) -> frozenset[dt.date]:
    """Feiertage des Bundeslandes und eigene Tage im Zeitraum [von, bis]."""
    if bis < von:
        return frozenset()
    land = bundesland(db, mandant_id)
    return frozenset(rein_feiertage.feiertage_zwischen(von, bis, land) | eigene_tage(db, mandant_id, von, bis))


def werktage(db: Any, von: dt.date, bis: dt.date, mandant_id: int) -> int:
    """Werktage von `von` bis `bis`, beide Tage eingeschlossen: Montag bis Freitag ohne freie Tage des Mandanten."""
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


def benannt(db: Any, mandant_id: int, jahr: int) -> list[tuple[dt.date, str, bool]]:
    """Alle freien Tage eines Jahres als (Tag, Textschlüssel oder Bezeichnung, eigen?) — für die Anzeige in den Einstellungen."""
    zeilen: dict[dt.date, tuple[str, bool]] = {t: (f"inventar.feiertag.{n}", False)
                                               for t, n in rein_feiertage.feiertage_benannt(jahr, bundesland(db, mandant_id)).items()}
    for z in db.execute(select(m.Feiertag).where(m.Feiertag.mandant_id == mandant_id, m.Feiertag.aktiv,
                                                 m.Feiertag.datum >= dt.date(jahr, 1, 1), m.Feiertag.datum <= dt.date(jahr, 12, 31))).scalars():
        zeilen[z.datum] = (z.bezeichnung, True)
    return [(t, name, eigen) for t, (name, eigen) in sorted(zeilen.items())]
