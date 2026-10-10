"""Der Tagesplan des Erinnerungsprozesses: wann ist der Lauf des Tages dran? Reine Funktionen, die Uhr kommt von außen."""

from __future__ import annotations

import datetime as dt
import re

STANDARD_UHRZEIT = "06:00"
_UHRZEIT = re.compile(r"^(\d{1,2}):(\d{2})$")


def uhrzeit(text: str) -> dt.time:
    """`HH:MM` (Ortszeit) als Uhrzeit; alles andere ist ein Fehler mit Satzschlüssel."""
    treffer = _UHRZEIT.match(text.strip())
    if treffer is None:
        raise ValueError("zeitplan.uhrzeit_ungueltig")
    stunde, minute = int(treffer.group(1)), int(treffer.group(2))
    if stunde > 23 or minute > 59:
        raise ValueError("zeitplan.uhrzeit_ungueltig")
    return dt.time(stunde, minute)


def uhrzeit_oder_standard(text: str) -> dt.time:
    """Die Uhrzeit der Einstellung; eine kaputte Angabe lässt den Prozess nicht stehen, es gilt der Standard."""
    try:
        return uhrzeit(text or STANDARD_UHRZEIT)
    except ValueError:
        return uhrzeit(STANDARD_UHRZEIT)


def tag_lesen(text: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(text.strip()) if text.strip() else None
    except ValueError:
        return None


def ist_dran(jetzt: dt.datetime, zeit: dt.time, letzter_lauf: dt.date | None) -> bool:
    """Der Lauf des Tages ist dran, wenn die Uhrzeit erreicht ist und heute noch keiner lief (ein verpasster Lauf holt nach)."""
    return jetzt.time().replace(tzinfo=None) >= zeit and letzter_lauf != jetzt.date()
