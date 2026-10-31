"""
Rutes de governança de dades (RGPD), només admin: només HTTP; la lògica, a
services.py.

- POST /api/dades/purga/analitzar  → manifest (només lectura) del que s'esborraria.
- POST /api/dades/purga/executar   → esborra realment (requereix confirmar=True).
- GET /api/dades/professors i POST /api/dades/professors/reanomena →
  anonimitzar un professor inactiu.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from dades import services
from dades.schemas import (
    AnalisiPurgaRequest,
    AnalisiPurgaResponse,
    ExecutarPurgaRequest,
    ProfessorsDeLaBdResponse,
    PurgaResponse,
    ReanomenaRequest,
    ReanomenaResponse,
)
from dependencies import get_db

router = APIRouter(prefix="/api/dades", tags=["Governança de dades"])


@router.post("/purga/analitzar", response_model=AnalisiPurgaResponse, response_model_exclude_unset=True)
def analitzar_purga(req: AnalisiPurgaRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Retorna el manifest (només lectura) de tot el que eliminaria la purga."""
    return services.analitzar_purga(db, current_user.institucio, req.data_inici, req.data_final)


@router.post("/purga/executar", response_model=PurgaResponse, response_model_exclude_unset=True)
def executar_purga(req: ExecutarPurgaRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Esborra realment les dades de l'interval. Requereix confirmar=True."""
    return services.executar_purga(db, current_user.institucio, req.data_inici, req.data_final, req.confirmar)


@router.get("/professors", response_model=ProfessorsDeLaBdResponse, response_model_exclude_unset=True)
def llista_professors(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Llista de professors de la BD amb el flag actiu (per anonimitzar)."""
    return {"professors": services.llista_professors_db(db)}


@router.post("/professors/reanomena", response_model=ReanomenaResponse, response_model_exclude_unset=True)
def reanomena_professor(req: ReanomenaRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Reanomena/anonimitza un professor inactiu a tots els registres."""
    counts = services.reanomena_professor(db, req.nom_actual, req.nom_nou)
    return {"ok": True, "counts": counts, "total": sum(counts.values())}
