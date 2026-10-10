"""Die Modulbeschreibung des Inventars — Muster: die Attrappe des Kerns (Steckbrief 0.15.2, Abschnitt 2 und 10).

Was hier steht, sagt das Modul dem Kern über sich. Vertrag: Namen und Wege sind wörtlich Auftrag 03, Abschnitt 4.
Kein Import eines anderen Moduls; der Schlüssel der Baustelle steht nur als Konstante `MODUL_BAUSTELLE` in der
`Verbindung` (APP nennt den Weg später). `app.modul` setzt das Inventar **nicht** (Steckbrief 11); die Überschrift
der Suchgruppe ist `bezeichnung` = `inventar.modul`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from digiassistenz_kern.konfig import KonfigFehler
from digiassistenz_kern.modul import (
    Erweiterung,
    Menueeintrag,
    Modulbeschreibung,
    Suchergebnis,
    Suchtreffer,
    Verbindung,
    fassung,
)
from digiassistenz_kern.texte import t

from .rechte import MODULRECHTE

SCHLUESSEL = "inventar"
VERSION = fassung("digiassistenz-inventar", neben=Path(__file__))
KERN_MINDESTFASSUNG = "0.15.2"

#: Schlüssel der Baustelle — nur für `Verbindung(braucht=…)`; offen, ob `app` oder `baustelle` (Auftrag 03, Abschnitt 4)
MODUL_BAUSTELLE = "baustelle"

WEG_UEBERSICHT = "/inventar"
WEG_HIER = "/inventar/hier"
WEG_FAELLIG = "/inventar/faellig"
WEG_VERWALTUNG = "/inventar/verwaltung"
WEG_KOSTENSTELLE = "/inventar/kostenstelle/{kostenstelle_id}"
WEG_UEBERSICHT_TEIL = "/inventar/uebersicht"
KONFIG_ETIKETT_URL = "INVENTAR_ETIKETT_URL"
SUCHE_HOECHSTENS = 20


@dataclass
class Folge:
    vermerke: list[str] = field(default_factory=list)


def _bei_kostenstelle_angelegt(*, mandant: Any, objekt: Any, arbeitsordner: Any, **_rest: Any) -> Folge:
    """Legt den Exportordner der Kostenstelle an; ein vorhandener ist kein Fehler."""
    from . import dateien

    if arbeitsordner is None:
        return Folge()
    ziel = dateien.kostenstellenordner(Path(arbeitsordner), mandant.ordnername, str(objekt.nummer))
    gab_es = ziel.exists()
    ziel.mkdir(parents=True, exist_ok=True)
    return Folge([] if gab_es else [t("inventar.ordner_kostenstelle", pfad=str(ziel))])


def _je_kostenstelle(sitzung: Any, kostenstellen: Any) -> dict[int, str]:
    from .dienstlogik import sicht

    return {k: t("inventar.n_stueck", anzahl=n) for k, n in sicht.stuecke_je_kostenstelle(sitzung).items()}


def _suche(sitzung: Any, begriff: str) -> Suchergebnis:
    from .dienstlogik import sicht

    zeilen, mehr = sicht.suchen(sitzung, begriff, SUCHE_HOECHSTENS)
    return Suchergebnis(
        spalten=("inventar.suche.spalte_nummer", "inventar.suche.spalte_bezeichnung", "inventar.suche.spalte_steht_auf"),
        treffer=tuple(Suchtreffer(f"/inventar/s/{quote(nummer, safe='')}", (nummer, bezeichnung, ort)) for nummer, bezeichnung, ort in zeilen),
        mehr=mehr,
    )


def _konfig_pruefen(konfiguration: Any) -> None:
    url = konfiguration.modul_werte.get(KONFIG_ETIKETT_URL, "").strip()
    if url and not url.startswith(("http://", "https://")):
        raise KonfigFehler(t("inventar.etikett_url_ungueltig"))


def _routen() -> Any:
    from . import web

    return web.router


def _kette(db_url: str, abzug_ordner: Any) -> str | None:
    from . import migration

    return migration.nachziehen(db_url, abzug_ordner)


def _schemastand(db_url: str) -> str | None:
    from . import migration

    nummer = migration.schema_version(migration.aktuelle_revision(db_url))
    return None if nummer is None else f"i{nummer}"


def _startdaten(db: Any, mandant: Any) -> None:
    from . import startdaten

    startdaten.startdaten(db, mandant)


BESCHREIBUNG = Modulbeschreibung(
    schluessel=SCHLUESSEL,
    bezeichnung="inventar.modul",
    version=VERSION,
    rechte=MODULRECHTE,
    menuepunkte=(
        Menueeintrag(WEG_UEBERSICHT, "inventar.menue_inventar", "inventar", reihenfolge=10,
                     rechte=(("inventar", "sehen"),)),
        Menueeintrag(WEG_HIER, "inventar.menue_hier", "inventar_hier", reihenfolge=11,
                     rechte=(("inventar", "scannen"), ("inventar", "sehen"))),
        Menueeintrag(WEG_FAELLIG, "inventar.menue_faellig", "inventar_faellig", reihenfolge=12,
                     rechte=(("inventar", "pruefen"), ("inventar", "werkstatt"))),
        Menueeintrag(WEG_VERWALTUNG, "inventar.menue_verwaltung", "inventar_verwaltung", reihenfolge=30,
                     rechte=(("inventar", "einstellen"), ("inventar", "pflegen")), unterzeile=True,
                     auch=("/inventar/verwaltung/",)),
    ),
    startseite=WEG_UEBERSICHT,
    konfig_schluessel=(KONFIG_ETIKETT_URL,),
    schemata=(SCHLUESSEL,),
    prozesse=(),
    arbeitsordner=("inventar",),
    texte=Path(__file__).with_name("texte"),
    vorlagen=Path(__file__).with_name("vorlagen"),
    statisch=Path(__file__).with_name("statisch"),
    quelltext=Path(__file__).parent,
    schemastand=_schemastand,
    kette=_kette,
    startdaten=_startdaten,
    routen=_routen,
    konfig_pruefen=_konfig_pruefen,
    sichtbarkeit="inventar.sehen",
    verbindungen=(Verbindung(braucht=MODUL_BAUSTELLE, menuepunkte=()),),
    erweiterungen=(
        Erweiterung("kostenstelle.seite", "inventar", "inventar.reiter_hier", route=WEG_KOSTENSTELLE,
                    rechte=(("inventar", "sehen"),), reihenfolge=40),
        Erweiterung("verwaltung.uebersicht", "inventar", "inventar.uebersicht_titel", route=WEG_UEBERSICHT_TEIL,
                    rechte=(("inventar", "sehen"),)),
        Erweiterung("verwaltung.uebersicht.kostenstelle", "inventar", "inventar.spalte_stueck", werte=_je_kostenstelle,
                    rechte=(("inventar", "sehen"),), leer=""),
    ),
    ereignisse=(("kostenstelle.angelegt", _bei_kostenstelle_angelegt),),
    zeilenfilter=(),
    suche=_suche,
)

__all__ = ["BESCHREIBUNG", "KERN_MINDESTFASSUNG", "MODUL_BAUSTELLE", "SCHLUESSEL", "VERSION"]
