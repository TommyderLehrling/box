"""Transfer: Zustandsautomat der Buchung (Abgang, Eingang, Scan, Zurueckziehen)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from typing import Any, Literal

from .fristen import werktage_zwischen

Status = Literal["angekuendigt", "bestaetigt", "ueberholt", "zurueckgezogen"]
Quelle = Literal["web", "handy", "import", "system", "baustelle", "pruefung", "werkstatt"]
_QUELLEN = ("web", "handy", "import", "system", "baustelle", "pruefung", "werkstatt")


@dataclass(frozen=True)
class Standort:
    stueck: str
    kostenstelle: int
    menge: int
    von: datetime
    bis: datetime | None
    transfer_id: str | None
    quelle: Quelle
    von_person: str


@dataclass(frozen=True)
class Transfer:
    id: str
    stueck: str
    menge: int
    von_kostenstelle: int | None
    nach_kostenstelle: int
    status: Status
    abgang_am: datetime | None
    abgang_von: str | None
    eingang_am: datetime | None
    eingang_von: str | None
    grund: str
    quelle: Quelle
    eintrag_schluessel: str
    erinnert_am: datetime | None
    beendet_am: datetime | None = None  # gesetzt bei ueberholt/zurueckgezogen
    eingang_schluessel: str | None = None  # Eintrag-Schluessel des Scans, der den Eingang bestaetigt hat


@dataclass(frozen=True)
class Zustand:
    standorte: tuple[Standort, ...]
    transfers: tuple[Transfer, ...]


@dataclass(frozen=True)
class Aenderung:
    art: Literal["standort_neu", "standort_geschlossen", "transfer_neu", "transfer_geaendert", "meldung"]
    daten: dict[str, Any]


@dataclass(frozen=True)
class Ergebnis:
    zustand: Zustand
    aenderungen: tuple[Aenderung, ...]
    protokoll: tuple[str, ...]


class _Arbeit:
    """Sammelt die Aenderungen eines einzigen Aufrufs (lokal, nie global)."""

    def __init__(self, z: Zustand, person: str, zeit: datetime, quelle: str) -> None:
        self.standorte = list(z.standorte)
        self.transfers = list(z.transfers)
        self.aenderungen: list[Aenderung] = []
        self.protokoll: list[str] = []
        self.person, self.zeit, self.quelle = person, zeit, quelle

    def _kopf(self, **felder: Any) -> dict[str, Any]:
        return {"person": self.person, "zeit": self.zeit, "quelle": self.quelle, **felder}

    def standort_oeffnen(self, stueck: str, ks: int, menge: int, transfer_id: str | None) -> Standort:
        s = Standort(stueck, ks, menge, self.zeit, None, transfer_id, self.quelle, self.person)  # type: ignore[arg-type]
        self.standorte.append(s)
        self.aenderungen.append(Aenderung("standort_neu", self._kopf(**asdict(s))))
        return s

    def standort_schliessen(self, s: Standort) -> None:
        self.standorte[self.standorte.index(s)] = replace(s, bis=self.zeit)
        self.aenderungen.append(Aenderung("standort_geschlossen", self._kopf(
            stueck=s.stueck, kostenstelle=s.kostenstelle, menge=s.menge,
            transfer_id=s.transfer_id, bis=self.zeit)))

    def transfer_neu(self, t: Transfer) -> None:
        self.transfers.append(t)
        self.aenderungen.append(Aenderung("transfer_neu", self._kopf(**asdict(t))))

    def transfer_aendern(self, t: Transfer, **felder: Any) -> Transfer:
        neu = replace(t, **felder)
        self.transfers[self.transfers.index(t)] = neu
        self.aenderungen.append(Aenderung("transfer_geaendert", self._kopf(id=t.id, felder=felder)))
        return neu

    def ergebnis(self) -> Ergebnis:
        return Ergebnis(Zustand(tuple(self.standorte), tuple(self.transfers)),
                        tuple(self.aenderungen), tuple(self.protokoll))


def _pruefe(z: Zustand, stueck: str, person: str, zeit: datetime, quelle: str | None = None) -> None:
    """Prueft Zeitzone, Person, Quelle und dass der Zustand nur dieses Stueck enthaelt."""
    if not isinstance(zeit, datetime) or zeit.tzinfo is None or zeit.utcoffset() is None:
        raise ValueError("transfer.zeit_naiv")
    if not person.strip():
        raise ValueError("transfer.person_fehlt")
    if quelle is not None and quelle not in _QUELLEN:
        raise ValueError("transfer.quelle_unbekannt")
    if any(s.stueck != stueck for s in z.standorte) or any(t.stueck != stueck for t in z.transfers):
        raise ValueError("transfer.stueck_fremd")


def _offen(z: Zustand) -> list[Standort]:
    return [s for s in z.standorte if s.bis is None]


def _offene_transfers(z: Zustand) -> list[Transfer]:
    return [t for t in z.transfers if t.status == "angekuendigt"]


def _finde(z: Zustand, transfer_id: str) -> Transfer:
    for t in z.transfers:
        if t.id == transfer_id:
            return t
    raise ValueError("transfer.unbekannt")


def _ohne(z: Zustand, schluessel: str) -> Ergebnis:
    return Ergebnis(z, (), (schluessel,))


def _eingang_anwenden(a: _Arbeit, t: Transfer) -> None:
    """Verkleinert bzw. schliesst die Quelle und oeffnet bzw. mehrt das Ziel."""
    if t.von_kostenstelle is not None:
        quelle = next((s for s in a.standorte if s.bis is None and s.kostenstelle == t.von_kostenstelle), None)
        if quelle is not None:
            a.standort_schliessen(quelle)
            if quelle.menge > t.menge:
                a.standort_oeffnen(t.stueck, quelle.kostenstelle, quelle.menge - t.menge, t.id)
    menge = t.menge
    ziel = next((s for s in a.standorte if s.bis is None and s.kostenstelle == t.nach_kostenstelle), None)
    if ziel is not None:
        a.standort_schliessen(ziel)
        menge += ziel.menge
    a.standort_oeffnen(t.stueck, t.nach_kostenstelle, menge, t.id)


def abgang_buchen(
    z: Zustand, stueck: str, von_ks: int, nach_ks: int, menge: int, person: str,
    zeit: datetime, quelle: Quelle, eintrag_schluessel: str, grund: str = "",
) -> Ergebnis:
    """Bucht den Abgang auf von_ks; das Stueck gilt auf nach_ks als angekuendigt."""
    _pruefe(z, stueck, person, zeit, quelle)
    if von_ks == nach_ks:
        raise ValueError("transfer.gleiche_kostenstelle")
    if menge < 1:
        raise ValueError("transfer.menge_ungueltig")
    if not eintrag_schluessel.strip():
        raise ValueError("transfer.eintrag_schluessel_fehlt")
    if any(t.eintrag_schluessel == eintrag_schluessel for t in z.transfers):
        return _ohne(z, "transfer.doppelt")
    a = _Arbeit(z, person, zeit, quelle)
    offen = _offen(z)
    src = next((s for s in offen if s.kostenstelle == von_ks), None)
    if src is None:
        if offen:
            raise ValueError("transfer.nicht_auf_kostenstelle")
        src = a.standort_oeffnen(stueck, von_ks, menge, None)
        a.protokoll.append("transfer.erstanlage")
    belegt = sum(t.menge for t in _offene_transfers(z) if t.von_kostenstelle == von_ks)
    if menge > src.menge - belegt:
        raise ValueError("transfer.menge_zu_gross")
    tid = "t:" + eintrag_schluessel
    a.transfer_neu(Transfer(tid, stueck, menge, von_ks, nach_ks, "angekuendigt", zeit, person,
                            None, None, grund, quelle, eintrag_schluessel, None))
    a.protokoll.append("transfer.abgang")
    return a.ergebnis()


def eingang_bestaetigen(
    z: Zustand, transfer_id: str, person: str, zeit: datetime, quelle: Quelle, menge: int | None = None,
    eingang_schluessel: str | None = None,
) -> Ergebnis:
    """Bestaetigt den Eingang (optional Teilmenge): Quelle verkleinern, Ziel oeffnen, Fehlmenge neu ankuendigen."""
    t = _finde(z, transfer_id)
    _pruefe(z, t.stueck, person, zeit, quelle)
    if t.status == "bestaetigt":
        return _ohne(z, "transfer.schon_bestaetigt")
    if t.status != "angekuendigt":
        raise ValueError("transfer.nicht_offen")
    if t.abgang_am is not None and zeit < t.abgang_am:
        raise ValueError("transfer.zeit_rueckwaerts")
    if menge is not None and menge < 1:
        raise ValueError("transfer.menge_ungueltig")
    if menge is not None and menge > t.menge:
        raise ValueError("transfer.menge_zu_gross")
    a = _Arbeit(z, person, zeit, quelle)
    fehl = 0 if menge is None else t.menge - menge
    if fehl:
        t = a.transfer_aendern(t, status="bestaetigt", eingang_am=zeit, eingang_von=person,
                              menge=menge, eingang_schluessel=eingang_schluessel)
        schluessel = t.eintrag_schluessel + "|fehlmenge"
        a.transfer_neu(Transfer("t:" + schluessel, t.stueck, fehl, t.von_kostenstelle, t.nach_kostenstelle,
                                "angekuendigt", t.abgang_am, t.abgang_von, None, None, "transfer.fehlmenge",
                                t.quelle, schluessel, None))
        a.protokoll.append("transfer.fehlmenge")
    else:
        t = a.transfer_aendern(t, status="bestaetigt", eingang_am=zeit, eingang_von=person,
                               eingang_schluessel=eingang_schluessel)
    _eingang_anwenden(a, t)
    a.protokoll.append("transfer.eingang")
    return a.ergebnis()


def scan_ist_hier(
    z: Zustand, stueck: str, ks: int, person: str, zeit: datetime, quelle: Quelle,
    eintrag_schluessel: str, menge: int | None = None,
) -> Ergebnis:
    """Verarbeitet einen Scan auf ks: bestaetigt, ueberholt, bucht system-seitig oder sieht nur."""
    _pruefe(z, stueck, person, zeit, quelle)
    if not eintrag_schluessel.strip():
        raise ValueError("transfer.eintrag_schluessel_fehlt")
    if menge is not None and menge < 1:
        raise ValueError("transfer.menge_ungueltig")
    if any(eintrag_schluessel in (t.eintrag_schluessel, t.eingang_schluessel) for t in z.transfers):
        return _ohne(z, "transfer.doppelt")
    offene = _offene_transfers(z)
    hierher = [t for t in offene if t.nach_kostenstelle == ks]
    if hierher:
        if len(hierher) > 1:
            raise ValueError("transfer.mehrdeutig")
        return eingang_bestaetigen(z, hierher[0].id, person, zeit, quelle, menge, eintrag_schluessel)
    offen = _offen(z)
    if any(s.kostenstelle == ks for s in offen):
        return _ohne(z, "inventur.gesehen")
    a = _Arbeit(z, person, zeit, quelle)
    tid = "t:" + eintrag_schluessel
    if offene:
        if len(offene) > 1:
            raise ValueError("transfer.mehrdeutig")
        alt = offene[0]
        if menge is not None and menge != alt.menge:
            raise ValueError("transfer.menge_abweichend")
        a.transfer_aendern(alt, status="ueberholt", grund=f"transfer.gesehen_auf:{ks}", beendet_am=zeit)
        a.protokoll.append("transfer.ueberholt")
        neu = Transfer(tid, stueck, alt.menge, alt.von_kostenstelle, ks, "bestaetigt", zeit, person,
                       zeit, person, "", "system", eintrag_schluessel, None)
        a.protokoll.append("transfer.abgang_system")
    elif offen:
        if len(offen) > 1:
            raise ValueError("transfer.mehrdeutig")
        src = offen[0]
        wieviel = src.menge if menge is None else menge
        if wieviel > src.menge:
            raise ValueError("transfer.menge_zu_gross")
        neu = Transfer(tid, stueck, wieviel, src.kostenstelle, ks, "bestaetigt", zeit, person,
                       zeit, person, "", "system", eintrag_schluessel, None)
        a.protokoll.append("transfer.abgang_system")
    else:
        neu = Transfer(tid, stueck, 1 if menge is None else menge, None, ks, "bestaetigt", None, None,
                       zeit, person, "", quelle, eintrag_schluessel, None)
        a.protokoll.append("transfer.erstanlage")
    a.transfer_neu(neu)
    _eingang_anwenden(a, neu)
    a.protokoll.append("transfer.eingang")
    return a.ergebnis()


def zurueckziehen(
    z: Zustand, transfer_id: str, grund: str, person: str, zeit: datetime, quelle: Quelle = "web"
) -> Ergebnis:
    """Zieht einen angekuendigten Transfer mit Grund zurueck (nichts wird geloescht)."""
    t = _finde(z, transfer_id)
    _pruefe(z, t.stueck, person, zeit, quelle)
    if not grund.strip():
        raise ValueError("transfer.grund_fehlt")
    if t.status != "angekuendigt":
        raise ValueError("transfer.nicht_zurueckziehbar")
    a = _Arbeit(z, person, zeit, quelle)
    a.transfer_aendern(t, status="zurueckgezogen", grund=grund, beendet_am=zeit)
    a.protokoll.append("transfer.zurueckgezogen")
    return a.ergebnis()


def ueberfaellige(
    z: Zustand, heute: date, frist_werktage: int, feiertage: Iterable[date] = ()
) -> tuple[Transfer, ...]:
    """Angekuendigte, noch nicht erinnerte Transfers, deren Frist in Werktagen erreicht ist."""
    frei = frozenset(feiertage)
    return tuple(
        t for t in z.transfers
        if t.status == "angekuendigt" and t.erinnert_am is None and t.abgang_am is not None
        and werktage_zwischen(t.abgang_am.date(), heute, frei) >= frist_werktage
    )


def erinnert(z: Zustand, transfer_id: str, zeit: datetime) -> Ergebnis:
    """Merkt, dass zu diesem Transfer erinnert wurde."""
    t = _finde(z, transfer_id)
    _pruefe(z, t.stueck, "system", zeit)
    if t.status != "angekuendigt":
        raise ValueError("transfer.nicht_offen")
    if t.erinnert_am is not None:
        return _ohne(z, "transfer.schon_erinnert")
    a = _Arbeit(z, "system", zeit, "system")
    a.transfer_aendern(t, erinnert_am=zeit)
    a.protokoll.append("transfer.erinnert")
    return a.ergebnis()


def status_auf(z: Zustand, ks: int, tag: date) -> tuple[tuple[int, Literal["vor_ort", "angekuendigt"]], ...]:
    """Zeilen (menge, status) auf der Kostenstelle am Tag; Eingangstag zaehlt zum Ziel."""
    zeilen: list[tuple[int, Literal["vor_ort", "angekuendigt"]]] = []
    for s in z.standorte:
        if s.kostenstelle == ks and s.von.date() <= tag and (s.bis is None or tag < s.bis.date()):
            zeilen.append((s.menge, "vor_ort"))
    for t in z.transfers:
        if t.nach_kostenstelle != ks or t.abgang_am is None:
            continue
        if t.status == "angekuendigt":
            ende = None
        elif t.status == "bestaetigt" and t.eingang_am is not None:
            ende = t.eingang_am.date()
        elif t.status in ("ueberholt", "zurueckgezogen") and t.beendet_am is not None:
            ende = t.beendet_am.date()
        else:
            continue
        if t.abgang_am.date() <= tag and (ende is None or tag < ende):
            zeilen.append((t.menge, "angekuendigt"))
    return tuple(zeilen)


def _verbinde(a: Ergebnis, b: Ergebnis) -> Ergebnis:
    return Ergebnis(b.zustand, a.aenderungen + b.aenderungen, a.protokoll + b.protokoll)


def zubehoer_folgt(
    hauptstueck_ergebnis: Ergebnis, zubehoer: Iterable[str], zustaende: dict[str, Zustand], zeit: datetime
) -> dict[str, Ergebnis]:
    """Wiederholt die Buchung des Hauptstuecks fuer jedes Zubehoerstueck (Quelle system)."""
    haupt = hauptstueck_ergebnis.zustand
    ergebnisse: dict[str, Ergebnis] = {}
    for stueck in zubehoer:
        if stueck not in zustaende:
            raise ValueError("transfer.zubehoer_unbekannt")
        erg = Ergebnis(zustaende[stueck], (), ())
        for aend in hauptstueck_ergebnis.aenderungen:
            d, z = aend.daten, erg.zustand
            person = d["person"]
            if aend.art == "transfer_neu" and d["grund"] == "transfer.fehlmenge":
                continue
            if aend.art == "transfer_neu":
                schluessel = f"{d['id']}|{stueck}"
                if d["status"] == "angekuendigt":
                    offen = [s for s in _offen(z) if s.kostenstelle == d["von_kostenstelle"]]
                    if _offen(z) and not offen:
                        schritt = _ohne(z, "zubehoer.nicht_am_ort")
                    else:
                        wieviel = offen[0].menge if offen else 1
                        schritt = abgang_buchen(z, stueck, d["von_kostenstelle"], d["nach_kostenstelle"],
                                                wieviel, person, zeit, "system", schluessel, d["grund"])
                else:
                    schritt = scan_ist_hier(z, stueck, d["nach_kostenstelle"], person, zeit, "system", schluessel)
            elif aend.art == "transfer_geaendert" and "status" in d["felder"]:
                haupt_t = _finde(haupt, d["id"])
                neu_status = d["felder"]["status"]
                if neu_status == "bestaetigt":
                    schritt = scan_ist_hier(z, stueck, haupt_t.nach_kostenstelle, person, zeit, "system",
                                            f"{d['id']}|{stueck}|eingang")
                elif neu_status == "zurueckgezogen":
                    passend = [t for t in _offene_transfers(z)
                               if (t.von_kostenstelle, t.nach_kostenstelle) == (haupt_t.von_kostenstelle, haupt_t.nach_kostenstelle)]
                    schritt = (zurueckziehen(z, passend[0].id, d["felder"]["grund"], person, zeit)
                               if passend else _ohne(z, "zubehoer.nichts_zurueckzuziehen"))
                else:
                    continue
            else:
                continue
            erg = _verbinde(erg, schritt)
        ergebnisse[stueck] = erg
    return ergebnisse
