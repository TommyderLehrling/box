"""Was der Dialog „Prüfung eintragen“ und die Prüfarten-Pflege an der Stück-Seite brauchen."""

from __future__ import annotations

from typing import Any

from digiassistenz_kern import Benutzer
from digiassistenz_kern.web import wahlfeld

from .. import modelle as m
from ..dienstlogik import pruefung
from . import helfer


def werte(sitzung: Any, zeile: m.Stueck, pruefart: str = "", weiter: str = "") -> dict[str, Any]:
    """Alles für die Dialoge; leer, wenn die Sitzung weder prüfen noch pflegen darf."""
    darf_pruefen = bool(sitzung.darf("inventar", "pruefen"))
    darf_pflegen = bool(sitzung.darf("inventar", "pflegen"))
    if not (darf_pruefen or darf_pflegen):
        return dict(pruefen_arten=[], pruefen_vorgabe="", pruefen_offen=False, pruefen_weiter="", pruefarten_stueck=[], pruefarten_dazu=[],
                    benutzer_auswahl=[], benutzer_ich=0, wahl_pruefer_lieferant=None, heute_iso="")
    arten = pruefung.pruefarten_des_stuecks(sitzung, zeile)
    aktive = [a for a in arten if a["aktiv"]]
    schluessel = {a["schluessel"] for a in aktive}
    vorgabe = pruefart if pruefart in schluessel else (aktive[0]["schluessel"] if len(aktive) == 1 else "")
    benutzer = []
    wahl = None
    if darf_pruefen:
        benutzer = [(int(b.id), b.name) for b in sitzung.db.execute(sitzung.abfrage(Benutzer).where(Benutzer.aktiv).order_by(Benutzer.name)).scalars()]
        wahl = wahlfeld.lieferant(sitzung, feld="pruefer_lieferant_id", leer="inventar.kein_lieferant", kennung="wahl-pruefer-lieferant")
    return dict(
        pruefen_arten=aktive, pruefen_vorgabe=vorgabe, pruefen_offen=darf_pruefen and bool(pruefart), pruefen_weiter=weiter,
        pruefarten_stueck=arten, pruefarten_dazu=pruefung.pruefarten_zum_hinzunehmen(sitzung, zeile) if darf_pflegen else [],
        benutzer_auswahl=benutzer, benutzer_ich=0 if sitzung.benutzer is None else int(sitzung.benutzer.id), wahl_pruefer_lieferant=wahl,
        heute_iso=helfer.heute().isoformat())
