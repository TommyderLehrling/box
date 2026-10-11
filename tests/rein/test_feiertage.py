"""Prueffaelle Feiertage (L16, L16a): Sollwerte 2026 und 2027 je Land, von Hand aus dem Kalender — gegen das Paket `holidays==0.60`."""
from __future__ import annotations

from datetime import date

import pytest

from digiassistenz_inventar.rein import feiertage as f
from digiassistenz_inventar.rein.fristen import werktage_zwischen


def tage(jahr: int, *paare: tuple[int, int]) -> set[date]:
    return {date(jahr, m, t) for m, t in paare}


# Bundesweit: Neujahr, Karfreitag, Ostermontag, 1. Mai, Christi Himmelfahrt, Pfingstmontag, 3. Oktober, 25. und 26. Dezember
BUND = {
    2026: tage(2026, (1, 1), (4, 3), (4, 6), (5, 1), (5, 14), (5, 25), (10, 3), (12, 25), (12, 26)),
    2027: tage(2027, (1, 1), (3, 26), (3, 29), (5, 1), (5, 6), (5, 17), (10, 3), (12, 25), (12, 26)),
}
FRONLEICHNAM = {2026: date(2026, 6, 4), 2027: date(2027, 5, 27)}
OSTER_PFINGST_SONNTAG = {2026: tage(2026, (4, 5), (5, 24)), 2027: tage(2027, (3, 28), (5, 16))}
BUSSTAG = {2026: date(2026, 11, 18), 2027: date(2027, 11, 17)}

# Zusaetzlich je Land (Jahr -> Tage)
EXTRA = {
    "BW": lambda j: tage(j, (1, 6), (11, 1)) | {FRONLEICHNAM[j]},
    "BY": lambda j: tage(j, (1, 6), (11, 1)) | {FRONLEICHNAM[j]},
    "BE": lambda j: tage(j, (3, 8)),
    "BB": lambda j: tage(j, (10, 31)) | OSTER_PFINGST_SONNTAG[j],  # das Paket fuehrt in Brandenburg auch die Sonntage (ohne Wirkung auf Werktage)
    "HB": lambda j: tage(j, (10, 31)),
    "HH": lambda j: tage(j, (10, 31)),
    "HE": lambda j: {FRONLEICHNAM[j]},
    "MV": lambda j: tage(j, (3, 8), (10, 31)),
    "NI": lambda j: tage(j, (10, 31)),
    "NW": lambda j: tage(j, (11, 1)) | {FRONLEICHNAM[j]},
    "RP": lambda j: tage(j, (11, 1)) | {FRONLEICHNAM[j]},
    "SL": lambda j: tage(j, (8, 15), (11, 1)) | {FRONLEICHNAM[j]},
    "SN": lambda j: tage(j, (10, 31)) | {BUSSTAG[j]},
    "ST": lambda j: tage(j, (1, 6), (10, 31)),
    "SH": lambda j: tage(j, (10, 31)),
    "TH": lambda j: tage(j, (9, 20), (10, 31)),
}


def test_sechzehn_laender():
    assert len(f.LAENDER) == 16 and set(f.LAENDER) == set(EXTRA)


@pytest.mark.parametrize("jahr", [2026, 2027])
@pytest.mark.parametrize("land", sorted(EXTRA))
def test_L16_feiertage_je_land_und_jahr(land, jahr):
    assert f.feiertage(jahr, f"DE-{land}") == BUND[jahr] | EXTRA[land](jahr)


def test_L16a_de_allein_ist_bundesweit():
    assert f.feiertage(2026, "DE") == BUND[2026] and f.feiertage(2027, "DE") == BUND[2027]


def test_L16a_region_teilen():
    assert f.region_teilen("de-ni") == ("DE", "NI") and f.region_teilen("DE") == ("DE", "") and f.region_teilen("") == ("", "")


def test_L16_ohne_region_keine_feiertage():
    assert f.feiertage(2026, "") == set() and f.feiertage(2026, "  ") == set()
    assert f.feiertage_benannt(2026, "") == {}


def test_L16a_kleinschreibung_ok_unbekannte_region_fehler():
    assert f.feiertage(2026, "de-by") == f.feiertage(2026, "DE-BY")
    for falsch in ("XX", "DE-XX"):
        with pytest.raises(ValueError, match="feiertage.region_unbekannt"):
            f.feiertage(2026, falsch)


def test_L16a_namen_kommen_aus_dem_paket_auf_deutsch():
    benannt = f.feiertage_benannt(2026, "DE-SN")
    assert "Buß- und Bettag" in benannt[date(2026, 11, 18)] and "Karfreitag" in benannt[date(2026, 4, 3)]
    assert list(benannt) == sorted(benannt)


def test_L16a_andere_laender_gehen_durch_den_umschlag():
    assert date(2026, 7, 14) in f.feiertage(2026, "FR") and date(2026, 7, 14) not in f.feiertage(2026, "DE")


def test_L16_zeitraum_ueber_den_jahreswechsel():
    assert f.feiertage_zwischen(date(2026, 12, 24), date(2027, 1, 2), "DE-BE") == tage(2026, (12, 25), (12, 26)) | tage(2027, (1, 1))
    assert f.feiertage_zwischen(date(2027, 1, 2), date(2026, 12, 24), "DE-BE") == set()


def test_L16_werktage_ohne_und_mit_feiertag():
    # Mo 30.03.2026 bis Di 07.04.2026: Karfreitag 3.4. und Ostermontag 6.4. fallen aus
    von, bis = date(2026, 3, 29), date(2026, 4, 7)  # werktage_zwischen zaehlt (von, bis]
    assert werktage_zwischen(von, bis) == 7
    assert werktage_zwischen(von, bis, f.feiertage_zwischen(von, bis, "DE-NW")) == 5
