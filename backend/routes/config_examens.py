"""
Routes per configuració d'exàmens:
- Assignatures per nivell
- Grups per nivell
- Aules (globals)
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import csv
import io

from dependencies import get_db
from repositories import MasterConfigRepository, ConfiguracioExamenRepository, AbreviaturaGrupRepository, PropostaDescartadaRepository
from schemas import RenameRequest, RenameNivellRequest
from auth_utils import require_admin
from helpers import (
    get_vigilancies_afinitats,
    save_vigilancies_afinitats,
    get_horari
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


@router.delete("/aules/{codi}")
async def delete_aula(codi: str, db: Session = Depends(get_db)):
    """Elimina una aula"""
    try:
        success = MasterConfigRepository.delete_aula(db, codi)
        if not success:
            raise HTTPException(status_code=404, detail="Aula no trobada")

        return {"success": True, "message": f"Aula '{codi}' eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar aula: {str(e)}")


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


@router.delete("/assignacions")
async def eliminar_assignacions_massiu(payload: Dict, db: Session = Depends(get_db),
                                       current_user=Depends(require_admin)):
    """Elimina diverses assignacions de cop (per net a fons abans de re-importar
    des d'un XML nou). `ids`: llista d'ids a esborrar; `tot: true` ho esborra tot."""
    try:
        from models import ConfiguracioExamen

        if payload.get("tot"):
            eliminades = db.query(ConfiguracioExamen).delete()
            db.commit()
            return {"success": True, "eliminades": eliminades}

        ids = payload.get("ids", [])
        if not ids:
            raise HTTPException(status_code=400, detail="Cal indicar 'ids' o 'tot: true'")

        eliminades = db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.id.in_(ids)
        ).delete(synchronize_session=False)
        db.commit()
        return {"success": True, "eliminades": eliminades}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar assignacions: {str(e)}")


def _esborra_tota_configuracio_examens(db: Session):
    """Esborra TOTA la configuració d'exàmens (nivells, grups, assignatures,
    aules i assignacions) de la institució actual. Fet servir per l'opció
    "Sobreescriu" de qualsevol dels diàlegs d'importació: en comptes de
    barrejar dades noves amb configuració mestra vella d'un XML anterior,
    comença sempre net. També oblida les propostes que s'havien descartat
    expressament (amb tot net, té sentit tornar-les a revisar de zero)."""
    from models import ConfiguracioExamen, Grup, Assignatura, Aula, Nivell
    db.query(ConfiguracioExamen).delete()
    db.query(Grup).delete()
    db.query(Assignatura).delete()
    db.query(Aula).delete()
    db.query(Nivell).delete()
    PropostaDescartadaRepository.elimina_totes(db)
    db.commit()


def _calcula_impacte_assignacions(db: Session, propostes: List[Dict], overwrite: bool) -> Dict:
    """Calcula què crearia una llista de propostes (nivells/grups/assignatures/
    aules/assignacions noves, quantes ja existeixen, avisos), SENSE escriure
    res a la BD. Fet servir tant pel resum previ (dry-run) com per calcular
    el resultat final un cop ja s'ha escrit de veritat."""
    if overwrite:
        nivells_vists = set()
        grups_vists = set()
        assignatures_vistes = set()
        aules_vistes = set()
        assignacions_vistes = set()
    else:
        nivells_vists = set(MasterConfigRepository.get_nivells(db))
        grups_vists = set()
        assignatures_vistes = set()
        for n in nivells_vists:
            grups_vists |= set(MasterConfigRepository.get_grups_per_nivell(db, n))
            assignatures_vistes |= {(n, a) for a in MasterConfigRepository.get_assignatures_per_nivell(db, n)}
        aules_vistes = set(MasterConfigRepository.get_aules(db))
        assignacions_vistes = {
            (a["assignatura"], a["grup"], a["titular"]) for a in ConfiguracioExamenRepository.get_all(db)
        }

    nivells_creats = []
    grups_creats = []
    assignatures_creades = []
    aules_creades = []
    assignacions_creades = []
    ja_existien = 0
    avisos = []

    for idx, p in enumerate(propostes, start=1):
        assignatura = (p.get("assignatura") or "").strip()
        grup = (p.get("grup") or "").strip()
        nivell = (p.get("nivell") or "").strip()
        titular = (p.get("titular") or "").strip() or None
        aula = (p.get("aula") or "").strip() or None

        if not assignatura or not grup or not nivell:
            falten = [n for n, v in [("assignatura", assignatura), ("grup", grup), ("nivell", nivell)] if not v]
            avisos.append(f"Proposta {idx}: falta {', '.join(falten)}, no s'importarà")
            continue

        if nivell not in nivells_vists:
            nivells_vists.add(nivell)
            nivells_creats.append(nivell)
        if (nivell, assignatura) not in assignatures_vistes:
            assignatures_vistes.add((nivell, assignatura))
            assignatures_creades.append(f"{assignatura} ({nivell})")
        if grup not in grups_vists:
            grups_vists.add(grup)
            grups_creats.append(f"{grup} ({nivell})")
        if aula and aula not in aules_vistes:
            aules_vistes.add(aula)
            aules_creades.append(aula)

        clau_assignacio = (assignatura, grup, titular)
        if clau_assignacio in assignacions_vistes:
            ja_existien += 1
            continue
        assignacions_vistes.add(clau_assignacio)
        assignacions_creades.append(f"{assignatura} – {grup}" + (f" ({titular})" if titular else ""))

    return {
        "nivells_creats": nivells_creats,
        "grups_creats": grups_creats,
        "assignatures_creades": assignatures_creades,
        "aules_creades": aules_creades,
        "assignacions_creades": assignacions_creades,
        "ja_existien": ja_existien,
        "avisos": avisos,
    }


@router.get("/importar-assignacions/preview")
async def importar_assignacions_preview(db: Session = Depends(get_db),
                                        current_user=Depends(require_admin)):
    """Genera propostes d'assignacions (assignatura/grup/titular/aula) a partir
    de l'horari XML actiu, sense escriure res a la BD."""
    try:
        from exam_import import generar_propostes, nivells_amb_substitucions

        horari = get_horari(current_user.institucio)
        propostes = generar_propostes(horari)

        # Descarta nivells que no s'usen mai a substitucions/vigilàncies
        # (Infantil/Primària a un IES, per exemple) perquè no s'omplin de
        # matèries que el centre no gestiona amb aquest mòdul.
        nivells_valids = nivells_amb_substitucions(db)
        if nivells_valids:
            propostes = [p for p in propostes if p["nivell"] in nivells_valids]

        existents = {
            (a["assignatura"], a["grup"], a["titular"])
            for a in ConfiguracioExamenRepository.get_all(db)
        }
        descartades = PropostaDescartadaRepository.get_totes(db)
        for p in propostes:
            clau = (p["assignatura"], p["grup"], p["titular"])
            p["ja_existeix"] = clau in existents
            p["descartada"] = clau in descartades

        return {"propostes": propostes, "nivells_valids": sorted(nivells_valids)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en generar propostes: {str(e)}")


@router.post("/importar-assignacions/dry-run")
async def importar_assignacions_dry_run(payload: Dict, db: Session = Depends(get_db),
                                        current_user=Depends(require_admin)):
    """Calcula què faria una importació (nivells/grups/assignatures/aules/
    assignacions que es crearien) SENSE escriure res, perquè es pugui mostrar
    un resum previ abans de confirmar."""
    try:
        propostes = payload.get("propostes", [])
        overwrite = bool(payload.get("overwrite"))
        return _calcula_impacte_assignacions(db, propostes, overwrite)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en calcular el resum previ: {str(e)}")


@router.post("/importar-assignacions")
async def importar_assignacions(payload: Dict, db: Session = Depends(get_db),
                                current_user=Depends(require_admin)):
    """Aplica una llista de propostes: crea nivell/assignatura/grup/aula mestres si
    calen, i l'assignació (evitant duplicats exactes assignatura+grup+titular).
    Amb `overwrite: true` s'esborra TOTA la configuració d'exàmens abans.
    `descartades`: propostes que l'usuari ha desmarcat expressament (no
    existeixen encara), perquè no es tornin a proposar marcades la propera
    vegada que s'obri el diàleg d'importació."""
    try:
        from models import ConfiguracioExamen

        if payload.get("overwrite"):
            _esborra_tota_configuracio_examens(db)

        propostes = payload.get("propostes", [])
        nivells_creats = []
        grups_creats = []
        assignatures_creades = []
        aules_creades = []
        assignacions_creades = []
        ja_existien = 0
        avisos = []

        for idx, p in enumerate(propostes, start=1):
            assignatura = (p.get("assignatura") or "").strip()
            grup = (p.get("grup") or "").strip()
            nivell = (p.get("nivell") or "").strip()
            titular = (p.get("titular") or "").strip() or None
            aula = (p.get("aula") or "").strip() or None

            if not assignatura or not grup or not nivell:
                falten = [n for n, v in [("assignatura", assignatura), ("grup", grup), ("nivell", nivell)] if not v]
                avisos.append(f"Proposta {idx}: falta {', '.join(falten)}, no s'ha importat")
                continue

            # Si es torna a marcar una proposta que abans s'havia descartat,
            # deixa de considerar-se descartada.
            PropostaDescartadaRepository.elimina(db, assignatura, grup, titular)

            if MasterConfigRepository.add_nivell(db, nivell):
                nivells_creats.append(nivell)
            if MasterConfigRepository.add_assignatura(db, nivell, assignatura):
                assignatures_creades.append(f"{assignatura} ({nivell})")
            if MasterConfigRepository.add_grup(db, nivell, grup):
                grups_creats.append(f"{grup} ({nivell})")
            if aula and MasterConfigRepository.add_aula(db, aula):
                aules_creades.append(aula)

            existent = db.query(ConfiguracioExamen).filter_by(
                assignatura=assignatura, grup=grup, titular=titular
            ).first()
            if existent:
                ja_existien += 1
                continue

            ConfiguracioExamenRepository.create(db, assignatura, grup, titular, aula)
            assignacions_creades.append(f"{assignatura} – {grup}" + (f" ({titular})" if titular else ""))

        for d in payload.get("descartades", []):
            assignatura = (d.get("assignatura") or "").strip()
            grup = (d.get("grup") or "").strip()
            titular = (d.get("titular") or "").strip() or None
            if assignatura and grup:
                PropostaDescartadaRepository.marca(db, assignatura, grup, titular)

        db.commit()

        return {
            "success": True,
            "nivells_creats": nivells_creats,
            "grups_creats": grups_creats,
            "assignatures_creades": assignatures_creades,
            "aules_creades": aules_creades,
            "assignacions_creades": assignacions_creades,
            "ja_existien": ja_existien,
            "avisos": avisos,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en importar assignacions: {str(e)}")


# ===== EXPORTAR / IMPORTAR ASSIGNACIONS EN CSV (per reutilitzar entre cursos/centres) =====

_CSV_COLUMNES = ["nivell", "assignatura", "grup", "titular", "aula"]


@router.get("/exportar-assignacions-csv")
async def exportar_assignacions_csv(db: Session = Depends(get_db),
                                    current_user=Depends(require_admin)):
    """Exporta totes les assignacions actuals a un fitxer CSV descarregable,
    incloent-hi el nivell real de cada grup (des de la taula mestra) perquè
    el fitxer es pugui reimportar sense ambigüitat."""
    try:
        from models import Grup, Nivell
        from exam_import import deriva_nivell

        nivell_per_grup = {
            codi: nivell_codi
            for codi, nivell_codi in db.query(Grup.codi, Nivell.codi).join(Nivell, Grup.nivell_id == Nivell.id)
        }

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNES)
        writer.writeheader()
        for a in ConfiguracioExamenRepository.get_all(db):
            nivell = nivell_per_grup.get(a["grup"]) or deriva_nivell(a["grup"])
            writer.writerow({"nivell": nivell, **{k: a.get(k, "") for k in _CSV_COLUMNES if k != "nivell"}})

        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=assignacions_{current_user.institucio}.csv"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en exportar el CSV: {str(e)}")


def _calcula_impacte_csv(db: Session, files_rows: List[tuple], overwrite: bool) -> Dict:
    """Igual que _calcula_impacte_assignacions però per files de CSV (mateixes
    regles que l'endpoint real: nivell/assignatura/grup obligatoris, i si es
    dona un titular ha d'existir a la BD; si falta algun d'aquests o el
    titular no es troba, la fila es descarta sencera amb un avís).
    SENSE escriure res, per al resum previ."""
    from models import Professor

    if overwrite:
        nivells_vists = set()
        grups_vists = set()
        assignatures_vistes = set()
        aules_vistes = set()
        assignacions_vistes = set()
    else:
        nivells_vists = set(MasterConfigRepository.get_nivells(db))
        grups_vists = set()
        assignatures_vistes = set()
        for n in nivells_vists:
            grups_vists |= set(MasterConfigRepository.get_grups_per_nivell(db, n))
            assignatures_vistes |= {(n, a) for a in MasterConfigRepository.get_assignatures_per_nivell(db, n)}
        aules_vistes = set(MasterConfigRepository.get_aules(db))
        assignacions_vistes = {
            (a["assignatura"], a["grup"], a["titular"]) for a in ConfiguracioExamenRepository.get_all(db)
        }

    nivells_creats = []
    grups_creats = []
    assignatures_creades = []
    aules_creades = []
    assignacions_creades = []
    ja_existien = 0
    avisos = []

    for num_fila, fila in files_rows:
        assignatura = (fila.get("assignatura") or "").strip()
        grup = (fila.get("grup") or "").strip()
        titular_csv = (fila.get("titular") or "").strip() or None
        aula = (fila.get("aula") or "").strip()
        nivell = (fila.get("nivell") or "").strip()

        if not any([nivell, grup, assignatura, titular_csv, aula]):
            continue

        falten = [camp for camp, valor in [("nivell", nivell), ("assignatura", assignatura), ("grup", grup)] if not valor]
        if falten:
            avisos.append(f"Línia {num_fila}: falten camps obligatoris ({', '.join(falten)}), no s'importarà")
            continue

        if titular_csv and not db.query(Professor).filter_by(nom=titular_csv).first():
            avisos.append(f"Línia {num_fila}: professor «{titular_csv}» no trobat, no s'importarà aquesta línia")
            continue

        if nivell not in nivells_vists:
            nivells_vists.add(nivell)
            nivells_creats.append(nivell)
        if aula and aula not in aules_vistes:
            aules_vistes.add(aula)
            aules_creades.append(aula)
        if grup not in grups_vists:
            grups_vists.add(grup)
            grups_creats.append(f"{grup} ({nivell})")
        if (nivell, assignatura) not in assignatures_vistes:
            assignatures_vistes.add((nivell, assignatura))
            assignatures_creades.append(f"{assignatura} ({nivell})")

        clau = (assignatura, grup, titular_csv)
        if clau in assignacions_vistes:
            ja_existien += 1
            continue
        assignacions_vistes.add(clau)
        assignacions_creades.append(f"{assignatura} – {grup}" + (f" ({titular_csv})" if titular_csv else ""))

    return {
        "nivells_creats": nivells_creats,
        "grups_creats": grups_creats,
        "assignatures_creades": assignatures_creades,
        "aules_creades": aules_creades,
        "assignacions_creades": assignacions_creades,
        "ja_existien": ja_existien,
        "avisos": avisos,
    }


def _llegeix_csv(file: UploadFile, contingut: bytes):
    """Comprova que el fitxer és un CSV amb columnes reconegudes i en
    retorna les files (num_línia, fila) llestes per processar."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="El fitxer ha de ser CSV")

    text = contingut.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    columnes_conegudes = {"nivell", "assignatura", "grup", "titular", "aula"}
    if not columnes_conegudes.intersection(reader.fieldnames or []):
        raise HTTPException(
            status_code=400,
            detail=f"El CSV ha de tenir com a mínim una d'aquestes columnes: {', '.join(sorted(columnes_conegudes))}"
        )

    return list(enumerate(reader, start=2))  # línia 1 = capçalera


@router.post("/importar-assignacions-csv/dry-run")
async def importar_assignacions_csv_dry_run(file: UploadFile = File(...),
                                            overwrite: bool = Form(False),
                                            db: Session = Depends(get_db),
                                            current_user=Depends(require_admin)):
    """Calcula què faria una importació CSV (mateixa lògica que l'endpoint
    real) SENSE escriure res, perquè es pugui mostrar un resum previ."""
    try:
        contingut = await file.read()
        files_rows = _llegeix_csv(file, contingut)
        return _calcula_impacte_csv(db, files_rows, overwrite)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en calcular el resum previ del CSV: {str(e)}")


@router.post("/importar-assignacions-csv")
async def importar_assignacions_csv(file: UploadFile = File(...),
                                    overwrite: bool = Form(False),
                                    db: Session = Depends(get_db),
                                    current_user=Depends(require_admin)):
    """Importa des d'un CSV (columnes: nivell,assignatura,grup,titular,aula).
    nivell, assignatura i grup són obligatoris (cap valor es dedueix ni
    s'inventa): si en falta algun, la fila es descarta sencera amb un avís.
    titular i aula són opcionals, però si es dona un titular que no existeix
    a la BD, la fila també es descarta sencera (no es crea a mitges sense
    titular). Una fila totalment buida s'ignora.
    Amb `overwrite=true` s'esborra TOTA la configuració d'exàmens abans."""
    try:
        from models import ConfiguracioExamen, Professor

        contingut = await file.read()
        files_rows = _llegeix_csv(file, contingut)

        if overwrite:
            _esborra_tota_configuracio_examens(db)

        nivells_creats = []
        grups_creats = []
        assignatures_creades = []
        aules_creades = []
        assignacions_creades = []
        ja_existien = 0
        avisos = []

        for num_fila, fila in files_rows:
            assignatura = (fila.get("assignatura") or "").strip()
            grup = (fila.get("grup") or "").strip()
            titular_csv = (fila.get("titular") or "").strip() or None
            aula = (fila.get("aula") or "").strip()
            nivell = (fila.get("nivell") or "").strip()

            if not any([nivell, grup, assignatura, titular_csv, aula]):
                continue  # fila totalment buida, no cal ni avisar

            falten = [camp for camp, valor in [("nivell", nivell), ("assignatura", assignatura), ("grup", grup)] if not valor]
            if falten:
                avisos.append(f"Línia {num_fila}: falten camps obligatoris ({', '.join(falten)}), no s'ha importat")
                continue

            if titular_csv and not db.query(Professor).filter_by(nom=titular_csv).first():
                avisos.append(f"Línia {num_fila}: professor «{titular_csv}» no trobat, no s'ha importat aquesta línia")
                continue

            if MasterConfigRepository.add_nivell(db, nivell):
                nivells_creats.append(nivell)
            if aula and MasterConfigRepository.add_aula(db, aula):
                aules_creades.append(aula)
            if MasterConfigRepository.add_grup(db, nivell, grup):
                grups_creats.append(f"{grup} ({nivell})")
            if MasterConfigRepository.add_assignatura(db, nivell, assignatura):
                assignatures_creades.append(f"{assignatura} ({nivell})")

            existent = db.query(ConfiguracioExamen).filter_by(
                assignatura=assignatura, grup=grup, titular=titular_csv
            ).first()
            if existent:
                ja_existien += 1
            else:
                ConfiguracioExamenRepository.create(db, assignatura, grup, titular_csv, aula or None)
                assignacions_creades.append(f"{assignatura} – {grup}" + (f" ({titular_csv})" if titular_csv else ""))

        return {
            "success": True,
            "nivells_creats": nivells_creats,
            "grups_creats": grups_creats,
            "assignatures_creades": assignatures_creades,
            "aules_creades": aules_creades,
            "assignacions_creades": assignacions_creades,
            "ja_existien": ja_existien,
            "avisos": avisos,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en importar el CSV: {str(e)}")


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
