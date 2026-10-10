"""Erinnerungen: überfällige Transfers an die Disposition und den Melder; Fälligkeiten (L13) an die Werkstatt.

Der Lauf ist **idempotent je Tag**: `erinnert_am` am Transfer verhindert eine zweite Mail. Empfänger kommen aus den
Funktionen des Kerns (`rechte.funktionen`); ob ein Konto aktiv ist und eine Adresse hat, prüft dieser Lauf.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from digiassistenz_kern import Benutzer, mail, protokoll, rechte, zeit
from digiassistenz_kern.texte import t

from .. import modelle as m
from ..rein import transfer as automat
from ..rein.stueck_status import im_bestand
from . import katalog, laden, pruefstand
from .stueckseite import ampel_hinweis

FUNKTION_DISPOSITION = "disposition"
FUNKTION_WERKSTATT = "werkstatt"
EINSTELLUNG_UM = "erinnern_um"
EINSTELLUNG_LETZTER = "erinnern_letzter_lauf"
EINSTELLUNG_PRUEFUNG_TAGE = "pruefung_erinnern_tage"
EINSTELLUNG_GESEHEN = "erinnern_pruefung_gesehen"
ZEILEN_IN_DER_MAIL = 50


@dataclass(frozen=True)
class Tageslauf:
    transfers: int
    pruefungen: int


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


def tageslauf(db: Any, mandant_id: int, heute: Any) -> Tageslauf | None:
    """Der Lauf des Tages — **idempotent je Tag**: der letzte Lauf steht in `einstellung`, ein zweiter am selben Tag tut nichts."""
    if katalog.einstellung(db, mandant_id, EINSTELLUNG_LETZTER) == heute.isoformat():
        return None
    ergebnis = Tageslauf(transfers=transfers_erinnern(db, mandant_id), pruefungen=pruefungen_erinnern(db, mandant_id, heute))
    katalog.setze_einstellung(db, mandant_id, EINSTELLUNG_LETZTER, heute.isoformat(), None)
    protokoll.schreiben(db, mandant_id=mandant_id, aktion="inventar.erinnern_lauf",
                        neu_wert=f"{heute.isoformat()} transfers={ergebnis.transfers} pruefungen={ergebnis.pruefungen}")
    return ergebnis


def _stufe(stand: Any, vorlauf_tage: int) -> str | None:
    """`ueberfaellig` bei roter Ampel, `bald` bei gelber, wenn die Frist nah ist (oder der Zähler es sagt); sonst nichts."""
    if stand.ampel == "rot":
        return "ueberfaellig"
    if stand.ampel == "gelb" and (stand.grund == "zaehler" or (stand.tage is not None and stand.tage <= vorlauf_tage)):
        return "bald"
    return None


def _schluessel(nummer: str, stand: Any, stufe: str) -> str:
    roh = f"{nummer}|{stand.pruefart}|{stufe}|{stand.faellig_am}"
    return hashlib.sha1(roh.encode("utf-8")).hexdigest()[:10]  # nur zum Wiedererkennen, nicht zur Sicherheit


def pruefungen_erinnern(db: Any, mandant_id: int, heute: Any) -> int:
    """Eine Mail an die Funktion `werkstatt`, wenn neue Fälligkeiten dazugekommen sind — montags auch mit allen Überfälligen.

    Was schon gemeldet wurde, merkt sich `einstellung` (kurze Kennungen, immer der aktuelle Stand). Liefert die Zahl der
    neu gemeldeten Fälligkeiten (0 = keine Mail).
    """
    vorlauf = int(katalog.einstellung(db, mandant_id, EINSTELLUNG_PRUEFUNG_TAGE, "14") or "14")
    stuecke = [z for z in db.execute(select(m.Stueck).where(m.Stueck.mandant_id == mandant_id).order_by(m.Stueck.inventarnummer)).scalars()
               if im_bestand(z.status)]
    arten = {p.schluessel: p.bezeichnung for p in db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mandant_id)).scalars()}
    treffer: list[tuple[str, str, Any, str, str]] = []  # (Kennung, Stufe, Stand, Nummer, Bezeichnung)
    for anfang in range(0, len(stuecke), 500):
        teil = stuecke[anfang:anfang + 500]
        staende = pruefstand.staende(db, mandant_id, teil, heute)
        for z in teil:
            for stand in staende.get(z.inventarnummer, []):
                stufe = _stufe(stand, vorlauf)
                if stufe is not None:
                    treffer.append((_schluessel(z.inventarnummer, stand, stufe), stufe, stand, z.inventarnummer, z.bezeichnung))
    gesehen = set(filter(None, katalog.einstellung(db, mandant_id, EINSTELLUNG_GESEHEN).split(",")))
    neu = [x for x in treffer if x[0] not in gesehen]
    katalog.setze_einstellung(db, mandant_id, EINSTELLUNG_GESEHEN, ",".join(sorted({x[0] for x in treffer})), None)
    montags = heute.weekday() == 0 and any(x[1] == "ueberfaellig" for x in treffer)
    if not neu and not montags:
        return 0
    an = adressen(db, mandant_id, FUNKTION_WERKSTATT)
    if not an:
        return 0
    zeilen_quelle = neu if neu else [x for x in treffer if x[1] == "ueberfaellig"]
    ueberfaellig = sum(1 for x in treffer if x[1] == "ueberfaellig")
    bald = sum(1 for x in treffer if x[1] == "bald")
    zeilen = [f"{nummer} {bezeichnung}: {arten.get(stand.pruefart, stand.pruefart)} — {ampel_hinweis(stand)}"
              for _, _, stand, nummer, bezeichnung in zeilen_quelle[:ZEILEN_IN_DER_MAIL]]
    if len(zeilen_quelle) > ZEILEN_IN_DER_MAIL:
        zeilen.append(t("inventar.erinnerung.pruefung_weitere", anzahl=len(zeilen_quelle) - ZEILEN_IN_DER_MAIL))
    text = "\n".join([t("inventar.erinnerung.pruefung_kopf", ueberfaellig=ueberfaellig, bald=bald), "", *zeilen, "", t("inventar.erinnerung.pruefung_fuss")])
    mail.einreihen(db, an=an, betreff=t("inventar.erinnerung.pruefung_betreff", ueberfaellig=ueberfaellig, bald=bald), text=text, mandant_id=mandant_id)
    return len(neu)
