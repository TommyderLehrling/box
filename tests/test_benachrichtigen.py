"""Die eine Mailstelle des Moduls ohne Datenbank: Adresse, Schlüsselwörter, Mandant, Fehlerfall — und niemand sonst reiht Mails ein."""
from __future__ import annotations

import re
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from pfade import PAKET
from digiassistenz_inventar.dienstlogik import benachrichtigen


class _Db:
    """Eine Sitzung, die nur mitschreibt: was hinzugefügt wurde, und ob eine Teiltransaktion geöffnet war."""

    def __init__(self) -> None:
        self.hinzu: list[object] = []
        self.teil = 0

    def add(self, satz: object) -> None:
        self.hinzu.append(satz)

    @contextmanager
    def begin_nested(self):
        self.teil += 1
        yield


@pytest.fixture
def aufruf(angemeldet, monkeypatch):
    """Ein Konto mit den gegebenen Adressen und ein Ersatz für `mail.einreihen`, der seine Aufrufe merkt."""
    gerufen: list[tuple[tuple, dict]] = []

    def einrichten(email="", benachrichtigung="", fehler: Exception | None = None):
        monkeypatch.setattr(benachrichtigen, "konto", lambda *_a: SimpleNamespace(id=5, email=email, benachrichtigung_email=benachrichtigung))

        def einreihen(*args, **kw):
            gerufen.append((args, kw))
            if fehler is not None:
                raise fehler

        monkeypatch.setattr(benachrichtigen.mail, "einreihen", einreihen)
        return gerufen

    return einrichten


def _aktionen(db: _Db) -> list[str]:
    return [e.aktion for e in db.hinzu]


def test_die_adresse_ist_benachrichtigung_sonst_email(aufruf):
    gerufen = aufruf(email="buero@firma.invalid", benachrichtigung="melder@firma.invalid")
    db = _Db()
    assert benachrichtigen.benachrichtigen(db, 5, "werkstatt_erledigt", mandant_id=3, nummer="BM-1", bezeichnung="Bagger", art="Schaden",
                                           beschreibung="Schlauch", rueckmeldung="getauscht", grund="") is True
    assert gerufen[0][1]["an"] == ["melder@firma.invalid"]
    gerufen.clear()
    aufruf(email="buero@firma.invalid")
    benachrichtigen.benachrichtigen(db, 5, "transfer_erinnert", mandant_id=3, nummer="BM-1", tage=3)
    assert db.teil == 2


def test_alle_argumente_nach_db_nur_als_schluesselwoerter_und_der_mandant_immer(aufruf):
    gerufen = aufruf(email="a@b.invalid")
    db = _Db()
    benachrichtigen.benachrichtigen(db, 5, "transfer_erinnert", mandant_id=3, von=7, nummer="BM-1", tage=3)
    args, kw = gerufen[0]
    assert args == (db,), "nach `db` kein Argument ohne Namen"
    assert kw["mandant_id"] == 3 and kw["benutzer_id"] == 7 and kw["an"] == ["a@b.invalid"]
    assert "BM-1" in kw["betreff"] and "3 Werktagen" in kw["text"]
    with pytest.raises(TypeError):
        benachrichtigen.benachrichtigen(db, 5, "transfer_erinnert", nummer="BM-1", tage=3)  # type: ignore[call-arg]  — ohne Mandant geht es nicht


def test_ohne_adresse_wird_nichts_eingereiht_sondern_vermerkt(aufruf):
    gerufen = aufruf(email="", benachrichtigung="")
    db = _Db()
    assert benachrichtigen.benachrichtigen(db, 5, "transfer_erinnert", mandant_id=3, objekt_id=12, nummer="BM-1", tage=3) is False
    assert gerufen == [] and _aktionen(db) == ["inventar.mail_ohne_adresse"]
    assert db.hinzu[0].objekt_id == 12 and db.hinzu[0].mandant_id == 3


def test_ohne_aktives_konto_wird_ebenfalls_vermerkt(angemeldet, monkeypatch):
    monkeypatch.setattr(benachrichtigen, "konto", lambda *_a: None)
    db = _Db()
    assert benachrichtigen.benachrichtigen(db, 99, "transfer_erinnert", mandant_id=3, nummer="BM-1", tage=3) is False
    assert _aktionen(db) == ["inventar.mail_ohne_adresse"]


def test_scheitert_das_einreihen_bleibt_die_handlung_und_ein_vermerk_sagt_es(aufruf):
    aufruf(email="a@b.invalid", fehler=RuntimeError("Warteschlange kaputt"))
    db = _Db()
    assert benachrichtigen.benachrichtigen(db, 5, "transfer_erinnert", mandant_id=3, objekt_id=12, nummer="BM-1", tage=3) is False
    assert _aktionen(db) == ["inventar.mail_nicht_eingereiht"] and db.teil == 1, "in einer Teiltransaktion, damit nichts mitgerissen wird"


def test_nur_die_benachrichtigungsstelle_reiht_mails_ein():
    treffer = [p.relative_to(PAKET).as_posix() for p in PAKET.rglob("*.py") if re.search(r"\bmail\.einreihen\(", p.read_text(encoding="utf-8"))]
    assert treffer == ["dienstlogik/benachrichtigen.py"], treffer
