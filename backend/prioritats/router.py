"""
Rutes de /api/prioritats:
- Categories i assignatures de prioritat (llistar; es desen totes d'una
  vegada amb «Desar tot»)
- Llista de no substituir
- De pas, fins que es migri el mòdul de grups: les activitats alliberables.
  (Les absències cobertes, abans «professors de baixa», són a absencia_coberta/.)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies import dia_del_calendari, get_db
from noms import NomNet
from prioritats import services
from prioritats.schemas import (
    ActivitatsAlliberables,
    AssignaturesPrioritatResponse,
    CategoriesResponse,
    CreacioResponse,
    MissatgeResponse,
    NoSubstituirRequest,
    NoSubstituirResponse,
    PrioritatsRequest,
)
from repositories import ConfiguracioRepository
from serveis.dia import Dia

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


# ===== ACTIVITATS ALLIBERABLES =====


@router.get("/activitats-alliberables")
def get_activitats_alliberables(db: Session = Depends(get_db), dia_calendari: Dia = Depends(dia_del_calendari)):
    """Activitats sense grup que es poden alliberar (surten com a files a la
    taula de grups alliberats) i les que hi ha a l'horari vigent a `data` (o,
    sense, avui) per triar-les."""
    from helpers import MissingXmlError
    from routes.grups import activitats_alliberables

    disponibles = set()
    try:
        # És configuració, no un dia: els professors de l'XML fins a l'«últim
        # professor», també els que tenen una absència coberta aquell dia
        horari = dia_calendari.horari_amb_tothom
        for dia in horari.dies:
            for hora in horari.hores:
                for professor in horari.professors:
                    act = horari.get_activitat(dia, hora, professor) or {}
                    if act.get("assignatura") and not act.get("grup"):
                        disponibles.add(act["assignatura"])
    except MissingXmlError:
        pass
    from repositories import GrupsAlliberatsRepository

    return {
        "activitats": activitats_alliberables(db),
        "per_defecte": GrupsAlliberatsRepository.activitats_per_defecte(db),
        "disponibles": sorted(disponibles),
    }


@router.put("/activitats-alliberables")
def set_activitats_alliberables(dades: ActivitatsAlliberables, db: Session = Depends(get_db)):
    import json

    from routes.grups import CLAU_ACTIVITATS_ALLIBERABLES

    activitats = sorted({a.strip() for a in dades.activitats if a and a.strip()})
    per_defecte = sorted({a.strip() for a in dades.per_defecte if a and a.strip() in activitats})
    ConfiguracioRepository.set(db, CLAU_ACTIVITATS_ALLIBERABLES, json.dumps(activitats, ensure_ascii=False), "json")
    ConfiguracioRepository.set(
        db, "activitats_alliberades_per_defecte", json.dumps(per_defecte, ensure_ascii=False), "json"
    )
    return {"success": True, "activitats": activitats, "per_defecte": per_defecte}


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
