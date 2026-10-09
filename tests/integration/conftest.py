"""Die Integrationsläufe des Inventars — T-I-5, T-I-6 (Muster: `tests/integration/conftest.py` des Kerns).

Sie stehen **nicht** im gewöhnlichen Lauf (`pytest.ini`: `norecursedirs`): jeder braucht einen bestimmten Aufbau
— welche Module installiert sind. Steht der falsche da, wird die Datei **rot**, nicht übersprungen
(`aufbau_pruefen`). Was hier steht, ist die Box: alle Ketten in der Reihenfolge der Installation
(`migration.alle_ketten_nachziehen`, derselbe Weg wie beim Start), Startdaten, ein Verwalter, ein Polier und die
Anwendung des Kerns. Aufruf siehe `laufen.md`.
"""

from __future__ import annotations

import importlib.util
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Die Wurzel des Betriebs: von Hand das Arbeitsverzeichnis — gesetzt, bevor irgendetwas `konfig.env` liest
os.environ.setdefault("DIGIASSISTENZ_WURZEL", str(Path.cwd()))

from digiassistenz_kern import modul as kern_modul  # noqa: E402

kern_modul.installierte_anmelden()

from digiassistenz_kern.pruefstand import (  # noqa: E402,F401 — Vorrichtungen
    SCHEMATA_KERN,
    _uhren_einhaengen,
    konfiguration,
    pruef_arbeitsordner,
    pruef_db_url,
    pruef_motor,
    pruefuhr,
)

GRUNDADRESSE = "https://pruefung.invalid"
PASSWORT = "Integration-Inventar-2026!"
VERWALTER = "verwalter@integration.invalid"
POLIER = "polier@integration.invalid"
POLIER_ZWEI = "polier2@integration.invalid"
MANDANT = "Prüfbetrieb Inventar"


def aufbau_pruefen(erwartet: set[str]) -> None:
    """Die installierten Module müssen **genau** diese sein — sonst ist der Lauf nichts wert."""
    gefunden = set(kern_modul.installierte_anmelden())
    assert gefunden == erwartet, (
        f"Dieser Lauf verlangt die Module {sorted(erwartet)}, installiert sind {sorted(gefunden)} — "
        "falscher Aufbau, siehe tests/integration/laufen.md")
    if "beleg" not in erwartet:
        assert importlib.util.find_spec("digiassistenz") is None, "die Belegerfassung ist auffindbar"


@pytest.fixture(scope="session")
def modul_schemata() -> tuple[str, ...]:
    """Die Schemata **aller installierten** Module — `pruef_motor` verwirft sie vor jedem Prüffall."""
    return tuple(s for s in kern_modul.schemata() if s not in SCHEMATA_KERN)


@pytest.fixture(autouse=True)
def _module_angemeldet() -> Iterator[None]:
    kern_modul.installierte_anmelden()
    yield
    kern_modul.installierte_anmelden()


@dataclass
class Box:
    klient: TestClient
    db_url: str
    arbeitsordner: Path
    staende: dict[str, str | None]


def _konto(db, mandant_id: int, anmeldename: str, vorlage: str) -> int:
    from digiassistenz_kern import Benutzer
    from digiassistenz_kern import passwort as passwort_modul
    from digiassistenz_kern import rechte as kern_rechte

    satz = Benutzer(
        mandant_id=mandant_id, anmeldename=anmeldename, name=anmeldename.split("@")[0].title(), rolle=vorlage,
        aktiv=True, muss_passwort_aendern=False, passwort_hash=passwort_modul.hashen(PASSWORT))
    db.add(satz)
    db.flush()
    kern_rechte.kopieren(db, benutzer=satz, vorlage_schluessel=vorlage)
    return int(satz.id)


def box_bauen(db_url: str, arbeitsordner: Path, *, vorher=None) -> Iterator[Box]:
    from digiassistenz_kern import Mandant, konfig, migration, ordner, startdaten
    from digiassistenz_kern.sitzung import systemsitzung
    from digiassistenz_kern.web import einstellungen as web_einstellungen
    from digiassistenz_kern.web import sitzung as web_sitzung
    from digiassistenz_kern.web.anwendung import bauen

    if vorher is not None:
        vorher(db_url)
    temp = arbeitsordner / "temp"
    temp.mkdir(parents=True, exist_ok=True)
    staende = migration.alle_ketten_nachziehen(db_url, temp)
    ordner.struktur_anlegen(arbeitsordner)
    startdaten.sichern_beim_start(MANDANT)
    web_einstellungen.setzen(konfig.Konfiguration(
        arbeitsordner=arbeitsordner, db_url=db_url, mandant_name=MANDANT, quelle=Path("konfig.env"),
        web_geheimnis="pruefgeheimnis-inventar", modul_werte={}))
    web_sitzung.geheimnis_vergessen()
    with systemsitzung("pruefung.integration") as db:
        mandant = db.execute(select(Mandant)).scalars().one()
        mandant.ordnername = "pruefbetrieb"
        _konto(db, mandant.id, VERWALTER, "verwalter")
        _konto(db, mandant.id, POLIER, "polier")
        _konto(db, mandant.id, POLIER_ZWEI, "polier")
    with TestClient(bauen(), base_url=GRUNDADRESSE) as klient:
        yield Box(klient, db_url, arbeitsordner, staende)
    web_einstellungen.vergessen()
    web_sitzung.geheimnis_vergessen()


@pytest.fixture
def box(pruef_motor: str, pruef_arbeitsordner: Path) -> Iterator[Box]:
    yield from box_bauen(pruef_motor, pruef_arbeitsordner)


def anmelden(klient: TestClient, name: str = VERWALTER) -> str:
    """Anmelden, Ziel der Umleitung zurück — die Startseite."""
    antwort = klient.post("/anmelden", data={"anmeldename": name, "passwort": PASSWORT}, follow_redirects=False)
    assert antwort.status_code == 303, antwort.text[:300]
    return antwort.headers["location"]


def menuewege(seite: str) -> list[str]:
    """Die Wege im Kopf der Seite — beide Kopfzeilen."""
    kopf = seite.split("<main", 1)[0]
    return sorted(set(re.findall(r'<a[^>]+href="(/[^"#?]*)"', kopf)))


def tote_links(klient: TestClient, seite: str) -> list[str]:
    """Jeder Weg im Kopf muss antworten — kein toter Link."""
    return [f"{weg} → {code}" for weg in menuewege(seite) if (code := klient.get(weg).status_code) != 200]


__all__ = ["Box", "MANDANT", "POLIER", "POLIER_ZWEI", "VERWALTER", "anmelden", "aufbau_pruefen", "box_bauen", "menuewege", "tote_links"]
