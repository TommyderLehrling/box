"""Prüfung eintragen — mit Nachweis-Datei (SHA-256 im Datensatz, unveränderlich), Recht `pruefen` — und die Prüfarten je Stück."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Benutzer, Lieferant, Mandant, protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import dateien
from .. import modelle as m
from ..rein import pruefung as rein
from . import pruefstand as staende
from .stueck import _benutzer
from .transfer import finde_stueck


def _zuordnungen(sitzung: Any, stueck: m.Stueck) -> list[rein.Zuordnung]:
    return staende.zuordnungen(sitzung.db, sitzung.kontext.mandant_id, [stueck]).get(stueck.inventarnummer, [])


def _pruefart(sitzung: Any, schluessel: str) -> m.Pruefart:
    zeile = sitzung.db.execute(select(m.Pruefart).where(
        m.Pruefart.mandant_id == sitzung.kontext.mandant_id, m.Pruefart.schluessel == schluessel)).scalar_one_or_none()
    if zeile is None:
        raise ValueError("pruefung.pruefart_unbekannt")
    return zeile


def _pruefer_pruefen(sitzung: Any, durchfuehrung: str, pruefer_text: str, benutzer_id: int | None,
                     lieferant_id: int | None) -> tuple[str, int | None, int | None]:
    """Wer geprüft hat: intern der Benutzer (sonst der Eintragende), extern ein Lieferant oder ein Name."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    text = pruefer_text.strip()
    if durchfuehrung == "extern":
        benutzer_id = None
        if not text and lieferant_id is None:
            raise ValueError("pruefung.pruefer_fehlt")
    else:
        lieferant_id = None
        if not text and benutzer_id is None:
            benutzer_id = _benutzer(sitzung)
    if benutzer_id is not None and db.execute(sitzung.abfrage(Benutzer).where(Benutzer.id == benutzer_id)).first() is None:
        raise ValueError("pruefung.pruefer_unbekannt")
    if lieferant_id is not None and db.execute(select(Lieferant.id).where(Lieferant.mandant_id == mid, Lieferant.id == lieferant_id)).first() is None:
        raise ValueError("pruefung.lieferant_unbekannt")
    return text, benutzer_id, lieferant_id


def eintragen(
    sitzung: Any, inventarnummer: str, pruefart: str, durchgefuehrt_am: dt.date, ergebnis: str, durchfuehrung: str = "intern",
    pruefer_text: str = "", zaehlerstand: Decimal | None = None, bemerkung: str = "", nachweis: tuple[str, bytes] | None = None,
    arbeitsordner: Path | None = None, quelle: str = "web", pruefer_benutzer_id: int | None = None,
    pruefer_lieferant_id: int | None = None,
) -> m.Pruefung:
    """Trägt eine Prüfung ein; `nachweis` ist (Dateiname, Inhalt). Die nächste Fälligkeit rechnet `rein.pruefung.eintragen`.

    Liegt der Zählerstand unter dem letzten Stand, bleibt er nur an der Prüfung; der Satz trägt dann `zaehler_unter` (der letzte Stand).
    """
    if not sitzung.darf("inventar", "pruefen"):
        raise gemeinsam.KeinRecht("inventar", "pruefen")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    zeile = finde_stueck(sitzung, inventarnummer, "pruefen")
    art = _pruefart(sitzung, pruefart)
    if durchfuehrung not in m.PRUEF_DURCHFUEHRUNG:
        raise ValueError("pruefung.durchfuehrung_unbekannt")
    zu = next((z for z in _zuordnungen(sitzung, zeile) if z.pruefart == pruefart), None)
    if zu is None:
        raise ValueError("pruefung.nicht_zugeordnet")
    folge = rein.eintragen(zu, durchgefuehrt_am, ergebnis, zeit.heute(), zaehlerstand)
    text, pruefer_id, lieferant_id = _pruefer_pruefen(sitzung, durchfuehrung, pruefer_text, pruefer_benutzer_id, pruefer_lieferant_id)
    pfad = pruefsumme = None
    if nachweis is not None:
        if arbeitsordner is None:
            raise ValueError("pruefung.arbeitsordner_fehlt")
        endung = dateien.nachweis_pruefen(nachweis[1])
        name = dateien.sauber(Path(nachweis[0] or "nachweis").stem or "nachweis") + endung
        ordnername = db.execute(select(Mandant.ordnername).where(Mandant.id == mid)).scalar_one()
        ziel, pruefsumme = dateien.speichern(
            dateien.stammordner(arbeitsordner, ordnername, zeile.inventarnummer, "pruefungen"), name, nachweis[1])
        pfad = str(ziel.relative_to(arbeitsordner))
    benutzer = _benutzer(sitzung)
    satz = m.Pruefung(
        mandant_id=mid, stueck_id=zeile.id, pruefart_id=art.id, faellig_am=folge.naechste_am, durchgefuehrt_am=durchgefuehrt_am,
        ergebnis=ergebnis, durchfuehrung=durchfuehrung, pruefer_text=text, pruefer_benutzer_id=pruefer_id,
        pruefer_lieferant_id=lieferant_id, zaehlerstand=zaehlerstand, nachweis_pfad=pfad, nachweis_sha256=pruefsumme,
        bemerkung=bemerkung.strip(), naechste_am=folge.naechste_am, quelle=quelle, angelegt_von=benutzer)
    db.add(satz)
    db.flush()
    satz.zaehler_unter = _zaehlerstand_nachtragen(sitzung, zeile, zaehlerstand)
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.pruefung_eingetragen", objekt_typ="inventar.stueck",
                        objekt_id=int(zeile.id), neu_wert=f"{zeile.inventarnummer}: {pruefart} {ergebnis}, nächste {folge.naechste_am}",
                        benutzer_id=benutzer)
    return satz


def _zaehlerstand_nachtragen(sitzung: Any, stueck: m.Stueck, stand: Decimal | None) -> Decimal | None:
    """Ein Stand aus der Prüfung gilt auch als Ablesung — sonst rechnet die Zähler-Fälligkeit mit einem älteren Stand.

    Gibt den letzten Stand zurück, wenn der Stand darunter liegt und darum nicht als Ablesung geführt wird; sonst `None`.
    """
    if stand is None or stueck.zaehler_einheit is None:
        return None
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    letzter = db.execute(select(m.Zaehlerstand.stand).where(m.Zaehlerstand.mandant_id == mid, m.Zaehlerstand.stueck_id == stueck.id)
                         .order_by(m.Zaehlerstand.abgelesen_am.desc(), m.Zaehlerstand.id.desc()).limit(1)).scalar_one_or_none()
    if letzter is not None and stand < letzter:
        return letzter
    db.add(m.Zaehlerstand(mandant_id=mid, stueck_id=stueck.id, stand=stand, einheit=stueck.zaehler_einheit, abgelesen_am=zeit.jetzt_utc(),
                          abgelesen_von=_benutzer(sitzung), quelle="pruefung"))
    db.flush()
    return None


def nachweis_lesen(sitzung: Any, pruefung_id: int, arbeitsordner: Path) -> tuple[str, bytes]:
    """Name und Inhalt des Nachweises; ein Stück, das die Sitzung nicht sehen darf, gibt es nicht. Die Prüfsumme muss stimmen."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    satz = db.execute(select(m.Pruefung).where(m.Pruefung.mandant_id == mid, m.Pruefung.id == pruefung_id)).scalar_one_or_none()
    stueck = None if satz is None else db.execute(select(m.Stueck).where(m.Stueck.id == satz.stueck_id)).scalar_one_or_none()
    if satz is None or stueck is None or not satz.nachweis_pfad:
        raise gemeinsam.KeinRecht("inventar", "sehen")
    finde_stueck(sitzung, stueck.inventarnummer, "sehen")
    datei = (arbeitsordner / satz.nachweis_pfad).resolve()
    if arbeitsordner.resolve() not in datei.parents or not datei.is_file():
        raise ValueError("pruefung.nachweis_fehlt")
    inhalt = datei.read_bytes()
    if dateien.pruefsumme(inhalt) != satz.nachweis_sha256:
        raise ValueError("pruefung.nachweis_veraendert")
    return datei.name, inhalt


# ---- Prüfarten je Stück ------------------------------------------------------------------------------------------

def pruefarten_des_stuecks(sitzung: Any, stueck: m.Stueck) -> list[dict[str, Any]]:
    """Welche Prüfarten für dieses Stück gelten, mit Herkunft des Intervalls — und was man hinzunehmen könnte."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    arten = list(db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid, m.Pruefart.aktiv).order_by(m.Pruefart.bezeichnung)).scalars())
    gruppe = {int(z.pruefart_id): z for z in db.execute(select(m.GruppePruefart).where(
        m.GruppePruefart.mandant_id == mid, m.GruppePruefart.gruppe_id == stueck.gruppe_id, m.GruppePruefart.aktiv)).scalars()}
    eigene = {int(z.pruefart_id): z for z in db.execute(select(m.StueckPruefart).where(m.StueckPruefart.stueck_id == stueck.id)).scalars()}
    wirksam = {z.pruefart: z.intervall_monate for z in _zuordnungen(sitzung, stueck)}
    zeilen = []
    for p in arten:
        g, e = gruppe.get(int(p.id)), eigene.get(int(p.id))
        if g is None and e is None:
            continue
        herkunft = "gruppe" if g is not None else "stueck"
        zeilen.append({
            "schluessel": p.schluessel, "bezeichnung": p.bezeichnung, "katalog_intervall": p.intervall_monate,
            "gruppe_intervall": None if g is None else g.intervall_monate, "stueck_intervall": None if e is None else e.intervall_monate,
            "aktiv": e is None or bool(e.aktiv), "herkunft": herkunft, "wirksam": wirksam.get(p.schluessel),
            "zaehler_intervall": p.zaehler_intervall, "je_merkmal": bool(p.intervall_je_merkmal)})
    return zeilen


def pruefarten_zum_hinzunehmen(sitzung: Any, stueck: m.Stueck) -> list[tuple[str, str]]:
    """Aktive Prüfarten, die für dieses Stück noch nicht gelten (weder über die Gruppe noch eigens)."""
    schon = {z["schluessel"] for z in pruefarten_des_stuecks(sitzung, stueck)}
    return [(p.schluessel, p.bezeichnung) for p in sitzung.db.execute(select(m.Pruefart).where(
        m.Pruefart.mandant_id == sitzung.kontext.mandant_id, m.Pruefart.aktiv).order_by(m.Pruefart.bezeichnung)).scalars()
        if p.schluessel not in schon]


def pruefart_setzen(sitzung: Any, inventarnummer: str, pruefart: str, intervall_monate: str = "", aktiv: bool = True) -> m.StueckPruefart:
    """Intervall für dieses Stück überschreiben, die Prüfart abschalten oder eigens hinzunehmen. Nichts wird gelöscht (R23)."""
    if not sitzung.darf("inventar", "pflegen"):
        raise gemeinsam.KeinRecht("inventar", "pflegen")
    zeile = finde_stueck(sitzung, inventarnummer, "pflegen")
    art = _pruefart(sitzung, pruefart)
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    text = intervall_monate.strip()
    monate: int | None = None
    if text:
        if not text.isdigit() or int(text) < 1 or int(text) > 600:
            raise ValueError("pruefung.intervall_ungueltig")
        monate = int(text)
    satz = db.execute(select(m.StueckPruefart).where(m.StueckPruefart.stueck_id == zeile.id, m.StueckPruefart.pruefart_id == art.id)).scalar_one_or_none()
    alt = None if satz is None else f"{satz.intervall_monate}/{satz.aktiv}"
    if satz is None:
        satz = m.StueckPruefart(mandant_id=mid, stueck_id=zeile.id, pruefart_id=art.id, intervall_monate=monate, aktiv=aktiv)
        db.add(satz)
    else:
        satz.intervall_monate, satz.aktiv = monate, aktiv
    db.flush()
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.pruefart_stueck", objekt_typ="inventar.stueck", objekt_id=int(zeile.id),
                        alt_wert=alt, neu_wert=f"{pruefart}: {monate}/{aktiv}", benutzer_id=_benutzer(sitzung))
    return satz
