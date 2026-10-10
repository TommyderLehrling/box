"""Die Seiten des Inventars: ein Router, Unterrouter je Bereich."""

from __future__ import annotations

from fastapi import APIRouter

from . import hier, inventur, kosten, kostenstelle, pruefungen, seiten, stueck, transfer, verwaltung, werkstatt

router = APIRouter()
# Reihenfolge zählt: feste Wege (`/inventar/stueck/neu`, `/inventar/hier`) vor Wegen mit Platzhalter
router.include_router(seiten.router)
router.include_router(hier.router)
router.include_router(pruefungen.router)
router.include_router(werkstatt.router)
router.include_router(kosten.router)
router.include_router(inventur.router)
router.include_router(stueck.router)
router.include_router(transfer.router)
router.include_router(verwaltung.router)
router.include_router(kostenstelle.router)

__all__ = ["router"]
