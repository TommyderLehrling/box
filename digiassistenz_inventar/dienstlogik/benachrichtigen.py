"""Die **eine** Stelle, über die das Inventar Benachrichtigungen an Personen schickt (Kern-Vertrag `mail.einreihen`).

Alle Mails des Moduls laufen hier durch — nirgends sonst steht `mail.einreihen`. Mit Block V kommt an dieser Stelle die
Kern-Meldung je Person dazu, ohne dass sich eine Aufrufstelle ändert.

Regeln des Kerns, die hier gelten:

* alle Argumente nach `db` nur als Schlüsselwörter;
* `mandant_id` immer — sonst wird die Mail ein Vorgang der Box statt der Firma;
* eingereiht wird nur, versendet wird heute nichts (die Zeile in `kern.mail_ausgang` hat den Status `wartend`).

Eine Mail blockiert nie die Handlung, die sie auslöst: ohne Adresse oder bei einem Fehler im Einreihen steht ein Vermerk im
Protokoll (`inventar.mail_ohne_adresse`, `inventar.mail_nicht_eingereiht`), und die Handlung gilt.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Benutzer, mail, protokoll
from digiassistenz_kern.texte import t

_log = logging.getLogger(__name__)

PRAEFIX = "inventar.mail."


def konto(db: Any, mandant_id: int, benutzer: Any) -> Benutzer | None:
    """Das aktive Konto dieses Mandanten zu einer Id oder einer Zeile; sonst `None`."""
    kennung = benutzer if isinstance(benutzer, int) else getattr(benutzer, "id", None)
    if kennung is None:
        return None
    return db.execute(select(Benutzer).where(Benutzer.mandant_id == mandant_id, Benutzer.id == int(kennung), Benutzer.aktiv)).scalar_one_or_none()


def adresse_von(zeile: Benutzer | None) -> str:
    """`benachrichtigung_email`, sonst `email`; leer, wenn das Konto keine hat."""
    return "" if zeile is None else (zeile.benachrichtigung_email or zeile.email or "")


def _vermerk(db: Any, mandant_id: int, aktion: str, schluessel: str, benutzer: Any, objekt_id: int | None, von: int | None) -> None:
    kennung = benutzer if isinstance(benutzer, int) else getattr(benutzer, "id", None)
    protokoll.schreiben(db, mandant_id=mandant_id, aktion=f"inventar.{aktion}", objekt_typ="inventar.stueck" if objekt_id else None,
                        objekt_id=objekt_id, neu_wert=f"{schluessel}: {kennung}", benutzer_id=von)


def benachrichtigen(
    db: Any, benutzer: Any, schluessel: str, *, mandant_id: int, von: int | None = None, objekt_id: int | None = None, **felder: Any,
) -> bool:
    """Reiht die Mail `inventar.mail.<schluessel>` (Betreff und Text mit den `felder`) für diese Person ein.

    `benutzer` ist die Id oder die Zeile des Empfängers; `von` ist die handelnde Person, `objekt_id` das Stück, an dessen
    Verlauf ein Vermerk gehört. Liefert `True`, wenn eine Mail in der Warteschlange steht. Ohne aktives Konto oder ohne
    Adresse wird nichts eingereiht, sondern vermerkt; scheitert das Einreihen, bleibt die Handlung gültig und der Vermerk
    sagt es. Das Einreihen läuft in einer Teiltransaktion, damit ein Fehler dort die Handlung nicht mitnimmt.
    """
    zeile = konto(db, mandant_id, benutzer)
    adresse = adresse_von(zeile)
    if not adresse:
        _vermerk(db, mandant_id, "mail_ohne_adresse", schluessel, benutzer, objekt_id, von)
        return False
    try:
        with db.begin_nested():
            mail.einreihen(
                db, an=[adresse], betreff=t(f"{PRAEFIX}{schluessel}.betreff", **felder), text=t(f"{PRAEFIX}{schluessel}.text", **felder),
                mandant_id=mandant_id, benutzer_id=von)
    except Exception:  # noqa: BLE001 — eine Mail darf nie die Handlung kippen, die sie auslöst
        _log.exception("inventar.mail_nicht_eingereiht %s", schluessel)
        _vermerk(db, mandant_id, "mail_nicht_eingereiht", schluessel, benutzer, objekt_id, von)
        return False
    return True
