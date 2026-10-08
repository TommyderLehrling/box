"""Status eines Stuecks: erlaubte Wechsel, Pflicht zur Begruendung, Wirkung auf Buchung und Bestand."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Status = Literal["aktiv", "in_reparatur", "vermisst", "stillgelegt", "verkauft", "verschrottet"]
ALLE: tuple[str, ...] = ("aktiv", "in_reparatur", "vermisst", "stillgelegt", "verkauft", "verschrottet")
ENDZUSTAENDE: tuple[str, ...] = ("stillgelegt", "verkauft", "verschrottet")


@dataclass(frozen=True)
class StatusWechsel:
    von: Status
    nach: Status
    grund: str
    person: str
    zeit: datetime
    protokoll: str  # z. B. "stueck_status.stillgelegt"


def ist_endzustand(status: str) -> bool:
    """Stillgelegt, verkauft und verschrottet sind Endzustaende (Rueckkehr nur mit Grund)."""
    return status in ENDZUSTAENDE


def buchbar(status: str) -> bool:
    """Abgang und Eingang sind ausser in Endzustaenden moeglich (auch in Reparatur und vermisst)."""
    _pruefe_status(status)
    return not ist_endzustand(status)


def im_bestand(status: str) -> bool:
    """Endzustaende erscheinen nicht im Bestand einer Kostenstelle."""
    return buchbar(status)


def hinweis(status: str) -> str:
    """Schluessel des Hinweises fuer die Bestandsanzeige; leer bei normalem Status."""
    _pruefe_status(status)
    return {"in_reparatur": "stueck_status.hinweis_in_reparatur", "vermisst": "stueck_status.hinweis_vermisst"}.get(status, "")


def _pruefe_status(status: str) -> None:
    if status not in ALLE:
        raise ValueError("stueck_status.unbekannt")


def wechsle(aktuell: str, neu: str, grund: str, person: str, zeit: datetime) -> StatusWechsel:
    """Prueft den Wechsel; Grund ist Pflicht bei vermisst, bei Endzustaenden und bei der Rueckkehr aus ihnen."""
    _pruefe_status(aktuell)
    _pruefe_status(neu)
    if zeit.tzinfo is None or zeit.utcoffset() is None:
        raise ValueError("stueck_status.zeit_naiv")
    if not person.strip():
        raise ValueError("stueck_status.person_fehlt")
    if aktuell == neu:
        raise ValueError("stueck_status.unveraendert")
    if aktuell in ("verkauft", "verschrottet") and neu in ENDZUSTAENDE:
        raise ValueError("stueck_status.wechsel_nicht_erlaubt")
    braucht_grund = neu in ENDZUSTAENDE or neu == "vermisst" or aktuell in ENDZUSTAENDE
    if braucht_grund and not grund.strip():
        raise ValueError("stueck_status.grund_fehlt")
    return StatusWechsel(aktuell, neu, grund.strip(), person, zeit, f"stueck_status.{neu}")  # type: ignore[arg-type]
