"""
Routes de governança de dades (RGPD), només admin.

- POST /api/dades/purga/analitzar  → manifest (només lectura) del que s'esborraria.
- POST /api/dades/purga/executar   → esborra realment (requereix confirmar=True).
"""
from datetime import date

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from dependencies import get_db
from auth_utils import get_current_user
import gestio_dades

router = APIRouter(prefix="/api/dades", tags=["Governança de dades"])


class AnalisiPurgaRequest(BaseModel):
    data_inici: date
    data_final: date


class ExecutarPurgaRequest(BaseModel):
    data_inici: date
    data_final: date
    confirmar: bool = False


class ReanomenaRequest(BaseModel):
    nom_actual: str
    nom_nou: str


@router.post("/purga/analitzar")
def analitzar_purga(req: AnalisiPurgaRequest,
                    db: Session = Depends(get_db),
                    current_user=Depends(get_current_user)):
    """Retorna el manifest (només lectura) de tot el que eliminaria la purga."""
    try:
        return gestio_dades.analitzar_purga(
            db, current_user.institucio, req.data_inici, req.data_final
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/purga/executar")
def executar_purga(req: ExecutarPurgaRequest,
                   db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    """Esborra realment les dades de l'interval. Requereix confirmar=True."""
    if not req.confirmar:
        raise HTTPException(
            status_code=400,
            detail="Cal confirmar l'operació (confirmar=true). És irreversible."
        )
    try:
        return gestio_dades.executar_purga(
            db, current_user.institucio, req.data_inici, req.data_final
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/professors")
def llista_professors(db: Session = Depends(get_db),
                      current_user=Depends(get_current_user)):
    """Llista de professors de la BD amb el flag actiu (per anonimitzar)."""
    return {"professors": gestio_dades.llista_professors_db(db)}


@router.post("/professors/reanomena")
def reanomena_professor(req: ReanomenaRequest,
                        db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)):
    """Reanomena/anonimitza un professor inactiu a tots els registres."""
    try:
        counts = gestio_dades.reanomena_professor(db, req.nom_actual, req.nom_nou)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "counts": counts, "total": sum(counts.values())}
