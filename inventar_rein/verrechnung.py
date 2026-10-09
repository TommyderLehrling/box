"""Verrechnung je Kostenstelle: Vorhaltung plus Einsatzstunden; Miete gegen eigen; CSV-Auswertung."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from .fristen import werktage_zwischen
from .kosten import _runde, miete_vs_eigen, vorhaltung
from .transfer import Standort

CSV_SPALTEN = ("kostenstelle", "inventarnummer", "tage", "betrag_vorhaltung", "stunden", "betrag_stunden", "summe")


@dataclass(frozen=True)
class VerrechnungsStueck:
    inventarnummer: str
    gruppe: str
    satz_tag: Decimal
    satz_stunde: Decimal | None
    standorte: tuple[Standort, ...]
    miete: bool = False
    miet_von: date | None = None
    miet_bis: date | None = None
    mietkosten: Decimal | None = None


@dataclass(frozen=True)
class Verrechnungszeile:
    kostenstelle: int
    inventarnummer: str
    tage: int
    betrag_vorhaltung: Decimal
    stunden: Decimal
    betrag_stunden: Decimal
    summe: Decimal


@dataclass(frozen=True)
class Summe:
    schluessel: str  # Kostenstelle bzw. Inventarnummer
    tage: int
    betrag_vorhaltung: Decimal
    stunden: Decimal
    betrag_stunden: Decimal
    summe: Decimal


@dataclass(frozen=True)
class Verrechnung:
    zeilen: tuple[Verrechnungszeile, ...]
    je_kostenstelle: tuple[Summe, ...]
    je_stueck: tuple[Summe, ...]
    hinweise: tuple[str, ...]


@dataclass(frozen=True)
class MieteGegenEigen:
    inventarnummer: str
    gruppe: str
    tage: int
    miete: Decimal
    eigen: Decimal | None  # None: kein eigenes Vergleichsstueck in der Gruppe
    differenz: Decimal | None


def _summiere(zeilen: Iterable[Verrechnungszeile], schluessel_von: str) -> tuple[Summe, ...]:
    summen: dict[str, list[Decimal | int]] = defaultdict(lambda: [0, Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
    for z in zeilen:
        s = summen[str(getattr(z, schluessel_von))]
        s[0] += z.tage
        s[1] += z.betrag_vorhaltung
        s[2] += z.stunden
        s[3] += z.betrag_stunden
        s[4] += z.summe
    ordnung = sorted(summen, key=lambda k: (int(k) if schluessel_von == "kostenstelle" else 0, k))
    return tuple(Summe(k, int(summen[k][0]), Decimal(summen[k][1]), Decimal(summen[k][2]), Decimal(summen[k][3]),
                       Decimal(summen[k][4])) for k in ordnung)


def verrechne(
    stuecke: Iterable[VerrechnungsStueck],
    stunden: Iterable[tuple[date, int, str, Decimal]],
    von: date,
    bis: date,
    werktage: bool = False,
    feiertage: Iterable[date] = (),
) -> Verrechnung:
    """Vorhaltung (mit Menge) plus Einsatzstunden mal Stundensatz je Kostenstelle und Stueck im Zeitraum [von, bis].

    Stunden ausserhalb des Zeitraums werden ignoriert; ohne Stundensatz zaehlen sie 0 und es gibt einen Hinweis.
    """
    if bis < von:
        raise ValueError("verrechnung.zeitraum_ungueltig")
    je_nummer = {s.inventarnummer: s for s in stuecke}
    frei = tuple(feiertage)
    std: dict[tuple[int, str], Decimal] = defaultdict(Decimal)
    for tag, ks, nummer, h in stunden:
        if nummer not in je_nummer:
            raise ValueError("verrechnung.stueck_unbekannt")
        if h < 0:
            raise ValueError("verrechnung.stunden_ungueltig")
        if von <= tag <= bis:
            std[(ks, nummer)] += h
    tage: dict[tuple[int, str], tuple[int, Decimal]] = {}
    for nummer, s in je_nummer.items():
        for v in vorhaltung(s.standorte, von, bis, s.satz_tag, True, werktage, frei):
            tage[(v.kostenstelle, nummer)] = (v.tage, v.betrag)
    hinweise: list[str] = []
    zeilen: list[Verrechnungszeile] = []
    for ks, nummer in sorted(set(tage) | set(std), key=lambda k: (k[0], k[1])):
        n, betrag_v = tage.get((ks, nummer), (0, Decimal("0.00")))
        h = std.get((ks, nummer), Decimal(0))
        satz = je_nummer[nummer].satz_stunde
        if h > 0 and satz is None:
            hinweise.append(f"verrechnung.satz_stunde_fehlt:{nummer}")
        betrag_s = _runde(h * satz) if satz is not None else Decimal("0.00")
        zeilen.append(Verrechnungszeile(ks, nummer, n, betrag_v, h, betrag_s, betrag_v + betrag_s))
    return Verrechnung(tuple(zeilen), _summiere(zeilen, "kostenstelle"), _summiere(zeilen, "inventarnummer"),
                       tuple(dict.fromkeys(hinweise)))


def miete_gegen_eigen(
    stuecke: Iterable[VerrechnungsStueck], von: date, bis: date, werktage: bool = False,
    feiertage: Iterable[date] = (),
) -> tuple[MieteGegenEigen, ...]:
    """Je Mietstueck: Mietkosten gegen den mittleren Tagessatz der eigenen Stuecke derselben Gruppe mal Miettage im Zeitraum."""
    if bis < von:
        raise ValueError("verrechnung.zeitraum_ungueltig")
    alle = list(stuecke)
    eigene: dict[str, list[Decimal]] = defaultdict(list)
    for s in alle:
        if not s.miete:
            eigene[s.gruppe].append(s.satz_tag)
    frei = frozenset(feiertage)
    ergebnis = []
    for s in sorted((x for x in alle if x.miete), key=lambda x: x.inventarnummer):
        if s.miet_von is None or s.miet_bis is None or s.mietkosten is None:
            raise ValueError("verrechnung.miete_unvollstaendig")
        anfang, ende = max(s.miet_von, von), min(s.miet_bis, bis)
        if ende < anfang:
            n = 0
        elif werktage:
            n = werktage_zwischen(anfang - timedelta(days=1), ende, frei)
        else:
            n = (ende - anfang).days + 1
        vergleich = eigene.get(s.gruppe)
        if not vergleich:
            ergebnis.append(MieteGegenEigen(s.inventarnummer, s.gruppe, n, _runde(s.mietkosten), None, None))
            continue
        mittel = sum(vergleich, Decimal(0)) / len(vergleich)
        miete, eigen, diff = miete_vs_eigen(s.mietkosten, mittel, n)
        ergebnis.append(MieteGegenEigen(s.inventarnummer, s.gruppe, n, miete, eigen, diff))
    return tuple(ergebnis)


def csv_text(zeilen: Iterable[Verrechnungszeile], trenner: str = ";", dezimal_komma: bool = True) -> str:
    """CSV der Verrechnungszeilen mit Kopfzeile; Standard fuer deutsches Excel (Semikolon, Dezimalkomma)."""
    def zahl(x: Decimal) -> str:
        text = f"{x:f}"
        return text.replace(".", ",") if dezimal_komma else text

    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=trenner, lineterminator="\r\n")
    schreiber.writerow(CSV_SPALTEN)
    for z in zeilen:
        schreiber.writerow([z.kostenstelle, z.inventarnummer, z.tage, zahl(z.betrag_vorhaltung), zahl(z.stunden),
                            zahl(z.betrag_stunden), zahl(z.summe)])
    return puffer.getvalue()


def schreibe_csv(pfad: Path, zeilen: Iterable[Verrechnungszeile], trenner: str = ";", dezimal_komma: bool = True) -> None:
    """Schreibt die CSV mit BOM (utf-8-sig), damit Excel Umlaute richtig liest."""
    pfad.write_text(csv_text(zeilen, trenner, dezimal_komma), encoding="utf-8-sig", newline="")
