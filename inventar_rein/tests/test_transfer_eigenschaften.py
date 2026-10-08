"""Eigenschaftstests fuer transfer: zufaellige Buchungsfolgen mit festem Startwert (P1-P4)."""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from inventar_rein.transfer import (
    Ergebnis,
    Standort,
    Transfer,
    Zustand,
    abgang_buchen,
    eingang_bestaetigen,
    erinnert,
    scan_ist_hier,
    zubehoer_folgt,
    zurueckziehen,
)

ZONE = timezone(timedelta(hours=1))
KOSTENSTELLEN = (100, 200, 300, 400)
STUECK = "SR-00001"
ANFANG = datetime(2026, 1, 1, 8, 0, tzinfo=ZONE)


def start(gesamt: int) -> Zustand:
    return Zustand((Standort(STUECK, 100, gesamt, ANFANG, None, None, "web", "anna"),), ())


def offen(z: Zustand) -> list[Standort]:
    return [s for s in z.standorte if s.bis is None]


def schwebend(z: Zustand) -> int:
    """Menge, die aus dem Standort abgespalten ist und auf Bestaetigung wartet."""
    return sum(t.menge for t in z.transfers if t.status == "angekuendigt" and t.abgespalten)


def pruefe_invarianten(z: Zustand, gesamt: int) -> None:
    ks = [s.kostenstelle for s in offen(z)]
    assert len(ks) == len(set(ks)), "hoechstens ein offener Standort je Kostenstelle"
    assert sum(s.menge for s in offen(z)) + schwebend(z) == gesamt, "Menge bleibt erhalten"
    assert all(s.menge >= 1 for s in offen(z)), "keine leeren Standorte"
    assert all(s.bis is None or s.bis >= s.von for s in z.standorte), "bis nicht vor von"
    ids = [t.id for t in z.transfers]
    assert len(ids) == len(set(ids)), "Transfer-Ids eindeutig"
    for t in z.transfers:
        assert t.status in ("angekuendigt", "bestaetigt", "ueberholt", "zurueckgezogen")
        assert (t.status == "bestaetigt") == (t.eingang_am is not None), "Eingang nur bei bestaetigt"
    frei = {s.kostenstelle: s.menge for s in offen(z)}
    ganze = sum(t.menge for t in z.transfers if t.status == "angekuendigt" and not t.abgespalten)
    assert ganze <= sum(frei.values()), "angekuendigte Ganz-Transfers liegen noch im Bestand"
    for t in z.transfers:
        if t.status == "angekuendigt" and not t.abgespalten:
            assert frei.get(t.von_kostenstelle, 0) >= t.menge, "Quelle hat noch genug"


def zufallsschritt(rng: random.Random, z: Zustand, nr: int, gesamt: int) -> tuple[Ergebnis | None, tuple]:
    """Fuehrt eine zufaellige Buchung aus; erlaubte Ablehnung (ValueError) liefert None."""
    zeit = ANFANG + timedelta(hours=nr + 1)
    schluessel = f"s{nr}"
    art = rng.choice(["abgang", "abgang", "scan", "scan", "eingang", "zurueck", "erinnert"])
    pend = [t for t in z.transfers if t.status == "angekuendigt"]
    try:
        if art == "abgang":
            von = rng.choice(KOSTENSTELLEN)
            nach = rng.choice([k for k in KOSTENSTELLEN if k != von])
            menge = rng.randint(1, gesamt)
            aufruf = ("abgang", von, nach, menge, schluessel)
            return abgang_buchen(z, STUECK, von, nach, menge, "p", zeit, "handy", schluessel), aufruf
        if art == "scan":
            ks = rng.choice(KOSTENSTELLEN)
            menge = rng.choice([None, None, rng.randint(1, gesamt)])
            aufruf = ("scan", ks, menge, schluessel)
            return scan_ist_hier(z, STUECK, ks, "p", zeit, "handy", schluessel, menge), aufruf
        if art == "eingang" and pend:
            t = rng.choice(pend)
            return eingang_bestaetigen(z, t.id, "p", zeit, "handy"), ("eingang", t.id)
        if art == "zurueck" and pend:
            t = rng.choice(pend)
            return zurueckziehen(z, t.id, "grund", "p", zeit), ("zurueck", t.id)
        if art == "erinnert" and pend:
            t = rng.choice(pend)
            return erinnert(z, t.id, zeit), ("erinnert", t.id)
    except ValueError:
        return None, ()
    return None, ()


@pytest.mark.parametrize("gesamt", [1, 40])
def test_P1_zufaellige_buchungsfolgen_halten_die_invarianten(gesamt: int):
    angewandt = 0
    for seed in range(250):
        rng = random.Random(seed)
        z = start(gesamt)
        for nr in range(30):
            vorher = (z.standorte, z.transfers)
            erg, _ = zufallsschritt(rng, z, nr, gesamt)
            assert (z.standorte, z.transfers) == vorher, "Eingabe bleibt unveraendert"
            if erg is not None:
                angewandt += 1
                z = erg.zustand
                pruefe_invarianten(z, gesamt)
    assert angewandt > 2000, "die Folgen sollen nicht an Ablehnungen haengen bleiben"


def test_P2_wiederholung_mit_gleichem_schluessel_aendert_nichts():
    pruefungen = 0
    for seed in range(150):
        rng = random.Random(1000 + seed)
        z = start(40)
        for nr in range(25):
            erg, aufruf = zufallsschritt(rng, z, nr, 40)
            if erg is None:
                continue
            if aufruf[0] in ("abgang", "scan") and erg.aenderungen:
                zeit = ANFANG + timedelta(hours=nr + 2)
                if aufruf[0] == "abgang":
                    _, von, nach, menge, sk = aufruf
                    nochmal = abgang_buchen(erg.zustand, STUECK, von, nach, menge, "p", zeit, "handy", sk)
                else:
                    _, ks, menge, sk = aufruf
                    nochmal = scan_ist_hier(erg.zustand, STUECK, ks, "p", zeit, "handy", sk, menge)
                if any(t.eintrag_schluessel == sk for t in erg.zustand.transfers):
                    assert nochmal.aenderungen == () and nochmal.zustand == erg.zustand
                    pruefungen += 1
            z = erg.zustand
    assert pruefungen > 200


def test_P3_aenderungen_beschreiben_den_zustandswechsel_vollstaendig():
    """Wer die Aenderungen der Reihe nach anwendet, kommt zum selben Zustand wie das Ergebnis."""
    for seed in range(120):
        rng = random.Random(5000 + seed)
        z = start(40)
        nachgebaut_standorte = list(z.standorte)
        nachgebaut_transfers = list(z.transfers)
        for nr in range(25):
            erg, _ = zufallsschritt(rng, z, nr, 40)
            if erg is None:
                continue
            for a in erg.aenderungen:
                d = a.daten
                if a.art == "standort_neu":
                    nachgebaut_standorte.append(Standort(d["stueck"], d["kostenstelle"], d["menge"], d["von"], None,
                                                         d["transfer_id"], d["quelle"], d["von_person"]))
                elif a.art == "standort_geschlossen":
                    i = next(i for i, s in enumerate(nachgebaut_standorte)
                             if s.bis is None and s.kostenstelle == d["kostenstelle"] and s.menge == d["menge"])
                    alt = nachgebaut_standorte[i]
                    nachgebaut_standorte[i] = Standort(alt.stueck, alt.kostenstelle, alt.menge, alt.von, d["bis"],
                                                       alt.transfer_id, alt.quelle, alt.von_person)
                elif a.art == "transfer_neu":
                    felder = {k: d[k] for k in Transfer.__dataclass_fields__}
                    nachgebaut_transfers.append(Transfer(**felder))
                elif a.art == "transfer_geaendert":
                    i = next(i for i, t in enumerate(nachgebaut_transfers) if t.id == d["id"])
                    nachgebaut_transfers[i] = replace(nachgebaut_transfers[i], **d["felder"])
            assert tuple(nachgebaut_standorte) == erg.zustand.standorte
            assert tuple(nachgebaut_transfers) == erg.zustand.transfers
            z = erg.zustand


def test_P4_zubehoer_zieht_mit_und_haelt_die_invarianten():
    for seed in range(80):
        rng = random.Random(9000 + seed)
        haupt = start(1)
        zubehoer = Zustand((Standort("AG-00001", 100, 1, ANFANG, None, None, "web", "anna"),), ())
        for nr in range(15):
            zeit = ANFANG + timedelta(hours=nr + 1)
            erg, _ = zufallsschritt(rng, haupt, nr, 1)
            if erg is None:
                continue
            haupt = erg.zustand
            try:
                folge = zubehoer_folgt(erg, ["AG-00001"], {"AG-00001": zubehoer}, zeit)["AG-00001"]
            except ValueError:
                continue
            zubehoer = folge.zustand
            ks = [s.kostenstelle for s in offen(zubehoer)]
            assert len(ks) == len(set(ks)) and sum(s.menge for s in offen(zubehoer)) == 1
