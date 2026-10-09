"""Erinnerungen: überfällige Transfers an die Disposition und den Melder; Fälligkeiten (L13) an die Werkstatt.

Der Lauf ist **idempotent je Tag**: `erinnert_am` am Transfer verhindert eine zweite Mail. Empfänger kommen aus den
Funktionen des Kerns (`rechte.funktionen`); ob ein Konto aktiv ist und eine Adresse hat, prüft dieser Lauf.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Benutzer, mail, protokoll, rechte, zeit
from digiassistenz_kern.texte import t

from .. import modelle as m
from ..rein import transfer as automat
from . import katalog, laden

FUNKTION_DISPOSITION = "disposition"
FUNKTION_WERKSTATT = "werkstatt"


def adressen(db: Any, mandant_id: int, art: str, zusaetzlich: tuple[int, ...] = ()) -> list[str]:
    """Adressen der aktiven Konten, die diese Funktion tragen, dazu weitere Konten (z. B. der Melder)."""
    ids = {int(f.benutzer_id) for f in rechte.funktionen(db, mandant_id=mandant_id, art=art)} | set(zusaetzlich)
    if not ids:
        return []
    konten = db.execute(select(Benutzer).where(Benutzer.mandant_id == mandant_id, Benutzer.id.in_(ids), Benutzer.aktiv)).scalars()
    return sorted({k.benachrichtigung_email or k.email for k in konten if (k.benachrichtigung_email or k.email)})


def transfers_erinnern(db: Any, mandant_id: int) -> int:
    """Mail für jeden überfälligen, noch nicht erinnerten Transfer; setzt `erinnert_am`. Liefert die Zahl der Mails."""
    heute, jetzt = zeit.heute(), zeit.jetzt_utc()
    frist = int(katalog.einstellung(db, mandant_id, "transfer_frist_werktage", "3"))
    offen = db.execute(select(m.Stueck).where(m.Stueck.id.in_(
        select(m.Transfer.stueck_id).where(m.Transfer.mandant_id == mandant_id, m.Transfer.status == "angekuendigt",
                                           m.Transfer.erinnert_am.is_(None))))).scalars().all()
    zustaende = laden.lade_zustaende(db, mandant_id, list(offen))
    namen = {s.inventarnummer: s for s in offen}
    gesendet = 0
    for nummer, z in zustaende.items():
        for ueberfaellig in automat.ueberfaellige(z, heute, frist):
            erg = automat.erinnert(z, ueberfaellig.id, jetzt)
            laden.speichern(db, mandant_id, namen[nummer], erg)
            melder = laden.benutzer_id(ueberfaellig.abgang_von)
            an = adressen(db, mandant_id, FUNKTION_DISPOSITION, () if melder is None else (melder,))
            if an:
                mail.einreihen(db, an=an, betreff=t("inventar.erinnerung.betreff", nummer=nummer),
                               text=t("inventar.erinnerung.transfer", tage=frist) + f": {nummer}", mandant_id=mandant_id)
                gesendet += 1
            protokoll.schreiben(db, mandant_id=mandant_id, aktion="inventar.transfer_erinnert", objekt_typ="inventar.stueck",
                                objekt_id=int(namen[nummer].id), neu_wert=nummer)
    return gesendet
