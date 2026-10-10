"""Werkstatt (G4): Posteingang der Meldungen, Reparatur-Vorgänge und der Status `in_reparatur` — Recht `werkstatt`.

Die Statusregeln stehen in `rein.werkstatt` (Automaten für Meldung und Reparatur); hier werden sie auf die Tabellen
angewendet, protokolliert und — bei „erledigt“ — dem Melder zurückgemeldet (Mail über `mail.einreihen`, Vermerk am Stück
im Protokoll). Nichts wird gelöscht: zurückgezogen ist ein Status mit Grund.

Reparaturkosten sind Kosten: eintragen darf sie, wer `kosten_pflegen` hat; sehen, wer `kosten_sehen` hat. Wer nur `werkstatt`
hat, beginnt und schließt Reparaturen ohne Betrag ab.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Benutzer, Lieferant, mail, protokoll, zeit
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import gemeinsam

from .. import dateien
from .. import modelle as m
from ..rein import werkstatt
from . import laden, sicht, stueck as fachstueck
from .stueckseite import namen_benutzer
from .transfer import finde_stueck

OBJEKT_TYP = "inventar.stueck"
#: Wie viele erledigte Meldungen und Reparaturen der Posteingang noch zeigt (die jüngsten)
ERLEDIGTE_ZEIGEN = 30
MELDUNG_NEU = ("angenommen", "in_arbeit", "erledigt", "zurueckgezogen")
REPARATUR_AKTIONEN = ("beginnen", "abschliessen", "zurueckziehen", "rechnung")


@dataclass(frozen=True)
class Posteingang:
    offen: list[dict[str, Any]]
    angenommen: list[dict[str, Any]]
    in_arbeit: list[dict[str, Any]]
    erledigt: list[dict[str, Any]]
    reparaturen: list[dict[str, Any]]  # offen und in Arbeit
    reparaturen_fertig: list[dict[str, Any]]  # die zuletzt erledigten
    stuecke_in_reparatur: list[dict[str, Any]]


def _benutzer(sitzung: Any) -> int | None:
    return None if sitzung.benutzer is None else int(sitzung.benutzer.id)


def _fordern(sitzung: Any) -> None:
    if not sitzung.darf("inventar", "werkstatt"):
        raise gemeinsam.KeinRecht("inventar", "werkstatt")


def _kosten_pflegen(sitzung: Any, kosten: Decimal | None) -> None:
    if kosten is not None and not sitzung.darf("inventar", "kosten_pflegen"):
        raise gemeinsam.KeinRecht("inventar", "kosten_pflegen")  # Reparaturkosten trägt nur ein, wer Kosten pflegen darf


def _meldung(sitzung: Any, meldung_id: int) -> m.Meldung:
    zeile = sitzung.db.execute(sitzung.abfrage(m.Meldung).where(m.Meldung.id == meldung_id)).scalar_one_or_none()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "werkstatt")
    return zeile


def _stueck(sitzung: Any, stueck_id: int) -> m.Stueck:
    zeile = sitzung.db.execute(sicht.stuecke(sitzung).where(m.Stueck.id == stueck_id)).scalars().first()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "werkstatt")
    return zeile


def _reparatur(sitzung: Any, reparatur_id: int) -> tuple[m.Reparatur, m.Stueck]:
    zeile = sitzung.db.execute(select(m.Reparatur).where(
        m.Reparatur.mandant_id == sitzung.kontext.mandant_id, m.Reparatur.id == reparatur_id)).scalar_one_or_none()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "werkstatt")
    return zeile, _stueck(sitzung, int(zeile.stueck_id))


def _rein_meldung(z: m.Meldung) -> werkstatt.Meldung:
    return werkstatt.Meldung(
        z.art, z.status, z.beschreibung, laden.person(z.gemeldet_von), z.gemeldet_am,  # type: ignore[arg-type]
        None if z.bearbeitet_von is None else laden.person(z.bearbeitet_von), z.erledigt_am, z.rueckmeldung, z.grund)


def _rein_reparatur(z: m.Reparatur) -> werkstatt.Reparatur:
    return werkstatt.Reparatur(z.status, z.durchfuehrung, z.begonnen_am, z.beendet_am, z.kosten, z.kosten_quelle, z.grund)  # type: ignore[arg-type]


def _uebernehmen(z: m.Reparatur, r: werkstatt.Reparatur) -> None:
    z.status, z.begonnen_am, z.beendet_am, z.kosten, z.kosten_quelle, z.grund = (
        r.status, r.begonnen_am, r.beendet_am, r.kosten, r.kosten_quelle, r.grund)


def _vermerk(sitzung: Any, stueck: m.Stueck, aktion: str, neu_wert: str) -> None:
    protokoll.schreiben(sitzung.db, mandant_id=sitzung.kontext.mandant_id, aktion=f"inventar.{aktion}", objekt_typ=OBJEKT_TYP,
                        objekt_id=int(stueck.id), neu_wert=neu_wert[:500], benutzer_id=_benutzer(sitzung))


# ---- Posteingang -------------------------------------------------------------------------------------------------

def posteingang(sitzung: Any) -> Posteingang:
    """Was bei der Werkstatt liegt: Meldungen nach Stand, Reparaturen und die Stücke, die in Reparatur sind."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    kosten_sehen = bool(sitzung.darf("inventar", "kosten_sehen"))
    laufend = list(db.execute(sitzung.abfrage(m.Meldung).where(m.Meldung.status.in_(("offen", "angenommen", "in_arbeit")))
                              .order_by(m.Meldung.gemeldet_am, m.Meldung.id)).scalars())
    fertig = list(db.execute(sitzung.abfrage(m.Meldung).where(m.Meldung.status == "erledigt")
                             .order_by(m.Meldung.erledigt_am.desc(), m.Meldung.id.desc()).limit(ERLEDIGTE_ZEIGEN)).scalars())
    zeilen = laufend + fertig
    sichtbar = sicht.stuecke(sitzung).with_only_columns(m.Stueck.id)
    offene_rep = list(db.execute(select(m.Reparatur).where(
        m.Reparatur.mandant_id == mid, m.Reparatur.status.in_(("offen", "in_arbeit")), m.Reparatur.stueck_id.in_(sichtbar))
        .order_by(m.Reparatur.id)).scalars())
    fertige_rep = list(db.execute(select(m.Reparatur).where(
        m.Reparatur.mandant_id == mid, m.Reparatur.status == "erledigt", m.Reparatur.stueck_id.in_(sichtbar))
        .order_by(m.Reparatur.beendet_am.desc(), m.Reparatur.id.desc()).limit(ERLEDIGTE_ZEIGEN)).scalars())
    in_rep = list(db.execute(sicht.stuecke(sitzung).where(m.Stueck.status == "in_reparatur").order_by(m.Stueck.inventarnummer)).scalars())
    stueck_ids = {int(z.stueck_id) for z in zeilen} | {int(r.stueck_id) for r in offene_rep + fertige_rep}
    stuecke = {int(s.id): s for s in db.execute(select(m.Stueck).where(m.Stueck.id.in_(stueck_ids))).scalars()} if stueck_ids else {}
    orte = sicht.kostenstellen_namen(sitzung, {int(z.kostenstelle_id) for z in zeilen})
    personen = namen_benutzer(sitzung, {z.gemeldet_von for z in zeilen} | {z.bearbeitet_von for z in zeilen})
    firmen = {int(x.id): (x.kurzname or x.name_gedruckt) for x in db.execute(select(Lieferant).where(
        Lieferant.mandant_id == mid, Lieferant.id.in_({int(r.lieferant_id) for r in offene_rep + fertige_rep if r.lieferant_id}))).scalars()} \
        if any(r.lieferant_id for r in offene_rep + fertige_rep) else {}
    laufende_je_stueck = {int(r.stueck_id) for r in offene_rep if r.status == "in_arbeit"}

    def meldung_zeile(z: m.Meldung) -> dict[str, Any]:
        s = stuecke.get(int(z.stueck_id))
        return {
            "id": int(z.id), "stueck_id": int(z.stueck_id), "nummer": "" if s is None else s.inventarnummer,
            "bezeichnung": "" if s is None else s.bezeichnung, "stueck_status": "" if s is None else s.status, "art": z.art,
            "beschreibung": z.beschreibung, "ort": orte.get(int(z.kostenstelle_id), ""), "status": z.status, "am": z.gemeldet_am,
            "von": personen.get(int(z.gemeldet_von), "") if z.gemeldet_von else "",
            "bearbeiter": personen.get(int(z.bearbeitet_von), "") if z.bearbeitet_von else "", "erledigt_am": z.erledigt_am,
            "rueckmeldung": z.rueckmeldung, "hat_foto": bool(z.foto_sha256)}

    def reparatur_zeile(r: m.Reparatur) -> dict[str, Any]:
        s = stuecke.get(int(r.stueck_id))
        return {
            "id": int(r.id), "stueck_id": int(r.stueck_id), "nummer": "" if s is None else s.inventarnummer,
            "bezeichnung": "" if s is None else s.bezeichnung, "stueck_status": "" if s is None else s.status, "status": r.status,
            "durchfuehrung": r.durchfuehrung, "beschreibung": r.beschreibung, "lieferant": firmen.get(int(r.lieferant_id), "") if r.lieferant_id else "",
            "begonnen": r.begonnen_am, "beendet": r.beendet_am, "kosten": r.kosten if kosten_sehen else None,
            "kosten_quelle": r.kosten_quelle if kosten_sehen else None, "laeuft": int(r.stueck_id) in laufende_je_stueck}

    je_status: dict[str, list[dict[str, Any]]] = {"offen": [], "angenommen": [], "in_arbeit": [], "erledigt": []}
    for z in zeilen:
        je_status[z.status].append(meldung_zeile(z))
    return Posteingang(
        offen=je_status["offen"], angenommen=je_status["angenommen"], in_arbeit=je_status["in_arbeit"], erledigt=je_status["erledigt"],
        reparaturen=[reparatur_zeile(r) for r in offene_rep], reparaturen_fertig=[reparatur_zeile(r) for r in fertige_rep],
        stuecke_in_reparatur=[{"id": int(s.id), "nummer": s.inventarnummer, "bezeichnung": s.bezeichnung, "seit": s.status_seit}
                              for s in in_rep])


# ---- Meldungen ---------------------------------------------------------------------------------------------------

def meldung_weiter(sitzung: Any, meldung_id: int, neu: str, rueckmeldung: str = "", grund: str = "") -> m.Meldung:
    """Annehmen (`angenommen`), Übernehmen (`in_arbeit`), Erledigen mit Rückmeldung, Zurückziehen mit Grund."""
    _fordern(sitzung)
    z = _meldung(sitzung, meldung_id)
    stueck = _stueck(sitzung, int(z.stueck_id))
    jetzt = zeit.jetzt_utc()
    erg = werkstatt.meldung_weiter(_rein_meldung(z), neu, laden.person(_benutzer(sitzung)), jetzt, rueckmeldung, grund)
    z.status, z.erledigt_am, z.rueckmeldung, z.grund = erg.status, erg.erledigt_am, erg.rueckmeldung, erg.grund
    if neu in ("angenommen", "in_arbeit", "erledigt"):
        z.bearbeitet_von = _benutzer(sitzung)
    sitzung.db.flush()
    text = erg.rueckmeldung if neu == "erledigt" else erg.grund if neu == "zurueckgezogen" else z.beschreibung[:200]
    _vermerk(sitzung, stueck, f"meldung_{neu}", f"{stueck.inventarnummer}: {text}")
    if neu == "erledigt":
        _rueckmelden(sitzung, z, stueck)
    return z


def _rueckmelden(sitzung: Any, meldung: m.Meldung, stueck: m.Stueck) -> bool:
    """Die Rückmeldung an den Melder als Mail; ohne aktives Konto oder Adresse bleibt nur der Vermerk am Stück."""
    if meldung.gemeldet_von is None:
        return False
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    konto = db.execute(select(Benutzer).where(Benutzer.mandant_id == mid, Benutzer.id == meldung.gemeldet_von, Benutzer.aktiv)).scalar_one_or_none()
    adresse = None if konto is None else (konto.benachrichtigung_email or konto.email)
    if not adresse:
        return False
    mail.einreihen(
        db, an=[adresse], betreff=t("inventar.werkstatt.mail_betreff", nummer=stueck.inventarnummer),
        text=t("inventar.werkstatt.mail_text", nummer=stueck.inventarnummer, bezeichnung=stueck.bezeichnung,
               art=t("inventar.meldung.art." + meldung.art), beschreibung=meldung.beschreibung, rueckmeldung=meldung.rueckmeldung),
        mandant_id=mid, benutzer_id=_benutzer(sitzung))
    return True


def meldung_foto_lesen(sitzung: Any, meldung_id: int, arbeitsordner: Path) -> tuple[str, bytes]:
    """Das Foto zur Meldung: nur für Meldungen, die man sehen darf; die Prüfsumme muss stimmen."""
    z = sitzung.db.execute(sitzung.abfrage(m.Meldung).where(m.Meldung.id == meldung_id)).scalar_one_or_none()
    if z is None or not z.foto_pfad:
        raise gemeinsam.KeinRecht("inventar", "sehen")
    datei = (arbeitsordner / z.foto_pfad).resolve()
    if arbeitsordner.resolve() not in datei.parents or not datei.is_file():
        raise ValueError("meldung.foto_fehlt")
    inhalt = datei.read_bytes()
    if dateien.pruefsumme(inhalt) != z.foto_sha256:
        raise ValueError("meldung.foto_veraendert")
    return datei.name, inhalt


# ---- Reparaturen -------------------------------------------------------------------------------------------------

def _status_folgen(sitzung: Any, stueck: m.Stueck) -> None:
    """`in_reparatur`, solange eine Reparatur läuft; danach zurück auf `aktiv` (andere Stati bleiben unberührt)."""
    laufende = sitzung.db.execute(select(m.Reparatur.id).where(
        m.Reparatur.mandant_id == sitzung.kontext.mandant_id, m.Reparatur.stueck_id == stueck.id, m.Reparatur.status == "in_arbeit")).all()
    folge = werkstatt.status_folge(stueck.status, len(laufende))
    if folge is not None:
        fachstueck.status_setzen(sitzung, stueck, folge)


def reparatur_anlegen(
    sitzung: Any, *, inventarnummer: str | None = None, meldung_id: int | None = None, durchfuehrung: str = "intern",
    beschreibung: str = "", lieferant_id: int | None = None,
) -> m.Reparatur:
    """Legt eine Reparatur (offen) zu einem Stück an — direkt oder aus einer Meldung; Lieferant nur bei bekannter Firma."""
    _fordern(sitzung)
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    meldung = None
    if meldung_id is not None:
        meldung = _meldung(sitzung, meldung_id)
        stueck = _stueck(sitzung, int(meldung.stueck_id))
    elif inventarnummer:
        stueck = finde_stueck(sitzung, inventarnummer, "werkstatt")
    else:
        raise ValueError("reparatur.ziel_fehlt")
    werkstatt.neue_reparatur(durchfuehrung)
    if lieferant_id is not None and db.execute(select(Lieferant.id).where(Lieferant.mandant_id == mid, Lieferant.id == lieferant_id)).first() is None:
        raise ValueError("reparatur.lieferant_unbekannt")
    text = beschreibung.strip() or (meldung.beschreibung if meldung is not None else "")
    satz = m.Reparatur(mandant_id=mid, stueck_id=stueck.id, meldung_id=None if meldung is None else meldung.id, beschreibung=text,
                       durchfuehrung=durchfuehrung, lieferant_id=lieferant_id, status="offen", angelegt_von=_benutzer(sitzung))
    db.add(satz)
    db.flush()
    _vermerk(sitzung, stueck, "reparatur_angelegt", f"{stueck.inventarnummer}: {durchfuehrung}")
    return satz


def reparatur_beginnen(sitzung: Any, reparatur_id: int, am: dt.date, geschaetzte_kosten: Decimal | None = None) -> m.Reparatur:
    """Beginn der Reparatur; das Stück steht ab jetzt `in_reparatur` (Abgang und Eingang lassen sich weiter buchen)."""
    _fordern(sitzung)
    _kosten_pflegen(sitzung, geschaetzte_kosten)
    z, stueck = _reparatur(sitzung, reparatur_id)
    _uebernehmen(z, werkstatt.reparatur_beginnen(_rein_reparatur(z), am, geschaetzte_kosten))
    sitzung.db.flush()
    _status_folgen(sitzung, stueck)
    _vermerk(sitzung, stueck, "reparatur_begonnen", f"{stueck.inventarnummer}: {am.isoformat()}")
    return z


def reparatur_abschliessen(
    sitzung: Any, reparatur_id: int, am: dt.date, kosten: Decimal | None = None, quelle: str = "geschaetzt",
) -> m.Reparatur:
    """Ende der Reparatur; ohne weitere laufende Reparatur ist das Stück wieder `aktiv`."""
    _fordern(sitzung)
    _kosten_pflegen(sitzung, kosten)
    z, stueck = _reparatur(sitzung, reparatur_id)
    _uebernehmen(z, werkstatt.reparatur_abschliessen(_rein_reparatur(z), am, kosten, quelle))
    sitzung.db.flush()
    _status_folgen(sitzung, stueck)
    _vermerk(sitzung, stueck, "reparatur_abgeschlossen", f"{stueck.inventarnummer}: {am.isoformat()}")
    return z


def reparatur_rechnung(sitzung: Any, reparatur_id: int, kosten: Decimal) -> m.Reparatur:
    """Ersetzt die Schätzung einer erledigten Reparatur durch den Betrag aus der Rechnung (Recht `kosten_pflegen`)."""
    _fordern(sitzung)
    _kosten_pflegen(sitzung, kosten)
    z, stueck = _reparatur(sitzung, reparatur_id)
    _uebernehmen(z, werkstatt.kosten_aus_rechnung(_rein_reparatur(z), kosten))
    sitzung.db.flush()
    _vermerk(sitzung, stueck, "reparatur_rechnung", f"{stueck.inventarnummer}: {kosten}")
    return z


def reparatur_zurueckziehen(sitzung: Any, reparatur_id: int, grund: str) -> m.Reparatur:
    """Zieht eine offene oder laufende Reparatur mit Grund zurück; das Stück wird wieder `aktiv`, wenn nichts mehr läuft."""
    _fordern(sitzung)
    z, stueck = _reparatur(sitzung, reparatur_id)
    _uebernehmen(z, werkstatt.reparatur_zurueckziehen(_rein_reparatur(z), grund))
    sitzung.db.flush()
    _status_folgen(sitzung, stueck)
    _vermerk(sitzung, stueck, "reparatur_zurueckgezogen", f"{stueck.inventarnummer}: {z.grund}")
    return z


# ---- Status in_reparatur von Hand ----------------------------------------------------------------------------------

def in_reparatur_setzen(sitzung: Any, stueck_id: int, setzen: bool, grund: str = "") -> m.Stueck:
    """Setzt `in_reparatur` oder hebt es auf (`aktiv`); nur zwischen diesen beiden Stati, das Recht ist `werkstatt`."""
    _fordern(sitzung)
    stueck = _stueck(sitzung, stueck_id)
    erwartet, ziel = ("aktiv", "in_reparatur") if setzen else ("in_reparatur", "aktiv")
    if stueck.status != erwartet:
        raise ValueError("werkstatt.status_nicht_moeglich")
    return fachstueck.status_setzen(sitzung, stueck, ziel, grund)
