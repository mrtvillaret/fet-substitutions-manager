"""
Routes per configuració de prioritats i professors de baixa:
- Professors de baixa (CRUD)
- Categories de prioritat (CRUD, reordenar)
- Assignatures dins categories (CRUD, pesos)
- Llista de no substituir (CRUD)
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict
from pydantic import BaseModel

from dependencies import get_db
from repositories import (
    ProfessorBaixaRepository,
    CategoriaPrioritatRepository,
    AssignaturaPrioritatRepository,
    NoSubstituirRepository
)

router = APIRouter(prefix="/api/prioritats", tags=["Prioritats i Professors"])


# ===== FUNCIONS AUXILIARS =====

def _recarregar_prioritats_desde_bd(db: Session):
    """
    Recarrega les constants de prioritats (PRIORITATS, ORDRE_PRIORITATS, CATEGORIES_ACTIVES, NO_SUBST)
    llegint-les des de la base de dades en lloc del JSON.
    """
    import config.constants as constants
    from models import CategoriaPrioritat, AssignaturaPrioritat

    # Obtenir totes les categories ordenades
    categories = db.query(CategoriaPrioritat).order_by(CategoriaPrioritat.ordre).all()

    # Obtenir totes les assignatures
    assignatures = db.query(AssignaturaPrioritat).all()

    # Construir ORDRE_PRIORITATS: llista de llistes d'assignatures per categoria
    ordre_prioritats = []
    categories_actives = []

    for cat in categories:
        # Obtenir assignatures d'aquesta categoria
        assignatures_cat = [a.assignatura for a in assignatures if a.categoria_id == cat.id]
        ordre_prioritats.append(assignatures_cat)
        categories_actives.append(cat.activa)

    # Construir PRIORITATS: dict {assignatura: pes}
    prioritats = {a.assignatura: a.pes for a in assignatures}

    # Obtenir NO_SUBST des del repositori
    no_subst_list = NoSubstituirRepository.get_all(db)
    no_subst = set(no_subst_list)  # get_all retorna List[str], no List[Dict]

    # Obtenir PROFESSORS_BAIXA des del repositori
    professors_baixa_list = ProfessorBaixaRepository.get_all(db)
    # Convertir a format que espera el sistema: llista de dicts amb professor, data_inici, data_final
    professors_baixa = [
        {
            'professor': p['professor'],
            'data_inici': p['data_inici'],
            'data_final': p['data_final'],
            'motiu': p.get('motiu', '')
        }
        for p in professors_baixa_list
    ]

    # Actualitzar constants globals
    constants.ORDRE_PRIORITATS = ordre_prioritats
    constants.CATEGORIES_ACTIVES = categories_actives
    constants.PRIORITATS = prioritats
    constants.NO_SUBST = no_subst
    constants.GENERA_ENCADENADES = [tipus for tipus in prioritats if tipus not in no_subst]
    constants.PROFESSORS_BAIXA = professors_baixa

    print(f"✅ Prioritats recarregades des de BD: {len(ordre_prioritats)} categories, {len(prioritats)} assignatures")
    print(f"   Categories actives: {categories_actives}")
    print(f"   NO_SUBST: {len(no_subst)} assignatures")
    print(f"   PROFESSORS_BAIXA: {len(professors_baixa)} professors")

    # Debug detallat per verificar
    for i, cat_assignatures in enumerate(ordre_prioritats):
        activa_str = "✅ ACTIVA" if i < len(categories_actives) and categories_actives[i] else "❌ INACTIVA"
        print(f"   Cat {i}: {activa_str} - {cat_assignatures}")


# ===== MODELS PYDANTIC =====

class ProfessorBaixaCreate(BaseModel):
    professor: str
    data_inici: str  # YYYY-MM-DD
    data_final: str  # YYYY-MM-DD
    motiu: str = ""


class CategoriaPrioritatCreate(BaseModel):
    nom: str
    ordre: int = None
    activa: bool = True


class AssignaturaPrioritatCreate(BaseModel):
    assignatura: str
    categoria_id: int
    pes: int = 1
    ordre: int = None


# ===== PROFESSORS DE BAIXA =====

@router.get("/professors-baixa")
async def get_professors_baixa(db: Session = Depends(get_db)):
    """Retorna tots els professors de baixa"""
    try:
        professors = ProfessorBaixaRepository.get_all(db)
        return {"professors_baixa": professors}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir professors baixa: {str(e)}")


@router.post("/professors-baixa")
async def create_professor_baixa(baixa: ProfessorBaixaCreate, db: Session = Depends(get_db)):
    """Crea un nou professor de baixa"""
    try:
        baixa_id = ProfessorBaixaRepository.create(
            db, baixa.professor, baixa.data_inici, baixa.data_final, baixa.motiu
        )
        return {"success": True, "id": baixa_id, "message": f"Professor '{baixa.professor}' afegit a baixa"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear professor baixa: {str(e)}")


@router.put("/professors-baixa/{baixa_id}")
async def update_professor_baixa(baixa_id: int, baixa: Dict, db: Session = Depends(get_db)):
    """Actualitza un professor de baixa"""
    try:
        success = ProfessorBaixaRepository.update(
            db, baixa_id,
            professor=baixa.get("professor"),
            data_inici=baixa.get("data_inici"),
            data_final=baixa.get("data_final"),
            motiu=baixa.get("motiu")
        )

        if not success:
            raise HTTPException(status_code=404, detail="Professor baixa no trobat")

        return {"success": True, "message": "Professor baixa actualitzat"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar professor baixa: {str(e)}")


@router.delete("/professors-baixa/{baixa_id}")
async def delete_professor_baixa(baixa_id: int, db: Session = Depends(get_db)):
    """Elimina un professor de baixa"""
    try:
        success = ProfessorBaixaRepository.delete(db, baixa_id)

        if not success:
            raise HTTPException(status_code=404, detail="Professor baixa no trobat")

        return {"success": True, "message": "Professor baixa eliminat"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar professor baixa: {str(e)}")


# ===== CATEGORIES PRIORITAT =====

@router.get("/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Retorna totes les categories de prioritat"""
    try:
        categories = CategoriaPrioritatRepository.get_all(db)
        return {"categories": categories}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir categories: {str(e)}")


@router.post("/categories")
async def create_categoria(cat: CategoriaPrioritatCreate, db: Session = Depends(get_db)):
    """Crea una nova categoria de prioritat"""
    try:
        cat_id = CategoriaPrioritatRepository.create(db, cat.nom, cat.ordre, cat.activa)
        return {"success": True, "id": cat_id, "message": f"Categoria '{cat.nom}' creada"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear categoria: {str(e)}")


@router.put("/categories/{categoria_id}")
async def update_categoria(categoria_id: int, cat: Dict, db: Session = Depends(get_db)):
    """Actualitza una categoria"""
    try:
        success = CategoriaPrioritatRepository.update(
            db, categoria_id,
            nom=cat.get("nom"),
            ordre=cat.get("ordre"),
            activa=cat.get("activa")
        )

        if not success:
            raise HTTPException(status_code=404, detail="Categoria no trobada")

        return {"success": True, "message": "Categoria actualitzada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar categoria: {str(e)}")


@router.put("/categories/ordre")
async def update_categories_ordre(categories: List[int], db: Session = Depends(get_db)):
    """Actualitza l'ordre de les categories"""
    try:
        CategoriaPrioritatRepository.update_ordre(db, categories)
        return {"success": True, "message": "Ordre actualitzat"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar ordre: {str(e)}")


@router.delete("/categories/{categoria_id}")
async def delete_categoria(categoria_id: int, db: Session = Depends(get_db)):
    """Elimina una categoria"""
    try:
        success = CategoriaPrioritatRepository.delete(db, categoria_id)

        if not success:
            raise HTTPException(status_code=404, detail="Categoria no trobada")

        return {"success": True, "message": "Categoria eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar categoria: {str(e)}")


# ===== ASSIGNATURES PRIORITAT =====

@router.get("/assignatures")
async def get_assignatures_prioritat(db: Session = Depends(get_db)):
    """Retorna totes les assignatures amb prioritat"""
    try:
        assignatures = AssignaturaPrioritatRepository.get_all(db)
        return {"assignatures": assignatures}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir assignatures: {str(e)}")


@router.get("/assignatures/{categoria_id}")
async def get_assignatures_by_categoria(categoria_id: int, db: Session = Depends(get_db)):
    """Retorna assignatures d'una categoria"""
    try:
        assignatures = AssignaturaPrioritatRepository.get_by_categoria(db, categoria_id)
        return {"assignatures": assignatures}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir assignatures: {str(e)}")


@router.post("/assignatures")
async def create_assignatura_prioritat(assig: AssignaturaPrioritatCreate, db: Session = Depends(get_db)):
    """Crea una nova assignatura dins una categoria"""
    try:
        assig_id = AssignaturaPrioritatRepository.create(
            db, assig.assignatura, assig.categoria_id, assig.pes, assig.ordre
        )
        return {"success": True, "id": assig_id, "message": f"Assignatura '{assig.assignatura}' afegida"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear assignatura: {str(e)}")


@router.put("/assignatures/{assignatura_id}")
async def update_assignatura_prioritat(assignatura_id: int, assig: Dict, db: Session = Depends(get_db)):
    """Actualitza una assignatura de prioritat"""
    try:
        success = AssignaturaPrioritatRepository.update(
            db, assignatura_id,
            assignatura=assig.get("assignatura"),
            categoria_id=assig.get("categoria_id"),
            pes=assig.get("pes"),
            ordre=assig.get("ordre")
        )

        if not success:
            raise HTTPException(status_code=404, detail="Assignatura no trobada")

        return {"success": True, "message": "Assignatura actualitzada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar assignatura: {str(e)}")


@router.delete("/assignatures/{assignatura_id}")
async def delete_assignatura_prioritat(assignatura_id: int, db: Session = Depends(get_db)):
    """Elimina una assignatura de prioritat"""
    try:
        success = AssignaturaPrioritatRepository.delete(db, assignatura_id)

        if not success:
            raise HTTPException(status_code=404, detail="Assignatura no trobada")

        return {"success": True, "message": "Assignatura eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar assignatura: {str(e)}")


# ===== NO SUBSTITUIR =====

@router.get("/no-substituir")
async def get_no_substituir(db: Session = Depends(get_db)):
    """Retorna llista d'assignatures que no es substitueixen"""
    try:
        assignatures = NoSubstituirRepository.get_all(db)
        return {"assignatures": assignatures}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir no substituir: {str(e)}")


@router.post("/no-substituir")
async def create_no_substituir(data: Dict, db: Session = Depends(get_db)):
    """Afegeix una assignatura a no substituir"""
    try:
        assignatura = data.get("assignatura")
        if not assignatura and assignatura != "":  # Acceptar string buit
            raise HTTPException(status_code=400, detail="Assignatura requerida")

        no_subst_id = NoSubstituirRepository.create(db, assignatura)
        return {"success": True, "id": no_subst_id, "message": f"Assignatura '{assignatura}' afegida a no substituir"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear no substituir: {str(e)}")


@router.delete("/no-substituir/{assignatura}")
async def delete_no_substituir(assignatura: str, db: Session = Depends(get_db)):
    """Elimina una assignatura de no substituir"""
    try:
        success = NoSubstituirRepository.delete(db, assignatura)

        if not success:
            raise HTTPException(status_code=404, detail="Assignatura no trobada")

        return {"success": True, "message": "Assignatura eliminada de no substituir"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar no substituir: {str(e)}")


# ===== DESAR TOTES LES PRIORITATS =====

class PrioritatsCompletesUpdate(BaseModel):
    """Model per actualitzar totes les prioritats d'una vegada"""
    ordre_categories: List[List[str]]  # [["Reforç", "alliberat"], ["Guàrdia", ...], ...]
    pesos: Dict[str, int]  # {"Reforç": 1, "Guàrdia": 6, ...}
    categories_actives: List[bool] = []  # [True, True, False, ...] - estat activa per cada categoria


@router.put("/desar-tot")
async def desar_totes_prioritats(data: PrioritatsCompletesUpdate, db: Session = Depends(get_db)):
    """
    Desa totes les prioritats d'una vegada:
    - Recrea categories amb el nou ordre
    - Actualitza assignatures i pesos
    """
    try:
        from models import CategoriaPrioritat, AssignaturaPrioritat

        # 1. Eliminar totes les assignatures (CASCADE elimina també les categories)
        db.query(AssignaturaPrioritat).delete()
        db.query(CategoriaPrioritat).delete()
        db.flush()

        # 2. Recrear categories i assignatures
        for cat_ordre, assignatures_list in enumerate(data.ordre_categories):
            if not assignatures_list:
                continue

            # Crear categoria amb el primer nom de la llista
            nom_categoria = assignatures_list[0] if len(assignatures_list) == 1 else ", ".join(assignatures_list[:2])

            # Obtenir estat activa de l'array (per defecte True si no existeix)
            activa = data.categories_actives[cat_ordre] if cat_ordre < len(data.categories_actives) else True

            nova_categoria = CategoriaPrioritat(
                nom=nom_categoria,
                ordre=cat_ordre,
                activa=activa
            )
            db.add(nova_categoria)
            db.flush()  # Per obtenir l'ID

            # Afegir assignatures a la categoria
            for assig_ordre, assignatura in enumerate(assignatures_list):
                pes = data.pesos.get(assignatura, 1)

                # Si la categoria està activa, totes les seves assignatures són auto_assignades
                nova_assignatura = AssignaturaPrioritat(
                    assignatura=assignatura,
                    categoria_id=nova_categoria.id,
                    pes=pes,
                    ordre=assig_ordre,
                    auto_assignada=activa
                )
                db.add(nova_assignatura)

        db.commit()

        # 3. Recarregar constants de prioritats des de la BD per al sistema de substitucions
        _recarregar_prioritats_desde_bd(db)

        return {
            "success": True,
            "message": f"Prioritats desades: {len(data.ordre_categories)} categories, {len(data.pesos)} pesos"
        }

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en desar prioritats: {str(e)}")
