"""Fiktive, deterministische Testdaten aus einem Seed (keine echten Seriennummern)."""
from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

from .fristen import ampel, naechste_faelligkeit
from .import_vorlage import ImportZeile
from .kataloge import Gruppe, Merkmal, Pruefart
from .nummernformat import Muster, naechste
from .transfer import Transfer

# Anteil je Gruppe in Prozent (Baumaschinen 8, Fahrzeuge 6, KG/WZ/EL 50, CO/SR 10, BA/IT 20, Rest 6).
GEWICHTE = {
    "baumaschine": 8, "fahrzeug": 6, "kleingeraet": 20, "werkzeug": 20, "elektro": 10, "container": 5,
    "schalung_ruestung": 5, "bueroausstattung": 8, "it": 12, "anbaugeraet": 2, "vermessung": 2,
    "hebezeug_anschlag": 2,
}
_NAMEN = {
    "baumaschine": ["Hydraulikbagger 21 t", "Minibagger 1,8 t", "Radlader 8 t", "Kettendumper 6 t", "Tandemwalze 12 t", "Mobilbagger 14 t", "Planierraupe 18 t", "Teleskoplader 3,5 t"],
    "fahrzeug": ["Kipper 3-Achs", "Transporter 3,5 t", "Pritschenwagen", "Kleinbus 9 Sitze", "Sattelzugmaschine", "Kastenwagen"],
    "anbaugeraet": ["Tieflöffel 600 mm", "Grabenlöffel 400 mm", "Hydraulikhammer 800 kg", "Sortiergreifer", "Palettengabel", "Kehrbesen 2 m"],
    "kleingeraet": ["Rüttelplatte 400 kg", "Stampfer 70 kg", "Trennschleifer 400 mm", "Tauchpumpe 2 Zoll", "Stromerzeuger 8 kVA", "Bautrockner", "Kompressor 10 bar", "Nassschneider"],
    "werkzeug": ["Schaufel", "Spitzhacke", "Wasserwaage 2 m", "Schubkarre", "Maurerkelle-Set", "Stemmhammer", "Bohrhammer", "Akkuschrauber-Set"],
    "elektro": ["Kabeltrommel 50 m", "Baustromverteiler", "Verlängerungskabel 25 m", "Flutlichtstrahler", "Handlampe", "Heizlüfter 3 kW", "Kabelbrücke"],
    "vermessung": ["Nivelliergerät", "Rotationslaser", "Messlatte 5 m", "Tachymeter", "GNSS-Empfänger", "Fluchtstab"],
    "container": ["Bürocontainer 20 ft", "Lagercontainer 20 ft", "Sanitärcontainer 10 ft", "Mannschaftscontainer 20 ft", "Abrollcontainer 10 m³"],
    "schalung_ruestung": ["Schalungsstütze", "Schaltafel 50 x 250", "Gerüstrahmen 2 m", "Gerüstbelag 3 m", "Deckenträger 4 m", "Eckschalung"],
    "hebezeug_anschlag": ["Kettenzug 2 t", "Rundschlinge 3 t", "Anschlagkette 2-strängig", "Traverse 4 m", "Hebeband 5 t", "Schäkel 4,75 t"],
    "bueroausstattung": ["Schreibtisch 160×80", "Bürostuhl", "Rollcontainer", "Aktenschrank", "Besprechungstisch", "Regal 5 Fächer"],
    "it": ["Laptop 15 Zoll", "Tablet 10 Zoll", "Monitor 27 Zoll", "Drucker A3", "Smartphone", "Dockingstation"],
}
_HERSTELLER = ["Teramax", "Nordwerk", "Granit-Technik", "Falkenstein Geräte", "Alpha-Tec", "Brandt Maschinenbau", "Kessler & Söhne", "Ostmark Technik"]
_LIEFERANTEN = ["Maschinenhandel Weber", "Baugeräte Süd", "Technikhaus Nord", "Büroteam Mitte", "Fahrzeughandel Rhein", "Industriebedarf Lenz"]
_HINWEISE = ["Lackschaden links", "Ersatzschlüssel im Büro", "Hydraulikschlauch erneuert", "Vom Subunternehmer übernommen", "Akku schwächelt", "Aufkleber fehlt", "Gebraucht gekauft", "Nur mit Einweisung benutzen"]
_PREISE = {  # (min, max, Schritt)
    "baumaschine": (25000, 350000, 500), "fahrzeug": (18000, 120000, 500), "anbaugeraet": (1500, 30000, 50),
    "kleingeraet": (300, 9000, 10), "werkzeug": (15, 1200, 1), "elektro": (30, 2500, 1),
    "vermessung": (800, 25000, 50), "container": (2500, 14000, 50), "schalung_ruestung": (20, 400, 1),
    "hebezeug_anschlag": (60, 4500, 5), "bueroausstattung": (80, 1500, 1), "it": (200, 2500, 10),
}
_ART = {  # Anteil gross, Anteil menge; Rest klein
    "baumaschine": (1.0, 0.0), "fahrzeug": (1.0, 0.0), "kleingeraet": (0.15, 0.0), "werkzeug": (0.0, 0.4),
    "schalung_ruestung": (0.0, 0.9), "bueroausstattung": (0.0, 0.25),
}
_ZAHLEN = {"betriebsgewicht": (1, 40), "motorleistung": (15, 400), "kettenbreite": (300, 800),
           "zul_gesamtgewicht": (2800, 40000), "arbeitsbreite": (300, 2500), "anbaugewicht": (50, 3000),
           "geraetegewicht": (3, 800), "nennleistung": (200, 9000), "anschlussleistung": (100, 3500),
           "leitungslaenge": (5, 50), "elementlaenge": (500, 6000), "tragfaehigkeit_kn": (5, 80),
           "tragfaehigkeit_kg": (250, 5000), "nutzlaenge": (1, 6)}
_TEXTE = {"abmessungen": ["6,05 x 2,44 x 2,59 m", "3,00 x 2,44 x 2,59 m"], "moebelmasse": ["160 x 80 cm", "120 x 60 cm", "200 x 100 cm"],
          "raum": ["Büro 1.01", "Büro 2.04", "Besprechung", "Lager"], "betriebssystem": ["Windows 11", "Windows 10", "Android 14"],
          "benutzer": ["Team Bauleitung", "Team Disposition", "Team Büro"], "genauigkeit": ["± 2 mm", "± 5 mm", "± 1 mm"],
          "schalungssystem": ["Rahmenschalung R2", "Trägerschalung T4"], "werkzeugart": ["Handwerkzeug", "Maschinenwerkzeug"],
          "werkzeuggroesse": ["klein", "mittel", "groß"], "passend_fuer": ["Bagger 8-12 t", "Bagger 18-24 t", "Radlader"]}
_NAMEN = MappingProxyType({k: tuple(v) for k, v in _NAMEN.items()})
_TEXTE = MappingProxyType({k: tuple(v) for k, v in _TEXTE.items()})
_HERSTELLER, _LIEFERANTEN, _HINWEISE = tuple(_HERSTELLER), tuple(_LIEFERANTEN), tuple(_HINWEISE)
GEWICHTE, _PREISE, _ART, _ZAHLEN = (MappingProxyType(d) for d in (GEWICHTE, _PREISE, _ART, _ZAHLEN))
STANDARD_ANZAHL = 2500
_UTC = timezone.utc


@dataclass(frozen=True)
class Testdaten:
    stuecke: tuple[ImportZeile, ...]
    transfers: tuple[Transfer, ...]
    pruefungen: tuple[tuple[str, str, date, date], ...]  # (inventarnummer, pruefart, durchgefuehrt_am, faellig_am)
    zaehlerstaende: tuple[tuple[str, Decimal, date], ...]  # (inventarnummer, stand, abgelesen_am)


def _verteile(anzahl: int, gewichte: dict[str, int]) -> dict[str, int]:
    """Verteilt anzahl nach Gewichten (groesster Rest), Summe stimmt immer."""
    summe = sum(gewichte.values())
    exakt = {k: anzahl * w / summe for k, w in gewichte.items()}
    zahlen = {k: int(v) for k, v in exakt.items()}
    rest = anzahl - sum(zahlen.values())
    for k in sorted(gewichte, key=lambda k: (zahlen[k] - exakt[k], k))[:rest]:
        zahlen[k] += 1
    return zahlen


def _monate_zurueck(tag: date, monate: int) -> date:
    gesamt = tag.year * 12 + tag.month - 1 - monate
    jahr, monat0 = divmod(gesamt, 12)
    monat = monat0 + 1
    ersten = date(jahr + (monat == 12), monat % 12 + 1, 1)
    return date(jahr, monat, min(tag.day, (ersten - timedelta(days=1)).day))


def _merkmal_wert(rng: random.Random, m: Merkmal, stichtag: date) -> str:
    if m.typ == "zahl":
        lo, hi = _ZAHLEN.get(m.schluessel, (1, 100))
        return str(rng.randint(lo, hi))
    if m.typ == "datum":
        tage = rng.randint(-300, 700) if m.schluessel == "hu_faellig" else -rng.randint(0, 700)
        return (stichtag + timedelta(days=tage)).isoformat()
    if m.typ == "ja_nein":
        return rng.choice(["ja", "nein"])
    if m.typ == "auswahl":
        return rng.choice(m.auswahl)
    if m.schluessel == "kennzeichen":
        return f"{rng.choice(['MZ', 'WI', 'DA', 'KH'])}-{rng.choice('ABCDEFGHKLMNPRSTUVWXZ')}{rng.choice('ABCDEFGHKLMNPRSTUVWXZ')} {rng.randint(10, 9999)}"
    return rng.choice(_TEXTE.get(m.schluessel, ("k. A.",)))


def _fristen_vergeben(
    rng: random.Random, eintraege: list[tuple[str, int, date]], stichtag: date
) -> list[tuple[str, date, date]]:
    """Weist jedem Eintrag (nummer, intervall, kaufdatum) eine Pruefung zu: 8 % rot, 10 % gelb, Rest gruen."""
    n = len(eintraege)
    soll = {"rot": round(0.08 * n), "gelb": round(0.10 * n)}
    bereiche = {"rot": (-180, 0), "gelb": (1, 30)}
    zuteilung: dict[int, tuple[date, date]] = {}

    def versuche(i: int, farbe: str) -> bool:
        _, monate, kauf = eintraege[i]
        lo, hi = bereiche.get(farbe, (31, max(32, monate * 30)))
        for _ in range(25):
            ziel = stichtag + timedelta(days=rng.randint(lo, hi))
            ausgefuehrt = _monate_zurueck(ziel, monate)
            faellig = naechste_faelligkeit(ausgefuehrt, monate)
            if kauf <= ausgefuehrt <= stichtag and ampel(faellig, stichtag) == farbe:
                zuteilung[i] = (ausgefuehrt, faellig)
                return True
        return False

    reihenfolge = list(range(n))
    rng.shuffle(reihenfolge)
    for farbe in ("rot", "gelb"):
        gefunden = 0
        for i in reihenfolge:
            if gefunden >= soll[farbe]:
                break
            if i not in zuteilung and versuche(i, farbe):
                gefunden += 1
    for i in reihenfolge:
        if i not in zuteilung and not versuche(i, "gruen"):
            _, monate, kauf = eintraege[i]
            ausgefuehrt = max(kauf, stichtag - timedelta(days=rng.randint(0, 20)))
            zuteilung[i] = (ausgefuehrt, naechste_faelligkeit(ausgefuehrt, monate))
    return [(eintraege[i][0], *zuteilung[i]) for i in range(n)]


def erzeuge(
    seed: int, anzahl: int, gruppen: Iterable[Gruppe], merkmale: Iterable[Merkmal],
    pruefarten: Iterable[Pruefart], kostenstellen: Iterable[int], muster: Muster, stichtag: date,
) -> Testdaten:
    """Erzeugt anzahl fiktive Stuecke samt Transfers, Pruefungen und Zaehlerstaenden; gleiche Eingabe, gleiche Ausgabe."""
    gruppen = [g for g in gruppen if g.schluessel in GEWICHTE]
    merkmale = list(merkmale)
    pruefarten = list(pruefarten)
    kostenstellen = sorted(set(kostenstellen))
    if anzahl < 1 or not gruppen or not kostenstellen:
        raise ValueError("testdaten.eingabe_ungueltig")
    rng = random.Random(seed)
    je_gruppe = _verteile(anzahl, {g.schluessel: GEWICHTE[g.schluessel] for g in gruppen})
    kuerzel = {g.schluessel: g.kuerzel for g in gruppen}
    roh: list[tuple[date, str]] = []
    for g in gruppen:
        roh += [(stichtag - timedelta(days=rng.randint(1, 3650)), g.schluessel) for _ in range(je_gruppe[g.schluessel])]
    roh.sort(key=lambda x: (x[0], x[1]))
    zaehler: dict[str, int] = {}
    stuecke: list[ImportZeile] = []
    for i, (kauf, gruppe) in enumerate(roh):
        nummer, zaehler = naechste(muster, zaehler, kauf.year, kuerzel[gruppe])
        gross, menge_anteil = _ART.get(gruppe, (0.0, 0.0))
        x = rng.random()
        art = "gross" if x < gross else "menge" if x < gross + menge_anteil else "klein"
        lo, hi, schritt = _PREISE[gruppe]
        preis = Decimal(rng.randrange(lo, hi + 1, schritt))
        werte = {m.schluessel: _merkmal_wert(rng, m, stichtag) for m in merkmale
                 if m.gruppe == gruppe and (m.pflicht or rng.random() < 0.6) and m.schluessel != "fahrgestellnummer"}
        stuecke.append(ImportZeile(
            i + 2, nummer, rng.choice(_NAMEN[gruppe]), gruppe, art, rng.choice(_HERSTELLER),
            f"{rng.choice('ABCDEFGHKLMNPRSTUVWXZ')}{rng.choice('ABCDEFGHKLMNPRSTUVWXZ')}-{rng.randint(100, 999)}",
            f"TEST-{rng.randint(0, 999999):06d}", max(1950, kauf.year - rng.choice([0, 0, 0, 1, 2, 3])), kauf, preis,
            rng.choice(_LIEFERANTEN), rng.choice(kostenstellen), rng.randint(5, 80) if art == "menge" else 1, "", werte))
    for i in rng.sample(range(anzahl), round(0.20 * anzahl)):
        z = stuecke[i]
        stuecke[i] = ImportZeile(**{**z.__dict__, "besonderheiten": rng.choice(_HINWEISE)})
    transfers: list[Transfer] = []
    if len(kostenstellen) > 1:
        for i in sorted(rng.sample(range(anzahl), round(0.05 * anzahl))):
            z = stuecke[i]
            nach = rng.choice([k for k in kostenstellen if k != z.kostenstelle])
            menge = rng.randint(1, max(1, z.menge // 2)) if z.art == "menge" else 1
            abgang = datetime.combine(stichtag - timedelta(days=rng.randint(1, 10)), datetime.min.time(), _UTC) + timedelta(hours=8)
            transfers.append(Transfer(
                f"t:testdaten-{seed}-{z.inventarnummer}", z.inventarnummer, menge, z.kostenstelle, nach,
                "angekuendigt", abgang, "testdaten", None, None, "", "import",
                f"testdaten-{seed}-{z.inventarnummer}", None, menge < z.menge))
    eintraege: list[tuple[str, str, int, date]] = []
    for z in stuecke:
        for p in pruefarten:
            if z.gruppe in p.gruppen:
                eintraege.append((z.inventarnummer, p.schluessel, p.intervall_monate, z.kaufdatum or stichtag))
    vergeben = _fristen_vergeben(rng, [(n, m, k) for n, _, m, k in eintraege], stichtag)
    pruefungen = tuple((n, e[1], a, f) for e, (n, a, f) in zip(eintraege, vergeben))
    staende: list[tuple[str, Decimal, date]] = []
    for z in stuecke:
        if z.art == "gross":
            jahre = max(1, (stichtag - (z.kaufdatum or stichtag)).days / 365)
            jetzt = Decimal(rng.randint(100, 900)) * Decimal(str(round(jahre, 1)))
            alt = (jetzt * Decimal("0.8")).quantize(Decimal("0.1"))
            tag = stichtag - timedelta(days=rng.randint(0, 30))
            staende.append((z.inventarnummer, alt, tag - timedelta(days=rng.randint(60, 120))))
            staende.append((z.inventarnummer, jetzt.quantize(Decimal("0.1")), tag))
    return Testdaten(tuple(stuecke), tuple(transfers), pruefungen, tuple(staende))
