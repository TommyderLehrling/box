"""Pflege am einzelnen Stück: ändern, Foto, Zubehör, Bauteil, Zählerstand und „Schaden melden“.

Rechte: `pflegen` (ändern, Foto, Zubehör, Bauteil), `scannen` oder `pflegen` (Zählerstand), `melden` (Schaden).
Nichts wird gelöscht: eine Beziehung endet mit `gueltig_bis`, eine Meldung bekommt später einen Status.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Mandant, protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import dateien
from .. import modelle as m
from .stueck import OBJEKT_TYP, _benutzer, _merkmale_schreiben
from .transfer import finde_stueck

ANGABEN = ("bezeichnung", "hersteller", "typ", "seriennummer", "baujahr", "lieferant_id", "kaufdatum", "kaufpreis", "besonderheiten")


def _fordern(sitzung: Any, aktion: str, kostenstelle_id: int | None = None) -> None:
    if not sitzung.darf("inventar", aktion, kostenstelle_id):
        raise gemeinsam.KeinRecht("inventar", aktion)


def _wert(wert: Any) -> str:
    return "" if wert is None else str(wert)


def aendern(sitzung: Any, inventarnummer: str, angaben: dict[str, Any], merkmale: dict[str, str] | None = None) -> m.Stueck:
    """Ändert die Stammangaben und Merkmale; das Protokoll nennt jedes geänderte Feld mit altem und neuem Wert."""
    _fordern(sitzung, "pflegen")
    zeile = finde_stueck(sitzung, inventarnummer, "pflegen")
    db, mid, benutzer = sitzung.db, sitzung.kontext.mandant_id, _benutzer(sitzung)
    if "bezeichnung" in angaben and not str(angaben["bezeichnung"]).strip():
        raise ValueError("stueck.bezeichnung_fehlt")
    alt, neu = [], []
    for name in ANGABEN:
        if name in angaben and angaben[name] != getattr(zeile, name):
            alt.append(f"{name}={_wert(getattr(zeile, name))}")
            neu.append(f"{name}={_wert(angaben[name])}")
            setattr(zeile, name, angaben[name])
    if merkmale is not None:
        vorhanden = {sp.schluessel: (z, sp) for z, sp in db.execute(
            select(m.StueckMerkmal, m.Merkmal).join(m.Merkmal, m.Merkmal.id == m.StueckMerkmal.merkmal_id)
            .where(m.StueckMerkmal.stueck_id == zeile.id)).all()}
        for schluessel, wert in merkmale.items():
            if schluessel not in vorhanden:
                _merkmale_schreiben(db, mid, zeile, {schluessel: wert}, benutzer)
                neu.append(f"{schluessel}={wert}")
                continue
            satz, spalte = vorhanden[schluessel]
            if satz.wert == wert:
                continue
            zahl = None
            if spalte.typ == "zahl":
                try:
                    zahl = Decimal(str(wert).replace(",", "."))
                except InvalidOperation as fehler:
                    raise ValueError("stueck.merkmal_wert_ungueltig") from fehler
            elif spalte.typ == "auswahl" and wert not in (spalte.auswahl or []):
                raise ValueError("stueck.merkmal_wert_ungueltig")
            alt.append(f"{schluessel}={satz.wert}")
            neu.append(f"{schluessel}={wert}")
            satz.wert, satz.wert_zahl, satz.geaendert_am, satz.geaendert_von = str(wert), zahl, zeit.jetzt_utc(), benutzer
    if not neu:
        return zeile
    zeile.geaendert_am, zeile.geaendert_von = zeit.jetzt_utc(), benutzer
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.stueck_geaendert", objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id),
                        alt_wert="; ".join(alt) or None, neu_wert="; ".join(neu), benutzer_id=benutzer)
    return zeile


def foto_speichern(sitzung: Any, inventarnummer: str, inhalt_typ: str, inhalt: bytes, arbeitsordner: Path) -> m.Stueck:
    """jpg oder png bis 8 MB nach `stamm/<nr>/bilder/`; der Hash steht am Stück, eine alte Datei bleibt liegen."""
    _fordern(sitzung, "pflegen")
    zeile = finde_stueck(sitzung, inventarnummer, "pflegen")
    endung = dateien.foto_pruefen(inhalt_typ, len(inhalt), inhalt)
    ordnername = sitzung.db.execute(select(Mandant.ordnername).where(Mandant.id == sitzung.kontext.mandant_id)).scalar_one()
    ziel, pruefsumme = dateien.speichern(
        dateien.stammordner(arbeitsordner, ordnername, zeile.inventarnummer, "bilder"), f"foto{endung}", inhalt)
    zeile.foto_pfad, zeile.foto_sha256 = str(ziel.relative_to(arbeitsordner)), pruefsumme
    zeile.geaendert_am, zeile.geaendert_von = zeit.jetzt_utc(), _benutzer(sitzung)
    sitzung.db.flush()
    protokoll.schreiben(sitzung.db, mandant_id=sitzung.kontext.mandant_id, aktion="inventar.stueck_foto", objekt_typ=OBJEKT_TYP,
                        objekt_id=int(zeile.id), neu_wert=pruefsumme, benutzer_id=_benutzer(sitzung))
    return zeile


def _beziehung_offen(db: Any, mid: int, **bedingung: Any) -> m.Beziehung | None:
    q = select(m.Beziehung).where(m.Beziehung.mandant_id == mid, m.Beziehung.gueltig_bis.is_(None))
    for name, wert in bedingung.items():
        q = q.where(getattr(m.Beziehung, name) == wert)
    return db.execute(q).scalars().first()


def zubehoer_zuordnen(sitzung: Any, inventarnummer: str, haupt_nummer: str) -> m.Beziehung:
    """Das Stück ist Zubehör des Hauptstücks und folgt ihm bei Transfers. Ein Stück hat höchstens ein Hauptstück."""
    _fordern(sitzung, "pflegen")
    zubehoer = finde_stueck(sitzung, inventarnummer, "pflegen")
    haupt = finde_stueck(sitzung, haupt_nummer, "pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    if int(zubehoer.id) == int(haupt.id):
        raise ValueError("zubehoer.selbst")
    if _beziehung_offen(db, mid, art="gehoert_zu", von_stueck_id=zubehoer.id) is not None:
        raise ValueError("zubehoer.schon_zugeordnet")
    if _beziehung_offen(db, mid, art="gehoert_zu", von_stueck_id=haupt.id, zu_stueck_id=zubehoer.id) is not None:
        raise ValueError("zubehoer.kreis")
    satz = m.Beziehung(mandant_id=mid, von_stueck_id=zubehoer.id, art="gehoert_zu", zu_stueck_id=haupt.id,
                       gueltig_von=zeit.heute(), angelegt_von=_benutzer(sitzung))
    db.add(satz)
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.zubehoer_zugeordnet", objekt_typ=OBJEKT_TYP, objekt_id=int(haupt.id),
                        neu_wert=zubehoer.inventarnummer, benutzer_id=_benutzer(sitzung))
    return satz


def beziehung_beenden(sitzung: Any, inventarnummer: str, beziehung_id: int) -> m.Beziehung:
    """Beendet Zubehör oder Passung (`gueltig_bis` = heute); gelöscht wird nichts."""
    _fordern(sitzung, "pflegen")
    zeile = finde_stueck(sitzung, inventarnummer, "pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    satz = db.execute(select(m.Beziehung).where(m.Beziehung.mandant_id == mid, m.Beziehung.id == beziehung_id,
                                                m.Beziehung.gueltig_bis.is_(None))).scalar_one_or_none()
    beteiligt = satz is not None and int(zeile.id) in (satz.von_stueck_id, satz.zu_stueck_id)
    if satz is None or not beteiligt:
        raise gemeinsam.KeinRecht("inventar", "pflegen")
    satz.gueltig_bis = zeit.heute()
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.beziehung_beendet", objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id),
                        alt_wert=satz.art, benutzer_id=_benutzer(sitzung))
    return satz


def bauteil_zuordnen(sitzung: Any, inventarnummer: str, bauteil_id: int) -> m.Beziehung:
    """Ein Bauteil aus dem Katalog passt zu diesem Stück (`passt_zu`)."""
    _fordern(sitzung, "pflegen")
    zeile = finde_stueck(sitzung, inventarnummer, "pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    bauteil = db.execute(select(m.Bauteil).where(m.Bauteil.mandant_id == mid, m.Bauteil.id == bauteil_id, m.Bauteil.aktiv)).scalar_one_or_none()
    if bauteil is None:
        raise ValueError("bauteil.unbekannt")
    if _beziehung_offen(db, mid, art="passt_zu", bauteil_id=bauteil.id, zu_stueck_id=zeile.id) is not None:
        raise ValueError("bauteil.schon_zugeordnet")
    satz = m.Beziehung(mandant_id=mid, art="passt_zu", bauteil_id=bauteil.id, zu_stueck_id=zeile.id, gueltig_von=zeit.heute(),
                       angelegt_von=_benutzer(sitzung))
    db.add(satz)
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.bauteil_zugeordnet", objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id),
                        neu_wert=bauteil.bauteilnummer, benutzer_id=_benutzer(sitzung))
    return satz


def zaehlerstand_eintragen(sitzung: Any, inventarnummer: str, stand: Decimal, kostenstelle_id: int | None = None,
                           quelle: str = "web") -> m.Zaehlerstand:
    """Ein Stand in der Einheit des Stücks (`h` bei Großgerät); er darf nicht unter dem letzten liegen."""
    if not (sitzung.darf("inventar", "scannen", kostenstelle_id) or sitzung.darf("inventar", "pflegen")):
        raise gemeinsam.KeinRecht("inventar", "scannen")
    zeile = finde_stueck(sitzung, inventarnummer, "sehen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    if zeile.zaehler_einheit is None:
        raise ValueError("zaehlerstand.kein_zaehler")
    if stand < 0:
        raise ValueError("zaehlerstand.negativ")
    letzter = db.execute(select(m.Zaehlerstand.stand).where(m.Zaehlerstand.mandant_id == mid, m.Zaehlerstand.stueck_id == zeile.id)
                         .order_by(m.Zaehlerstand.abgelesen_am.desc(), m.Zaehlerstand.id.desc()).limit(1)).scalar_one_or_none()
    if letzter is not None and stand < letzter:
        raise ValueError("zaehlerstand.zurueck")
    satz = m.Zaehlerstand(mandant_id=mid, stueck_id=zeile.id, stand=stand, einheit=zeile.zaehler_einheit, abgelesen_am=zeit.jetzt_utc(),
                          abgelesen_von=_benutzer(sitzung), quelle=quelle, kostenstelle_id=kostenstelle_id)
    db.add(satz)
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.zaehlerstand", objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id),
                        neu_wert=f"{stand} {zeile.zaehler_einheit}", benutzer_id=_benutzer(sitzung), kostenstelle_id=kostenstelle_id)
    return satz


def schaden_melden(sitzung: Any, inventarnummer: str, kostenstelle_id: int, beschreibung: str, eintrag_schluessel: str,
                   foto: tuple[str, bytes] | None = None, arbeitsordner: Path | None = None, art: str = "schaden") -> m.Meldung:
    """Legt eine `meldung` mit Status `offen` an (G4 bearbeitet sie später); dieselbe Buchung zweimal gibt dieselbe Meldung."""
    _fordern(sitzung, "melden", kostenstelle_id)
    zeile = finde_stueck(sitzung, inventarnummer, "melden")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    if art not in m.MELDUNG_ART:
        raise ValueError("meldung.art_unbekannt")
    if not beschreibung.strip():
        raise ValueError("meldung.beschreibung_fehlt")
    schon = db.execute(select(m.Meldung).where(m.Meldung.mandant_id == mid, m.Meldung.eintrag_schluessel == eintrag_schluessel)).scalar_one_or_none()
    if schon is not None:
        return schon
    pfad = pruefsumme = None
    if foto is not None and foto[1]:
        if arbeitsordner is None:
            raise ValueError("pruefung.arbeitsordner_fehlt")
        endung = dateien.foto_pruefen(foto[0], len(foto[1]), foto[1])
        ordnername = db.execute(select(Mandant.ordnername).where(Mandant.id == mid)).scalar_one()
        ziel, pruefsumme = dateien.speichern(
            dateien.stammordner(arbeitsordner, ordnername, zeile.inventarnummer, "meldungen"), f"meldung{endung}", foto[1])
        pfad = str(ziel.relative_to(arbeitsordner))
    satz = m.Meldung(mandant_id=mid, stueck_id=zeile.id, kostenstelle_id=kostenstelle_id, art=art, beschreibung=beschreibung.strip(),
                     foto_pfad=pfad, foto_sha256=pruefsumme, status="offen", gemeldet_von=_benutzer(sitzung),
                     eintrag_schluessel=eintrag_schluessel)
    db.add(satz)
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.meldung_angelegt", objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id),
                        neu_wert=f"{art}: {beschreibung.strip()[:200]}", benutzer_id=_benutzer(sitzung), kostenstelle_id=kostenstelle_id)
    return satz
