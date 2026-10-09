"""Transfer buchen, bestätigen, scannen, zurückziehen — lädt den Zustand, ruft `rein.transfer`, speichert, protokolliert.

Rechte: `inventar.buchen` auf der Kostenstelle des Abgangs, `inventar.scannen` für Eingang und Scan. Ein Stück,
das die Sitzung nicht sehen darf, gibt es nicht (gleiche Antwort wie „kein Recht“, N7).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import func, select

from digiassistenz_kern import protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein import transfer as automat
from ..rein.nummernformat import normalisiere
from . import laden, sicht

OBJEKT_TYP = "inventar.stueck"
Quelle = str


def finde_stueck(sitzung: Any, inventarnummer: str, aktion: str = "sehen") -> m.Stueck:
    """Das Stück mit dieser Nummer (auch Groß/Klein-unabhängig), sonst `KeinRecht`."""
    nummer = normalisiere(inventarnummer)
    zeile = sitzung.db.execute(
        sicht.stuecke(sitzung).where(func.upper(m.Stueck.inventarnummer) == nummer)).scalars().first()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", aktion)
    return zeile


def zustand(sitzung: Any, stueck: m.Stueck) -> automat.Zustand:
    return laden.lade_zustaende(sitzung.db, sitzung.kontext.mandant_id, [stueck])[stueck.inventarnummer]


def _benutzer(sitzung: Any) -> int | None:
    return None if sitzung.benutzer is None else int(sitzung.benutzer.id)


def _protokollieren(sitzung: Any, stueck: m.Stueck, ergebnis: automat.Ergebnis, kostenstelle_id: int | None) -> None:
    neu = next((a.daten for a in ergebnis.aenderungen if a.art == "transfer_neu"), None)
    detail = stueck.inventarnummer
    if neu is not None:
        detail += f": {neu['von_kostenstelle']} → {neu['nach_kostenstelle']} × {neu['menge']}"
    for schluessel in ergebnis.protokoll:
        protokoll.schreiben(
            sitzung.db, mandant_id=sitzung.kontext.mandant_id, aktion=laden.aktion_aus(schluessel),
            objekt_typ=OBJEKT_TYP, objekt_id=int(stueck.id), neu_wert=detail, benutzer_id=_benutzer(sitzung),
            kostenstelle_id=kostenstelle_id)


def _zubehoer(sitzung: Any, stueck: m.Stueck) -> list[m.Stueck]:
    """Zubehör, das dem Hauptstück folgt (Beziehung `gehoert_zu`, noch gültig)."""
    ids = select(m.Beziehung.von_stueck_id).where(
        m.Beziehung.mandant_id == sitzung.kontext.mandant_id, m.Beziehung.art == "gehoert_zu",
        m.Beziehung.zu_stueck_id == stueck.id, m.Beziehung.gueltig_bis.is_(None))
    return list(sitzung.db.execute(select(m.Stueck).where(m.Stueck.id.in_(ids)).order_by(m.Stueck.id)).scalars())


def _speichern(sitzung: Any, stueck: m.Stueck, ergebnis: automat.Ergebnis, kostenstelle_id: int | None,
               folgt: bool, jetzt: dt.datetime) -> automat.Ergebnis:
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    laden.speichern(db, mid, stueck, ergebnis)
    _protokollieren(sitzung, stueck, ergebnis, kostenstelle_id)
    if folgt and ergebnis.aenderungen:
        zub = _zubehoer(sitzung, stueck)
        if zub:
            zustaende = laden.lade_zustaende(db, mid, zub)
            for nummer, folge in automat.zubehoer_folgt(ergebnis, [z.inventarnummer for z in zub], zustaende, jetzt).items():
                zeile = next(z for z in zub if z.inventarnummer == nummer)
                laden.speichern(db, mid, zeile, folge)
                _protokollieren(sitzung, zeile, folge, kostenstelle_id)
    return ergebnis


def abgang_buchen(
    sitzung: Any, inventarnummer: str, von_ks: int, nach_ks: int, menge: int, eintrag_schluessel: str,
    grund: str = "", quelle: Quelle = "web",
) -> automat.Ergebnis:
    if not sitzung.darf("inventar", "buchen", von_ks):
        raise gemeinsam.KeinRecht("inventar", "buchen")
    stueck = finde_stueck(sitzung, inventarnummer, "buchen")
    jetzt = zeit.jetzt_utc()
    erg = automat.abgang_buchen(zustand(sitzung, stueck), stueck.inventarnummer, von_ks, nach_ks, menge,
                                laden.person(_benutzer(sitzung)), jetzt, quelle, eintrag_schluessel, grund)  # type: ignore[arg-type]
    return _speichern(sitzung, stueck, erg, von_ks, True, jetzt)


def eingang_bestaetigen(
    sitzung: Any, inventarnummer: str, eintrag_schluessel: str, menge: int | None = None,
    eingang_schluessel: str | None = None, quelle: Quelle = "web",
) -> automat.Ergebnis:
    """Bestätigt den angekündigten Transfer mit diesem `eintrag_schluessel` (optional Teilmenge)."""
    stueck = finde_stueck(sitzung, inventarnummer, "scannen")
    z = zustand(sitzung, stueck)
    t = next((t for t in z.transfers if t.eintrag_schluessel == eintrag_schluessel), None)
    if t is None:
        raise gemeinsam.KeinRecht("inventar", "scannen")
    if not sitzung.darf("inventar", "scannen", t.nach_kostenstelle):
        raise gemeinsam.KeinRecht("inventar", "scannen")
    jetzt = zeit.jetzt_utc()
    erg = automat.eingang_bestaetigen(z, t.id, laden.person(_benutzer(sitzung)), jetzt, quelle, menge,  # type: ignore[arg-type]
                                      eingang_schluessel)
    return _speichern(sitzung, stueck, erg, t.nach_kostenstelle, True, jetzt)


def scan_ist_hier(
    sitzung: Any, inventarnummer: str, ks: int, eintrag_schluessel: str, menge: int | None = None, quelle: Quelle = "handy",
) -> automat.Ergebnis:
    if not sitzung.darf("inventar", "scannen", ks):
        raise gemeinsam.KeinRecht("inventar", "scannen")
    stueck = finde_stueck(sitzung, inventarnummer, "scannen")
    jetzt = zeit.jetzt_utc()
    erg = automat.scan_ist_hier(zustand(sitzung, stueck), stueck.inventarnummer, ks,
                                laden.person(_benutzer(sitzung)), jetzt, quelle, eintrag_schluessel, menge)  # type: ignore[arg-type]
    return _speichern(sitzung, stueck, erg, ks, True, jetzt)


def zurueckziehen(
    sitzung: Any, inventarnummer: str, eintrag_schluessel: str, grund: str, quelle: Quelle = "web",
) -> automat.Ergebnis:
    stueck = finde_stueck(sitzung, inventarnummer, "buchen")
    z = zustand(sitzung, stueck)
    t = next((t for t in z.transfers if t.eintrag_schluessel == eintrag_schluessel), None)
    if t is None or t.von_kostenstelle is None or not sitzung.darf("inventar", "buchen", t.von_kostenstelle):
        raise gemeinsam.KeinRecht("inventar", "buchen")
    jetzt = zeit.jetzt_utc()
    erg = automat.zurueckziehen(z, t.id, grund, laden.person(_benutzer(sitzung)), jetzt, quelle)  # type: ignore[arg-type]
    return _speichern(sitzung, stueck, erg, t.von_kostenstelle, True, jetzt)
