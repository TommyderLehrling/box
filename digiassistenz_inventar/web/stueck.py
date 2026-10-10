"""Die Stück-Seite, Stück anlegen und ändern, Status, Zubehör, Bauteil, Zählerstand und „Schaden melden“."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from digiassistenz_kern import zeit
from digiassistenz_kern.sitzung import Sitzung
from digiassistenz_kern.texte import t
from digiassistenz_kern.web import gemeinsam, wahlfeld

from .. import dateien
from .. import modelle as m
from .. import rechte
from ..dienstlogik import liste, nummer as nummernvergabe, pflege, stueck as fachstueck, stueckseite
from . import helfer, pruefdialog

router = APIRouter()
WEG = "/inventar/stueck"
FERTIG = ("angelegt", "geaendert", "status", "zubehoer", "bauteil", "zaehlerstand", "meldung", "abgang", "eingang", "zurueck", "scan",
          "pruefung", "pruefart")


async def formular(request: Request) -> dict[str, Any]:
    """Das Formular als einfaches Wörterbuch; Dateien bleiben `UploadFile`."""
    daten = await request.form()
    return {schluessel: wert for schluessel, wert in daten.multi_items()}


def _text(f: dict[str, Any], name: str) -> str:
    wert = f.get(name, "")
    return wert.strip() if isinstance(wert, str) else ""


def _datei(f: dict[str, Any], name: str) -> tuple[str, bytes] | None:
    """Eine hochgeladene Datei (höchstens 8 MB + 1 Byte gelesen, die Prüfung folgt in `dateien`)."""
    wert = f.get(name)
    if wert is None or isinstance(wert, str) or not getattr(wert, "filename", ""):
        return None
    inhalt = wert.file.read(dateien.FOTO_HOECHSTENS + 1)
    return (wert.content_type or "", inhalt) if inhalt else None


def _krumen(zeile: m.Stueck | None = None, titel: str = "") -> list[tuple[str, str]]:
    glieder = [(t("inventar.menue_inventar"), "/inventar")]
    if zeile is not None:
        glieder.append((zeile.inventarnummer, f"{WEG}/{int(zeile.id)}"))
    if titel:
        glieder.append((titel, ""))
    return glieder


def _merkmal_felder(sitzung: Sitzung, gruppe_id: int, werte: dict[str, str]) -> list[dict[str, Any]]:
    zeilen = sitzung.db.execute(select(m.Merkmal).where(
        m.Merkmal.mandant_id == sitzung.kontext.mandant_id, m.Merkmal.gruppe_id == gruppe_id, m.Merkmal.aktiv)
        .order_by(m.Merkmal.sortierung, m.Merkmal.id)).scalars()
    return [{"schluessel": z.schluessel, "bezeichnung": z.bezeichnung, "typ": z.typ, "einheit": z.einheit,
             "auswahl": list(z.auswahl or []), "pflicht": z.pflicht, "wert": werte.get(z.schluessel, "")} for z in zeilen]


def _merkmale_aus(f: dict[str, Any]) -> dict[str, str]:
    return {name[2:]: wert.strip() for name, wert in f.items() if name.startswith("m_") and isinstance(wert, str) and wert.strip()}


def _pflicht_fehlt(sitzung: Sitzung, gruppe_id: int, werte: dict[str, str]) -> bool:
    return any(z["pflicht"] and not werte.get(z["schluessel"]) for z in _merkmal_felder(sitzung, gruppe_id, werte))


def _vorschlag(sitzung: Sitzung, gruppe_id: int) -> str:
    zeile = sitzung.db.execute(select(m.Gruppe).where(m.Gruppe.mandant_id == sitzung.kontext.mandant_id, m.Gruppe.id == gruppe_id)).scalar_one_or_none()
    if zeile is None:
        return ""
    try:
        return nummernvergabe.vorschlag(sitzung.db, sitzung.kontext.mandant_id, zeile.kuerzel, zeit.heute().year)
    except ValueError:
        return ""


@router.get("/inventar/merkmale", response_class=HTMLResponse)
def merkmale_nachladen(
    gruppe: str = "", neu: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    """Die Merkmalsfelder einer Gruppe — dazu (beim Anlegen) der Nummernvorschlag als Platzhalter des Nummernfelds."""
    gruppe_id = sitzung.db.execute(select(m.Gruppe.id).where(
        m.Gruppe.mandant_id == sitzung.kontext.mandant_id, m.Gruppe.schluessel == gruppe)).scalar_one_or_none()
    if gruppe_id is None:
        raise gemeinsam.KeinRecht("inventar", "pflegen")
    return gemeinsam.teil("teil_inventar_merkmale.html", felder=_merkmal_felder(sitzung, int(gruppe_id), {}),
                          vorschlag=_vorschlag(sitzung, int(gruppe_id)) if neu else "", ist_neu=bool(neu))


def _form_seite(request: Request, sitzung: Sitzung, zeile: m.Stueck | None, werte: dict[str, Any] | None = None) -> HTMLResponse:
    mid = sitzung.kontext.mandant_id
    gruppen = liste.gruppen_auswahl(sitzung)
    if zeile is None:
        gruppe_id = int(sitzung.db.execute(select(m.Gruppe.id).where(m.Gruppe.mandant_id == mid, m.Gruppe.aktiv)
                                           .order_by(m.Gruppe.sortierung, m.Gruppe.bezeichnung).limit(1)).scalar_one_or_none() or 0)
        merkmal_werte: dict[str, str] = {}
    else:
        gruppe_id = int(zeile.gruppe_id)
        merkmal_werte = {s: w for s, w in sitzung.db.execute(
            select(m.Merkmal.schluessel, m.StueckMerkmal.wert).join(m.Merkmal, m.Merkmal.id == m.StueckMerkmal.merkmal_id)
            .where(m.StueckMerkmal.stueck_id == zeile.id)).all()}
    wahl_ks = wahlfeld.kostenstelle(sitzung, feld="kostenstelle", modul="inventar", aktion="pflegen", leer="inventar.waehlen",
                                    beschriftung="inventar.feld.startstandort", kennung="wahl-start-ks", pflicht=True)
    wahl_lieferant = wahlfeld.lieferant(sitzung, feld="lieferant_id", leer="inventar.kein_lieferant",
                                        gewaehlt=None if zeile is None else zeile.lieferant_id, kennung="wahl-lieferant")
    titel = t("inventar.stueck_neu") if zeile is None else t("inventar.taste.bearbeiten")
    return gemeinsam.seite(
        request, sitzung, "inventar_stueck_form.html", aktiv="inventar", brotkrumen=_krumen(zeile, titel), zeile=zeile, titel_form=titel,
        gruppen=gruppen, gruppe_gewaehlt=gruppe_id, felder=_merkmal_felder(sitzung, gruppe_id, merkmal_werte),
        vorschlag=_vorschlag(sitzung, gruppe_id) if zeile is None else "", ist_neu=False, arten=list(m.ART), wahl_ks=wahl_ks,
        wahl_lieferant=wahl_lieferant, buchung=helfer.neuer_schluessel(), rueckmeldung_objekt=("inventar.stueck", int(zeile.id) if zeile else 0),
        **rechte.darf_alle(sitzung))


@router.get(WEG + "/neu", response_class=HTMLResponse)
def neu_form(
    request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet), _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    return _form_seite(request, sitzung, None)


def _kaufpreis(sitzung: Sitzung, f: dict[str, Any]) -> Decimal | None:
    text = _text(f, "kaufpreis").replace(",", ".")
    if not text or not sitzung.darf("inventar", "kosten_pflegen"):
        return None
    try:
        preis = Decimal(text)
    except InvalidOperation:
        raise ValueError("web.zahl_ungueltig") from None
    if preis < 0:
        raise ValueError("web.zahl_ungueltig")
    return preis


@router.post(WEG + "/neu", response_class=HTMLResponse)
def neu_speichern(
    request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    try:
        gruppe = fachstueck.gruppe_holen(sitzung, _text(f, "gruppe"))
        werte = _merkmale_aus(f)
        if _pflicht_fehlt(sitzung, int(gruppe.id), werte):
            raise ValueError("web.merkmal_pflicht")
        start_ks = liste.kostenstelle_id(sitzung, _text(f, "kostenstelle"))
        if start_ks is None:
            raise ValueError("web.startstandort_fehlt")  # der Startstandort ist Pflicht: kein Stück ohne offenen Standort
        zeile = fachstueck.anlegen(
            sitzung, bezeichnung=_text(f, "bezeichnung"), gruppe=gruppe.schluessel, art=_text(f, "art"),
            inventarnummer=_text(f, "inventarnummer") or None, hersteller=_text(f, "hersteller"), typ=_text(f, "typ"),
            seriennummer=_text(f, "seriennummer"), baujahr=helfer.ganzzahl(_text(f, "baujahr")),
            lieferant_id=helfer.ganzzahl(_text(f, "lieferant_id")), kaufdatum=helfer.datum(_text(f, "kaufdatum")),
            kaufpreis=_kaufpreis(sitzung, f), kostenstelle_id=start_ks,
            menge=helfer.ganzzahl(_text(f, "menge"), 1) or 1, merkmale=werte, besonderheiten=_text(f, "besonderheiten"), quelle="web")
        foto = _datei(f, "foto")
        if foto is not None:
            pflege.foto_speichern(sitzung, zeile.inventarnummer, foto[0], foto[1], helfer.arbeitsordner())
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return gemeinsam.umleiten(f"{WEG}/{int(zeile.id)}?fertig=angelegt", request)


@router.get(WEG + "/{stueck_id}/aendern", response_class=HTMLResponse)
def aendern_form(
    stueck_id: int, request: Request, sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    return _form_seite(request, sitzung, stueckseite.holen(sitzung, stueck_id))


@router.post(WEG + "/{stueck_id}/aendern", response_class=HTMLResponse)
def aendern_speichern(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        angaben: dict[str, Any] = {
            "bezeichnung": _text(f, "bezeichnung"), "hersteller": _text(f, "hersteller"), "typ": _text(f, "typ"),
            "seriennummer": _text(f, "seriennummer"), "baujahr": helfer.ganzzahl(_text(f, "baujahr")),
            "lieferant_id": helfer.ganzzahl(_text(f, "lieferant_id")), "besonderheiten": _text(f, "besonderheiten")}
        if sitzung.darf("inventar", "kosten_pflegen"):
            angaben["kaufdatum"] = helfer.datum(_text(f, "kaufdatum"))
            angaben["kaufpreis"] = _kaufpreis(sitzung, f)
        werte = _merkmale_aus(f)
        if _pflicht_fehlt(sitzung, int(zeile.gruppe_id), werte):
            raise ValueError("web.merkmal_pflicht")
        pflege.aendern(sitzung, zeile.inventarnummer, angaben, werte)
        foto = _datei(f, "foto")
        if foto is not None:
            pflege.foto_speichern(sitzung, zeile.inventarnummer, foto[0], foto[1], helfer.arbeitsordner())
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return gemeinsam.umleiten(f"{WEG}/{stueck_id}?fertig=geaendert", request)


@router.get(WEG + "/{stueck_id}", response_class=HTMLResponse)
def stueck_seite(
    stueck_id: int, request: Request, ks: str = "", art: str = "", fertig: str = "", pruefart: str = "", weiter: str = "", stand: str = "",
    letzter: str = "", sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "sehen")),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    d = stueckseite.daten(sitzung, zeile)
    fertig = fertig if fertig in FERTIG else ""
    mid = sitzung.kontext.mandant_id
    von_ks = [o for o in d["offen"] if o["darf_buchen"]]
    wahl_nach = wahlfeld.kostenstelle(sitzung, feld="nach", modul="inventar", aktion="buchen", beschriftung="inventar.transfer.feld.nach",
                                      leer="inventar.waehlen", kennung="wahl-abgang-nach")
    melde_ks = [o for o in d["offen"] if o["darf_melden"]]
    bauteile_katalog = [(int(b.id), f"{b.bauteilnummer} {b.bezeichnung}") for b in sitzung.db.execute(
        select(m.Bauteil).where(m.Bauteil.mandant_id == mid, m.Bauteil.aktiv).order_by(m.Bauteil.bauteilnummer)).scalars()]
    status_moeglich = [s for s in m.STATUS if s != zeile.status
                       and sitzung.darf("inventar", "werkstatt" if s == "in_reparatur" else "stilllegen")]
    hauptlage = ("eingang" if any(x["darf_eingang"] for x in d["transfers"]) else "abgang" if von_ks else "")
    antwort = gemeinsam.seite(
        request, sitzung, "inventar_stueck.html", aktiv="inventar", brotkrumen=_krumen(zeile), fertig=fertig, wahl_nach=wahl_nach,
        zaehler_hinweis=helfer.zaehler_hinweis(stand, letzter) if fertig == "pruefung" else "",
        von_ks=von_ks, melde_ks=melde_ks, bauteile_katalog=bauteile_katalog, status_moeglich=status_moeglich, hauptlage=hauptlage,
        buchung=helfer.neuer_schluessel(), scan_ks=ks if ks.isdigit() else "", scan_art="kamera" if art == "kamera" else "",
        scan_ok=ks.isdigit() and bool(sitzung.darf("inventar", "scannen", int(ks))), rueckmeldung_objekt=("inventar.stueck", stueck_id),
        **pruefdialog.werte(sitzung, zeile, pruefart, weiter), **d, **rechte.darf_alle(sitzung))
    return antwort


def _zurueck(request: Request, stueck_id: int, fertig: str) -> HTMLResponse:
    return gemeinsam.umleiten(f"{WEG}/{stueck_id}?fertig={fertig}", request)


@router.post(WEG + "/{stueck_id}/status", response_class=HTMLResponse)
def status_setzen(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "stilllegen"), ("inventar", "werkstatt"))),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        fachstueck.status_wechseln(sitzung, zeile.inventarnummer, _text(f, "status"), _text(f, "grund"))
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _zurueck(request, stueck_id, "status")


@router.post(WEG + "/{stueck_id}/zubehoer", response_class=HTMLResponse)
def zubehoer(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        if _text(f, "beenden"):
            pflege.beziehung_beenden(sitzung, zeile.inventarnummer, helfer.ganzzahl(_text(f, "beenden"), 0) or 0)
        else:
            pflege.zubehoer_zuordnen(sitzung, zeile.inventarnummer, _text(f, "haupt_nummer"))
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _zurueck(request, stueck_id, "zubehoer")


@router.post(WEG + "/{stueck_id}/bauteil", response_class=HTMLResponse)
def bauteil(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "pflegen")),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        if _text(f, "beenden"):
            pflege.beziehung_beenden(sitzung, zeile.inventarnummer, helfer.ganzzahl(_text(f, "beenden"), 0) or 0)
        else:
            pflege.bauteil_zuordnen(sitzung, zeile.inventarnummer, helfer.ganzzahl(_text(f, "bauteil_id"), 0) or 0)
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _zurueck(request, stueck_id, "bauteil")


@router.post(WEG + "/{stueck_id}/zaehlerstand", response_class=HTMLResponse)
def zaehlerstand(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt_eines(("inventar", "scannen"), ("inventar", "pflegen"))),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        try:
            stand = Decimal(_text(f, "stand").replace(",", "."))
        except InvalidOperation:
            raise ValueError("web.zahl_ungueltig") from None
        pflege.zaehlerstand_eintragen(sitzung, zeile.inventarnummer, stand, liste.kostenstelle_id(sitzung, _text(f, "kostenstelle")), "web")
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _zurueck(request, stueck_id, "zaehlerstand")


@router.post(WEG + "/{stueck_id}/meldung", response_class=HTMLResponse)
def schaden_melden(
    stueck_id: int, request: Request, f: dict[str, Any] = Depends(formular), sitzung: Sitzung = Depends(gemeinsam.angemeldet),
    _recht=Depends(gemeinsam.verlangt("inventar", "melden")),
) -> HTMLResponse:
    zeile = stueckseite.holen(sitzung, stueck_id)
    try:
        ks = helfer.ganzzahl(_text(f, "kostenstelle_id"), 0) or 0
        pflege.schaden_melden(sitzung, zeile.inventarnummer, ks, _text(f, "beschreibung"), _text(f, "buchung") or helfer.neuer_schluessel(),
                              _datei(f, "foto"), helfer.arbeitsordner())
    except ValueError as fehler:
        sitzung.db.rollback()
        return helfer.fehlerteil(fehler)
    return _zurueck(request, stueck_id, "meldung")
