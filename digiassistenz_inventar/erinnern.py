"""`python -m digiassistenz_inventar.erinnern` — einmal am Tag, vom Cron der Box angestoßen (kein Dauerprozess).

Reiht für jeden überfälligen Transfer eine Mail an die Disposition und den Melder ein und merkt es am Transfer.
Die Fälligkeits-Erinnerung an die Werkstatt kommt mit L13.
"""

from __future__ import annotations

import sys

from digiassistenz_kern import Mandant, hochlauf, zeit
from digiassistenz_kern.sitzung import einzelmandant

from .dienstlogik import erinnerungen


def main() -> int:
    hochlauf.hochlaufen(leise=True)
    with einzelmandant("inventar.erinnern") as sitzung:
        gesendet = erinnerungen.transfers_erinnern(sitzung.db, sitzung.kontext.mandant_id)
    sys.stdout.write(f"{zeit.heute().isoformat()} {gesendet}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
