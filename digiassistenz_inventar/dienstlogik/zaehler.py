"""Zählerstände eines Stücks (Betriebsstunden, Kilometer): eintragen mit Plausibilität, Verlauf lesen.

Quellen: `web` (von Hand), `pruefung`, `werkstatt`, `import`; `baustelle` kommt erst mit dem Dienst `maschinenstunden` (AP-K2).
Ein Stand unter dem letzten wird **nicht** als Ablesung geführt — der Aufrufer bekommt den letzten Stand zurück und sagt es
(Hinweis statt stiller Korrektur); nichts wird überschrieben oder gelöscht.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import protokoll, zeit

from .. import modelle as m

OBJEKT_TYP = "inventar.stueck"
QUELLEN = ("web", "pruefung", "werkstatt", "import")


def letzter_stand(db: Any, mandant_id: int, stueck_id: int) -> Decimal | None:
    return db.execute(select(m.Zaehlerstand.stand).where(m.Zaehlerstand.mandant_id == mandant_id, m.Zaehlerstand.stueck_id == stueck_id)
                      .order_by(m.Zaehlerstand.abgelesen_am.desc(), m.Zaehlerstand.id.desc()).limit(1)).scalar_one_or_none()


def eintragen(
    sitzung: Any, stueck: m.Stueck, stand: Decimal, quelle: str, kostenstelle_id: int | None = None, *, protokollieren: bool = False,
) -> tuple[m.Zaehlerstand | None, Decimal | None]:
    """Trägt den Stand ein und liefert `(Zeile, letzter Stand)`; liegt er unter dem letzten, ist die Zeile `None`."""
    if stueck.zaehler_einheit is None:
        raise ValueError("zaehlerstand.kein_zaehler")
    if stand < 0:
        raise ValueError("zaehlerstand.negativ")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    letzter = letzter_stand(db, mid, int(stueck.id))
    if letzter is not None and stand < letzter:
        return None, letzter
    benutzer = None if sitzung.benutzer is None else int(sitzung.benutzer.id)
    satz = m.Zaehlerstand(mandant_id=mid, stueck_id=stueck.id, stand=stand, einheit=stueck.zaehler_einheit, abgelesen_am=zeit.jetzt_utc(),
                          abgelesen_von=benutzer, quelle=quelle, kostenstelle_id=kostenstelle_id)
    db.add(satz)
    db.flush()
    if protokollieren:
        protokoll.schreiben(db, mandant_id=mid, aktion="inventar.zaehlerstand", objekt_typ=OBJEKT_TYP, objekt_id=int(stueck.id),
                            neu_wert=f"{stand} {stueck.zaehler_einheit}", benutzer_id=benutzer, kostenstelle_id=kostenstelle_id)
    return satz, letzter


def verlauf(sitzung: Any, stueck_id: int, grenze: int = 200) -> list[dict[str, Any]]:
    """Der Verlauf eines Stücks, neueste zuerst: Stand, Einheit, Zeit, Quelle, wer."""
    from .stueckseite import namen_benutzer

    zeilen = list(sitzung.db.execute(select(m.Zaehlerstand).where(
        m.Zaehlerstand.mandant_id == sitzung.kontext.mandant_id, m.Zaehlerstand.stueck_id == stueck_id)
        .order_by(m.Zaehlerstand.abgelesen_am.desc(), m.Zaehlerstand.id.desc()).limit(grenze)).scalars())
    namen = namen_benutzer(sitzung, {z.abgelesen_von for z in zeilen})
    return [{"stand": z.stand, "einheit": z.einheit, "am": z.abgelesen_am, "quelle": z.quelle,
             "wer": namen.get(int(z.abgelesen_von), "") if z.abgelesen_von else ""} for z in zeilen]
