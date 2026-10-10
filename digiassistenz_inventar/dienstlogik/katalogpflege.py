"""Verwaltung → Inventar: Kataloge und Einstellungen pflegen (anlegen, ändern, deaktivieren — nie löschen).

Recht `einstellen`; die Kostensätze verlangen `kosten_pflegen`. Fehler sind Schlüssel `katalog.<was>` (Text unter
`inventar.code.katalog.<was>`). Startwerte (`startwert`) bleiben als solche markiert.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein import zeitplan
from ..rein.nummernformat import pruefe_muster
from . import katalog

EINSTELLUNGEN_ZAHL = ("transfer_frist_werktage", "tage_je_monat", "werktage", "gelb_ab_tagen", "zaehler_gelb_prozent", "pruefung_erinnern_tage")
EINSTELLUNGEN_TEXT = ("nummernmuster", "etikett_layout", "zins_prozent", "auslieferung_am", "erinnern_um")
_SCHLUESSEL = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_KUERZEL = re.compile(r"^[A-Z]{2}$")


def _fordern(sitzung: Any, aktion: str = "einstellen") -> None:
    if not sitzung.darf("inventar", aktion):
        raise gemeinsam.KeinRecht("inventar", aktion)


def _benutzer(sitzung: Any) -> int | None:
    return None if sitzung.benutzer is None else int(sitzung.benutzer.id)


def _schluessel(text: str) -> str:
    wert = text.strip()
    if not _SCHLUESSEL.match(wert):
        raise ValueError("katalog.schluessel_ungueltig")
    return wert


def _protokoll(sitzung: Any, aktion: str, objekt: str, alt: str | None, neu: str | None) -> None:
    protokoll.schreiben(sitzung.db, mandant_id=sitzung.kontext.mandant_id, aktion=f"inventar.{aktion}", objekt_typ=f"inventar.{objekt}",
                        alt_wert=alt, neu_wert=neu, benutzer_id=_benutzer(sitzung))


def _zahl(text: str, fehler: str, *, ganz: bool = False, minimum: int = 0) -> Decimal | int:
    try:
        wert = Decimal(str(text).strip().replace(",", "."))
    except InvalidOperation as ursache:
        raise ValueError(fehler) from ursache
    if wert < minimum or (ganz and wert != wert.to_integral_value()):
        raise ValueError(fehler)
    return int(wert) if ganz else wert


# ---- Gruppen ------------------------------------------------------------------------------------------------------

def gruppe_speichern(sitzung: Any, schluessel: str, bezeichnung: str, kuerzel: str, oben: str = "", sortierung: int = 0,
                     aktiv: bool = True) -> m.Gruppe:
    _fordern(sitzung)
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    schluessel = _schluessel(schluessel)
    if not bezeichnung.strip():
        raise ValueError("katalog.bezeichnung_fehlt")
    if not _KUERZEL.match(kuerzel.strip()):
        raise ValueError("katalog.kuerzel_ungueltig")
    zeile = db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid, m.Gruppe.schluessel == schluessel)).scalar_one_or_none()
    anderes = db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid, m.Gruppe.kuerzel == kuerzel.strip())).scalar_one_or_none()
    if anderes is not None and (zeile is None or anderes.id != zeile.id):
        raise ValueError("katalog.kuerzel_doppelt")
    oben_id = None
    if oben:
        ober = db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid, m.Gruppe.schluessel == oben)).scalar_one_or_none()
        if ober is None or ober.schluessel == schluessel:
            raise ValueError("katalog.oben_unbekannt")
        oben_id = ober.id
    if zeile is None:
        zeile = m.Gruppe(mandant_id=mid, schluessel=schluessel, bezeichnung=bezeichnung.strip(), kuerzel=kuerzel.strip(),
                         oben_id=oben_id, sortierung=sortierung, aktiv=aktiv)
        db.add(zeile)
        _protokoll(sitzung, "gruppe_angelegt", "gruppe", None, schluessel)
    else:
        alt = f"{zeile.bezeichnung}/{zeile.kuerzel}/{zeile.aktiv}"
        zeile.bezeichnung, zeile.kuerzel, zeile.oben_id, zeile.sortierung, zeile.aktiv = bezeichnung.strip(), kuerzel.strip(), oben_id, sortierung, aktiv
        _protokoll(sitzung, "gruppe_geaendert", "gruppe", alt, f"{zeile.bezeichnung}/{zeile.kuerzel}/{zeile.aktiv}")
    db.flush()
    return zeile


# ---- Merkmale -----------------------------------------------------------------------------------------------------

def merkmal_speichern(sitzung: Any, gruppe: str, schluessel: str, bezeichnung: str, typ: str, einheit: str = "",
                      auswahl: str = "", pflicht: bool = False, sortierung: int = 0, aktiv: bool = True) -> m.Merkmal:
    _fordern(sitzung)
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    schluessel = _schluessel(schluessel)
    zeile_gruppe = db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid, m.Gruppe.schluessel == gruppe)).scalar_one_or_none()
    if zeile_gruppe is None:
        raise ValueError("katalog.gruppe_unbekannt")
    if typ not in m.MERKMAL_TYP:
        raise ValueError("katalog.typ_unbekannt")
    if not bezeichnung.strip():
        raise ValueError("katalog.bezeichnung_fehlt")
    werte = [w.strip() for w in auswahl.replace("\n", ",").split(",") if w.strip()]
    if typ == "auswahl" and (not werte or len(set(werte)) != len(werte)):
        raise ValueError("katalog.auswahl_ungueltig")
    if typ != "auswahl":
        werte = []
    zeile = db.execute(select(m.Merkmal).where(m.Merkmal.mandant_id == mid, m.Merkmal.gruppe_id == zeile_gruppe.id,
                                               m.Merkmal.schluessel == schluessel)).scalar_one_or_none()
    if zeile is None:
        zeile = m.Merkmal(mandant_id=mid, gruppe_id=zeile_gruppe.id, schluessel=schluessel, bezeichnung=bezeichnung.strip(), typ=typ,
                          einheit=einheit.strip(), auswahl=werte, pflicht=pflicht, sortierung=sortierung, aktiv=aktiv)
        db.add(zeile)
        _protokoll(sitzung, "merkmal_angelegt", "merkmal", None, f"{gruppe}.{schluessel}")
    else:
        if zeile.typ != typ and db.execute(select(m.StueckMerkmal.id).where(m.StueckMerkmal.merkmal_id == zeile.id).limit(1)).first():
            raise ValueError("katalog.typ_in_benutzung")
        alt = f"{zeile.bezeichnung}/{zeile.typ}/{zeile.aktiv}"
        zeile.bezeichnung, zeile.typ, zeile.einheit, zeile.auswahl = bezeichnung.strip(), typ, einheit.strip(), werte
        zeile.pflicht, zeile.sortierung, zeile.aktiv = pflicht, sortierung, aktiv
        _protokoll(sitzung, "merkmal_geaendert", "merkmal", alt, f"{zeile.bezeichnung}/{zeile.typ}/{zeile.aktiv}")
    db.flush()
    return zeile


# ---- Prüfarten ----------------------------------------------------------------------------------------------------

def _je_merkmal(text: str) -> dict[str, dict[str, int]]:
    """Zeilen `merkmal=wert:monate` (z. B. `fahrzeugklasse=pkw:24`), eine je Zeile oder durch Strichpunkt getrennt."""
    ergebnis: dict[str, dict[str, int]] = {}
    for zeile in re.split(r"[;\n]", text):
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            links, monate = zeile.rsplit(":", 1)
            merkmal, wert = links.split("=", 1)
            zahl = int(monate)
        except ValueError as ursache:
            raise ValueError("katalog.je_merkmal_ungueltig") from ursache
        if zahl < 1 or not merkmal.strip() or not wert.strip():
            raise ValueError("katalog.je_merkmal_ungueltig")
        ergebnis.setdefault(merkmal.strip(), {})[wert.strip()] = zahl
    return ergebnis


def je_merkmal_text(tabelle: dict[str, dict[str, int]] | None) -> str:
    return "\n".join(f"{merkmal}={wert}:{monate}" for merkmal, werte in (tabelle or {}).items() for wert, monate in werte.items())


def pruefart_speichern(sitzung: Any, schluessel: str, bezeichnung: str, intervall_monate: str, zaehler_intervall: str = "",
                       rechtsgrund: str = "", durchfuehrung: str = "intern", je_merkmal: str = "", gruppen: tuple[str, ...] = (),
                       aktiv: bool = True, gruppen_intervall: dict[str, str] | None = None) -> m.Pruefart:
    _fordern(sitzung)
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    schluessel = _schluessel(schluessel)
    if not bezeichnung.strip():
        raise ValueError("katalog.bezeichnung_fehlt")
    monate = _zahl(intervall_monate, "katalog.intervall_ungueltig", ganz=True, minimum=1)
    zaehler = _zahl(zaehler_intervall, "katalog.intervall_ungueltig", ganz=True, minimum=1) if zaehler_intervall.strip() else None
    if durchfuehrung not in m.DURCHFUEHRUNG:
        raise ValueError("katalog.durchfuehrung_unbekannt")
    tabelle = _je_merkmal(je_merkmal)
    zeilen_gruppen = {g.schluessel: g for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    if any(g not in zeilen_gruppen for g in gruppen):
        raise ValueError("katalog.gruppe_unbekannt")
    zeile = db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid, m.Pruefart.schluessel == schluessel)).scalar_one_or_none()
    if zeile is None:
        zeile = m.Pruefart(mandant_id=mid, schluessel=schluessel, bezeichnung=bezeichnung.strip(), intervall_monate=monate,
                           zaehler_intervall=zaehler, rechtsgrund=rechtsgrund.strip(), durchfuehrung=durchfuehrung,
                           intervall_je_merkmal=tabelle, aktiv=aktiv)
        db.add(zeile)
        _protokoll(sitzung, "pruefart_angelegt", "pruefart", None, schluessel)
    else:
        alt = f"{zeile.intervall_monate}/{zeile.zaehler_intervall}/{zeile.aktiv}"
        zeile.bezeichnung, zeile.intervall_monate, zeile.zaehler_intervall = bezeichnung.strip(), monate, zaehler
        zeile.rechtsgrund, zeile.durchfuehrung, zeile.intervall_je_merkmal, zeile.aktiv = rechtsgrund.strip(), durchfuehrung, tabelle, aktiv
        _protokoll(sitzung, "pruefart_geaendert", "pruefart", alt, f"{monate}/{zaehler}/{aktiv}")
    db.flush()
    zugeordnet = {int(z.gruppe_id): z for z in db.execute(select(m.GruppePruefart).where(
        m.GruppePruefart.mandant_id == mid, m.GruppePruefart.pruefart_id == zeile.id)).scalars()}
    eigene_intervalle = gruppen_intervall or {}
    for gruppen_schluessel, g in zeilen_gruppen.items():
        z = zugeordnet.get(int(g.id))
        soll = gruppen_schluessel in gruppen
        text = eigene_intervalle.get(gruppen_schluessel, "").strip()
        # je Gruppe darf das Intervall des Katalogs überschrieben werden; leer = das Intervall der Prüfart gilt
        gruppen_monate = _zahl(text, "katalog.intervall_ungueltig", ganz=True, minimum=1) if text and soll else None
        if z is None and soll:
            db.add(m.GruppePruefart(mandant_id=mid, gruppe_id=g.id, pruefart_id=zeile.id, intervall_monate=gruppen_monate, aktiv=True))
        elif z is not None:
            z.aktiv = soll
            if gruppen_intervall is not None and soll:
                z.intervall_monate = gruppen_monate
    db.flush()
    return zeile


# ---- Bauteile -----------------------------------------------------------------------------------------------------

def bauteil_speichern(sitzung: Any, bauteilnummer: str, bezeichnung: str, hersteller: str = "", preis: str = "", hinweis: str = "",
                      aktiv: bool = True, lieferant_id: int | None = None) -> m.Bauteil:
    _fordern(sitzung, "pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    nummer = bauteilnummer.strip()
    if not nummer:
        raise ValueError("katalog.bauteilnummer_fehlt")
    if not bezeichnung.strip():
        raise ValueError("katalog.bezeichnung_fehlt")
    wert = _zahl(preis, "katalog.preis_ungueltig") if preis.strip() else None
    zeile = db.execute(select(m.Bauteil).where(m.Bauteil.mandant_id == mid, m.Bauteil.bauteilnummer == nummer)).scalar_one_or_none()
    if zeile is None:
        zeile = m.Bauteil(mandant_id=mid, bauteilnummer=nummer, bezeichnung=bezeichnung.strip(), hersteller=hersteller.strip(),
                          preis_zuletzt=wert, hinweis=hinweis.strip(), aktiv=aktiv, lieferant_id=lieferant_id)
        db.add(zeile)
        _protokoll(sitzung, "bauteil_angelegt", "bauteil", None, nummer)
    else:
        alt = f"{zeile.bezeichnung}/{zeile.preis_zuletzt}/{zeile.aktiv}"
        zeile.bezeichnung, zeile.hersteller, zeile.preis_zuletzt = bezeichnung.strip(), hersteller.strip(), wert
        zeile.hinweis, zeile.aktiv, zeile.lieferant_id = hinweis.strip(), aktiv, lieferant_id
        _protokoll(sitzung, "bauteil_geaendert", "bauteil", alt, f"{zeile.bezeichnung}/{wert}/{aktiv}")
    db.flush()
    return zeile


# ---- Kostensätze --------------------------------------------------------------------------------------------------

def kostensatz_speichern(sitzung: Any, gruppe: str, nutzungsdauer_monate: str, zins_prozent: str, reparatur_prozent_jahr: str,
                         restwert_prozent: str = "", satz_monat: str = "", satz_tag: str = "", satz_woche: str = "",
                         satz_stunde: str = "", gueltig_ab: dt.date | None = None) -> m.Kostensatz:
    """Ein neuer Satz mit Gültigkeitsbeginn; der alte bleibt stehen (Verlauf). Quelle `manuell`."""
    _fordern(sitzung, "kosten_pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    zeile_gruppe = db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid, m.Gruppe.schluessel == gruppe)).scalar_one_or_none()
    if zeile_gruppe is None:
        raise ValueError("katalog.gruppe_unbekannt")
    ab = gueltig_ab or zeit.heute()

    def betrag(text: str) -> Decimal | None:
        return _zahl(text, "katalog.preis_ungueltig") if text.strip() else None  # type: ignore[return-value]

    satz = m.Kostensatz(
        mandant_id=mid, gruppe_id=zeile_gruppe.id, gueltig_ab=ab,
        nutzungsdauer_monate=_zahl(nutzungsdauer_monate, "katalog.intervall_ungueltig", ganz=True, minimum=1),
        zins_prozent=_zahl(zins_prozent, "katalog.prozent_ungueltig"),
        reparatur_prozent_jahr=_zahl(reparatur_prozent_jahr, "katalog.prozent_ungueltig"),
        restwert_prozent=betrag(restwert_prozent), satz_monat=betrag(satz_monat), satz_tag=betrag(satz_tag),
        satz_woche=betrag(satz_woche), satz_stunde=betrag(satz_stunde), quelle="manuell", angelegt_von=_benutzer(sitzung))
    if db.execute(select(m.Kostensatz.id).where(m.Kostensatz.mandant_id == mid, m.Kostensatz.gruppe_id == zeile_gruppe.id,
                                                m.Kostensatz.gueltig_ab == ab)).first():
        raise ValueError("katalog.satz_gibt_es")
    db.add(satz)
    db.flush()
    _protokoll(sitzung, "kostensatz_angelegt", "kostensatz", None, f"{gruppe} ab {ab}")
    return satz


# ---- Einstellungen ------------------------------------------------------------------------------------------------

def einstellungen_speichern(sitzung: Any, werte: dict[str, str]) -> list[str]:
    """Setzt die übergebenen Einstellungen; liefert die Schlüssel, die sich geändert haben."""
    _fordern(sitzung)
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    geaendert: list[str] = []
    for schluessel, wert in werte.items():
        wert = wert.strip()
        if schluessel in EINSTELLUNGEN_ZAHL:
            _zahl(wert, "katalog.zahl_ungueltig", ganz=True)
        elif schluessel == "nummernmuster":
            if pruefe_muster(wert):
                raise ValueError("katalog.muster_ungueltig")
        elif schluessel == "zins_prozent":
            _zahl(wert, "katalog.prozent_ungueltig")
        elif schluessel == "erinnern_um":
            try:
                zeitplan.uhrzeit(wert)
            except ValueError as ursache:
                raise ValueError("katalog.uhrzeit_ungueltig") from ursache
        elif schluessel == "auslieferung_am" and wert:
            try:
                dt.date.fromisoformat(wert)
            except ValueError as ursache:
                raise ValueError("katalog.datum_ungueltig") from ursache
        elif schluessel not in EINSTELLUNGEN_TEXT:
            raise ValueError("katalog.einstellung_unbekannt")
        alt = katalog.einstellung(db, mid, schluessel)
        if schluessel == "auslieferung_am" and alt and not wert:
            raise ValueError("katalog.auslieferung_bleibt")  # die Auslieferung nimmt niemand zurück
        if alt != wert:
            katalog.setze_einstellung(db, mid, schluessel, wert, _benutzer(sitzung))
            _protokoll(sitzung, "einstellung_geaendert", "einstellung", f"{schluessel}={alt}", f"{schluessel}={wert}")
            geaendert.append(schluessel)
    return geaendert
