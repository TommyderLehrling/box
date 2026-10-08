"""Inventarnummern nach einem einstellbaren Muster; reine Funktionen ohne Zustand."""
from __future__ import annotations

import re
from dataclasses import dataclass

_ZEICHEN_GRUPPE = re.compile(r"[A-Z]{2}")
_NR_BREITE = re.compile(r"nr:(\d+)")
_MAX_BREITE = 12


@dataclass(frozen=True)
class Muster:
    """Nummernmuster, z. B. '{gruppe}-{nr:5}'."""

    text: str


def _zerlege(text: str) -> tuple[list[tuple[str, str | int]], list[str]]:
    """Zerlegt ein Muster in Bausteine und sammelt Fehlerschluessel."""
    teile: list[tuple[str, str | int]] = []
    fehler: list[str] = []
    nr_anzahl = 0
    pos = 0

    def roh(stueck: str) -> None:
        if "{" in stueck or "}" in stueck:
            fehler.append("muster.klammer_unpaarig")
        if stueck:
            teile.append(("text", stueck))

    for treffer in re.finditer(r"\{[^{}]*\}", text):
        roh(text[pos:treffer.start()])
        name = treffer.group(0)[1:-1]
        nr = _NR_BREITE.fullmatch(name)
        if name == "nr":
            fehler.append("muster.nr_breite_fehlt")
            nr_anzahl += 1
        elif nr:
            breite = int(nr.group(1))
            if str(breite) != nr.group(1) or not 1 <= breite <= _MAX_BREITE:
                fehler.append("muster.nr_breite_ungueltig")
            nr_anzahl += 1
            teile.append(("nr", breite))
        elif name in ("jahr", "jahr2", "gruppe"):
            teile.append((name, 0))
        else:
            fehler.append("muster.platzhalter_unbekannt:" + name)
        pos = treffer.end()
    roh(text[pos:])
    if nr_anzahl == 0:
        fehler.append("muster.nr_fehlt")
    elif nr_anzahl > 1:
        fehler.append("muster.nr_doppelt")
    return teile, fehler


def _teile(muster: Muster) -> list[tuple[str, str | int]]:
    """Liefert die Bausteine oder wirft ValueError bei ungueltigem Muster."""
    teile, fehler = _zerlege(muster.text)
    if fehler:
        raise ValueError(fehler[0])
    return teile


def pruefe_muster(text: str) -> list[str]:
    """Liefert Fehlerschluessel zum Muster; leere Liste bedeutet in Ordnung."""
    return _zerlege(text)[1]


def _benutzt(teile: list[tuple[str, str | int]], art: str) -> bool:
    return any(t[0] == art for t in teile)


def _pruefe_jahr(jahr: int) -> None:
    if not 1000 <= jahr <= 9999:
        raise ValueError("nummernformat.jahr_ungueltig")


def _pruefe_gruppe(gruppe: str | None) -> str:
    if gruppe is None:
        raise ValueError("nummernformat.gruppe_fehlt")
    if not _ZEICHEN_GRUPPE.fullmatch(gruppe):
        raise ValueError("nummernformat.gruppe_ungueltig")
    return gruppe


def zaehler_schluessel(muster: Muster, jahr: int, gruppe: str | None) -> str:
    """Nennt den Zaehler, der zaehlt: '' | '2026' | 'BM' | '2026/BM'."""
    teile = _teile(muster)
    schluessel: list[str] = []
    if _benutzt(teile, "jahr") or _benutzt(teile, "jahr2"):
        _pruefe_jahr(jahr)
        schluessel.append(str(jahr))
    if _benutzt(teile, "gruppe"):
        schluessel.append(_pruefe_gruppe(gruppe))
    return "/".join(schluessel)


def naechste(
    muster: Muster, letzte: dict[str, int], jahr: int, gruppe: str | None
) -> tuple[str, dict[str, int]]:
    """Gibt die naechste Nummer und den fortgeschriebenen Zaehlerstand zurueck."""
    teile = _teile(muster)
    schluessel = zaehler_schluessel(muster, jahr, gruppe)
    bisher = letzte.get(schluessel, 0)
    if bisher < 0:
        raise ValueError("nummernformat.zaehler_ungueltig")
    neu = bisher + 1
    nummer = ""
    for art, wert in teile:
        if art == "text":
            nummer += str(wert)
        elif art == "nr":
            nummer += str(neu).zfill(int(wert))
        elif art == "jahr":
            nummer += str(jahr)
        elif art == "jahr2":
            nummer += str(jahr % 100).zfill(2)
        else:
            nummer += str(gruppe)
    fortgeschrieben = dict(letzte)
    fortgeschrieben[schluessel] = neu
    return nummer, fortgeschrieben


def entspricht(muster: Muster, nummer: str) -> bool:
    """Prueft streng (ohne Normalisierung), ob die Nummer zum Muster passt."""
    regex = ""
    for art, wert in _teile(muster):
        if art == "text":
            regex += re.escape(str(wert))
        elif art == "nr":
            breite = int(wert)
            regex += f"(?:[0-9]{{{breite}}}|[1-9][0-9]{{{breite},}})"
        elif art == "jahr":
            regex += "[0-9]{4}"
        elif art == "jahr2":
            regex += "[0-9]{2}"
        else:
            regex += "[A-Z]{2}"
    return re.fullmatch(regex, nummer) is not None


def normalisiere(nummer: str) -> str:
    """Trimmt, macht Grossbuchstaben (ss-Laut bleibt) und kuerzt Leerraum auf eines."""
    gross = "".join(z if z == "ß" else z.upper() for z in nummer)
    return " ".join(gross.split())
