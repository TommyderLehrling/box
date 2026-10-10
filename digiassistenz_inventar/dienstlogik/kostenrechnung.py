"""Kostenrechnung (G5): wirksame Sätze, Kosten je Stück, Vorhaltung je Kostenstelle, Miete gegen eigen und die CSV-Auszüge.

Kalkulatorisch nach der Logik der Baugeräteliste, **nicht steuerlich**: die steuerliche AfA kommt nicht vor, vorgehalten sind nur
`buchwert_extern` und `afa_hinweis` am Stück und der Auszug „Anlagenbuch“ mit den Kaufdaten.

Rechte: alles hier nur mit `kosten_sehen` — und nur auf den Kostenstellen, für die der Baustein gilt; ändern nur mit
`kosten_pflegen`. Poliere sehen keine Preise. Einsatzstunden aus der Baustelle und Rechnungen aus den Belegen gehören nicht hierher
(Dienste `maschinenstunden` und `rechnungen_zu_stueck`, nach AP-K2).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select

from digiassistenz_kern import Lieferant, Mandant, protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import dateien
from .. import modelle as m
from ..rein import kosten as rein_kosten
from ..rein import kostenexport
from ..rein import verrechnung as rein_verrechnung
from ..rein import werkstatt as rein_werkstatt
from ..rein.transfer import Standort as ReinStandort
from . import katalog, sicht
from .transfer import finde_stueck

OBJEKT_TYP = "inventar.stueck"
ZEILEN_HOECHSTENS = 500
_CENT = Decimal("0.01")


# ---- Einstellungen ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Rechenwerte:
    """Kalendertage (Standard, 30 je Monat) oder Werktage (Mo–Fr, einstellbar, z. B. 21,67 je Monat)."""

    tage_je_monat: Decimal
    werktage: bool


def dezimal_einstellung(text: str, standard: Decimal) -> Decimal:
    try:
        wert = Decimal(text.strip().replace(",", ".")) if text.strip() else standard
    except InvalidOperation:
        return standard
    return wert if wert >= 0 else standard


def rechenwerte(db: Any, mandant_id: int) -> Rechenwerte:
    werktage = dezimal_einstellung(katalog.einstellung(db, mandant_id, "werktage", "0"), Decimal(0))
    if werktage > 0:
        return Rechenwerte(werktage, True)
    tage = dezimal_einstellung(katalog.einstellung(db, mandant_id, "tage_je_monat", "30"), Decimal(30))
    return Rechenwerte(tage if tage > 0 else Decimal(30), False)


def _fordern(sitzung: Any, aktion: str) -> None:
    if not sitzung.darf("inventar", aktion):
        raise gemeinsam.KeinRecht("inventar", aktion)


def _benutzer(sitzung: Any) -> int | None:
    return None if sitzung.benutzer is None else int(sitzung.benutzer.id)


# ---- Wirksame Sätze -----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Satz:
    """Der Kostensatz, der für ein Stück gilt: seine eigene Zeile vor der der Gruppe (und der übergeordneten Gruppen)."""

    herkunft: str  # "stueck" | "gruppe" | "keiner"
    quelle: str  # gerechnet | manuell | bgl | vorschlag_box
    gueltig_ab: dt.date | None
    gerechnet_am: dt.datetime | None
    nutzungsdauer_monate: int | None
    zins_prozent: Decimal | None
    reparatur_prozent_jahr: Decimal | None
    restwert: Decimal | None
    restwert_prozent: Decimal | None
    kaufpreis: Decimal | None
    satz_monat: Decimal | None
    satz_tag: Decimal | None
    satz_woche: Decimal | None
    satz_stunde: Decimal | None
    von_hand: bool  # die Sätze stehen so in der Zeile (manuell, BGL) und werden nicht aus den Parametern gerechnet
    hinweis: str  # leer, `kaufpreis_fehlt` oder `preis_ungueltig`

    @property
    def vorhanden(self) -> bool:
        return self.satz_monat is not None


KEIN_SATZ = Satz("keiner", "gerechnet", None, None, None, None, None, None, None, None, None, None, None, None, False, "")


def _satz_aus_zeile(zeile: m.Kostensatz, herkunft: str, kaufpreis: Decimal | None, rw: Rechenwerte) -> Satz:
    basis = dict(herkunft=herkunft, quelle=zeile.quelle, gueltig_ab=zeile.gueltig_ab, gerechnet_am=zeile.angelegt_am,
                 nutzungsdauer_monate=int(zeile.nutzungsdauer_monate), zins_prozent=zeile.zins_prozent,
                 reparatur_prozent_jahr=zeile.reparatur_prozent_jahr, restwert_prozent=zeile.restwert_prozent, satz_stunde=zeile.satz_stunde)
    if zeile.satz_monat is not None:  # von Hand oder aus der BGL gesetzt: diese Sätze gelten, fehlende werden aus dem Monatssatz abgeleitet
        tag, woche = rein_kosten.satz_aus_monat(zeile.satz_monat, rw.tage_je_monat)
        return Satz(**basis, restwert=zeile.restwert, kaufpreis=kaufpreis, satz_monat=zeile.satz_monat,
                    satz_tag=zeile.satz_tag if zeile.satz_tag is not None else tag,
                    satz_woche=zeile.satz_woche if zeile.satz_woche is not None else woche, von_hand=True, hinweis="")
    if kaufpreis is None:
        return Satz(**basis, restwert=zeile.restwert, kaufpreis=None, satz_monat=None, satz_tag=None, satz_woche=None, von_hand=False,
                    hinweis="kaufpreis_fehlt")
    restwert = zeile.restwert if zeile.restwert is not None else (
        (kaufpreis * zeile.restwert_prozent / 100).quantize(_CENT) if zeile.restwert_prozent is not None else Decimal(0))
    try:
        s = rein_kosten.kostensatz(rein_kosten.Kostenparameter(
            kaufpreis, restwert, int(zeile.nutzungsdauer_monate), zeile.zins_prozent, zeile.reparatur_prozent_jahr, rw.tage_je_monat))
    except ValueError:
        return Satz(**basis, restwert=restwert, kaufpreis=kaufpreis, satz_monat=None, satz_tag=None, satz_woche=None, von_hand=False,
                    hinweis="preis_ungueltig")
    return Satz(**basis, restwert=restwert, kaufpreis=kaufpreis, satz_monat=s.satz_monat, satz_tag=s.satz_tag, satz_woche=s.satz_woche,
                von_hand=False, hinweis="")


def saetze_fuer(db: Any, mandant_id: int, stuecke: list[m.Stueck], heute: dt.date, rw: Rechenwerte) -> dict[int, Satz]:
    """Je Stück der wirksame Satz zum Stichtag: die eigene Zeile (jüngster Beginn bis heute), sonst die der Gruppe, sonst die darüber."""
    if not stuecke:
        return {}
    ids = [int(s.id) for s in stuecke]
    eigene: dict[int, m.Kostensatz] = {}
    for z in db.execute(select(m.Kostensatz).where(m.Kostensatz.mandant_id == mandant_id, m.Kostensatz.stueck_id.in_(ids),
                                                   m.Kostensatz.gueltig_ab <= heute).order_by(m.Kostensatz.gueltig_ab, m.Kostensatz.id)).scalars():
        eigene[int(z.stueck_id)] = z  # die spätere Zeile überschreibt die frühere im Wörterbuch
    je_gruppe: dict[int, m.Kostensatz] = {}
    for z in db.execute(select(m.Kostensatz).where(m.Kostensatz.mandant_id == mandant_id, m.Kostensatz.gruppe_id.is_not(None),
                                                   m.Kostensatz.gueltig_ab <= heute).order_by(m.Kostensatz.gueltig_ab, m.Kostensatz.id)).scalars():
        je_gruppe[int(z.gruppe_id)] = z
    oben = {int(g.id): (int(g.oben_id) if g.oben_id else None) for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    ergebnis: dict[int, Satz] = {}
    for s in stuecke:
        eigene_zeile = eigene.get(int(s.id))
        gruppe_id: int | None = int(s.gruppe_id)
        gruppen_zeile = None
        for _ in range(10):  # höchstens zehn Stufen nach oben (Schutz gegen Kreise)
            if gruppe_id is None:
                break
            gruppen_zeile = je_gruppe.get(gruppe_id)
            if gruppen_zeile is not None:
                break
            gruppe_id = oben.get(gruppe_id)
        zeile, herkunft = (eigene_zeile, "stueck") if eigene_zeile is not None else (gruppen_zeile, "gruppe")
        if zeile is None:
            ergebnis[int(s.id)] = KEIN_SATZ
            continue
        preis = zeile.kaufpreis_basis if eigene_zeile is not None and zeile.kaufpreis_basis is not None else s.kaufpreis
        if preis is None and zeile.kaufpreis_basis is not None:
            preis = zeile.kaufpreis_basis  # die Gruppe nennt einen Richtpreis für Stücke ohne eigenen
        ergebnis[int(s.id)] = _satz_aus_zeile(zeile, herkunft, preis, rw)
    return ergebnis


# ---- Kosten je Stück ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StueckKosten:
    id: int
    nummer: str
    bezeichnung: str
    gruppe: str
    kaufdatum: dt.date | None
    kaufpreis: Decimal | None
    satz: Satz
    kalkulatorisch: Decimal | None
    reparaturen_belegt: Decimal
    reparaturen_geschaetzt: Decimal
    gesamt: Decimal | None
    hat_zaehler: bool = False


def _rein_reparatur(z: m.Reparatur) -> rein_werkstatt.Reparatur:
    return rein_werkstatt.Reparatur(z.status, z.durchfuehrung, z.begonnen_am, z.beendet_am, z.kosten, z.kosten_quelle, z.grund)  # type: ignore[arg-type]


def stueck_kosten(db: Any, mandant_id: int, stuecke: list[m.Stueck], heute: dt.date, rw: Rechenwerte) -> list[StueckKosten]:
    """Kaufpreis, kalkulatorische Kosten bis heute (volle Monate seit Kauf × Monatssatz), Reparaturkosten nach Quelle, Gesamtkosten."""
    saetze = saetze_fuer(db, mandant_id, stuecke, heute, rw)
    ids = [int(s.id) for s in stuecke]
    reparaturen: dict[int, list[rein_werkstatt.Reparatur]] = {}
    if ids:
        for z in db.execute(select(m.Reparatur).where(m.Reparatur.mandant_id == mandant_id, m.Reparatur.stueck_id.in_(ids),
                                                      m.Reparatur.status == "erledigt")).scalars():
            reparaturen.setdefault(int(z.stueck_id), []).append(_rein_reparatur(z))
    gruppen = {int(g.id): g.bezeichnung for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mandant_id)).scalars()}
    ergebnis = []
    for s in stuecke:
        satz = saetze[int(s.id)]
        belegt, geschaetzt = rein_werkstatt.reparaturkosten(reparaturen.get(int(s.id), []))
        kalk = None
        if satz.satz_monat is not None and s.kaufdatum is not None and satz.nutzungsdauer_monate:
            kalk = rein_kosten.kalkulatorisch_aus_satz(satz.satz_monat, satz.nutzungsdauer_monate, s.kaufdatum, heute)
        gesamt = None if s.kaufpreis is None else rein_kosten.gesamtkosten(s.kaufpreis, [belegt, geschaetzt])
        ergebnis.append(StueckKosten(int(s.id), s.inventarnummer, s.bezeichnung, gruppen.get(int(s.gruppe_id), ""), s.kaufdatum, s.kaufpreis,
                                     satz, kalk, belegt, geschaetzt, gesamt, s.zaehler_einheit is not None))
    return ergebnis


def kosten_fuer_stueck(sitzung: Any, stueck: m.Stueck, heute: dt.date | None = None) -> StueckKosten:
    """Die Kosten eines einzelnen Stücks für die Stück-Seite (Aufrufer prüft `kosten_sehen`)."""
    heute = heute or zeit.heute()
    rw = rechenwerte(sitzung.db, sitzung.kontext.mandant_id)
    return stueck_kosten(sitzung.db, sitzung.kontext.mandant_id, [stueck], heute, rw)[0]


def stuecke_mit_filter(sitzung: Any, kostenstelle_nummer: str = "", gruppe: str = "", hoechstens: int = ZEILEN_HOECHSTENS) -> tuple[list[m.Stueck], int]:
    """Die Stücke, für die diese Sitzung Kosten sehen darf, nach Kostenstelle und Gruppe eingegrenzt; liefert auch die Gesamtzahl."""
    abfrage = sicht.stuecke(sitzung, "kosten_sehen")
    if gruppe:
        abfrage = abfrage.where(m.Stueck.gruppe_id.in_(select(m.Gruppe.id).where(
            m.Gruppe.mandant_id == sitzung.kontext.mandant_id, m.Gruppe.schluessel == gruppe)))
    if kostenstelle_nummer:
        from digiassistenz_kern import Kostenstelle

        ks = sitzung.db.execute(sitzung.abfrage(Kostenstelle).where(Kostenstelle.nummer == kostenstelle_nummer)).scalars().first()
        abfrage = abfrage.where(m.Stueck.id.in_(select(m.Standort.stueck_id).where(
            m.Standort.bis.is_(None), m.Standort.kostenstelle_id == (-1 if ks is None else ks.id))))
    gesamt = int(sitzung.db.execute(abfrage.with_only_columns(func.count())).scalar_one())
    return list(sitzung.db.execute(abfrage.order_by(m.Stueck.inventarnummer).limit(hoechstens)).scalars()), gesamt


# ---- Vorhaltung je Kostenstelle -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class KostenstellenKosten:
    verrechnung: rein_verrechnung.Verrechnung
    namen: dict[int, str]
    bezeichnungen: dict[str, str]  # Inventarnummer → Bezeichnung
    ohne_satz: int  # Stücke, die im Zeitraum standen, aber keinen Kostensatz haben


def _lokal(zeitpunkt: dt.datetime | None) -> dt.datetime | None:
    return None if zeitpunkt is None else zeit.als_ortszeit(zeitpunkt)


def vorhaltung_je_kostenstelle(sitzung: Any, von: dt.date, bis: dt.date) -> KostenstellenKosten:
    """Σ Standorttage × Tagessatz × Menge je Kostenstelle im Zeitraum — nur was dort `vor_ort` stand, nur Kostenstellen mit `kosten_sehen`.

    Ein Teil-Eingang rechnet richtig, weil jede Menge ihre eigene Standortzeile hat: was unterwegs ist, steht nirgends vor Ort.
    """
    if bis < von:
        raise ValueError("kosten.zeitraum_ungueltig")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    tz = zeit.zeitzone()
    anfang = dt.datetime.combine(von, dt.time.min, tzinfo=tz)
    ende = dt.datetime.combine(bis + dt.timedelta(days=1), dt.time.min, tzinfo=tz)
    erlaubt = sicht.erlaubte_kostenstellen(sitzung, "kosten_sehen")
    abfrage = select(m.Standort).where(m.Standort.mandant_id == mid, m.Standort.von < ende, or_(m.Standort.bis.is_(None), m.Standort.bis >= anfang))
    if erlaubt is not None:
        abfrage = abfrage.where(m.Standort.kostenstelle_id.in_(erlaubt))
    zeilen = list(db.execute(abfrage.order_by(m.Standort.id)).scalars())
    stueck_ids = {int(z.stueck_id) for z in zeilen}
    stuecke = {int(s.id): s for s in db.execute(select(m.Stueck).where(m.Stueck.id.in_(stueck_ids))).scalars()} if stueck_ids else {}
    rw = rechenwerte(db, mid)
    saetze = saetze_fuer(db, mid, list(stuecke.values()), bis, rw)
    gruppen = {int(g.id): g.schluessel for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    standorte: dict[int, list[ReinStandort]] = {}
    for z in zeilen:
        s = stuecke[int(z.stueck_id)]
        standorte.setdefault(int(z.stueck_id), []).append(ReinStandort(
            s.inventarnummer, int(z.kostenstelle_id), int(z.menge), _lokal(z.von), _lokal(z.bis), None, z.quelle, str(z.von_person or "")))  # type: ignore[arg-type]
    rechnen, ohne = [], 0
    for sid, orte in standorte.items():
        s, satz = stuecke[sid], saetze[sid]
        if satz.satz_tag is None:
            ohne += 1
            continue
        rechnen.append(rein_verrechnung.VerrechnungsStueck(s.inventarnummer, gruppen[int(s.gruppe_id)], satz.satz_tag, satz.satz_stunde, tuple(orte)))
    erg = rein_verrechnung.verrechne(rechnen, [], von, bis, werktage=rw.werktage)
    namen = sicht.kostenstellen_namen(sitzung, {z.kostenstelle for z in erg.zeilen})
    return KostenstellenKosten(erg, namen, {s.inventarnummer: s.bezeichnung for s in stuecke.values()}, ohne)


# ---- Miete gegen eigen --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class MieteErgebnis:
    zeilen: tuple[rein_verrechnung.MieteGegenEigen, ...]
    bezeichnungen: dict[str, str]
    unvollstaendig: int  # Mietstücke ohne Zeitraum oder Mietkosten
    eigene: tuple[str, ...]  # Nummern der eigenen Stücke, die als Vergleich wählbar sind


def miete_gegen_eigen(sitzung: Any, von: dt.date, bis: dt.date, vergleich: str = "") -> MieteErgebnis:
    """Mietkosten (von Hand je Zeitraum) gegen den Tagessatz eines eigenen Stücks derselben Gruppe × Miettage."""
    if bis < von:
        raise ValueError("kosten.zeitraum_ungueltig")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    alle = list(db.execute(sicht.stuecke(sitzung, "kosten_sehen").where(m.Stueck.status.notin_(("verkauft", "verschrottet", "stillgelegt")))
                           .order_by(m.Stueck.inventarnummer)).scalars())
    rw = rechenwerte(db, mid)
    saetze = saetze_fuer(db, mid, alle, bis, rw)
    gruppen = {int(g.id): g.schluessel for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    vs, unvollstaendig, eigene = [], 0, []
    for s in alle:
        satz = saetze[int(s.id)]
        schluessel = gruppen[int(s.gruppe_id)]
        if s.miete:
            if s.miet_von is None or s.miet_bis is None or s.mietkosten is None:
                unvollstaendig += 1
                continue
            vs.append(rein_verrechnung.VerrechnungsStueck(s.inventarnummer, schluessel, Decimal(0), None, (), True, s.miet_von, s.miet_bis, s.mietkosten))
        elif satz.satz_tag is not None:
            vs.append(rein_verrechnung.VerrechnungsStueck(s.inventarnummer, schluessel, satz.satz_tag, satz.satz_stunde, ()))
            eigene.append(s.inventarnummer)
    zeilen = rein_verrechnung.miete_gegen_eigen(vs, von, bis, rw.werktage, vergleichsstueck=vergleich or None)
    return MieteErgebnis(zeilen, {s.inventarnummer: s.bezeichnung for s in alle}, unvollstaendig, tuple(eigene))


# ---- Sätze und Miete ändern (kosten_pflegen) ----------------------------------------------------------------------

def _betrag(text: str, fehler: str = "katalog.preis_ungueltig") -> Decimal | None:
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        wert = Decimal(text)
    except InvalidOperation:
        raise ValueError(fehler) from None
    if wert < 0:
        raise ValueError(fehler)
    return wert


def stueck_satz_speichern(
    sitzung: Any, inventarnummer: str, nutzungsdauer_monate: str, zins_prozent: str, reparatur_prozent_jahr: str, restwert: str = "",
    restwert_prozent: str = "", kaufpreis_basis: str = "", satz_monat: str = "", satz_tag: str = "", satz_woche: str = "",
    satz_stunde: str = "", gueltig_ab: dt.date | None = None,
) -> m.Kostensatz:
    """Überschreibt den Satz für **dieses** Stück (neue Zeile ab einem Datum; die alte bleibt als Verlauf stehen).

    Ohne Monatssatz rechnet die Seite aus den Parametern (Quelle `gerechnet`); mit einem von Hand gesetzten Satz gilt dieser (`manuell`).
    """
    _fordern(sitzung, "kosten_pflegen")
    zeile = finde_stueck(sitzung, inventarnummer, "kosten_pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    ab = gueltig_ab or zeit.heute()

    def ganz(text: str, fehler: str, minimum: int) -> int:
        try:
            wert = int(text.strip())
        except ValueError:
            raise ValueError(fehler) from None
        if wert < minimum:
            raise ValueError(fehler)
        return wert

    von_hand = any(x.strip() for x in (satz_monat, satz_tag, satz_woche))
    satz = m.Kostensatz(
        mandant_id=mid, stueck_id=zeile.id, gueltig_ab=ab, kaufpreis_basis=_betrag(kaufpreis_basis),
        nutzungsdauer_monate=ganz(nutzungsdauer_monate, "katalog.intervall_ungueltig", 1),
        zins_prozent=_betrag(zins_prozent or "0", "katalog.prozent_ungueltig"),
        reparatur_prozent_jahr=_betrag(reparatur_prozent_jahr or "0", "katalog.prozent_ungueltig"),
        restwert=_betrag(restwert), restwert_prozent=_betrag(restwert_prozent, "katalog.prozent_ungueltig"),
        satz_monat=_betrag(satz_monat), satz_tag=_betrag(satz_tag), satz_woche=_betrag(satz_woche), satz_stunde=_betrag(satz_stunde),
        quelle="manuell" if von_hand else "gerechnet", angelegt_von=_benutzer(sitzung))
    if (satz.satz_tag is not None or satz.satz_woche is not None) and satz.satz_monat is None:
        raise ValueError("kosten.monatssatz_fehlt")
    if db.execute(select(m.Kostensatz.id).where(m.Kostensatz.mandant_id == mid, m.Kostensatz.stueck_id == zeile.id, m.Kostensatz.gueltig_ab == ab)).first():
        raise ValueError("katalog.satz_gibt_es")
    db.add(satz)
    db.flush()
    wirksam = saetze_fuer(db, mid, [zeile], ab, rechenwerte(db, mid))[int(zeile.id)]
    if wirksam.hinweis == "preis_ungueltig":
        raise ValueError("kosten.preis_ungueltig")  # z. B. Restwert über dem Kaufpreis: nichts wird gespeichert
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.kostensatz_stueck", objekt_typ=OBJEKT_TYP, objekt_id=int(zeile.id),
                        neu_wert=f"ab {ab}: {satz.quelle}", benutzer_id=_benutzer(sitzung))
    return satz


def miete_eintragen(
    sitzung: Any, inventarnummer: str, miete: bool, von: dt.date | None = None, bis: dt.date | None = None, mietkosten: Decimal | None = None,
) -> m.Stueck:
    """Ein Mietgerät: Zeitraum und Mietkosten von Hand. Ohne Haken bleiben die Angaben stehen, das Stück gilt nicht mehr als gemietet."""
    _fordern(sitzung, "kosten_pflegen")
    zeile = finde_stueck(sitzung, inventarnummer, "kosten_pflegen")
    if miete:
        if von is None or bis is None or mietkosten is None:
            raise ValueError("verrechnung.miete_unvollstaendig")
        if bis < von:
            raise ValueError("kosten.zeitraum_ungueltig")
        if mietkosten < 0:
            raise ValueError("kosten.preis_ungueltig")
        zeile.miet_von, zeile.miet_bis, zeile.mietkosten = von, bis, mietkosten
    zeile.miete = miete
    zeile.geaendert_am, zeile.geaendert_von = zeit.jetzt_utc(), _benutzer(sitzung)
    sitzung.db.flush()
    protokoll.schreiben(sitzung.db, mandant_id=sitzung.kontext.mandant_id, aktion="inventar.miete_geaendert", objekt_typ=OBJEKT_TYP,
                        objekt_id=int(zeile.id), neu_wert=f"{zeile.inventarnummer}: {von}..{bis} {mietkosten}" if miete else zeile.inventarnummer,
                        benutzer_id=_benutzer(sitzung))
    return zeile


# ---- CSV-Auszüge --------------------------------------------------------------------------------------------------

def _lieferanten(db: Any, mid: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {int(z.id): (z.kurzname or z.name_gedruckt) for z in db.execute(select(Lieferant).where(Lieferant.mandant_id == mid, Lieferant.id.in_(ids))).scalars()}


def zeilen_fuer_export(sitzung: Any, block: str, von: dt.date, bis: dt.date, kostenstelle: str = "", gruppe: str = "", vergleich: str = "") -> list[tuple[object, ...]]:
    """Die Zeilen eines Blocks für die CSV — dieselben Rechnungen wie auf der Seite, dieselben Rechte."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    if block == "kostenstelle":
        k = vorhaltung_je_kostenstelle(sitzung, von, bis)
        return [(k.namen.get(z.kostenstelle, str(z.kostenstelle)), z.inventarnummer, z.tage, z.betrag_vorhaltung) for z in k.verrechnung.zeilen]
    if block == "miete":
        r = miete_gegen_eigen(sitzung, von, bis, vergleich)
        return [(z.inventarnummer, z.gruppe, z.tage, z.miete, z.eigen, z.differenz) for z in r.zeilen]
    stuecke, _gesamt = stuecke_mit_filter(sitzung, kostenstelle, gruppe, hoechstens=100000)
    if block == "stueck":
        rw = rechenwerte(db, mid)
        return [(k.nummer, k.bezeichnung, k.gruppe, k.kaufdatum, k.kaufpreis, k.satz.satz_tag, k.satz.satz_monat, k.kalkulatorisch,
                 k.reparaturen_belegt, k.reparaturen_geschaetzt, k.gesamt, k.satz.quelle if k.satz.vorhanden else "")
                for k in stueck_kosten(db, mid, stuecke, zeit.heute(), rw)]
    if block == "anlagenbuch":
        gruppen = {int(g.id): g.bezeichnung for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
        firmen = _lieferanten(db, mid, {int(s.lieferant_id) for s in stuecke if s.lieferant_id})
        return [(s.inventarnummer, s.bezeichnung, gruppen.get(int(s.gruppe_id), ""), s.kaufdatum, s.kaufpreis,
                 firmen.get(int(s.lieferant_id), "") if s.lieferant_id else "", s.buchwert_extern, s.afa_hinweis or "") for s in stuecke]
    raise ValueError("kosten.block_unbekannt")


def schreibe_csv(sitzung: Any, block: str, zeilen: list[tuple[object, ...]], arbeitsordner: Path) -> Path:
    """Legt die CSV unter `export/` ab: Name mit Zeitstempel, nichts wird überschrieben (ein Zähler im Namen, wenn es ihn schon gibt)."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    text = kostenexport.csv_text(block, zeilen)
    ordnername = db.execute(select(Mandant.ordnername).where(Mandant.id == mid)).scalar_one()
    ziel, summe = dateien.speichern(dateien.exportordner(arbeitsordner, ordnername), kostenexport.dateiname(block, zeit.jetzt_ortszeit()),
                                    text.encode("utf-8-sig"))
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.kosten_export", objekt_typ=None, neu_wert=f"{ziel.relative_to(arbeitsordner)} {summe[:12]}",
                        benutzer_id=_benutzer(sitzung))
    return ziel


def exportieren(sitzung: Any, block: str, von: dt.date, bis: dt.date, arbeitsordner: Path, kostenstelle: str = "", gruppe: str = "",
                vergleich: str = "") -> Path:
    """Rechnet den Block und schreibt die Datei — Recht `kosten_sehen`."""
    _fordern(sitzung, "kosten_sehen")
    if block not in kostenexport.BLOECKE:
        raise ValueError("kosten.block_unbekannt")
    return schreibe_csv(sitzung, block, zeilen_fuer_export(sitzung, block, von, bis, kostenstelle, gruppe, vergleich), arbeitsordner)


def exportierte_dateien(sitzung: Any, arbeitsordner: Path, hoechstens: int = 20) -> list[str]:
    """Die jüngsten Dateien im Exportordner als Pfade relativ zum Arbeitsordner — jüngste zuerst."""
    ordnername = sitzung.db.execute(select(Mandant.ordnername).where(Mandant.id == sitzung.kontext.mandant_id)).scalar_one()
    ordner = dateien.exportordner(arbeitsordner, ordnername)
    if not ordner.is_dir():
        return []
    dateien_liste = sorted((p for p in ordner.iterdir() if p.is_file()), key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return [str(p.relative_to(arbeitsordner)) for p in dateien_liste[:hoechstens]]
