"""Rutes de les absències cobertes (/api/absencies-cobertes)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from absencia_coberta import services
from absencia_coberta.schemas import (
    AbsenciaCobertaRequest,
    AbsenciesCobertesResponse,
    DesadaResponse,
    EdicioAbsenciaCobertaRequest,
    EsborradaResponse,
)
from auth.dependencies import require_admin
from auth.domain import UsuariActual
from dependencies import get_db

router = APIRouter(prefix="/api/absencies-cobertes", tags=["Absències cobertes"])


@router.get("", response_model=AbsenciesCobertesResponse)
def llista_absencies_cobertes(db: Session = Depends(get_db)):
    return {"absencies_cobertes": services.llista(db)}


@router.post("", response_model=DesadaResponse, response_model_exclude_unset=True)
def crea_absencia_coberta(
    absencia: AbsenciaCobertaRequest,
    db: Session = Depends(get_db),
    current_user: UsuariActual = Depends(require_admin),
):
    resultat = services.crea(
        db, current_user.institucio, absencia.professor, absencia.data_inici, absencia.data_final, absencia.motiu
    )
    return {"success": True, "message": "Absència coberta afegida", **resultat}


@router.put("/{absencia_id}", response_model=DesadaResponse, response_model_exclude_unset=True)
def edita_absencia_coberta(
    absencia_id: int,
    canvis: EdicioAbsenciaCobertaRequest,
    db: Session = Depends(get_db),
    current_user: UsuariActual = Depends(require_admin),
):
    resultat = services.edita(db, current_user.institucio, absencia_id, **canvis.model_dump())
    return {"success": True, "message": "Absència coberta actualitzada", **resultat}


@router.delete("/{absencia_id}", response_model=EsborradaResponse)
def esborra_absencia_coberta(absencia_id: int, db: Session = Depends(get_db)):
    services.esborra(db, absencia_id)
    return {"success": True, "message": "Absència coberta eliminada"}
