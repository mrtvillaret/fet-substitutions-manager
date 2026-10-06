"""
Routes per grups sense classe (grups alliberats) i professors alliberats:
- GET: Obtenir grups sense classe i professors alliberats per una data
- PUT: Desar-los per una data
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime

from dependencies import get_db
from repositories import GrupsAlliberatsRepository
from helpers import get_gestors
from core.alliberats import clau_professor, nomes_grups, professors_de

from config.settings import config

router = APIRouter(prefix="/api/grups", tags=["Grups Sense Classe"])


class AlliberatsDia(BaseModel):
    grups: Dict[str, List[str]] = {}       # {hora: [grups sense classe]}
    professors: Dict[str, List[str]] = {}  # {hora: [professors alliberats]}


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

        # horari.grups ja és el conjunt de grups de treball (selecció manual;
        # si no n'hi ha, tots els detectats). El filtre viu al parser.
        tots_grups = sorted(horari.grups)

        # Obtenir hores del dia (sense Pati)
        hores = [h for h in horari.hores if h != "Pati"]

        # Carregar grups alliberats des de SQLite (inclou els professors alliberats)
        alliberats_per_hora = GrupsAlliberatsRepository.get_by_date(db, data)

        # Grups que a una hora tenen classe amb més d'un professor (p.ex. una
        # optativa): només en aquests té sentit alliberar un professor sol. Si
        # n'hi ha un de sol, alliberar-lo és deixar el grup sense classe.
        dia = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
        professors_per_grup_hora = {}
        grups_visibles = set(tots_grups)
        for hora in hores:
            per_grup = {}
            for professor in sorted(horari.professors):
                activitat = horari.get_activitat(dia, hora, professor) or {}
                grup = activitat.get("grup", "")
                if grup in grups_visibles and activitat.get("assignatura"):
                    per_grup.setdefault(grup, []).append(professor)
            compartits = {grup: profs for grup, profs in per_grup.items() if len(profs) > 1}
            if compartits:
                professors_per_grup_hora[hora] = compartits

        # Retornar en format esperat pel frontend
        return {
            "hores": hores,
            "grups_disponibles": tots_grups,
            "grups_seleccionats_per_hora": {
                hora: nomes_grups(valors) for hora, valors in alliberats_per_hora.items()
                if nomes_grups(valors)
            },
            "professors_per_grup_hora": professors_per_grup_hora,
            "professors_alliberats_per_hora": {
                hora: professors_de(valors) for hora, valors in alliberats_per_hora.items()
                if professors_de(valors)
            },
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir grups: {str(e)}")


@router.put("/{data}")
async def desar_grups_sense_classe(data: str, payload: AlliberatsDia, db: Session = Depends(get_db)):
    """
    Desa grups sense classe per una data (SQLite)

    IMPORTANT: Després de desar, regenera substitucions pendents (sense substitut)
    perquè canviar els grups sense classe afecta quines substitucions són necessàries.

    Args:
        payload.grups: Dict[hora, List[grups]]
        payload.professors: Dict[hora, List[professors]] (alliberats sense el seu grup)
    """
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid")

    # Els professors alliberats es desen a la mateixa llista per hora que els
    # grups, amb un prefix (veure core/alliberats.py).
    grups_per_hora = {}
    for hora, grups in payload.grups.items():
        valors = [g.strip() for g in nomes_grups(grups) if g and g.strip()]
        if valors:
            grups_per_hora[hora] = valors
    for hora, professors in payload.professors.items():
        claus = [clau_professor(p.strip()) for p in professors if p and p.strip()]
        if claus:
            grups_per_hora.setdefault(hora, []).extend(dict.fromkeys(claus))

    try:
        # Les hores que es desmarquen també s'han de reconciliar
        hores_anteriors = set(GrupsAlliberatsRepository.get_by_date(db, data).keys())
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

        # 🔧 IMPORTANT: Reconciliar les cobertures de vigilància (Tipus B) de les hores afectades.
        # En alliberar un grup, un professor que abans "calia substituir" pot quedar alliberat
        # (el seu grup fa examen) i la seva cobertura VIGILANCIA esdevé innecessària. Si no es
        # reconcilia, queda un registre ranci amb substitut buit que provoca falsos avisos
        # ("vigilàncies cobertes automàticament sense substitut assignat").
        # Reutilitzem la mateixa reconciliació que ja s'executa en crear/editar vigilàncies,
        # perquè el resultat NO depengui de l'ordre d'entrada de dades (abans calia editar
        # l'hora manualment perquè es netegés).
        try:
            from routes.vigilancies import _refresh_vigilancia_substitucions
            from repositories import VigilanciaRepository

            vig_dict = VigilanciaRepository.get_by_date(db, data)
            hores_amb_vig = {
                (v.get("hora") or "").strip()
                for vigs in vig_dict.values() for v in vigs
                if (v.get("hora") or "").strip()
            }
            hores_afectades = hores_amb_vig | {h.strip() for h in (set(grups_per_hora) | hores_anteriors) if h.strip()}
            for hora in hores_afectades:
                _refresh_vigilancia_substitucions(data, hora, db)
        except Exception as e:
            print(f"⚠️ Error reconciliant cobertures de vigilància: {e}")
            # No fallar si falla la reconciliació

        return {
            "success": True,
            "message": f"Grups sense classe actualitzats per {data}",
            "total_hores": len(grups_per_hora),
            "total_grups": sum(len(nomes_grups(v)) for v in grups_per_hora.values()),
            "total_professors": sum(len(professors_de(v)) for v in grups_per_hora.values())
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en desar grups: {str(e)}")
