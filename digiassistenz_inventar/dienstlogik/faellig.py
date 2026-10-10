"""Die Fällig-Liste: überfällig · fällig · ohne Nachweis — aus den Prüfständen der sichtbaren Stücke im Bestand."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import zeit

from .. import modelle as m
from ..rein import pruefung as rein
from ..rein.stueck_status import im_bestand
from . import liste, pruefstand, sicht
from .liste import AMPEL_ZEICHEN
from .stueckseite import ampel_hinweis

ZEILEN_JE_BLOCK = 200


@dataclass(frozen=True)
class Filter:
    pruefart: str = ""  # Schlüssel der Prüfart
    kostenstelle: str = ""  # Nummer
    gruppe: str = ""  # Schlüssel

    def als_weg(self) -> str:
        from urllib.parse import urlencode

        return urlencode({k: v for k, v in (("pruefart", self.pruefart), ("kostenstelle", self.kostenstelle), ("gruppe", self.gruppe)) if v})


@dataclass
class Block:
    zeilen: list[dict[str, Any]] = field(default_factory=list)
    gesamt: int = 0

    @property
    def gekuerzt(self) -> bool:
        return self.gesamt > len(self.zeilen)


@dataclass
class Uebersicht:
    ueberfaellig: Block
    faellig: Block
    ohne_nachweis: Block
    gelesen: int  # wie viele Stücke angesehen wurden
    abgeschnitten: bool  # mehr Stücke vorhanden, als gelesen werden (dann Filter nutzen)


def _zeilen(paare: list[tuple[str, rein.Pruefstand]], stuecke: dict[str, m.Stueck], arten: dict[str, str], gruppen: dict[int, str],
            orte: dict[int, str]) -> list[dict[str, Any]]:
    ergebnis = []
    for nummer, stand in paare[:ZEILEN_JE_BLOCK]:
        s = stuecke[nummer]
        ergebnis.append({
            "id": int(s.id), "nummer": nummer, "bezeichnung": s.bezeichnung, "gruppe": gruppen.get(int(s.gruppe_id), ""),
            "ort": orte.get(int(s.id), ""), "pruefart": stand.pruefart, "pruefart_name": arten.get(stand.pruefart, stand.pruefart),
            "ampel": stand.ampel, "zeichen": AMPEL_ZEICHEN[stand.ampel], "faellig_am": stand.faellig_am, "hinweis": ampel_hinweis(stand)})
    return ergebnis


def uebersicht(sitzung: Any, f: Filter) -> Uebersicht:
    """Nur Stücke im Bestand (keine verkauften, verschrotteten …) und nur, was die Sitzung sehen darf."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    abfrage = liste._abfrage(sitzung, liste.Filter(kostenstelle=f.kostenstelle, gruppe=f.gruppe)).order_by(m.Stueck.inventarnummer)
    gelesen = list(db.execute(abfrage.limit(liste.HOECHSTENS + 1)).scalars())
    abgeschnitten = len(gelesen) > liste.HOECHSTENS
    stuecke = [s for s in gelesen[:liste.HOECHSTENS] if im_bestand(s.status)]
    staende = pruefstand.staende(db, mid, stuecke, zeit.heute())
    paare = [(n, s) for n, standliste in staende.items() for s in standliste if not f.pruefart or s.pruefart == f.pruefart]
    nach_nummer = {s.inventarnummer: s for s in stuecke}
    arten = {p.schluessel: p.bezeichnung for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid)).scalars()}
    gruppen = {int(g.id): g.bezeichnung for g in db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    ids = [int(s.id) for s in stuecke]
    orte_roh = sicht.standorte_offen(sitzung, ids) if ids else {}
    namen = sicht.kostenstellen_namen(sitzung, {k for liste_ in orte_roh.values() for k, _ in liste_}) if orte_roh else {}
    orte = {sid: ", ".join(namen.get(k, "") for k, _ in eintraege) for sid, eintraege in orte_roh.items()}

    def block(auswahl: list[tuple[str, rein.Pruefstand]]) -> Block:
        return Block(_zeilen(auswahl, nach_nummer, arten, gruppen, orte), len(auswahl))

    return Uebersicht(
        block(rein.faellig_liste(paare, nur=("rot",))), block(rein.faellig_liste(paare, nur=("gelb",))), block(rein.ohne_nachweis(paare)),
        len(stuecke), abgeschnitten)
