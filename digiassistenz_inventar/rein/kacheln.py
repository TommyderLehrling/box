"""Posteingang-Kacheln des Inventars: eine Zeile je Zaehler (Text, Zahl, Weg, Recht); Zahl 0 entfaellt."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from .bestand import StueckInfo
from .pruefung import Pruefstand
from .stueck_status import im_bestand
from .transfer import Zustand, ueberfaellige
from .werkstatt import Meldung, Reparatur

WEG_UEBERSICHT = "/inventar"
WEG_HIER = "/inventar/hier"
WEG_FAELLIG = "/inventar/faellig"
WEG_VERWALTUNG = "/inventar/verwaltung"


@dataclass(frozen=True)
class Kachel:
    text_schluessel: str
    zahl: int
    weg: str
    recht: str


def kacheln(
    stuecke: Iterable[tuple[StueckInfo, Zustand]],
    pruefstaende: Mapping[str, Iterable[Pruefstand]],
    meldungen: Iterable[tuple[str, Meldung]],
    heute: date,
    reparaturen: Iterable[tuple[str, Reparatur]] = (),
    meine_kostenstellen: Iterable[int] = (),
    frist_werktage: int = 3,
    feiertage: Iterable[date] = (),
) -> tuple[Kachel, ...]:
    """Zaehlt aus, was auf den Stuecken (schon nach Rechten gefiltert) ansteht; nur Stuecke im Bestand zaehlen.

    meine_kostenstellen: die Kostenstellen aus Sitzung.kostenstellen_fuer("inventar", "scannen").
    "Meldungen offen" zaehlt nur den Status offen; "in Arbeit" zaehlt Stuecke mit einer angenommenen oder
    in Arbeit befindlichen Meldung oder einer Reparatur in Arbeit (ein Stueck einmal).
    """
    meine = frozenset(meine_kostenstellen)
    frei = tuple(feiertage)
    im_bestand_nummern: set[str] = set()
    an_mich = ueberfaellig = 0
    for info, zustand in stuecke:
        if not im_bestand(info.status):
            continue
        im_bestand_nummern.add(info.inventarnummer)
        an_mich += sum(1 for t in zustand.transfers if t.status == "angekuendigt" and t.nach_kostenstelle in meine)
        ueberfaellig += len(ueberfaellige(zustand, heute, frist_werktage, frei))
    faellig = ohne_nachweis = 0
    for nummer in im_bestand_nummern:
        for stand in pruefstaende.get(nummer, ()):
            faellig += stand.ampel in ("rot", "gelb")
            ohne_nachweis += stand.ampel == "unbekannt"
    offen = sum(1 for n, m in meldungen if n in im_bestand_nummern and m.status == "offen")
    in_arbeit = {n for n, m in meldungen if n in im_bestand_nummern and m.status in ("angenommen", "in_arbeit")}
    in_arbeit |= {n for n, r in reparaturen if n in im_bestand_nummern and r.status == "in_arbeit"}
    alle = (
        Kachel("inventar.kachel.pruefungen_faellig", faellig, WEG_FAELLIG, "inventar.pruefen"),
        Kachel("inventar.kachel.ohne_nachweis", ohne_nachweis, WEG_FAELLIG, "inventar.pruefen"),
        Kachel("inventar.kachel.transfers_an_mich", an_mich, WEG_HIER, "inventar.scannen"),
        Kachel("inventar.kachel.transfers_ueberfaellig", ueberfaellig, WEG_UEBERSICHT, "inventar.buchen"),
        Kachel("inventar.kachel.meldungen_offen", offen, WEG_UEBERSICHT, "inventar.werkstatt"),
        Kachel("inventar.kachel.in_arbeit", len(in_arbeit), WEG_UEBERSICHT, "inventar.werkstatt"),
    )
    return tuple(k for k in alle if k.zahl > 0)
