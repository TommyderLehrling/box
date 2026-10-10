"""Excel-Import: Datei lesen und prüfen → planen → anlegen (idempotent über die Inventarnummer, Quelle `import`)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Lieferant, protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein import import_plan, import_vorlage
from ..rein.import_vorlage import ImportZeile, Leseergebnis
from ..rein.nummernformat import normalisiere
from . import katalog, nummer as nummernvergabe, stueck


@dataclass(frozen=True)
class Bericht:
    lesen: Leseergebnis
    plan: import_plan.Plan | None
    angelegt: int = 0
    lieferanten_unbekannt: tuple[str, ...] = ()  # Namen, die der Kern nicht kennt: es wird kein Lieferant angelegt
    ohne_recht: tuple[str, ...] = ()  # "<Nummer> (<Kostenstelle>)": Zeilen auf einer Kostenstelle ohne `pflegen`, nicht angelegt
    kaufdaten_uebersprungen: int = 0  # Zeilen mit Kaufpreis/-datum, die ohne `kosten_pflegen` nicht übernommen werden


def _vorhanden(db: Any, mid: int, gelesen: dict[str, ImportZeile], mit_kosten: bool = True) -> dict[str, ImportZeile]:
    gruppen = {int(g.id): g.schluessel for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    werte: dict[int, dict[str, str]] = {}
    for sid, schluessel, wert in db.execute(select(m.StueckMerkmal.stueck_id, m.Merkmal.schluessel, m.StueckMerkmal.wert)
                                            .join(m.Merkmal, m.Merkmal.id == m.StueckMerkmal.merkmal_id)
                                            .where(m.StueckMerkmal.mandant_id == mid)):
        werte.setdefault(int(sid), {})[schluessel] = wert
    lieferanten = {int(k.id): k.name_gedruckt for k in db.execute(select(Lieferant).where(Lieferant.mandant_id == mid)).scalars()}
    ergebnis = {}
    for s in db.execute(select(m.Stueck).where(m.Stueck.mandant_id == mid)).scalars():
        ergebnis[s.inventarnummer] = ImportZeile(
            0, s.inventarnummer, s.bezeichnung, gruppen[int(s.gruppe_id)], s.art, s.hersteller, s.typ, s.seriennummer,
            s.baujahr, s.kaufdatum if mit_kosten else None, s.kaufpreis if mit_kosten else None,
            lieferanten.get(int(s.lieferant_id), "") if s.lieferant_id else _gelesen_lieferant(gelesen, s.inventarnummer),
            0, 1, s.besonderheiten, werte.get(int(s.id), {}))
    return ergebnis


def _gelesen_lieferant(gelesen: dict[str, ImportZeile], nummer: str) -> str:
    """Ohne Lieferant am Stück (Name dem Kern unbekannt) gilt der Name der Datei — sonst wäre jede Zeile „abweichend“."""
    zeile = gelesen.get(normalisiere(nummer))
    return "" if zeile is None else zeile.lieferant


def _unbekannt(db: Any, mid: int, zeilen: tuple[ImportZeile, ...]) -> tuple[str, ...]:
    bekannt = set()
    for k in db.execute(select(Lieferant).where(Lieferant.mandant_id == mid)).scalars():
        bekannt |= {k.name_gedruckt.casefold(), (k.kurzname or "").casefold()}
    return tuple(sorted({z.lieferant for z in zeilen if z.lieferant.strip() and z.lieferant.casefold() not in bekannt}))


def pruefen(sitzung: Any, pfad: Path) -> Leseergebnis:
    """Liest die Datei gegen die Kataloge und Kostenstellen dieses Mandanten; Fehler stehen je Zeile im Ergebnis."""
    if not sitzung.darf("inventar", "pflegen"):
        raise gemeinsam.KeinRecht("inventar", "pflegen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    return import_vorlage.lies_mit_hinweisen(
        pfad, katalog.gruppen(db, mid), katalog.merkmale(db, mid), katalog.kostenstellen_nummern(sitzung), nummernvergabe.muster(db, mid),
        zeit.heute())


def bericht(sitzung: Any, pfad: Path) -> Bericht:
    """Prüfbericht und Plan, ohne etwas zu schreiben."""
    gelesen = pruefen(sitzung, pfad)
    if gelesen.fehler:
        return Bericht(gelesen, None)
    mid = sitzung.kontext.mandant_id
    mit_kosten = bool(sitzung.darf("inventar", "kosten_pflegen"))
    # Der Startstandort ist Stammpflege: `pflegen` auf der Kostenstelle der Zeile. Wo es fehlt, wird nicht angelegt (Abweichung im Bericht).
    kostenstellen = katalog.kostenstellen_nummern(sitzung)
    erlaubt = [z for z in gelesen.zeilen if sitzung.darf("inventar", "pflegen", kostenstellen[z.kostenstelle])]
    ohne_recht = tuple(f"{z.inventarnummer} ({z.kostenstelle})" for z in gelesen.zeilen if z not in erlaubt)
    # Kaufdaten nimmt der Import nur mit `kosten_pflegen` an; sonst bleiben sie außen vor (auch im Vergleich mit dem Bestand)
    uebersprungen = 0 if mit_kosten else sum(1 for z in erlaubt if z.kaufdatum is not None or z.kaufpreis is not None)
    zeilen = tuple(erlaubt) if mit_kosten else tuple(replace(z, kaufdatum=None, kaufpreis=None) for z in erlaubt)
    vorhanden = _vorhanden(sitzung.db, mid, {normalisiere(z.inventarnummer): z for z in zeilen}, mit_kosten)
    return Bericht(gelesen, import_plan.plane(zeilen, vorhanden), 0, _unbekannt(sitzung.db, mid, zeilen), ohne_recht, uebersprungen)


def einspielen(sitzung: Any, pfad: Path, quelle: str = "import") -> Bericht:
    """Legt an, was neu ist; was abweicht oder schon da ist, bleibt unberührt. Nur ohne Fehler in der Datei."""
    erg = bericht(sitzung, pfad)
    if erg.plan is None:
        raise ValueError("import_lauf.fehler_in_datei")
    return replace(erg, angelegt=anlegen(sitzung, erg.plan.neu, quelle))


def anlegen(sitzung: Any, zeilen: tuple[ImportZeile, ...] | list[ImportZeile], quelle: str = "import") -> int:
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    ks = katalog.kostenstellen_nummern(sitzung)
    lieferanten = {}
    for k in db.execute(select(Lieferant).where(Lieferant.mandant_id == mid)).scalars():
        lieferanten[k.name_gedruckt.casefold()] = int(k.id)
        if k.kurzname:
            lieferanten[k.kurzname.casefold()] = int(k.id)
    for z in zeilen:
        stueck.anlegen(
            sitzung, bezeichnung=z.bezeichnung, gruppe=z.gruppe, art=z.art, inventarnummer=z.inventarnummer, hersteller=z.hersteller,
            typ=z.typ, seriennummer=z.seriennummer, baujahr=z.baujahr, lieferant_id=lieferanten.get(z.lieferant.casefold()),
            kaufdatum=z.kaufdatum, kaufpreis=z.kaufpreis, kostenstelle_id=ks[z.kostenstelle], menge=z.menge, merkmale=z.merkmale,
            besonderheiten=z.besonderheiten, quelle=quelle, pruefen=False, protokollieren=False)
    if zeilen:
        protokoll.schreiben(db, mandant_id=mid, aktion="inventar.import", objekt_typ="inventar.import",
                            neu_wert=f"{len(zeilen)} Stück, Quelle {quelle}",
                            benutzer_id=None if sitzung.benutzer is None else int(sitzung.benutzer.id))
    return len(zeilen)
