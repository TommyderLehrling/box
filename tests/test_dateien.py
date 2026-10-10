"""Nachweise: PDF, JPG oder PNG bis 10 MB — es zählt der Anfang der Datei, nicht der Name."""

import pytest

from digiassistenz_inventar import dateien

PNG = bytes.fromhex("89504e470d0a1a0a") + b"rest"


@pytest.mark.parametrize("inhalt,endung", [(b"%PDF-1.7 ...", ".pdf"), (b"\xff\xd8\xff\xe0abc", ".jpg"), (PNG, ".png")])
def test_erlaubte_nachweise(inhalt, endung):
    assert dateien.nachweis_pruefen(inhalt) == endung


@pytest.mark.parametrize("inhalt", [b"", b"GIF89a", b"<html>", b"PK\x03\x04", b"MZ"])
def test_andere_dateien_werden_abgewiesen(inhalt):
    with pytest.raises(dateien.DateiFehler, match="dateien.nachweis_typ"):
        dateien.nachweis_pruefen(inhalt)


def test_zu_grosse_nachweise_werden_abgewiesen():
    with pytest.raises(dateien.DateiFehler, match="dateien.nachweis_gross"):
        dateien.nachweis_pruefen(b"%PDF-" + b"0" * dateien.NACHWEIS_HOECHSTENS)
    assert dateien.nachweis_pruefen(b"%PDF-" + b"0" * (dateien.NACHWEIS_HOECHSTENS - 5)) == ".pdf"
