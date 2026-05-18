"""
Routes per grups sense classe (grups alliberats):
- GET: Obtenir grups sense classe per una data
- PUT: Desar grups sense classe per una data
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime

from dependencies import get_db
from repositories import GrupsAlliberatsRepository
from helpers import get_gestors

from config.settings import config

router = APIRouter(prefix="/api/grups", tags=["Grups Sense Classe"])


@router.get("/{data}")
async def obtenir_grups_sense_classe(data: str, db: Session = Depends(get_db)):
    """
    Retorna grups sense classe per una data (SQLite)
    Format compatible amb GrupsView.vue
    """
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid")

    try:
        # Obtenir gestors per carregar horari
        substitucions_mgr, horari, alliberats, absencies = get_gestors(data_iso=data)

        # Obtenir tots els grups disponibles del centre
        tots_grups = sorted(horari.grups)

        # Obtenir hores del dia (sense Pati)
        hores = [h for h in horari.hores if h != "Pati"]

        # Carregar grups alliberats des de SQLite
        grups_per_hora = GrupsAlliberatsRepository.get_by_date(db, data)

        # Retornar en format esperat pel frontend
        return {
            "hores": hores,
            "grups_disponibles": tots_grups,
            "grups_seleccionats_per_hora": grups_per_hora
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir grups: {str(e)}")


@router.put("/{data}")
async def desar_grups_sense_classe(data: str, grups_per_hora: Dict[str, List[str]], db: Session = Depends(get_db)):
    """
    Desa grups sense classe per una data (SQLite)

    IMPORTANT: Després de desar, regenera substitucions pendents (sense substitut)
    perquè canviar els grups sense classe afecta quines substitucions són necessàries.

    Args:
        grups_per_hora: Dict[hora, List[grups]]
    """
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid")

    try:
        GrupsAlliberatsRepository.set_for_date(db, data, grups_per_hora)

        # 🔧 IMPORTANT: Regenerar substitucions pendents després de canviar grups sense classe
        # Cridar l'endpoint de generar substitucions amb regenerar_tot=False
        from routes.substitucions import generar_substitucions

        try:
            result_subs = await generar_substitucions(data, regenerar_tot=False, db=db)
            print(f"✅ Substitucions regenerades després de canviar grups sense classe: {result_subs.get('message')}")
        except Exception as e:
            print(f"⚠️ Error regenerant substitucions: {e}")
            # No fallar si falla la regeneració

        return {
            "success": True,
            "message": f"Grups sense classe actualitzats per {data}",
            "total_hores": len(grups_per_hora),
            "total_grups": sum(len(grups) for grups in grups_per_hora.values())
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en desar grups: {str(e)}")
