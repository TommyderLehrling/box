"""Was jemand sehen darf: Stücke, Standorte, Zähler — immer über `sitzung.abfrage` (Mandant, Kostenstellen).

Das Stück selbst trägt keine Kostenstelle (der Ort steht in `standort`). Darum wird die Stückliste auf Stücke
eingeschränkt, die auf einer erlaubten Kostenstelle stehen oder dorthin angekündigt sind (Spec v0.2 Abschnitt 3).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, distinct, func, or_, select

from digiassistenz_kern import aehnlichkeit
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein.nummernformat import normalisiere

BAUSTEIN_SEHEN = ("inventar", "sehen")


def erlaubte_kostenstellen(sitzung: Any, aktion: str = "sehen") -> tuple[int, ...] | None:
    """`None` = alle des Mandanten; sonst genau diese Kostenstellen (leer heißt: keine)."""
    umfang = sitzung.kostenstellen_fuer("inventar", aktion)
    return tuple(umfang) if isinstance(umfang, tuple) else None


def stuecke(sitzung: Any, aktion: str = "sehen") -> Select[Any]:
    """Alle Stücke, die diese Sitzung sehen darf — mit `aktion` die, die sie für diesen Baustein sehen darf (z. B. `kosten_sehen`)."""
    abfrage = sitzung.abfrage(m.Stueck)
    ks = erlaubte_kostenstellen(sitzung, aktion)
    if ks is None:
        return abfrage
    steht = select(m.Standort.stueck_id).where(m.Standort.bis.is_(None), m.Standort.kostenstelle_id.in_(ks))
    kommt = select(m.Transfer.stueck_id).where(m.Transfer.status == "angekuendigt", m.Transfer.nach_kostenstelle_id.in_(ks))
    return abfrage.where(or_(m.Stueck.id.in_(steht), m.Stueck.id.in_(kommt)))


def aufloesen(sitzung: Any, kennung: str) -> m.Stueck | None:
    """Das Stück zu dem, was ein Scan oder eine Eingabe liefert — die **einzige** Stelle, die das auflöst.

    Zuerst die Inventarnummer, dann die Seriennummer. Der Etikett-Code vorgedruckter QR-Codes (Spec E24, noch nicht gebaut)
    kommt hier als weiterer Schritt dazu; die Wege `/inventar/s/...` und das Eingabefeld der Scan-Seite ändern sich dafür nicht.
    """
    nummer = normalisiere(kennung)
    if not nummer:
        return None
    zeile = sitzung.db.execute(stuecke(sitzung).where(func.upper(m.Stueck.inventarnummer) == nummer)).scalars().first()
    if zeile is None:
        zeile = sitzung.db.execute(stuecke(sitzung).where(
            func.upper(m.Stueck.seriennummer) == nummer).order_by(m.Stueck.inventarnummer)).scalars().first()
    return zeile


def stuecke_je_kostenstelle(sitzung: Any) -> dict[int, int]:
    """Anzahl der Stücke, die dort stehen — eine Abfrage für alle Kostenstellen (T-UE-2)."""
    q = sitzung.abfrage(m.Standort).where(m.Standort.bis.is_(None))
    zeilen = sitzung.db.execute(
        q.with_only_columns(m.Standort.kostenstelle_id, func.count(distinct(m.Standort.stueck_id))).group_by(m.Standort.kostenstelle_id)
    ).all()
    return {int(k): int(n) for k, n in zeilen}


def standorte_offen(sitzung: Any, stueck_ids: list[int]) -> dict[int, list[tuple[int, Any]]]:
    """Je Stück die offenen Standorte (Kostenstelle, Menge, seit) — nur auf erlaubten Kostenstellen."""
    if not stueck_ids:
        return {}
    q = sitzung.abfrage(m.Standort).where(m.Standort.bis.is_(None), m.Standort.stueck_id.in_(stueck_ids))
    ergebnis: dict[int, list[tuple[int, Any]]] = {}
    for s in sitzung.db.execute(q).scalars():
        ergebnis.setdefault(int(s.stueck_id), []).append((int(s.kostenstelle_id), s))
    return ergebnis


def transfers_angekuendigt(sitzung: Any, stueck_ids: list[int]) -> dict[int, list[m.Transfer]]:
    """Die angekündigten Transfers je Stück, soweit die Sitzung das Ziel oder die Herkunft sehen darf."""
    if not stueck_ids:
        return {}
    q = select(m.Transfer).where(m.Transfer.mandant_id == sitzung.kontext.mandant_id, m.Transfer.status == "angekuendigt",
                                 m.Transfer.stueck_id.in_(stueck_ids)).order_by(m.Transfer.abgang_am, m.Transfer.id)
    erlaubt = erlaubte_kostenstellen(sitzung)
    if erlaubt is not None:
        q = q.where(or_(m.Transfer.nach_kostenstelle_id.in_(erlaubt), m.Transfer.von_kostenstelle_id.in_(erlaubt)))
    ergebnis: dict[int, list[m.Transfer]] = {}
    for z in sitzung.db.execute(q).scalars():
        ergebnis.setdefault(int(z.stueck_id), []).append(z)
    return ergebnis


def kostenstellen_namen(sitzung: Any, ids: set[int]) -> dict[int, str]:
    """`Nummer Bezeichnung` je Kostenstelle — nur der erlaubten (Kostenstelle selbst filtert über `id`)."""
    from digiassistenz_kern import Kostenstelle

    if not ids:
        return {}
    q = sitzung.abfrage(Kostenstelle).where(Kostenstelle.id.in_(ids))
    return {int(k.id): f"{k.nummer} {k.bezeichnung}" for k in sitzung.db.execute(q).scalars()}


def suchen(sitzung: Any, begriff: str, hoechstens: int) -> tuple[list[tuple[str, str, str]], bool]:
    """Nummer, Bezeichnung, Ort der Treffer; `mehr` heißt: es gab mehr, als gezeigt wird."""
    rang = aehnlichkeit.rang(
        (m.Stueck.inventarnummer, m.Stueck.bezeichnung, m.Stueck.seriennummer), begriff, gemeinsam.aehnlichkeit_schwelle())
    zeilen = list(sitzung.db.execute(
        stuecke(sitzung).where(rang.bedingung).order_by(*rang.ordnung(), m.Stueck.inventarnummer).limit(hoechstens + 1)
    ).scalars())
    sichtbar = zeilen[:hoechstens]
    orte = standorte_offen(sitzung, [int(z.id) for z in sichtbar])
    namen = kostenstellen_namen(sitzung, {k for liste in orte.values() for k, _ in liste})
    treffer = [
        (z.inventarnummer, z.bezeichnung, ", ".join(namen.get(k, "") for k, _ in orte.get(int(z.id), [])).strip(", "))
        for z in sichtbar
    ]
    return treffer, len(zeilen) > hoechstens
