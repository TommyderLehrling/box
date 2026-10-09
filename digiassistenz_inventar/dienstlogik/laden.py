"""Zwischen Datenbank und den reinen Modulen: Zustand eines Stücks laden, Ergebnis des Automaten speichern.

In `rein` sind Kostenstellen einfache Zahlen und Personen Zeichenketten. Hier sind es `kostenstelle_id` und
`str(benutzer_id)` (`"system"` für das System). Die Id eines Transfers ist dort `t:<eintrag_schluessel>`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import modelle as m
from ..rein.transfer import Aenderung, Ergebnis, Standort, Transfer, Zustand

SYSTEM = "system"


def person(benutzer_id: int | None) -> str:
    return SYSTEM if benutzer_id is None else str(int(benutzer_id))


def benutzer_id(wer: str | None) -> int | None:
    return int(wer) if wer is not None and wer.isdigit() else None


def transfer_id(schluessel: str) -> str:
    return "t:" + schluessel


def _menge(x: Decimal | int) -> int:
    return int(x)


def lade_zustaende(db: Session, mandant_id: int, stuecke: list[m.Stueck]) -> dict[str, Zustand]:
    """Der Zustand je Inventarnummer — alle Standorte und Transfers dieser Stücke."""
    if not stuecke:
        return {}
    nummer = {int(s.id): s.inventarnummer for s in stuecke}
    ids = list(nummer)
    transfers = list(db.execute(select(m.Transfer).where(
        m.Transfer.mandant_id == mandant_id, m.Transfer.stueck_id.in_(ids)).order_by(m.Transfer.id)).scalars())
    schluessel = {int(t.id): t.eintrag_schluessel for t in transfers}
    standorte = db.execute(select(m.Standort).where(
        m.Standort.mandant_id == mandant_id, m.Standort.stueck_id.in_(ids)).order_by(m.Standort.id)).scalars()
    je_stand: dict[str, list[Standort]] = {n: [] for n in nummer.values()}
    je_transfer: dict[str, list[Transfer]] = {n: [] for n in nummer.values()}
    for s in standorte:
        je_stand[nummer[int(s.stueck_id)]].append(Standort(
            nummer[int(s.stueck_id)], int(s.kostenstelle_id), _menge(s.menge), s.von, s.bis,
            None if s.transfer_id is None else transfer_id(schluessel[int(s.transfer_id)]), s.quelle,  # type: ignore[arg-type]
            person(s.von_person)))
    for t in transfers:
        je_transfer[nummer[int(t.stueck_id)]].append(Transfer(
            transfer_id(t.eintrag_schluessel), nummer[int(t.stueck_id)], _menge(t.menge),
            None if t.von_kostenstelle_id is None else int(t.von_kostenstelle_id), int(t.nach_kostenstelle_id),
            t.status, t.abgang_am, None if t.abgang_von is None and t.abgang_am is None else person(t.abgang_von),  # type: ignore[arg-type]
            t.eingang_am, None if t.eingang_am is None else person(t.eingang_von), t.grund, t.quelle,  # type: ignore[arg-type]
            t.eintrag_schluessel, t.erinnert_am, t.beendet_am, t.eingang_schluessel))
    return {n: Zustand(tuple(je_stand[n]), tuple(je_transfer[n])) for n in nummer.values()}


def _nach_schluessel(db: Session, mandant_id: int, stueck_id: int, schluessel: str) -> m.Transfer:
    return db.execute(select(m.Transfer).where(
        m.Transfer.mandant_id == mandant_id, m.Transfer.stueck_id == stueck_id,
        m.Transfer.eintrag_schluessel == schluessel)).scalar_one()


def _transfer_feld(name: str, wert: Any) -> tuple[str, Any]:
    if name in ("eingang_von", "abgang_von"):
        return name, benutzer_id(wert)
    return name, wert


def speichern(db: Session, mandant_id: int, stueck: m.Stueck, ergebnis: Ergebnis) -> None:
    """Schreibt die `Aenderung`-Einträge als Zeilen: erst Transfers, dann die Standorte."""
    sid = int(stueck.id)
    neue = [a for a in ergebnis.aenderungen if a.art == "transfer_neu"]
    geaendert = [a for a in ergebnis.aenderungen if a.art == "transfer_geaendert"]
    for a in neue:
        d = a.daten
        db.add(m.Transfer(
            mandant_id=mandant_id, stueck_id=sid, menge=d["menge"], von_kostenstelle_id=d["von_kostenstelle"],
            nach_kostenstelle_id=d["nach_kostenstelle"], status=d["status"], abgang_am=d["abgang_am"],
            abgang_von=benutzer_id(d["abgang_von"]), eingang_am=d["eingang_am"], eingang_von=benutzer_id(d["eingang_von"]),
            beendet_am=d["beendet_am"], grund=d["grund"], quelle=d["quelle"], eintrag_schluessel=d["eintrag_schluessel"],
            eingang_schluessel=d["eingang_schluessel"], erinnert_am=d["erinnert_am"]))
    db.flush()
    for a in geaendert:
        zeile = _nach_schluessel(db, mandant_id, sid, a.daten["id"][2:])
        for name, wert in a.daten["felder"].items():
            feld, wert = _transfer_feld(name, wert)
            setattr(zeile, feld, wert)
    db.flush()
    for a in ergebnis.aenderungen:
        if a.art == "standort_geschlossen":
            d = a.daten
            offen = db.execute(select(m.Standort).where(
                m.Standort.stueck_id == sid, m.Standort.bis.is_(None), m.Standort.kostenstelle_id == d["kostenstelle"],
                m.Standort.menge == d["menge"]).order_by(m.Standort.id)).scalars().first()
            if offen is None:
                raise ValueError("laden.standort_fehlt")
            offen.bis = d["bis"]
        elif a.art == "standort_neu":
            d = a.daten
            tid = None if d["transfer_id"] is None else _nach_schluessel(db, mandant_id, sid, d["transfer_id"][2:]).id
            db.add(m.Standort(
                mandant_id=mandant_id, stueck_id=sid, kostenstelle_id=d["kostenstelle"], menge=d["menge"], von=d["von"],
                bis=None, transfer_id=tid, quelle=d["quelle"], von_person=benutzer_id(d["von_person"])))
        db.flush()


def aktion_aus(schluessel: str) -> str:
    """`transfer.abgang` → `inventar.transfer_abgang` (Protokollaktion)."""
    return "inventar." + schluessel.replace(".", "_")

