"""
Routes per configuració d'exàmens:
- Assignatures per nivell
- Grups per nivell
- Aules (globals)
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict

from dependencies import get_db
from repositories import MasterConfigRepository, ConfiguracioExamenRepository, AbreviaturaGrupRepository
from schemas import RenameRequest, RenameNivellRequest
from helpers import (
    get_vigilancies_afinitats,
    save_vigilancies_afinitats
)

router = APIRouter(prefix="/api/config", tags=["Configuració Exàmens"])


# ===== NIVELLS =====

@router.get("/nivells")
async def get_nivells(db: Session = Depends(get_db)):
    """Retorna tots els nivells disponibles"""
    try:
        nivells = MasterConfigRepository.get_nivells(db)
        return {"nivells": nivells}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir nivells: {str(e)}")


@router.post("/nivells")
async def add_nivell(nivell: Dict[str, str], db: Session = Depends(get_db)):
    """Afegeix un nou nivell"""
    try:
        codi = nivell.get("codi")
        nom = nivell.get("nom")

        if not codi:
            raise HTTPException(status_code=400, detail="Codi de nivell requerit")

        success = MasterConfigRepository.add_nivell(db, codi, nom)
        if not success:
            raise HTTPException(status_code=400, detail="Nivell ja existeix")

        return {"success": True, "message": f"Nivell '{codi}' afegit"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en afegir nivell: {str(e)}")


@router.put("/nivells/{codi}")
async def rename_nivell(codi: str, rename: RenameNivellRequest, db: Session = Depends(get_db)):
    """Reanomena un nivell"""
    try:
        success = MasterConfigRepository.rename_nivell(db, codi, rename.nou_codi)
        if not success:
            raise HTTPException(status_code=400, detail="No s'ha pogut reanomenar el nivell")

        return {"success": True, "message": f"Nivell '{codi}' reanomenat a '{rename.nou_codi}'"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en reanomenar nivell: {str(e)}")


@router.delete("/nivells/{codi}")
async def delete_nivell(codi: str, db: Session = Depends(get_db)):
    """Elimina un nivell"""
    try:
        success = MasterConfigRepository.delete_nivell(db, codi)
        if not success:
            raise HTTPException(status_code=404, detail="Nivell no trobat")

        return {"success": True, "message": f"Nivell '{codi}' eliminat"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar nivell: {str(e)}")


@router.put("/nivells/ordre")
async def update_nivells_ordre(nivells: List[str], db: Session = Depends(get_db)):
    """Actualitza l'ordre dels nivells"""
    try:
        MasterConfigRepository.update_nivells_ordre(db, nivells)
        return {"success": True, "message": "Ordre actualitzat"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar ordre: {str(e)}")


# ===== ASSIGNATURES =====

@router.get("/assignatures")
async def get_all_assignatures(db: Session = Depends(get_db)):
    """Retorna totes les assignatures de tots els nivells (llista plana)"""
    try:
        master = MasterConfigRepository.get_master_config(db)
        nivells = master.get("nivells", {})
        totes = set()
        for data in nivells.values():
            for a in data.get("assignatures", []):
                totes.add(a)
        return sorted(list(totes))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assignatures/{nivell}")
async def get_assignatures(nivell: str, db: Session = Depends(get_db)):
    """Retorna assignatures d'un nivell"""
    try:
        assignatures = MasterConfigRepository.get_assignatures_per_nivell(db, nivell)
        return {"assignatures": assignatures}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir assignatures: {str(e)}")


@router.post("/assignatures/{nivell}")
async def add_assignatura(nivell: str, assignatura: Dict[str, str], db: Session = Depends(get_db)):
    """Afegeix una assignatura a un nivell"""
    try:
        nom = assignatura.get("nom")
        if not nom:
            raise HTTPException(status_code=400, detail="Nom d'assignatura requerit")

        success = MasterConfigRepository.add_assignatura(db, nivell, nom)
        if not success:
            raise HTTPException(status_code=400, detail="Assignatura ja existeix o nivell no trobat")

        return {"success": True, "message": f"Assignatura '{nom}' afegida a {nivell}"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en afegir assignatura: {str(e)}")


@router.put("/assignatures/{nivell}/{nom}")
async def rename_assignatura(nivell: str, nom: str, rename: RenameRequest, db: Session = Depends(get_db)):
    """Reanomena una assignatura i propaga el canvi"""
    try:
        success = MasterConfigRepository.rename_assignatura(db, nivell, nom, rename.nou_nom)
        if not success:
            raise HTTPException(status_code=400, detail="No s'ha pogut reanomenar l'assignatura")

        return {"success": True, "message": f"Assignatura '{nom}' reanomenada a '{rename.nou_nom}'"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en reanomenar assignatura: {str(e)}")


@router.delete("/assignatures/{nivell}/{nom}")
async def delete_assignatura(nivell: str, nom: str, db: Session = Depends(get_db)):
    """Elimina una assignatura d'un nivell"""
    try:
        success = MasterConfigRepository.delete_assignatura(db, nivell, nom)
        if not success:
            raise HTTPException(status_code=404, detail="Assignatura no trobada")

        return {"success": True, "message": f"Assignatura '{nom}' eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar assignatura: {str(e)}")


@router.put("/assignatures/{nivell}/ordre")
async def update_assignatures_ordre(nivell: str, assignatures: List[str], db: Session = Depends(get_db)):
    """Actualitza l'ordre de les assignatures"""
    try:
        MasterConfigRepository.update_assignatures_ordre(db, nivell, assignatures)
        return {"success": True, "message": "Ordre actualitzat"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar ordre: {str(e)}")


# ===== GRUPS =====

@router.get("/grups")
async def get_all_grups(db: Session = Depends(get_db)):
    """Retorna tots els grups de tots els nivells (llista plana d'objectes)"""
    try:
        master = MasterConfigRepository.get_master_config(db)
        nivells = master.get("nivells", {})
        tots = []
        vistos = set()
        for data in nivells.values():
            for g in data.get("grups", []):
                if g not in vistos:
                    tots.append({"codi": g, "nom": g})
                    vistos.add(g)
        return sorted(tots, key=lambda x: x["nom"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/grups/{nivell}")
async def get_grups(nivell: str, db: Session = Depends(get_db)):
    """Retorna grups d'un nivell"""
    try:
        grups = MasterConfigRepository.get_grups_per_nivell(db, nivell)
        return {"grups": grups}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir grups: {str(e)}")


@router.post("/grups/{nivell}")
async def add_grup(nivell: str, grup: Dict[str, str], db: Session = Depends(get_db)):
    """Afegeix un grup a un nivell"""
    try:
        codi = grup.get("codi")
        if not codi:
            raise HTTPException(status_code=400, detail="Codi de grup requerit")

        success = MasterConfigRepository.add_grup(db, nivell, codi)
        if not success:
            raise HTTPException(status_code=400, detail="Grup ja existeix o nivell no trobat")

        return {"success": True, "message": f"Grup '{codi}' afegit a {nivell}"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en afegir grup: {str(e)}")


@router.put("/grups/{codi}")
async def rename_grup(codi: str, rename: RenameRequest, db: Session = Depends(get_db)):
    """Reanomena un grup i propaga el canvi"""
    try:
        success = MasterConfigRepository.rename_grup(db, codi, rename.nou_nom)
        if not success:
            raise HTTPException(status_code=400, detail="No s'ha pogut reanomenar el grup")

        return {"success": True, "message": f"Grup '{codi}' reanomenat a '{rename.nou_nom}'"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en reanomenar grup: {str(e)}")


@router.delete("/grups/{codi}")
async def delete_grup(codi: str, db: Session = Depends(get_db)):
    """Elimina un grup"""
    try:
        success = MasterConfigRepository.delete_grup(db, codi)
        if not success:
            raise HTTPException(status_code=404, detail="Grup no trobat")

        return {"success": True, "message": f"Grup '{codi}' eliminat"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar grup: {str(e)}")


@router.put("/grups/{nivell}/ordre")
async def update_grups_ordre(nivell: str, grups: List[str], db: Session = Depends(get_db)):
    """Actualitza l'ordre dels grups"""
    try:
        MasterConfigRepository.update_grups_ordre(db, nivell, grups)
        return {"success": True, "message": "Ordre actualitzat"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar ordre: {str(e)}")


# ===== AULES =====

@router.get("/aules")
async def get_aules(db: Session = Depends(get_db)):
    """Retorna totes les aules"""
    try:
        aules = MasterConfigRepository.get_aules(db)
        return {"aules": aules}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir aules: {str(e)}")


@router.post("/aules")
async def add_aula(aula: Dict[str, str], db: Session = Depends(get_db)):
    """Afegeix una aula"""
    try:
        codi = aula.get("codi")
        if not codi:
            raise HTTPException(status_code=400, detail="Codi d'aula requerit")

        success = MasterConfigRepository.add_aula(db, codi)
        if not success:
            raise HTTPException(status_code=400, detail="Aula ja existeix")

        return {"success": True, "message": f"Aula '{codi}' afegida"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en afegir aula: {str(e)}")


@router.put("/aules/{codi}")
async def rename_aula(codi: str, rename: RenameRequest, db: Session = Depends(get_db)):
    """Reanomena una aula i propaga el canvi"""
    try:
        success = MasterConfigRepository.rename_aula(db, codi, rename.nou_nom)
        if not success:
            raise HTTPException(status_code=400, detail="No s'ha pogut reanomenar l'aula")

        return {"success": True, "message": f"Aula '{codi}' reanomenada a '{rename.nou_nom}'"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en reanomenar aula: {str(e)}")


# ===== ASSIGNACIONS PROFESSOR-TITULAR =====

@router.get("/assignacions")
async def get_assignacions(db: Session = Depends(get_db)):
    """Retorna totes les assignacions professor-titular"""
    try:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        return {"assignacions": assignacions}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir assignacions: {str(e)}")


@router.get("/assignacions/{assignatura}")
async def get_assignacions_by_assignatura(assignatura: str, db: Session = Depends(get_db)):
    """Retorna assignacions d'una assignatura específica"""
    try:
        assignacions = ConfiguracioExamenRepository.get_by_assignatura(db, assignatura)
        return {"assignacions": assignacions}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir assignacions: {str(e)}")


@router.post("/assignacions")
async def create_assignacio(assignacio: Dict, db: Session = Depends(get_db)):
    """Crea una nova assignació professor-titular"""
    try:
        assignatura = assignacio.get("assignatura")
        grup = assignacio.get("grup")
        titular = assignacio.get("titular", "")
        aula = assignacio.get("aula", "")
        ordre = assignacio.get("ordre", 0)

        if not assignatura or not grup:
            raise HTTPException(status_code=400, detail="Assignatura i grup són obligatoris")

        # Convertir strings buides a None
        titular = titular if titular else None
        aula = aula if aula else None

        assignacio_id = ConfiguracioExamenRepository.create(
            db, assignatura, grup, titular, aula, ordre
        )

        return {
            "success": True,
            "id": assignacio_id,
            "message": f"Assignació creada: {assignatura} - {grup}"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear assignació: {str(e)}")


@router.put("/assignacions/{assignacio_id}")
async def update_assignacio(assignacio_id: int, assignacio: Dict, db: Session = Depends(get_db)):
    """Actualitza una assignació existent"""
    try:
        titular = assignacio.get("titular", "")
        aula = assignacio.get("aula", "")

        # Convertir strings buides a None
        titular = titular if titular else None
        aula = aula if aula else None

        success = ConfiguracioExamenRepository.update(db, assignacio_id, titular, aula)
        if not success:
            raise HTTPException(status_code=404, detail="Assignació no trobada")

        return {"success": True, "message": "Assignació actualitzada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar assignació: {str(e)}")


@router.delete("/assignacions/{assignacio_id}")
async def delete_assignacio(assignacio_id: int, db: Session = Depends(get_db)):
    """Elimina una assignació"""
    try:
        success = ConfiguracioExamenRepository.delete(db, assignacio_id)
        if not success:
            raise HTTPException(status_code=404, detail="Assignació no trobada")

        return {"success": True, "message": "Assignació eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar assignació: {str(e)}")


# ===== ABREVIATURES =====

@router.get("/abreviatures")
async def get_abreviatures(db: Session = Depends(get_db)):
    """Retorna totes les abreviatures de grups"""
    try:
        abreviatures = AbreviaturaGrupRepository.get_all(db)
        return {"abreviatures": abreviatures}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir abreviatures: {str(e)}")


@router.post("/abreviatures")
async def create_abreviatura(abreviatura: Dict, db: Session = Depends(get_db)):
    """Crea una nova abreviatura"""
    try:
        grups_originals = abreviatura.get("grups_originals")
        abreviatura_text = abreviatura.get("abreviatura")

        if not grups_originals or not abreviatura_text:
            raise HTTPException(status_code=400, detail="Grups originals i abreviatura són obligatoris")

        abreviatura_id = AbreviaturaGrupRepository.create(db, grups_originals, abreviatura_text)

        # Invalidar tot l'horari per forçar recàrrega amb les noves abreviatures
        from helpers import invalidar_horari
        invalidar_horari()

        return {
            "success": True,
            "id": abreviatura_id,
            "message": f"Abreviatura creada: {grups_originals} → {abreviatura_text}"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear abreviatura: {str(e)}")


@router.put("/abreviatures/{abreviatura_id}")
async def update_abreviatura(abreviatura_id: int, abreviatura: Dict, db: Session = Depends(get_db)):
    """Actualitza una abreviatura existent"""
    try:
        grups_originals = abreviatura.get("grups_originals")
        abreviatura_text = abreviatura.get("abreviatura")

        success = AbreviaturaGrupRepository.update(db, abreviatura_id, grups_originals, abreviatura_text)
        if not success:
            raise HTTPException(status_code=404, detail="Abreviatura no trobada")

        # Invalidar tot l'horari per forçar recàrrega amb les noves abreviatures
        from helpers import invalidar_horari
        invalidar_horari()

        return {"success": True, "message": "Abreviatura actualitzada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar abreviatura: {str(e)}")


@router.delete("/abreviatures/{abreviatura_id}")
async def delete_abreviatura(abreviatura_id: int, db: Session = Depends(get_db)):
    """Elimina una abreviatura"""
    try:
        success = AbreviaturaGrupRepository.delete(db, abreviatura_id)
        if not success:
            raise HTTPException(status_code=404, detail="Abreviatura no trobada")

        # Invalidar tot l'horari per forçar recàrrega amb les noves abreviatures
        from helpers import invalidar_horari
        invalidar_horari()

        return {"success": True, "message": "Abreviatura eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar abreviatura: {str(e)}")


# ===== AFINITATS VIGILÀNCIES =====

@router.get("/afinitats")
async def get_afinitats(db: Session = Depends(get_db)):
    """Retorna la configuració d'afinitats per autoassignació de vigilàncies."""
    try:
        return {"afinitats": get_vigilancies_afinitats(db)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir afinitats: {str(e)}")


@router.put("/afinitats")
async def update_afinitats(payload: Dict, db: Session = Depends(get_db)):
    """Desa la configuració d'afinitats (format: [{base, ordre:[...]}])."""
    try:
        afinitats = payload.get("afinitats", [])
        if not isinstance(afinitats, list):
            raise HTTPException(status_code=400, detail="El camp 'afinitats' ha de ser una llista")
        normalized = save_vigilancies_afinitats(db, afinitats)
        return {
            "success": True,
            "afinitats": normalized,
            "message": "Afinitats desades correctament"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en desar afinitats: {str(e)}")
