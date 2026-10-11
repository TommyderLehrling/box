"""Stichtags-Inventur (E10, G5): Stichtag setzen, je Kostenstelle „gesehen / nicht gesehen“, Vermisst **vorschlagen**, CSV.

Gesehen heißt: seit dem Stichtag gescannt („Ist hier“ auf der Kostenstelle, auf der das Stück schon stand) oder dort eingegangen
(ein bestätigter Eingang ist ein Scan). Nicht Gesehenes wird nur **vorgeschlagen**: der Status `vermisst` wird nie automatisch gesetzt,
sondern von Hand, mit Grund, je Zeile (`status_wechseln`, Recht `stilllegen`).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from digiassistenz_kern import Protokoll, protokoll, zeit
from digiassistenz_kern.web import gemeinsam

from .. import modelle as m
from ..rein import inventur as rein
from ..rein.stueck_status import ENDZUSTAENDE
from . import katalog, kostenrechnung, sicht
from . import stueck as fachstueck

EINSTELLUNG = "inventur_stichtag"
EINSTELLUNG_LETZTE = "inventur_letzte"  # `<Stichtag>|<Pfad der CSV relativ zum Arbeitsordner>` der zuletzt abgeschlossenen Inventur
_ORT = re.compile(r"^ks:(\d+)(?:;menge:(\d+))?$")  # Ort der Sichtung, auf Wunsch mit der gezählten Menge


def _benutzer(sitzung: Any) -> int | None:
    return None if sitzung.benutzer is None else int(sitzung.benutzer.id)


def darf_inventur(sitzung: Any) -> bool:
    return bool(sitzung.darf("inventar", "stilllegen") or sitzung.darf("inventar", "einstellen"))


def fordern(sitzung: Any) -> None:
    if not darf_inventur(sitzung):
        raise gemeinsam.KeinRecht("inventar", "stilllegen")


def stichtag(db: Any, mandant_id: int) -> dt.date | None:
    text = katalog.einstellung(db, mandant_id, EINSTELLUNG)
    try:
        return dt.date.fromisoformat(text) if text else None
    except ValueError:
        return None


def stichtag_setzen(sitzung: Any, datum: dt.date | None) -> None:
    """Setzt den Stichtag (Recht `einstellen`); ein Datum in der Zukunft gibt es nicht. Leer nimmt den Stichtag zurück."""
    if not sitzung.darf("inventar", "einstellen"):
        raise gemeinsam.KeinRecht("inventar", "einstellen")
    if datum is not None and datum > zeit.heute():
        raise ValueError("inventur.stichtag_zukunft")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    alt = katalog.einstellung(db, mid, EINSTELLUNG)
    neu = "" if datum is None else datum.isoformat()
    if alt != neu:
        katalog.setze_einstellung(db, mid, EINSTELLUNG, neu, _benutzer(sitzung))
        protokoll.schreiben(db, mandant_id=mid, aktion="inventar.inventur_stichtag", objekt_typ="inventar.einstellung", alt_wert=alt or None,
                            neu_wert=neu or None, benutzer_id=_benutzer(sitzung))


@dataclass(frozen=True)
class Zeile:
    stueck_id: int
    nummer: str
    bezeichnung: str
    kostenstelle: int
    erwartet: int
    gesehen: int
    ergebnis: str  # gesehen | teilweise | nicht_gesehen | woanders | wieder_aufgetaucht | vermisst
    woanders_auf: int | None = None
    vorschlag: bool = False  # nicht gesehen und nirgends sonst: Vermisst darf vorgeschlagen werden


@dataclass(frozen=True)
class Bericht:
    stichtag: dt.date
    je_kostenstelle: dict[int, list[Zeile]]
    namen: dict[int, str]
    gesehen: int = 0
    nicht_gesehen: int = 0
    unbekannt: tuple[str, ...] = field(default_factory=tuple)


def _sichtungen(sitzung: Any, anfang: dt.datetime, erlaubt: tuple[int, ...] | None) -> dict[tuple[int, int], int | None]:
    """(Stück, Kostenstelle) → genannte Menge oder `None` (= so viel wie erwartet), aus den Scans „Ist hier“ seit dem Stichtag.

    Mehrere Sichtungen desselben Stücks auf derselben Kostenstelle ergeben **eine** (die jüngste gilt): wer sich vertippt hat, scannt noch einmal
    und nennt die richtige Zahl. Ein gewöhnlicher Scan ohne Menge macht eine genannte Menge nicht rückgängig.
    """
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    letzte: dict[tuple[int, int], int | None] = {}
    abfrage = select(Protokoll).where(Protokoll.mandant_id == mid, Protokoll.aktion == "inventar.inventur_gesehen", Protokoll.zeitpunkt >= anfang,
                                      Protokoll.objekt_typ == "inventar.stueck").order_by(Protokoll.zeitpunkt, Protokoll.id)
    for p in db.execute(abfrage).scalars():
        treffer = _ORT.match(p.alt_wert or "")
        if treffer is not None and p.objekt_id is not None and (erlaubt is None or int(treffer.group(1)) in erlaubt):
            schluessel = (int(p.objekt_id), int(treffer.group(1)))
            menge = None if treffer.group(2) is None else int(treffer.group(2))
            if menge is None and letzte.get(schluessel) is not None:
                continue  # ein gewöhnlicher Scan macht eine genannte Menge nicht rückgängig
            letzte[schluessel] = menge
    return letzte


def _gesehen_seit(sitzung: Any, anfang: dt.datetime, nummern: dict[int, str], erlaubt: tuple[int, ...] | None) -> list[tuple[int, int, int | None]]:
    """(Stück, Kostenstelle, Menge oder `None` = so viel wie erwartet) aus Scans und bestätigten Eingängen seit dem Stichtag."""
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    ergebnis: list[tuple[int, int, int | None]] = [(sid, ks, menge) for (sid, ks), menge in _sichtungen(sitzung, anfang, erlaubt).items()]
    q = select(m.Standort).where(m.Standort.mandant_id == mid, m.Standort.transfer_id.is_not(None), m.Standort.von >= anfang)
    if erlaubt is not None:
        q = q.where(m.Standort.kostenstelle_id.in_(erlaubt))
    for s in db.execute(q).scalars():
        ergebnis.append((int(s.stueck_id), int(s.kostenstelle_id), int(s.menge)))
    return ergebnis


def zaehlen_abfragen(sitzung: Any, stueck: m.Stueck, kostenstelle_id: int) -> int | None:
    """Die Zahl, mit der das Feld „Menge vor Ort“ beim Scan vorbelegt ist — sonst `None` (es wird nicht gefragt).

    Gefragt wird, wenn eine Inventur läuft (Stichtag gesetzt), das Stück ein Mengenartikel ist und auf dieser Kostenstelle steht. Vorbelegt ist die
    Buchmenge; wurde hier seit dem Stichtag schon gezählt, die zuletzt genannte Menge — wer sich vertippt hat, scannt noch einmal und
    nennt die richtige Zahl (die jüngste Sichtung gilt). Gebucht wird dabei nichts.
    """
    if stueck.art != "menge" or stueck.status in ENDZUSTAENDE:
        return None
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    tag = stichtag(db, mid)
    if tag is None:
        return None
    buch = buchmenge(db, mid, int(stueck.id), kostenstelle_id)
    if buch < 1:
        return None
    anfang = dt.datetime.combine(tag, dt.time.min, tzinfo=zeit.zeitzone())
    genannt = _sichtungen(sitzung, anfang, None).get((int(stueck.id), kostenstelle_id))
    return buch if genannt is None else genannt


def buchmenge(db: Any, mandant_id: int, stueck_id: int, kostenstelle_id: int) -> int:
    """Die gebuchte Menge des Stücks auf der Kostenstelle (offene Standorte)."""
    return int(db.execute(select(func.coalesce(func.sum(m.Standort.menge), 0)).where(
        m.Standort.mandant_id == mandant_id, m.Standort.stueck_id == stueck_id, m.Standort.kostenstelle_id == kostenstelle_id,
        m.Standort.bis.is_(None))).scalar_one())


def bericht(sitzung: Any) -> Bericht | None:
    """Der Stand der Inventur zum Stichtag; `None`, wenn keiner gesetzt ist."""
    fordern(sitzung)
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    tag = stichtag(db, mid)
    if tag is None:
        return None
    anfang = dt.datetime.combine(tag, dt.time.min, tzinfo=zeit.zeitzone())
    erlaubt = sicht.erlaubte_kostenstellen(sitzung)
    q = select(m.Standort, m.Stueck).join(m.Stueck, m.Stueck.id == m.Standort.stueck_id).where(
        m.Standort.mandant_id == mid, m.Standort.bis.is_(None), m.Stueck.status.notin_(ENDZUSTAENDE))
    if erlaubt is not None:
        q = q.where(m.Standort.kostenstelle_id.in_(erlaubt))
    summe: dict[tuple[int, int], int] = {}
    stuecke: dict[int, m.Stueck] = {}
    for standort, s in db.execute(q).all():
        schluessel = (int(s.id), int(standort.kostenstelle_id))
        summe[schluessel] = summe.get(schluessel, 0) + int(standort.menge)
        stuecke[int(s.id)] = s
    nummer = {sid: s.inventarnummer for sid, s in stuecke.items()}
    erwartet = [rein.Erwartet(nummer[sid], ks, menge, stuecke[sid].status) for (sid, ks), menge in sorted(summe.items())]
    gesehen_roh = _gesehen_seit(sitzung, anfang, nummer, erlaubt)
    gesehen = []
    for sid, ks, menge in gesehen_roh:
        if sid not in nummer:
            continue
        gesehen.append(rein.Gesehen(nummer[sid], ks, summe.get((sid, ks), 1) if menge is None else menge, anfang))
    umfang = {e.kostenstelle for e in erwartet} | {g.kostenstelle for g in gesehen}
    erg = rein.auswerten(erwartet, gesehen, umfang)
    fehlt = {(f.inventarnummer, f.kostenstelle): f for f in erg.fehlmengen}
    woanders = {(w.inventarnummer, w.erwartet_auf): w for w in erg.woanders}
    zurueck, vorschlag = set(erg.wieder_aufgetaucht), set(erg.vermisst_vorschlag)
    gesehen_je: dict[tuple[str, int], int] = {}
    for g in gesehen:
        gesehen_je[(g.inventarnummer, g.kostenstelle)] = gesehen_je.get((g.inventarnummer, g.kostenstelle), 0) + g.menge
    id_von = {n: sid for sid, n in nummer.items()}
    je_ks: dict[int, list[Zeile]] = {}
    gesehen_zahl = nicht_zahl = 0
    for e in erwartet:
        s = stuecke[id_von[e.inventarnummer]]
        gesehen_hier = gesehen_je.get((e.inventarnummer, e.kostenstelle), 0)
        if e.inventarnummer in zurueck:
            ergebnis, auf = "wieder_aufgetaucht", None
        elif e.status == "vermisst":
            ergebnis, auf = "vermisst", None
        elif (e.inventarnummer, e.kostenstelle) in woanders:
            ergebnis, auf = "woanders", woanders[(e.inventarnummer, e.kostenstelle)].gesehen_auf
        elif (e.inventarnummer, e.kostenstelle) in fehlt:
            ergebnis, auf = ("teilweise" if fehlt[(e.inventarnummer, e.kostenstelle)].gesehen > 0 else "nicht_gesehen"), None
        else:
            ergebnis, auf = "gesehen", None
        if ergebnis in ("gesehen", "wieder_aufgetaucht", "woanders"):
            gesehen_zahl += 1
        elif ergebnis in ("nicht_gesehen", "teilweise"):
            nicht_zahl += 1
        je_ks.setdefault(e.kostenstelle, []).append(Zeile(
            int(s.id), e.inventarnummer, s.bezeichnung, e.kostenstelle, e.menge, gesehen_hier, ergebnis, auf,
            vorschlag=ergebnis == "nicht_gesehen" and e.inventarnummer in vorschlag and s.status != "vermisst"))
    namen = sicht.kostenstellen_namen(sitzung, set(je_ks) | {z.woanders_auf for zs in je_ks.values() for z in zs if z.woanders_auf})
    return Bericht(tag, dict(sorted(je_ks.items(), key=lambda kv: namen.get(kv[0], str(kv[0])))), namen, gesehen_zahl, nicht_zahl, erg.unbekannt)


def als_vermisst_eintragen(sitzung: Any, stueck_id: int, grund: str) -> m.Stueck:
    """Der Vorschlag wird angenommen: Status `vermisst` mit Grund, von Hand je Stück (Recht `stilllegen`) — nie von selbst."""
    if not sitzung.darf("inventar", "stilllegen"):
        raise gemeinsam.KeinRecht("inventar", "stilllegen")
    if not grund.strip():
        raise ValueError("stueck_status.grund_fehlt")
    zeile = sitzung.db.execute(sicht.stuecke(sitzung).where(m.Stueck.id == stueck_id)).scalars().first()
    if zeile is None:
        raise gemeinsam.KeinRecht("inventar", "stilllegen")
    return fachstueck.status_wechseln(sitzung, zeile.inventarnummer, "vermisst", grund)


def zeilen_fuer_export(b: Bericht) -> list[tuple[object, ...]]:
    return [(b.namen.get(ks, str(ks)), z.nummer, z.bezeichnung, z.erwartet, z.gesehen, z.ergebnis) for ks, zs in b.je_kostenstelle.items() for z in zs]


def exportieren(sitzung: Any, arbeitsordner: Path) -> Path:
    """Schreibt die Inventur als CSV unter `export/` (Name mit Zeitstempel, nichts wird überschrieben)."""
    b = bericht(sitzung)
    if b is None:
        raise ValueError("inventur.stichtag_fehlt")
    return kostenrechnung.schreibe_csv(sitzung, "inventur", zeilen_fuer_export(b), arbeitsordner)


def abschliessen(sitzung: Any, arbeitsordner: Path) -> Path:
    """„Inventur abschließen“ (Recht `einstellen`): friert das Ergebnis als CSV `export/inventur_<stichtag>_<zeitstempel>.csv` ein
    (je Kostenstelle gesehen / nicht gesehen, dazu die Vermisst-Vorschläge), merkt Stichtag und Pfad in `inventur_letzte`, leert den Stichtag
    und schreibt `inventar.inventur_abgeschlossen`. Den Status `vermisst` setzt das nicht — das bleibt Handarbeit je Stück."""
    if not sitzung.darf("inventar", "einstellen"):
        raise gemeinsam.KeinRecht("inventar", "einstellen")
    b = bericht(sitzung)
    if b is None:
        raise ValueError("inventur.stichtag_fehlt")
    db, mid = sitzung.db, sitzung.kontext.mandant_id
    zeilen = [(ort, z.nummer, z.bezeichnung, z.erwartet, z.gesehen, z.ergebnis, z.vorschlag) for ort, zs in
              ((b.namen.get(ks, str(ks)), zs) for ks, zs in b.je_kostenstelle.items()) for z in zs]
    pfad = kostenrechnung.schreibe_csv(sitzung, "inventur_abschluss", zeilen, arbeitsordner, stichtag=b.stichtag, vermerk=False)
    relativ = str(pfad.relative_to(arbeitsordner))
    alt = katalog.einstellung(db, mid, EINSTELLUNG_LETZTE)
    katalog.setze_einstellung(db, mid, EINSTELLUNG_LETZTE, f"{b.stichtag.isoformat()}|{relativ}", _benutzer(sitzung))
    katalog.setze_einstellung(db, mid, EINSTELLUNG, "", _benutzer(sitzung))
    protokoll.schreiben(db, mandant_id=mid, aktion="inventar.inventur_abgeschlossen", objekt_typ="inventar.einstellung", alt_wert=alt or None,
                        neu_wert=f"{b.stichtag.isoformat()} {relativ} gesehen={b.gesehen} nicht_gesehen={b.nicht_gesehen}", benutzer_id=_benutzer(sitzung))
    return pfad


def letzte(db: Any, mandant_id: int) -> tuple[dt.date, str] | None:
    """Stichtag und Dateiname (ohne Ordner) der zuletzt abgeschlossenen Inventur; `None`, wenn es noch keine gibt."""
    text = katalog.einstellung(db, mandant_id, EINSTELLUNG_LETZTE)
    tag, _, pfad = text.partition("|")
    try:
        return dt.date.fromisoformat(tag), Path(pfad).name
    except ValueError:
        return None


__all__ = ["Bericht", "Zeile", "abschliessen", "als_vermisst_eintragen", "bericht", "buchmenge", "exportieren", "letzte", "stichtag", "stichtag_setzen",
           "zaehlen_abfragen"]
