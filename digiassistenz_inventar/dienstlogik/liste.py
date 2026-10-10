"""Die Inventarliste: Filter, Suche, Sortierung, Seiten und der Ordner (Gruppe › Kostenstelle) — alles im Umfang der Sitzung."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, func, or_, select

from digiassistenz_kern import Kostenstelle, zeit

from .. import modelle as m
from ..rein.pruefung import gesamt_ampel
from . import pruefstand, sicht

GROESSE_SEITE = 100
AB_ZEILEN = 200  # bis dahin steht alles auf einer Seite
HOECHSTENS = 5000  # Ordner und „nur fällig“ lesen höchstens so viele Stücke
SORTIERBAR = ("nummer", "bezeichnung", "gruppe", "status")
AMPEL_ZEICHEN = {"gruen": "✓", "gelb": "⚠", "rot": "✗", "unbekannt": "◌"}


@dataclass(frozen=True)
class Filter:
    q: str = ""
    status: str = ""
    gruppe: str = ""  # Schlüssel der Gruppe
    kostenstelle: str = ""  # Nummer der Kostenstelle
    angekuendigt: bool = False
    faellig: bool = False

    def als_weg(self) -> str:
        from urllib.parse import urlencode

        werte = {"q": self.q, "status": self.status, "gruppe": self.gruppe, "kostenstelle": self.kostenstelle}
        werte = {k: v for k, v in werte.items() if v}
        if self.angekuendigt:
            werte["angekuendigt"] = "1"
        if self.faellig:
            werte["faellig"] = "1"
        return urlencode(werte)


@dataclass(frozen=True)
class Seite:
    zeilen: list[dict[str, Any]]
    gesamt: int
    nummer: int
    letzte: int
    groesse: int = GROESSE_SEITE


@dataclass
class Knoten:
    """Ein Ordnerzweig: Gruppe → Kostenstelle → Stücke."""

    titel: str
    anzahl: int = 0
    kinder: list[Knoten] = field(default_factory=list)
    stuecke: list[dict[str, Any]] = field(default_factory=list)


def kostenstelle_id(sitzung: Any, nummer: str) -> int | None:
    """Die Id zu einer Kostenstellen-Nummer — nur im Umfang der Sitzung."""
    if not nummer:
        return None
    zeile = sitzung.db.execute(sitzung.abfrage(Kostenstelle).where(Kostenstelle.nummer == nummer)).scalars().first()
    return None if zeile is None else int(zeile.id)


def _escape(wort: str) -> str:
    return "%" + wort.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _abfrage(sitzung: Any, f: Filter) -> Select[Any]:
    abfrage = sicht.stuecke(sitzung)
    wort = " ".join(f.q.split())
    if wort:
        muster = _escape(wort)
        kennzeichen = select(m.StueckMerkmal.stueck_id).join(m.Merkmal, m.Merkmal.id == m.StueckMerkmal.merkmal_id).where(
            m.Merkmal.schluessel == "kennzeichen", m.StueckMerkmal.wert.ilike(muster, escape="\\"))
        ort = select(m.Standort.stueck_id).join(Kostenstelle, Kostenstelle.id == m.Standort.kostenstelle_id).where(
            m.Standort.bis.is_(None),
            or_(Kostenstelle.nummer.ilike(muster, escape="\\"), Kostenstelle.bezeichnung.ilike(muster, escape="\\"),
                Kostenstelle.ort.ilike(muster, escape="\\")))
        abfrage = abfrage.where(or_(
            m.Stueck.inventarnummer.ilike(muster, escape="\\"), m.Stueck.bezeichnung.ilike(muster, escape="\\"),
            m.Stueck.seriennummer.ilike(muster, escape="\\"), m.Stueck.id.in_(kennzeichen), m.Stueck.id.in_(ort)))
    if f.status in m.STATUS:
        abfrage = abfrage.where(m.Stueck.status == f.status)
    if f.gruppe:
        abfrage = abfrage.where(m.Stueck.gruppe_id.in_(select(m.Gruppe.id).where(
            m.Gruppe.mandant_id == sitzung.kontext.mandant_id, m.Gruppe.schluessel == f.gruppe)))
    if f.kostenstelle:
        ks = kostenstelle_id(sitzung, f.kostenstelle)
        steht = select(m.Standort.stueck_id).where(m.Standort.bis.is_(None), m.Standort.kostenstelle_id == ks)
        kommt = select(m.Transfer.stueck_id).where(m.Transfer.status == "angekuendigt", m.Transfer.nach_kostenstelle_id == ks)
        abfrage = abfrage.where(or_(m.Stueck.id.in_(steht), m.Stueck.id.in_(kommt)))
    if f.angekuendigt:
        abfrage = abfrage.where(m.Stueck.id.in_(select(m.Transfer.stueck_id).where(
            m.Transfer.mandant_id == sitzung.kontext.mandant_id, m.Transfer.status == "angekuendigt")))
    return abfrage


def _ordnung(abfrage: Select[Any], sortieren: str, absteigend: bool) -> Select[Any]:
    if sortieren == "gruppe":
        abfrage = abfrage.join(m.Gruppe, m.Gruppe.id == m.Stueck.gruppe_id)
        spalte = m.Gruppe.bezeichnung
    else:
        spalte = {"bezeichnung": m.Stueck.bezeichnung, "status": m.Stueck.status}.get(sortieren, m.Stueck.inventarnummer)
    return abfrage.order_by(spalte.desc() if absteigend else spalte.asc(), m.Stueck.inventarnummer)


def zeilen_fuer(sitzung: Any, stuecke: list[m.Stueck]) -> list[dict[str, Any]]:
    """Die Anzeigezeilen für diese Stücke: Ort, seit, Ampel — jeweils mit wenigen Abfragen für alle."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    if not stuecke:
        return []
    ids = [int(s.id) for s in stuecke]
    gruppen = {int(g.id): g.bezeichnung for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    orte = sicht.standorte_offen(sitzung, ids)
    kommt = sicht.transfers_angekuendigt(sitzung, ids)
    namen = sicht.kostenstellen_namen(
        sitzung, {k for liste in orte.values() for k, _ in liste} | {int(t.nach_kostenstelle_id) for liste in kommt.values() for t in liste})
    staende = pruefstand.staende(db, mid, stuecke, zeit.heute())
    ergebnis = []
    for s in stuecke:
        sid = int(s.id)
        offen = orte.get(sid, [])
        angekuendigt = [namen.get(int(t.nach_kostenstelle_id), "") for t in kommt.get(sid, [])]
        ampel = gesamt_ampel(staende.get(s.inventarnummer, []))
        ergebnis.append({
            "id": sid, "nummer": s.inventarnummer, "bezeichnung": s.bezeichnung, "gruppe": gruppen.get(int(s.gruppe_id), ""),
            "steht_auf": ", ".join(namen.get(k, "") for k, _ in offen), "seit": min((o.von for _, o in offen), default=None),
            "angekuendigt_auf": ", ".join(a for a in angekuendigt if a), "status": s.status, "ampel": ampel,
            "ampel_zeichen": AMPEL_ZEICHEN[ampel],
        })
    return ergebnis


def seite(sitzung: Any, f: Filter, sortieren: str = "nummer", absteigend: bool = False, nummer: int = 1) -> Seite:
    """Eine Seite der Liste; bis 200 Treffer steht alles auf einer Seite, darüber 100 je Seite."""
    db = sitzung.db
    basis = _abfrage(sitzung, f)
    if f.faellig:
        alle = list(db.execute(_ordnung(basis, sortieren, absteigend).limit(HOECHSTENS)).scalars())
        staende = pruefstand.staende(db, sitzung.kontext.mandant_id, alle, zeit.heute())
        treffer = [s for s in alle if gesamt_ampel(staende.get(s.inventarnummer, [])) in ("rot", "gelb")]
        gesamt = len(treffer)
        groesse = GROESSE_SEITE if gesamt > AB_ZEILEN else max(gesamt, 1)
        nummer = min(max(nummer, 1), max(-(-gesamt // groesse), 1))
        return Seite(zeilen_fuer(sitzung, treffer[(nummer - 1) * groesse: nummer * groesse]), gesamt, nummer, max(-(-gesamt // groesse), 1), groesse)
    gesamt = int(db.execute(select(func.count()).select_from(basis.order_by(None).subquery())).scalar_one())
    groesse = GROESSE_SEITE if gesamt > AB_ZEILEN else max(gesamt, 1)
    letzte = max(-(-gesamt // groesse), 1)
    nummer = min(max(nummer, 1), letzte)
    stuecke = list(db.execute(_ordnung(basis, sortieren, absteigend).offset((nummer - 1) * groesse).limit(groesse)).scalars())
    return Seite(zeilen_fuer(sitzung, stuecke), gesamt, nummer, letzte, groesse)


def ordner(sitzung: Any, f: Filter) -> list[Knoten]:
    """Gruppe › Kostenstelle, Zähler je Knoten; ein Stück steht dort, wo es offen steht (sonst unter „angekündigt“)."""
    stuecke = list(sitzung.db.execute(_ordnung(_abfrage(sitzung, f), "nummer", False).limit(HOECHSTENS)).scalars())
    zeilen = zeilen_fuer(sitzung, stuecke)
    orte = sicht.standorte_offen(sitzung, [z["id"] for z in zeilen])
    namen = sicht.kostenstellen_namen(sitzung, {k for liste in orte.values() for k, _ in liste})
    baum: dict[str, dict[str, Knoten]] = {}
    for z in zeilen:
        ziele = [namen.get(k, "") for k, _ in orte.get(z["id"], [])] or [z["angekuendigt_auf"] or ""]
        for ziel in ziele:
            knoten = baum.setdefault(z["gruppe"], {}).setdefault(ziel, Knoten(ziel))
            knoten.stuecke.append(z)
            knoten.anzahl += 1
    ergebnis = []
    for gruppe, je_ks in sorted(baum.items()):
        kinder = sorted(je_ks.values(), key=lambda k: k.titel)
        ergebnis.append(Knoten(gruppe, sum(k.anzahl for k in kinder), kinder))
    return ergebnis


def gruppen_auswahl(sitzung: Any) -> list[tuple[str, str]]:
    zeilen = sitzung.db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == sitzung.kontext.mandant_id, m.Gruppe.aktiv)
                                .order_by(m.Gruppe.sortierung, m.Gruppe.bezeichnung)).scalars()
    return [(g.schluessel, g.bezeichnung) for g in zeilen]


def nummern(sitzung: Any, f: Filter, hoechstens: int = 2000) -> list[str]:
    """Die Inventarnummern der Auswahl, wie die Liste sie zeigt (für den Etikettenbogen)."""
    return list(sitzung.db.execute(_ordnung(_abfrage(sitzung, f), "nummer", False).with_only_columns(m.Stueck.inventarnummer)
                                   .limit(hoechstens)).scalars())
