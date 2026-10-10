"""Der Tagesplan des Erinnerungsprozesses: Uhrzeit lesen, „ist der Lauf des Tages dran?“ — ohne Uhr, ohne Datenbank."""

import datetime as dt

import pytest

from digiassistenz_inventar.rein import zeitplan


@pytest.mark.parametrize("text,erwartet", [("06:00", dt.time(6, 0)), ("6:05", dt.time(6, 5)), (" 23:59 ", dt.time(23, 59)), ("00:00", dt.time(0, 0))])
def test_uhrzeit_wird_gelesen(text, erwartet):
    assert zeitplan.uhrzeit(text) == erwartet


@pytest.mark.parametrize("text", ["", "6", "24:00", "12:60", "12-30", "12:3", "abc", "06:00:00"])
def test_ungueltige_uhrzeit_ist_ein_fehler_mit_satzschluessel(text):
    with pytest.raises(ValueError, match="zeitplan.uhrzeit_ungueltig"):
        zeitplan.uhrzeit(text)


def test_kaputte_einstellung_haelt_den_prozess_nicht_an():
    assert zeitplan.uhrzeit_oder_standard("kaputt") == dt.time(6, 0)
    assert zeitplan.uhrzeit_oder_standard("") == dt.time(6, 0)
    assert zeitplan.uhrzeit_oder_standard("07:30") == dt.time(7, 30)


def test_tag_lesen():
    assert zeitplan.tag_lesen("2026-10-10") == dt.date(2026, 10, 10)
    assert zeitplan.tag_lesen("") is None and zeitplan.tag_lesen("morgen") is None


def jetzt(stunde: int, minute: int = 0, tag: int = 10) -> dt.datetime:
    return dt.datetime(2026, 10, tag, stunde, minute, tzinfo=dt.timezone(dt.timedelta(hours=2)))


def test_vor_der_uhrzeit_ist_nichts_dran():
    assert not zeitplan.ist_dran(jetzt(5, 59), dt.time(6, 0), None)


def test_ab_der_uhrzeit_ist_der_lauf_dran_einmal_am_tag():
    assert zeitplan.ist_dran(jetzt(6, 0), dt.time(6, 0), None)
    assert zeitplan.ist_dran(jetzt(6, 0), dt.time(6, 0), dt.date(2026, 10, 9))
    assert not zeitplan.ist_dran(jetzt(6, 1), dt.time(6, 0), dt.date(2026, 10, 10)), "heute schon gelaufen"


def test_ein_verpasster_lauf_holt_am_selben_tag_nach():
    assert zeitplan.ist_dran(jetzt(14, 30), dt.time(6, 0), dt.date(2026, 10, 9))


def test_neuer_tag_neuer_lauf():
    assert zeitplan.ist_dran(jetzt(6, 0, tag=11), dt.time(6, 0), dt.date(2026, 10, 10))
