"""
Routes per als grups amagats (configuració de grups del centre):
- GET: obtenir la llista de grups que el centre amaga
- PUT: desar-la

Llista d'EXCLUSIÓ: sense classe i la resta mostren tots els grups detectats
excepte els amagats. Independent dels exàmens i dels nivells.
"""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dependencies import get_db
from repositories import GrupsAmagatsRepository

router = APIRouter(prefix="/api/grups-amagats", tags=["Grups amagats"])


@router.get("")
async def obtenir_grups_amagats(db: Session = Depends(get_db)):
    """Retorna la llista de grups amagats."""
    return {"grups": GrupsAmagatsRepository.get_all(db)}


@router.put("")
async def desar_grups_amagats(payload: Dict, db: Session = Depends(get_db)):
    """Desa la llista de grups amagats (reemplaça la llista sencera)."""
    grups = payload.get("grups")
    if not isinstance(grups, list):
        raise HTTPException(status_code=400, detail="'grups' ha de ser una llista")
    total = GrupsAmagatsRepository.set_all(db, grups)
    # L'horari filtra els grups segons aquesta llista durant la càrrega;
    # cal invalidar-lo perquè es recarregui.
    from helpers import invalidar_horari
    invalidar_horari()
    return {"success": True, "total": total}
