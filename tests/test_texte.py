"""T-T-2 und T-HI-1 für dieses Paket: jeder Textschlüssel existiert, jede Seite hat vier Hilfeschlüssel (Steckbrief 10)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pfade import PAKET

EIGENE = json.loads((PAKET / "texte" / "de.json").read_text(encoding="utf-8"))
DATEIEN = [p for p in PAKET.rglob("*") if p.suffix in {".py", ".html", ".js"} and "__pycache__" not in p.parts
           and "rein" not in p.relative_to(PAKET).parts[:1]]
FEST = re.compile(r"""\bt\(\s*["']([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*[._]?)["']""")
SEITE = re.compile(r'seite = "([a-z_]+)"[^%]*%\}\{% include "teil_seitenkopf\.html"')


class _Dummy(dict):
    def __missing__(self, key: str) -> str:
        return "x"


def _vorhanden(schluessel: str) -> bool:
    from digiassistenz_kern import texte

    if schluessel in EIGENE or texte.schluessel_vorhanden(schluessel):
        return True
    if schluessel.endswith((".", "_")):  # Präfix eines dynamisch gebauten Schlüssels
        return any(k.startswith(schluessel) for k in EIGENE) or any(k.startswith(schluessel) for k in texte.alle_schluessel())
    return False


def test_T_T_2_jedes_t_hat_einen_schluessel(angemeldet):
    aufrufe = [(p.name, s) for p in DATEIEN for s in FEST.findall(p.read_text(encoding="utf-8"))]
    assert len(aufrufe) >= 40, "ein leerer Suchraum ist kein Grün"
    assert sorted({f"{n}: {s}" for n, s in aufrufe if not _vorhanden(s)}) == []


def test_T_HI_1_jede_seite_mit_seitenkopf_hat_vier_hilfeschluessel():
    seiten = [(p.name, s) for p in (PAKET / "vorlagen").glob("*.html") for s in SEITE.findall(p.read_text(encoding="utf-8"))]
    assert len(seiten) >= 4, "ein leerer Suchraum ist kein Grün"
    for datei, seite in seiten:
        for endung in ("", ".liegt", ".tasten", ".danach"):
            assert f"hilfe.{seite}{endung}" in EIGENE, (datei, seite, endung)


def test_keine_kernschluessel_ueberschrieben(angemeldet):
    kern = json.loads((Path(__import__("digiassistenz_kern").__file__).parent / "texte" / "de.json").read_text(encoding="utf-8"))
    assert sorted(set(EIGENE) & set(kern)) == []
    from digiassistenz_kern import texte

    assert texte.ueberschriebene() == ()


def test_jeder_text_laesst_sich_formatieren_und_hat_keinen_ausruf():
    for schluessel, text in EIGENE.items():
        text.format_map(_Dummy())
        assert "!" not in text, schluessel


def test_jeder_schluessel_beginnt_mit_einem_erlaubten_praefix():
    for schluessel in EIGENE:
        assert schluessel.startswith(("inventar.", "hilfe.inventar_", "recht.inventar_")), schluessel
