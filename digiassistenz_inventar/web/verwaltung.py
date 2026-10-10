"""Verwaltung → Inventar: die Kacheln und die Pflegeseiten (Gruppen, Merkmale, Prüfarten, Bauteile, Kostensätze,
Einstellungen, Import, Etiketten, Testdaten). Gelöscht wird nichts; ausblenden heißt `aktiv = false`."""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import func, select

from digiassistenz_kern import Mandant
from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import einstellungen, gemeinsam, wahlfeld

from .. import dateien
from .. import modelle as m
from .. import rechte
from ..dienstlogik import etiketten as fachetiketten
from ..dienstlogik import import_lauf, katalog, katalogpflege, liste, testdaten
from ..rein import import_vorlage
from . import helfer
from .stueck import _text, formular

router = APIRouter()
WEG = "/inventar/verwaltung"
IMPORT_HOECHSTENS = 10 * 1024 * 1024
HEX = re.compile(r"^[0-9a-f]{32}$")
KACHELN = (
    ("gruppen", "einstellen"), ("merkmale", "einstellen"), ("pruefarten", "einstellen"), ("bauteile", "pflegen"),
    ("kostensaetze", "kosten_pflegen"), ("einstellungen", "einstellen"), ("import", "pflegen"), ("etiketten", "pflegen"),
    ("testdaten", "einstellen"),
)
MODELLE = {"gruppen": m.Gruppe, "merkmale": m.Merkmal, "pruefarten": m.Pruefart, "bauteile": m.Bauteil,
           "kostensaetze": m.Kostensatz, "einstellungen": m.Einstellung}


def _krumen(schluessel: str = "") -> list[tuple[str, str]]:
    glieder = [(t("inventar.menue_verwaltung"), WEG)]
    if schluessel:
        glieder.append((t("inventar.verwaltung." + schluessel), ""))
    return glieder


def _seite(request: Request, sitzung: Sitzung, name: str, schluessel: str, **werte: Any) -> HTMLResponse:
    return gemeinsam.seite(request, sitzung, name, aktiv="verwaltung", brotkrumen=_krumen(schluessel), **werte, **rechte.darf_alle(sitzung))


def _speichern(request: Request, sitzung: Sitzung, schluessel: str, tun: Any) -> HTMLResponse:
    """Führt die Speicherung aus: Fehler als ein Satz (409), Erfolg als Rückkehr auf die Seite mit Vermerk ✓."""
    try:
        tun()
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return gemeinsam.umleiten(f"{WEG}/{schluessel}?fertig=gespeichert", request)


@router.get(WEG, response_class=HTMLResponse)
def kacheln(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "einstellen"), ("inventar", "pflegen"))),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    freigegeben = katalog.einstellung(sitzung.db, mid, "auslieferung_am") == ""
    zeilen = []
    for schluessel, aktion in KACHELN:
        if not sitzung.darf("inventar", aktion) or (schluessel == "testdaten" and not freigegeben):
            continue
        modell = MODELLE.get(schluessel)
        zahl = None if modell is None else int(sitzung.db.execute(select(func.count()).select_from(modell).where(modell.mandant_id == mid)).scalar_one())
        zeilen.append((schluessel, f"{WEG}/{schluessel}", zahl))
    return _seite(request, sitzung, "inventar_verwaltung.html", "", kacheln=zeilen)


# ---- Gruppen ------------------------------------------------------------------------------------------------------

@router.get(WEG + "/gruppen", response_class=HTMLResponse)
def gruppen(
    request: Request, bearbeiten: str = "", fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    zeilen = list(sitzung.db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid).order_by(m.Gruppe.sortierung, m.Gruppe.id)).scalars())
    oben = {int(g.id): g.schluessel for g in zeilen}
    eintrag = next((g for g in zeilen if g.schluessel == bearbeiten), None)
    return _seite(request, sitzung, "inventar_verwaltung_gruppen.html", "gruppen", zeilen=[
        {"schluessel": g.schluessel, "bezeichnung": g.bezeichnung, "kuerzel": g.kuerzel, "oben": oben.get(int(g.oben_id), "") if g.oben_id else "",
         "sortierung": g.sortierung, "aktiv": g.aktiv, "startwert": g.startwert} for g in zeilen],
        eintrag={"schluessel": "", "bezeichnung": "", "kuerzel": "", "oben": "", "sortierung": 0, "aktiv": True} if eintrag is None else {
            "schluessel": eintrag.schluessel, "bezeichnung": eintrag.bezeichnung, "kuerzel": eintrag.kuerzel,
            "oben": oben.get(int(eintrag.oben_id), "") if eintrag.oben_id else "", "sortierung": eintrag.sortierung, "aktiv": eintrag.aktiv},
        fertig=bool(fertig))


@router.post(WEG + "/gruppen", response_class=HTMLResponse)
def gruppe_speichern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    return _speichern(request, sitzung, "gruppen", lambda: katalogpflege.gruppe_speichern(
        sitzung, _text(f, "schluessel"), _text(f, "bezeichnung"), _text(f, "kuerzel"), _text(f, "oben"),
        helfer.ganzzahl(_text(f, "sortierung"), 0) or 0, "aktiv" in f))


# ---- Merkmale -----------------------------------------------------------------------------------------------------

@router.get(WEG + "/merkmale", response_class=HTMLResponse)
def merkmale(
    request: Request, gruppe: str = "", bearbeiten: str = "", fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    alle_gruppen = list(sitzung.db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid).order_by(m.Gruppe.sortierung, m.Gruppe.id)).scalars())
    gewaehlt = next((g for g in alle_gruppen if g.schluessel == gruppe), alle_gruppen[0] if alle_gruppen else None)
    zeilen = [] if gewaehlt is None else list(sitzung.db.execute(select(m.Merkmal).where(
        m.Merkmal.mandant_id == mid, m.Merkmal.gruppe_id == gewaehlt.id).order_by(m.Merkmal.sortierung, m.Merkmal.id)).scalars())
    eintrag = next((z for z in zeilen if z.schluessel == bearbeiten), None)
    return _seite(request, sitzung, "inventar_verwaltung_merkmale.html", "merkmale", gruppen=[(g.schluessel, g.bezeichnung) for g in alle_gruppen],
                  gruppe=gewaehlt.schluessel if gewaehlt else "", typen=list(m.MERKMAL_TYP), fertig=bool(fertig),
                  zeilen=[{"schluessel": z.schluessel, "bezeichnung": z.bezeichnung, "typ": z.typ, "einheit": z.einheit,
                           "auswahl": ", ".join(z.auswahl or []), "pflicht": z.pflicht, "sortierung": z.sortierung, "aktiv": z.aktiv,
                           "startwert": z.startwert} for z in zeilen],
                  eintrag={"schluessel": "", "bezeichnung": "", "typ": "text", "einheit": "", "auswahl": "", "pflicht": False, "sortierung": 0,
                           "aktiv": True} if eintrag is None else {
                      "schluessel": eintrag.schluessel, "bezeichnung": eintrag.bezeichnung, "typ": eintrag.typ, "einheit": eintrag.einheit,
                      "auswahl": ", ".join(eintrag.auswahl or []), "pflicht": eintrag.pflicht, "sortierung": eintrag.sortierung,
                      "aktiv": eintrag.aktiv})


@router.post(WEG + "/merkmale", response_class=HTMLResponse)
def merkmal_speichern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    return _speichern(request, sitzung, "merkmale?gruppe=" + _text(f, "gruppe"), lambda: katalogpflege.merkmal_speichern(
        sitzung, _text(f, "gruppe"), _text(f, "schluessel"), _text(f, "bezeichnung"), _text(f, "typ"), _text(f, "einheit"),
        _text(f, "auswahl"), "pflicht" in f, helfer.ganzzahl(_text(f, "sortierung"), 0) or 0, "aktiv" in f))


# ---- Prüfarten ----------------------------------------------------------------------------------------------------

@router.get(WEG + "/pruefarten", response_class=HTMLResponse)
def pruefarten(
    request: Request, bearbeiten: str = "", fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    alle_gruppen = {int(g.id): g for g in sitzung.db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    je_art: dict[int, list[str]] = {}
    je_art_intervall: dict[int, dict[str, int]] = {}
    for z in sitzung.db.execute(select(m.GruppePruefart).where(m.GruppePruefart.mandant_id == mid, m.GruppePruefart.aktiv)).scalars():
        je_art.setdefault(int(z.pruefart_id), []).append(alle_gruppen[int(z.gruppe_id)].schluessel)
        if z.intervall_monate is not None:
            je_art_intervall.setdefault(int(z.pruefart_id), {})[alle_gruppen[int(z.gruppe_id)].schluessel] = int(z.intervall_monate)
    zeilen = [{
        "schluessel": p.schluessel, "bezeichnung": p.bezeichnung, "intervall": p.intervall_monate, "zaehler": p.zaehler_intervall or "",
        "rechtsgrund": p.rechtsgrund, "durchfuehrung": p.durchfuehrung, "je_merkmal": katalogpflege.je_merkmal_text(p.intervall_je_merkmal),
        "gruppen": je_art.get(int(p.id), []), "gruppen_intervall": je_art_intervall.get(int(p.id), {}), "aktiv": p.aktiv, "startwert": p.startwert}
        for p in sitzung.db.execute(select(m.Pruefart).where(m.Pruefart.mandant_id == mid).order_by(m.Pruefart.id)).scalars()]
    leer = {"schluessel": "", "bezeichnung": "", "intervall": 12, "zaehler": "", "rechtsgrund": "", "durchfuehrung": "intern", "je_merkmal": "",
            "gruppen": [], "gruppen_intervall": {}, "aktiv": True}
    return _seite(request, sitzung, "inventar_verwaltung_pruefarten.html", "pruefarten", zeilen=zeilen, fertig=bool(fertig),
                  eintrag=next((z for z in zeilen if z["schluessel"] == bearbeiten), leer), durchfuehrungen=list(m.DURCHFUEHRUNG),
                  gruppen=[(g.schluessel, g.bezeichnung) for g in alle_gruppen.values()])


@router.post(WEG + "/pruefarten", response_class=HTMLResponse)
def pruefart_speichern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    gewaehlt = tuple(wert for name, wert in f.items() if name.startswith("g_") and isinstance(wert, str))
    return _speichern(request, sitzung, "pruefarten", lambda: katalogpflege.pruefart_speichern(
        sitzung, _text(f, "schluessel"), _text(f, "bezeichnung"), _text(f, "intervall_monate"), _text(f, "zaehler_intervall"),
        _text(f, "rechtsgrund"), _text(f, "durchfuehrung"), _text(f, "je_merkmal"), gewaehlt, "aktiv" in f,
        {name[3:]: wert for name, wert in f.items() if name.startswith("gi_") and isinstance(wert, str)}))


# ---- Bauteile -----------------------------------------------------------------------------------------------------

@router.get(WEG + "/bauteile", response_class=HTMLResponse)
def bauteile(
    request: Request, bearbeiten: str = "", fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    zeilen = [{"nummer": b.bauteilnummer, "bezeichnung": b.bezeichnung, "hersteller": b.hersteller, "preis": b.preis_zuletzt,
               "hinweis": b.hinweis, "aktiv": b.aktiv}
              for b in sitzung.db.execute(select(m.Bauteil).where(m.Bauteil.mandant_id == sitzung.kontext.mandant_id)
                                          .order_by(m.Bauteil.bauteilnummer)).scalars()]
    leer = {"nummer": "", "bezeichnung": "", "hersteller": "", "preis": "", "hinweis": "", "aktiv": True}
    eintrag = next((z for z in zeilen if z["nummer"] == bearbeiten), leer)
    return _seite(request, sitzung, "inventar_verwaltung_bauteile.html", "bauteile", zeilen=zeilen, fertig=bool(fertig),
                  eintrag={**eintrag, "preis": "" if eintrag["preis"] is None else eintrag["preis"]},
                  zeigt_preis=bool(sitzung.darf("inventar", "kosten_sehen")))


@router.post(WEG + "/bauteile", response_class=HTMLResponse)
def bauteil_speichern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    preis = _text(f, "preis") if sitzung.darf("inventar", "kosten_sehen") else ""
    return _speichern(request, sitzung, "bauteile", lambda: katalogpflege.bauteil_speichern(
        sitzung, _text(f, "bauteilnummer"), _text(f, "bezeichnung"), _text(f, "hersteller"), preis, _text(f, "hinweis"), "aktiv" in f))


# ---- Kostensätze --------------------------------------------------------------------------------------------------

@router.get(WEG + "/kostensaetze", response_class=HTMLResponse)
def kostensaetze(
    request: Request, fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "kosten_pflegen")),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    namen = {int(g.id): g.bezeichnung for g in sitzung.db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid)).scalars()}
    gruppen_liste = list(sitzung.db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == mid, m.Gruppe.aktiv)
                                            .order_by(m.Gruppe.sortierung, m.Gruppe.id)).scalars())
    zeilen = [{"gruppe": namen.get(int(s.gruppe_id), ""), "ab": s.gueltig_ab, "nutzungsdauer": s.nutzungsdauer_monate,
               "zins": s.zins_prozent, "reparatur": s.reparatur_prozent_jahr, "restwert": s.restwert_prozent, "monat": s.satz_monat,
               "tag": s.satz_tag, "woche": s.satz_woche, "stunde": s.satz_stunde, "quelle": s.quelle}
              for s in sitzung.db.execute(select(m.Kostensatz).where(m.Kostensatz.mandant_id == mid, m.Kostensatz.gruppe_id.is_not(None))
                                          .order_by(m.Kostensatz.gruppe_id, m.Kostensatz.gueltig_ab.desc())).scalars()]
    return _seite(request, sitzung, "inventar_verwaltung_kostensaetze.html", "kostensaetze", zeilen=zeilen, fertig=bool(fertig),
                  gruppen=[(g.schluessel, g.bezeichnung) for g in gruppen_liste], heute=helfer.heute())


@router.post(WEG + "/kostensaetze", response_class=HTMLResponse)
def kostensatz_speichern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "kosten_pflegen")),
) -> HTMLResponse:
    return _speichern(request, sitzung, "kostensaetze", lambda: katalogpflege.kostensatz_speichern(
        sitzung, _text(f, "gruppe"), _text(f, "nutzungsdauer"), _text(f, "zins"), _text(f, "reparatur"), _text(f, "restwert"),
        _text(f, "satz_monat"), _text(f, "satz_tag"), _text(f, "satz_woche"), _text(f, "satz_stunde"), helfer.datum(_text(f, "ab"))))


# ---- Einstellungen ------------------------------------------------------------------------------------------------

@router.get(WEG + "/einstellungen", response_class=HTMLResponse)
def einstellungen_seite(
    request: Request, fertig: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    felder = [(s, katalog.einstellung(sitzung.db, mid, s)) for s in katalogpflege.EINSTELLUNGEN_ZAHL + ("nummernmuster", "zins_prozent", "etikett_layout", "erinnern_um")]
    return _seite(request, sitzung, "inventar_verwaltung_einstellungen.html", "einstellungen", felder=felder, fertig=bool(fertig),
                  auslieferung=katalog.einstellung(sitzung.db, mid, "auslieferung_am"))


@router.post(WEG + "/einstellungen", response_class=HTMLResponse)
def einstellungen_speichern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    namen = katalogpflege.EINSTELLUNGEN_ZAHL + ("nummernmuster", "zins_prozent", "etikett_layout", "erinnern_um", "auslieferung_am")
    return _speichern(request, sitzung, "einstellungen", lambda: katalogpflege.einstellungen_speichern(
        sitzung, {n: _text(f, n) for n in namen if n in f}))


# ---- Import -------------------------------------------------------------------------------------------------------

def _ordnername(sitzung: Sitzung) -> str:
    return sitzung.db.execute(select(Mandant.ordnername).where(Mandant.id == sitzung.kontext.mandant_id)).scalar_one()


@router.get(WEG + "/import/vorlage", response_class=Response)
def import_vorlage_laden(
    sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> Response:
    """Die Excel-Vorlage; die Kostenstellen des Mandanten stehen im Kommentar der Kopfzeile."""
    mid = sitzung.kontext.mandant_id
    with tempfile.TemporaryDirectory() as ordner:
        pfad = Path(ordner) / "vorlage.xlsx"
        import_vorlage.erzeuge_vorlage(pfad, katalog.gruppen(sitzung.db, mid), katalog.merkmale(sitzung.db, mid))
        inhalt = pfad.read_bytes()
    return Response(inhalt, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="inventar_vorlage.xlsx"'})


def _bericht_zeilen(erg: import_lauf.Bericht) -> dict[str, Any]:
    plan = erg.plan
    return {
        "fehler": [{"zeile": f.zeile, "spalte": f.spalte, "text": f.text_schluessel, "wert": f.wert} for f in erg.lesen.fehler],
        "hinweise": [{"zeile": h.zeile, "text": h.text_schluessel} for h in erg.lesen.hinweise],
        "gelesen": len(erg.lesen.zeilen),
        "je_gruppe": [] if plan is None else [{"gruppe": z.gruppe, "art": z.art, "neu": z.neu, "unveraendert": z.unveraendert,
                                                "abweichend": z.abweichend} for z in plan.bericht],
        "abweichungen": [] if plan is None else [{"text": h.text_schluessel, "detail": h.detail} for h in plan.hinweise],
        "neu": 0 if plan is None else len(plan.neu), "angelegt": erg.angelegt, "unbekannte_lieferanten": list(erg.lieferanten_unbekannt),
    }


@router.get(WEG + "/import", response_class=HTMLResponse)
def import_seite(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    return _seite(request, sitzung, "inventar_verwaltung_import.html", "import", bericht=None, datei="")


@router.post(WEG + "/import", response_class=HTMLResponse)
def import_ausfuehren(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    """Schritt 1: Datei hochladen und prüfen (Bericht). Schritt 2: mit der Kennung der Datei einspielen — nur ohne Fehler."""
    ordner = dateien.importordner(helfer.arbeitsordner(), _ordnername(sitzung))
    try:
        if _text(f, "aktion") == "einspielen":
            kennung = _text(f, "datei")
            if not HEX.match(kennung):
                raise ValueError("import_lauf.datei_unbekannt")
            pfad = ordner / f"{kennung}.xlsx"
            if not pfad.is_file():
                raise ValueError("import_lauf.datei_unbekannt")
            erg = import_lauf.einspielen(sitzung, pfad)
        else:
            hochgeladen = f.get("datei")
            if hochgeladen is None or isinstance(hochgeladen, str) or not hochgeladen.filename:
                raise ValueError("import_lauf.datei_fehlt")
            inhalt = hochgeladen.file.read(IMPORT_HOECHSTENS + 1)
            if len(inhalt) > IMPORT_HOECHSTENS:
                raise ValueError("import_lauf.datei_gross")
            ordner.mkdir(parents=True, exist_ok=True)
            kennung = helfer.neuer_schluessel().replace("-", "")
            pfad = ordner / f"{kennung}.xlsx"
            pfad.write_bytes(inhalt)
            try:
                erg = import_lauf.bericht(sitzung, pfad)
            except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError) as ursache:
                raise ValueError("import_lauf.datei_unlesbar") from ursache
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _seite(request, sitzung, "inventar_verwaltung_import.html", "import", bericht=_bericht_zeilen(erg), datei=kennung)


# ---- Etiketten ----------------------------------------------------------------------------------------------------

@router.get(WEG + "/etiketten", response_class=HTMLResponse)
def etiketten_seite(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    wahl = wahlfeld.kostenstelle(sitzung, feld="kostenstelle", modul="inventar", aktion="sehen", leer="inventar.alle", kennung="wahl-etikett-ks",
                                 beschriftung="inventar.feld.kostenstelle")
    return _seite(request, sitzung, "inventar_verwaltung_etiketten.html", "etiketten", gruppen=liste.gruppen_auswahl(sitzung), wahl_ks=wahl)


@router.post(WEG + "/etiketten", response_class=Response)
def etiketten_drucken(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> Response:
    """Bogen als PDF zum Herunterladen; dieselbe Datei liegt unter `export/etiketten_<datum>.pdf`."""
    basis = einstellungen.konfiguration().modul_werte.get("INVENTAR_ETIKETT_URL", "").strip() or str(request.base_url).rstrip("/")
    liste_text = [n for n in re.split(r"[\s,;]+", _text(f, "nummern")) if n]
    try:
        auswahl = liste_text or liste.nummern(sitzung, liste.Filter(gruppe=_text(f, "gruppe"), kostenstelle=_text(f, "kostenstelle")))
        if not auswahl:
            raise ValueError("etiketten.leer")
        html = fachetiketten.bogen(sitzung, auswahl, basis)
        inhalt, pfad = fachetiketten.pdf_ablegen(sitzung, html, helfer.arbeitsordner())
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return Response(inhalt, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{pfad.name}"'})


# ---- Testdaten ----------------------------------------------------------------------------------------------------

@router.post(WEG + "/testdaten", response_class=HTMLResponse)
def testdaten_einspielen(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    try:
        anzahl = testdaten.einspielen(sitzung, helfer.ganzzahl(_text(f, "seed"), 1) or 1, helfer.ganzzahl(_text(f, "anzahl"), 200) or 200)
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return gemeinsam.teil("teil_inventar_fertig.html", text=t("inventar.testdaten_fertig", anzahl=anzahl))


@router.get(WEG + "/testdaten", response_class=HTMLResponse)
def testdaten_seite(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "einstellen")),
) -> HTMLResponse:
    erlaubt = testdaten.erlaubt(sitzung.db, sitzung.kontext.mandant_id)
    return _seite(request, sitzung, "inventar_verwaltung_testdaten.html", "testdaten", erlaubt=erlaubt)
