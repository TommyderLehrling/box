"""Bausteine des Inventars, Vorlagen-Ergänzung, Nachzug und die Rechtefragen für Seiten (Spec v0.2 Abschnitt 3)."""

from __future__ import annotations

from typing import Any

from digiassistenz_kern.rechte import Modulrechte, VorlagenErgaenzung, _b

SCHLUESSEL = "inventar"

#: Die elf Bausteine in der Reihenfolge der Spec
AKTIONEN: tuple[str, ...] = (
    "sehen", "scannen", "buchen", "melden", "pflegen", "pruefen",
    "werkstatt", "stilllegen", "kosten_sehen", "kosten_pflegen", "einstellen",
)

#: Startwerte je Systemvorlage (Spec v0.2 Abschnitt 3); `verwalter` bekommt alles ohne Ergänzung
VORLAGEN: dict[str, tuple[str, ...]] = {
    "polier": ("sehen", "scannen", "buchen", "melden"),
    "bauleiter": ("sehen", "scannen", "buchen", "melden", "kosten_sehen"),
    "abteilungsleiter": ("sehen", "kosten_sehen"),
    "buero": ("sehen", "pflegen", "pruefen"),
    "einkauf": ("sehen", "pflegen", "kosten_sehen"),
    "abrechner": ("sehen", "kosten_sehen"),
    "buchhaltung": ("sehen", "kosten_sehen", "kosten_pflegen"),
    "geschaeftsfuehrung": ("sehen", "kosten_sehen"),
    "pruefer": ("sehen",),
}

NACHZUG_GRUND = "nachzug:inventar_einbau"


def baustein(aktion: str) -> str:
    return f"{SCHLUESSEL}.{aktion}"


#: Paare (Baustein, Grund): erreicht bestehende Konten, deren Vorlage den Baustein trägt (Kern 0.14.0)
NACHZUG: tuple[tuple[str, str], ...] = tuple((baustein(a), NACHZUG_GRUND) for a in AKTIONEN)

MODULRECHTE = Modulrechte(
    schluessel=SCHLUESSEL,
    bausteine=tuple(_b(baustein(a)) for a in AKTIONEN),
    ergaenzung=tuple(
        VorlagenErgaenzung(vorlage, tuple(baustein(a) for a in aktionen)) for vorlage, aktionen in VORLAGEN.items()
    ),
    nachzug=NACHZUG,
)


def darf(sitzung: Any, aktion: str, kostenstelle_id: int | None = None) -> bool:
    """Die Rechtefrage für eine Taste — nur Booleans gehen in den Kontext einer Vorlage."""
    return bool(sitzung.darf(SCHLUESSEL, aktion, kostenstelle_id))


def darf_alle(sitzung: Any, kostenstelle_id: int | None = None) -> dict[str, bool]:
    """`darf_<aktion>` für jede Aktion, bereit für den Kontext einer Seite."""
    return {f"darf_{a}": darf(sitzung, a, kostenstelle_id) for a in AKTIONEN}


def darf_sehen(sitzung: Any, kostenstelle_id: int | None = None) -> bool:
    return darf(sitzung, "sehen", kostenstelle_id)


def darf_buchen(sitzung: Any, kostenstelle_id: int | None = None) -> bool:
    return darf(sitzung, "buchen", kostenstelle_id)


def darf_pflegen(sitzung: Any, kostenstelle_id: int | None = None) -> bool:
    return darf(sitzung, "pflegen", kostenstelle_id)


def darf_kosten_sehen(sitzung: Any, kostenstelle_id: int | None = None) -> bool:
    return darf(sitzung, "kosten_sehen", kostenstelle_id)
