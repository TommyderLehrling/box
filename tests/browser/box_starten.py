"""Startet eine Prüf-Box für die Browserfälle: Ketten (Kern, dann Inventar), Startdaten, drei Konten und den Webserver.

Aufruf (Kern 0.15.5 und Inventar sind eingebaut, `konfig.env` im Arbeitsverzeichnis wie bei jedem Lauf)::

    DIGIASSISTENZ_WURZEL=$PWD python <pfad>/tests/browser/box_starten.py --port 8765

Die Datenbank in `DB_URL` muss beim ersten Start **leer** sein (eine frische Prüfdatenbank): ist das Schema `kern` schon da, bricht das Skript ab — es löscht nichts.
Mit `--weiter` startet es nur den Webserver auf einer Datenbank, die es schon aufgebaut hat (zweiter Start, Zustand bleibt).
Kostenstellen `1000 79795 80010 70101 70102`; die Poliere sind 70101/70102 (`polier2`: 70102) zugeordnet, das Büro allen fünf. Konten (Passwort `Browser-Inventar-2026!`): `verwalter@browser.invalid` (Vorlage verwalter), `polier@browser.invalid` und `polier2@browser.invalid` (Vorlage polier),
`buero@browser.invalid` (Vorlage buero: pflegen, pruefen — kein buchen). Beenden mit Strg+C.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PASSWORT = "Browser-Inventar-2026!"
MANDANT = "Prüfbetrieb Browser"
KONTEN = (("verwalter@browser.invalid", "verwalter"), ("polier@browser.invalid", "polier"),
          ("polier2@browser.invalid", "polier"), ("buero@browser.invalid", "buero"))
KOSTENSTELLEN = ("1000", "79795", "80010", "70101", "70102")
#: welche Kostenstellen ein Konto bekommt (der Verwalter braucht keine Zuordnung)
ZUORDNUNG = {"polier@browser.invalid": ("70101", "70102"), "polier2@browser.invalid": ("70102",), "buero@browser.invalid": KOSTENSTELLEN}


def aufbauen(weiter: bool = False) -> None:
    from sqlalchemy import create_engine, inspect, select

    from digiassistenz_kern import Benutzer, BenutzerKostenstelle, Kostenstelle, Mandant, konfig, migration, ordner, startdaten
    from digiassistenz_kern import modul as kern_modul
    from digiassistenz_kern import passwort as passwort_modul
    from digiassistenz_kern import rechte as kern_rechte
    from digiassistenz_kern.sitzung import systemsitzung
    from digiassistenz_kern.web import einstellungen as web_einstellungen

    kern_modul.installierte_anmelden()
    wurzel = Path(os.environ.get("DIGIASSISTENZ_WURZEL", Path.cwd()))
    k = konfig.lesen(wurzel / "konfig.env")
    if not weiter:
        motor = create_engine(k.db_url)
        try:
            if "kern" in inspect(motor).get_schema_names():
                sys.exit("Die Datenbank ist nicht leer (Schema kern ist da): bitte eine frische Prüfdatenbank in DB_URL eintragen oder --weiter nehmen.")
        finally:
            motor.dispose()
    temp = k.arbeitsordner / "temp"
    temp.mkdir(parents=True, exist_ok=True)
    if not weiter:
        migration.alle_ketten_nachziehen(k.db_url, temp)
        ordner.struktur_anlegen(k.arbeitsordner)
        startdaten.sichern_beim_start(MANDANT)
    web_einstellungen.setzen(konfig.Konfiguration(arbeitsordner=k.arbeitsordner, db_url=k.db_url, mandant_name=MANDANT,
                                                  quelle=Path("konfig.env"), web_geheimnis=k.web_geheimnis, modul_werte=k.modul_werte))
    if weiter:
        return
    with systemsitzung("browser.aufbau") as db:
        mandant = db.execute(select(Mandant)).scalars().one()
        mandant.ordnername = "browserbetrieb"
        mandant.feiertagsregion = "DE-SN"  # die Region stellt im Betrieb die Verwaltung im Kern ein (L16a); der Fall prüft die Wirkung
        stellen = {}
        for nummer in KOSTENSTELLEN:
            stellen[nummer] = Kostenstelle(mandant_id=mandant.id, nummer=nummer, bezeichnung=f"Baustelle {nummer}", strasse="Weg 1", plz="25813", ort="Husum")
            db.add(stellen[nummer])
        db.flush()
        for name, vorlage in KONTEN:
            satz = Benutzer(mandant_id=mandant.id, anmeldename=name, name=name.split("@")[0].title(), rolle=vorlage, aktiv=True,
                            muss_passwort_aendern=False, passwort_hash=passwort_modul.hashen(PASSWORT))
            db.add(satz)
            db.flush()
            kern_rechte.kopieren(db, benutzer=satz, vorlage_schluessel=vorlage)
            for nummer in ZUORDNUNG.get(name, ()):
                db.add(BenutzerKostenstelle(benutzer_id=satz.id, kostenstelle_id=stellen[nummer].id))


def main() -> None:
    teile = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    teile.add_argument("--port", type=int, default=8765)
    teile.add_argument("--host", default="127.0.0.1")
    teile.add_argument("--weiter", action="store_true", help="Datenbank ist schon aufgebaut: nur den Webserver starten")
    angaben = teile.parse_args()
    aufbauen(angaben.weiter)
    import uvicorn

    from digiassistenz_kern.web.anwendung import bauen

    uvicorn.run(bauen(), host=angaben.host, port=angaben.port, log_level="warning")


if __name__ == "__main__":
    main()
