"""Alles, was die Stück-Seite zeigt: Statuszeile, Lage, Beziehungen, Prüfungen, Zähler, Kosten, Verlauf.

Nur Lesen. Jede Abfrage geht über die Sitzung (Mandant, Kostenstellen). Kosten stehen nur mit `kosten_sehen` im Ergebnis.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Benutzer, protokoll, zeit
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein.pruefung import gesamt_ampel
from . import pruefstand, sicht
from .liste import AMPEL_ZEICHEN

AMPEL_RANG = {"gruen": 0, "unbekannt": 1, "gelb": 2, "rot": 3}


def holen(sitzung: Any, stueck_id: int) -> m.Stueck:
    """Das Stück, wenn die Sitzung es sehen darf — sonst „kein Recht“ (N7)."""
    zeile = sitzung.db.execute(sicht.stuecke(sitzung).where(m.Stueck.id == stueck_id)).scalars().first()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "sehen")
    return zeile


def namen_benutzer(sitzung: Any, ids: set[int | None]) -> dict[int, str]:
    echte = {int(i) for i in ids if i is not None}
    if not echte:
        return {}
    return {int(b.id): b.name for b in sitzung.db.execute(sitzung.abfrage(Benutzer).where(Benutzer.id.in_(echte))).scalars()}


def aktion_text(aktion: str) -> str:
    """Protokollaktion → Satz; unbekannte Aktionen bleiben, wie sie sind."""
    name = aktion.removeprefix("inventar.")
    for praefix, bereich in (("transfer_", "transfer"), ("stueck_status_", "stueck_status")):
        if name.startswith(praefix):
            schluessel = f"inventar.code.{bereich}.{name.removeprefix(praefix)}"
            text = t(schluessel)
            if text != schluessel:
                return text
    schluessel = f"inventar.aktion.{name}"
    text = t(schluessel)
    return aktion if text == schluessel else text


def ampel_hinweis(stand: Any) -> str:
    if stand.ampel == "unbekannt":
        return t("inventar.pruefung.ohne_nachweis")
    if stand.grund == "zaehler" and stand.faellig_bei_zaehler is not None:
        return t("inventar.pruefung.zaehler_faellig", stand=stand.faellig_bei_zaehler)
    if stand.tage is None:
        return t("inventar.pruefung.ampel." + stand.ampel)
    if stand.tage < 0:
        return t("inventar.pruefung.ueberfaellig_seit", tage=-stand.tage)
    return t("inventar.pruefung.faellig_in", tage=stand.tage)


def _lieferanten(db: Any, mid: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    from digiassistenz_kern import Lieferant

    return {int(z.id): (z.kurzname or z.name_gedruckt) for z in db.execute(
        select(Lieferant).where(Lieferant.mandant_id == mid, Lieferant.id.in_(ids))).scalars()}


def daten(sitzung: Any, stueck: m.Stueck) -> dict[str, Any]:
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    sid = int(stueck.id)
    gruppe = db.execute(select(m.Gruppe).where(m.Gruppe.id == stueck.gruppe_id)).scalar_one()
    kosten_sehen = bool(sitzung.darf("inventar", "kosten_sehen"))

    merkmale = [
        {"bezeichnung": mm.bezeichnung, "wert": z.wert, "einheit": mm.einheit}
        for z, mm in db.execute(select(m.StueckMerkmal, m.Merkmal).join(m.Merkmal, m.Merkmal.id == m.StueckMerkmal.merkmal_id)
                                .where(m.StueckMerkmal.stueck_id == sid).order_by(m.Merkmal.sortierung, m.Merkmal.id)).all()]

    alle_orte = list(db.execute(sitzung.abfrage(m.Standort).where(m.Standort.stueck_id == sid).order_by(m.Standort.von, m.Standort.id)).scalars())
    angekuendigt = sicht.transfers_angekuendigt(sitzung, [sid]).get(sid, [])
    ks_namen = sicht.kostenstellen_namen(
        sitzung, {int(o.kostenstelle_id) for o in alle_orte} | {int(x.nach_kostenstelle_id) for x in angekuendigt}
        | {int(x.von_kostenstelle_id) for x in angekuendigt if x.von_kostenstelle_id is not None})
    offen = [{"kostenstelle_id": int(o.kostenstelle_id), "kostenstelle": ks_namen.get(int(o.kostenstelle_id), ""), "menge": int(o.menge),
              "seit": o.von, "darf_buchen": bool(sitzung.darf("inventar", "buchen", int(o.kostenstelle_id))),
              "darf_scannen": bool(sitzung.darf("inventar", "scannen", int(o.kostenstelle_id))),
              "darf_melden": bool(sitzung.darf("inventar", "melden", int(o.kostenstelle_id)))} for o in alle_orte if o.bis is None]
    verlauf_orte = [{"kostenstelle": ks_namen.get(int(o.kostenstelle_id), ""), "menge": int(o.menge), "von": o.von, "bis": o.bis,
                     "quelle": o.quelle} for o in reversed(alle_orte)]
    transfers = [{
        "id": int(x.id), "menge": int(x.menge), "von": ks_namen.get(int(x.von_kostenstelle_id), "") if x.von_kostenstelle_id else "",
        "nach": ks_namen.get(int(x.nach_kostenstelle_id), ""), "nach_id": int(x.nach_kostenstelle_id), "abgang_am": x.abgang_am,
        "grund": x.grund, "darf_eingang": bool(sitzung.darf("inventar", "scannen", int(x.nach_kostenstelle_id))),
        "darf_zurueck": x.von_kostenstelle_id is not None and bool(sitzung.darf("inventar", "buchen", int(x.von_kostenstelle_id))),
    } for x in angekuendigt]

    staende = pruefstand.staende(db, mid, [stueck], zeit.heute()).get(stueck.inventarnummer, [])
    arten = {p.schluessel: p.bezeichnung for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid)).scalars()}
    stand_zeilen = [{"art": arten.get(s.pruefart, s.pruefart), "ampel": s.ampel, "zeichen": AMPEL_ZEICHEN[s.ampel],
                     "faellig_am": s.faellig_am, "hinweis": ampel_hinweis(s)} for s in staende]
    schlimmster = max(staende, key=lambda s: AMPEL_RANG[s.ampel], default=None)
    ampel = gesamt_ampel(staende)

    arten_id = {int(p.id): p.bezeichnung for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid)).scalars()}
    pruef_zeilen = list(db.execute(select(m.Pruefung).where(m.Pruefung.mandant_id == mid, m.Pruefung.stueck_id == sid)
                                   .order_by(m.Pruefung.durchgefuehrt_am.desc(), m.Pruefung.id.desc())).scalars())
    pruefer_namen = namen_benutzer(sitzung, {p.pruefer_benutzer_id for p in pruef_zeilen})
    pruefer_firmen = _lieferanten(db, mid, {int(p.pruefer_lieferant_id) for p in pruef_zeilen if p.pruefer_lieferant_id})
    pruefungen = [{"id": int(p.id), "art": arten_id.get(int(p.pruefart_id), ""), "am": p.durchgefuehrt_am, "ergebnis": p.ergebnis,
                   "durchfuehrung": p.durchfuehrung, "naechste": p.naechste_am, "nachweis": bool(p.nachweis_sha256),
                   "pruefer": ", ".join(x for x in (
                       p.pruefer_text, pruefer_namen.get(int(p.pruefer_benutzer_id), "") if p.pruefer_benutzer_id else "",
                       pruefer_firmen.get(int(p.pruefer_lieferant_id), "") if p.pruefer_lieferant_id else "") if x)}
                  for p in pruef_zeilen]
    meldungen_zeilen = list(db.execute(sitzung.abfrage(m.Meldung).where(m.Meldung.stueck_id == sid).order_by(m.Meldung.gemeldet_am.desc())).scalars())
    wer = namen_benutzer(sitzung, {z.gemeldet_von for z in meldungen_zeilen} | {z.bearbeitet_von for z in meldungen_zeilen})
    meldungen = [{"id": int(z.id), "art": z.art, "beschreibung": z.beschreibung, "status": z.status, "am": z.gemeldet_am,
                  "von": wer.get(int(z.gemeldet_von), "") if z.gemeldet_von else "", "hat_foto": bool(z.foto_sha256),
                  "bearbeiter": wer.get(int(z.bearbeitet_von), "") if z.bearbeitet_von else "", "erledigt_am": z.erledigt_am,
                  "rueckmeldung": z.rueckmeldung, "grund": z.grund} for z in meldungen_zeilen]
    reparaturen = [{"status": r.status, "beschreibung": r.beschreibung, "begonnen": r.begonnen_am, "beendet": r.beendet_am,
                    "kosten": r.kosten if kosten_sehen else None, "durchfuehrung": r.durchfuehrung, "grund": r.grund}
                   for r in db.execute(select(m.Reparatur).where(m.Reparatur.mandant_id == mid, m.Reparatur.stueck_id == sid)
                                       .order_by(m.Reparatur.id.desc())).scalars()]
    zaehler = [{"stand": z.stand, "einheit": z.einheit, "am": z.abgelesen_am, "quelle": z.quelle}
               for z in db.execute(select(m.Zaehlerstand).where(m.Zaehlerstand.mandant_id == mid, m.Zaehlerstand.stueck_id == sid)
                                   .order_by(m.Zaehlerstand.abgelesen_am.desc(), m.Zaehlerstand.id.desc()).limit(20)).scalars()]

    zubehoer, haupt, bauteile = [], None, []
    beziehungen = list(db.execute(select(m.Beziehung).where(m.Beziehung.mandant_id == mid, m.Beziehung.gueltig_bis.is_(None)).where(
        (m.Beziehung.zu_stueck_id == sid) | (m.Beziehung.von_stueck_id == sid))).scalars())
    andere = {int(s.id): s for s in db.execute(sicht.stuecke(sitzung).where(m.Stueck.id.in_(
        [int(b.von_stueck_id) for b in beziehungen if b.von_stueck_id] + [int(b.zu_stueck_id) for b in beziehungen if b.zu_stueck_id]))).scalars()}
    bauteil_ids = [int(b.bauteil_id) for b in beziehungen if b.bauteil_id]
    katalog_bauteile = {int(b.id): b for b in db.execute(select(m.Bauteil).where(m.Bauteil.id.in_(bauteil_ids))).scalars()} if bauteil_ids else {}
    for b in beziehungen:
        if b.art == "gehoert_zu" and b.zu_stueck_id == sid and b.von_stueck_id in andere:
            s = andere[int(b.von_stueck_id)]
            zubehoer.append({"beziehung_id": int(b.id), "id": int(s.id), "nummer": s.inventarnummer, "bezeichnung": s.bezeichnung})
        elif b.art == "gehoert_zu" and b.von_stueck_id == sid and b.zu_stueck_id in andere:
            s = andere[int(b.zu_stueck_id)]
            haupt = {"beziehung_id": int(b.id), "id": int(s.id), "nummer": s.inventarnummer, "bezeichnung": s.bezeichnung}
        elif b.art == "passt_zu" and b.bauteil_id in katalog_bauteile:
            bt = katalog_bauteile[int(b.bauteil_id)]
            bauteile.append({"beziehung_id": int(b.id), "nummer": bt.bauteilnummer, "bezeichnung": bt.bezeichnung,
                             "preis": bt.preis_zuletzt if kosten_sehen else None})

    kosten = None
    if kosten_sehen:
        satz = db.execute(select(m.Kostensatz).where(m.Kostensatz.mandant_id == mid, m.Kostensatz.gruppe_id == stueck.gruppe_id)
                          .order_by(m.Kostensatz.gueltig_ab.desc()).limit(1)).scalar_one_or_none()
        kosten = {"kaufpreis": stueck.kaufpreis, "kaufdatum": stueck.kaufdatum, "buchwert_extern": stueck.buchwert_extern,
                  "mietkosten": stueck.mietkosten, "miete": stueck.miete, "satz_monat": None if satz is None else satz.satz_monat,
                  "satz_tag": None if satz is None else satz.satz_tag, "nutzungsdauer": None if satz is None else satz.nutzungsdauer_monate}

    verlauf = [{"am": v.zeitpunkt, "text": aktion_text(v.aktion), "alt": v.alt_wert, "neu": v.neu_wert, "wer": v.wer, "fuer": v.fuer}
               for v in protokoll.verlauf(db, mandant_id=mid, objekt_typ="inventar.stueck", objekt_id=sid)]
    lieferant = None
    if stueck.lieferant_id:
        from digiassistenz_kern import Lieferant

        zeile = db.execute(select(Lieferant).where(Lieferant.mandant_id == mid, Lieferant.id == stueck.lieferant_id)).scalar_one_or_none()
        lieferant = None if zeile is None else (zeile.kurzname or zeile.name_gedruckt)

    return {
        "stueck": stueck, "gruppe": gruppe, "merkmale": merkmale, "offen": offen, "verlauf_orte": verlauf_orte, "transfers": transfers,
        "pruefstaende": stand_zeilen, "ampel": ampel, "ampel_zeichen": AMPEL_ZEICHEN[ampel],
        "ampel_hinweis": "" if schlimmster is None else ampel_hinweis(schlimmster), "pruefungen": pruefungen, "meldungen": meldungen,
        "reparaturen": reparaturen, "zaehlerstaende": zaehler, "zubehoer": zubehoer, "haupt": haupt, "bauteile": bauteile, "kosten": kosten,
        "verlauf": verlauf, "lieferant": lieferant,
        "steht_auf": ", ".join(o["kostenstelle"] for o in offen), "seit": min((o["seit"] for o in offen), default=None),
        "angekuendigt_auf": ", ".join(x["nach"] for x in transfers),
    }
