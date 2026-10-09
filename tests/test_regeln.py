"""Bauweise-Regeln des Kerns (Steckbrief 10), nachgebaut für dieses Paket: T-K-10d, T-K-12/12d, T-AP02-10/11/13, T-Z-1."""
from __future__ import annotations

import ast
import re

import pytest

from pfade import PAKET, WURZEL

DATEIEN = sorted(p for p in PAKET.rglob("*.py") if "__pycache__" not in p.parts)
VORLAGEN = sorted((PAKET / "vorlagen").glob("*.html"))
MODUL_PRAEFIXE = ("beleg.", "rechnung.", "maske.", "export.", "auswertung.", "stunden.", "bericht.", "merker.",
                  "/pruefen", "/belege", "/ablegen", "/baustelle")
WORT_BELEG = re.compile(r"(?<![a-z])beleg(?![a-z])", re.I)
TEIL_BELEG = re.compile(r"^beleg(?!t$|ung$|t_|ung_)")


def baum(pfad):
    return ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))


def texte_im_code(pfad, ohne_docstrings: bool = True):
    """Alle Zeichenketten-Konstanten mit Knoten; Docstrings und alleinstehende Zeichenketten bleiben draußen."""
    b = baum(pfad)
    if ohne_docstrings:
        weg = {id(k.value) for k in ast.walk(b) if isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant)}
    else:
        weg = set()
    return [(k, k.value) for k in ast.walk(b) if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in weg]


def test_paket_hat_dateien():
    assert len(DATEIEN) > 30 and len(VORLAGEN) >= 6, "ein leerer Suchraum ist kein Grün"


def test_T_K_10d_kein_import_eines_anderen_moduls_und_nie_die_modelle_des_kerns():
    muster = re.compile(r"^\s*(?:from|import)\s+(digiassistenz(?:\.|\s|$)|digiassistenz_baustelle|digiassistenz_kern\.modelle)", re.M)
    treffer = [str(p.relative_to(WURZEL)) for p in DATEIEN if muster.search(p.read_text(encoding="utf-8"))]
    assert treffer == []


def test_T_K_12_keine_fremden_wege_bausteine_oder_prozesse_ausserhalb_der_verbindung():
    fehler = []
    for p in DATEIEN:
        b = baum(p)
        in_verbindung = {
            id(k) for aufruf in ast.walk(b) if isinstance(aufruf, ast.Call)
            and getattr(aufruf.func, "id", getattr(aufruf.func, "attr", "")) == "Verbindung" for k in ast.walk(aufruf)}
        for k, wert in texte_im_code(p):
            if id(k) not in in_verbindung and wert.startswith(MODUL_PRAEFIXE):
                fehler.append(f"{p.relative_to(WURZEL)}: {wert}")
    assert fehler == []


def test_T_K_12d_das_wort_beleg_kommt_nirgends_vor():
    fehler = []
    for p in DATEIEN:
        b = baum(p)
        fehler += [f"{p.name}: {w!r}" for _, w in texte_im_code(p) if WORT_BELEG.search(w)]
        for k in ast.walk(b):
            namen = [k.id] if isinstance(k, ast.Name) else [k.name] if isinstance(k, (ast.FunctionDef, ast.ClassDef)) else \
                [k.attr] if isinstance(k, ast.Attribute) else [k.arg] if isinstance(k, ast.arg) else []
            fehler += [f"{p.name}: {n}" for n in namen if any(TEIL_BELEG.match(t) for t in n.lower().split("_"))]
    for v in VORLAGEN:
        ohne_kommentar = re.sub(r"\{#.*?#\}", "", v.read_text(encoding="utf-8"), flags=re.S)
        if WORT_BELEG.search(ohne_kommentar):
            fehler.append(v.name)
    assert fehler == []


def test_T_AP02_10_keine_systemsitzung_im_modul():
    treffer = [p.name for p in DATEIEN if re.search(r"^[^#\n]*systemsitzung\(", p.read_text(encoding="utf-8"), re.M)]
    assert treffer == []


def test_T_AP02_11_migrationen_sind_additiv_und_marke_i_vierstellig():
    versionen = sorted((PAKET / "migrationen" / "versions").glob("*.py"))
    assert versionen, "ein leerer Suchraum ist kein Grün"
    for p in versionen:
        assert re.match(r"^i\d{4}_", p.name), p.name
        hoch = p.read_text(encoding="utf-8").split("def downgrade", 1)[0]
        for verboten in ("op.drop_column(", "op.drop_table(", "op.drop_constraint(", "op.drop_index(", "op.alter_column("):
            assert verboten not in hoch, (p.name, verboten)
        assert not re.search(r"\bDELETE\b|\bTRUNCATE\b|\bDROP\b", hoch), p.name


def test_T_AP02_13_kein_deutscher_satz_im_code():
    """Wie im Kern: print/Fehler/RuntimeError/ValueError mit langer Zeichenkette ohne `t(`; ein Satz hat Leerzeichen."""
    muster = re.compile(r'(print|Fehler|RuntimeError|ValueError)\(\s*"([^"]{25,})"')
    treffer = []
    for p in DATEIEN:
        for zeile in p.read_text(encoding="utf-8").splitlines():
            m = muster.search(zeile)
            if m and "t(" not in zeile and " " in m.group(2):
                treffer.append(f"{p.name}: {zeile.strip()}")
    assert treffer == []


def test_keine_wanduhr_kein_print_nichts_loeschen():
    fehler = []
    for p in DATEIEN:
        quelle = p.read_text(encoding="utf-8")
        for verboten in ("datetime.now(", "datetime.utcnow(", "date.today(", "print(", ".delete(", "DELETE FROM", "session.delete"):
            if verboten in quelle and p.name != "migration_erzeugen.py":
                fehler.append(f"{p.name}: {verboten}")
    assert fehler == []


def test_T_Z_1_nur_lf_in_textdateien():
    textdateien = [p for p in list(PAKET.rglob("*")) + list((WURZEL / "tests").rglob("*")) + list(WURZEL.glob("*"))
                   if p.is_file() and p.suffix in {".py", ".html", ".json", ".css", ".js", ".md", ".toml", ".ini", ".txt", ".yml",
                                                   ".mako", ".sh", ".env", ".beispiel"} and "__pycache__" not in p.parts]
    assert len(textdateien) > 60
    assert [str(p.relative_to(WURZEL)) for p in textdateien if b"\r\n" in p.read_bytes()] == []


def test_kein_fremdschluessel_in_ein_anderes_modulschema():
    from digiassistenz_inventar import modelle

    ziele = {fk.target_fullname.split(".")[0] for t in modelle.Basis.metadata.tables.values()
             if t.schema == modelle.SCHEMA for c in t.columns for fk in c.foreign_keys}
    assert ziele == {"kern", "inventar"}


@pytest.mark.parametrize("datei", ["rechte.py", "modul.py"])
def test_modul_und_rechte_nennen_keinen_fremden_baustein(datei):
    for _, wert in texte_im_code(PAKET / datei):
        assert not wert.startswith(("beleg.", "rechnung.", "baustelle.", "app.")) or wert == "app.modul", wert
