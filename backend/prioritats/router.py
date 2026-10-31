"""
Rutes de /api/prioritats:
- Categories i assignatures de prioritat (llistar; es desen totes d'una
  vegada amb «Desar tot»)
- Llista de no substituir
(Les activitats alliberables són al mòdul grups/; les absències cobertes, abans
«professors de baixa», a absencia_coberta/.)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies import get_db
from noms import NomNet
from prioritats import services
from prioritats.schemas import (
    AssignaturesPrioritatResponse,
    CategoriesResponse,
    CreacioResponse,
    MissatgeResponse,
    NoSubstituirRequest,
    NoSubstituirResponse,
    PrioritatsRequest,
)

router = APIRouter(prefix="/api/prioritats", tags=["Prioritats i Professors"])


# ===== CATEGORIES I ASSIGNATURES DE PRIORITAT =====


@router.get("/categories", response_model=CategoriesResponse)
def get_categories(db: Session = Depends(get_db)):
    """Retorna totes les categories de prioritat"""
    return {"categories": services.llista_categories(db)}


@router.get("/assignatures", response_model=AssignaturesPrioritatResponse)
def get_assignatures_prioritat(db: Session = Depends(get_db)):
    """Retorna totes les assignatures amb prioritat"""
    return {"assignatures": services.llista_assignatures(db)}


# ===== NO SUBSTITUIR =====


@router.get("/no-substituir", response_model=NoSubstituirResponse)
def get_no_substituir(db: Session = Depends(get_db)):
    """Retorna llista d'assignatures que no es substitueixen"""
    return {"assignatures": services.llista_no_substituir(db)}


@router.post("/no-substituir", response_model=CreacioResponse)
def create_no_substituir(data: NoSubstituirRequest, db: Session = Depends(get_db)):
    """Afegeix una assignatura a no substituir"""
    assignatura = data.assignatura
    no_subst_id = services.afegeix_no_substituir(db, assignatura)
    return {"success": True, "id": no_subst_id, "message": f"Assignatura '{assignatura}' afegida a no substituir"}


@router.delete("/no-substituir/{assignatura}", response_model=MissatgeResponse)
def delete_no_substituir(assignatura: NomNet, db: Session = Depends(get_db)):
    """Elimina una assignatura de no substituir"""
    services.treu_no_substituir(db, assignatura)
    return {"success": True, "message": "Assignatura eliminada de no substituir"}


# ===== DESAR TOTES LES PRIORITATS =====


@router.put("/desar-tot", response_model=MissatgeResponse)
def desar_totes_prioritats(data: PrioritatsRequest, db: Session = Depends(get_db)):
    """
    Desa totes les prioritats d'una vegada:
    - Recrea categories amb el nou ordre
    - Actualitza assignatures i pesos
    """
    services.desa_totes(db, data.ordre_categories, data.pesos, data.categories_actives)
    return {
        "success": True,
        "message": f"Prioritats desades: {len(data.ordre_categories)} categories, {len(data.pesos)} pesos",
    }
