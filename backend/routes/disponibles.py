"""
Routes per llistat de professors disponibles
"""

from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from config.constants import ORDRE_PRIORITATS
from dependencies import dia_de_la_peticio, get_db
from routes.parametres import DataISO, data_iso
from serveis.dia import Dia

router = APIRouter(prefix="/api/disponibles", tags=["Disponibles"])


@router.get("/{data}")
async def get_disponibles_dia(
    data: DataISO,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Retorna professors disponibles per cada hora d'un dia concret,
    agrupats per categoria i tipus de disponibilitat.

    Estructura retornada:
    {
      "data": "2026-01-15",
      "dia": "Dimecres",
      "disponibles": {
        "08:00": {
          "GUARDIA": [
            {"nom": "Prof_C", "tipus": "alliberat", "detall": "cap classe"},
            {"nom": "Prof_B", "tipus": "disponible", "detall": "Guàrdia-R"}
          ],
          "LLENGUA": [...]
        },
        ...
      }
    }
    """
    data_iso(data)

    try:
        dia_obj = datetime.strptime(data, "%Y-%m-%d")
        dia_name = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres"][dia_obj.weekday()]
    except IndexError:  # cap de setmana
        raise HTTPException(status_code=400, detail="Data invàlida") from None

    # Carregar gestors (retornen: substitucions, horari, alliberats, absencies)
    try:
        substitucions_mgr, horari_mgr, alliberats_mgr, absencies_mgr = dia.gestors()
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Error carregant horari: {str(e)}") from e

    # Obtenir substitucions del dia
    from repositories import SubstitucioRepository

    substitucions_data = SubstitucioRepository.get_by_date(db, data)

    # Crear mapa de substituts per hora
    substituts_per_hora = defaultdict(set)
    for sub in substitucions_data:
        hora = sub.get("hora", "")
        substitut = sub.get("substitut", "")
        if hora and substitut:
            substituts_per_hora[hora].add(substitut)

    # Obtenir grups alliberats
    from repositories import GrupsAlliberatsRepository

    grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data)

    resultat = {}

    # Per cada hora del dia
    for hora in horari_mgr.hores:
        grups_hora = grups_alliberats_data.get(hora, [])

        # Obtenir disponibles
        disponibles = alliberats_mgr.get_tots_disponibles(dia_name, hora, grups_hora)

        # Fora els substituts ja assignats (els que tenen una absència coberta ja no són a l'horari)
        disponibles_filtrats = [
            (prof, tipus, detall)
            for prof, tipus, detall in disponibles
            if prof not in substituts_per_hora.get(hora, set())
        ]

        # Agrupar per categoria i tipus
        agrupats = defaultdict(lambda: defaultdict(list))

        for prof, tipus, detall in disponibles_filtrats:
            # Obtenir categoria segons el tipus de disponibilitat
            from core.vigilancia_assignacio import get_categoria_prioritat

            categoria_idx = get_categoria_prioritat(tipus)

            # Obtenir nom de categoria de ORDRE_PRIORITATS
            if categoria_idx < len(ORDRE_PRIORITATS):
                # Obtenir primer tipus de la categoria com a nom
                categoria = list(ORDRE_PRIORITATS[categoria_idx])[0] if ORDRE_PRIORITATS[categoria_idx] else "ALTRES"
            else:
                categoria = "ALTRES"

            # Determinar tipus de disponibilitat
            if tipus == detall and tipus != "alliberat":
                tipus_display = f"disponible ({tipus})"
            else:
                tipus_display = f"{tipus} ({detall})"

            agrupats[categoria][tipus_display].append({"nom": prof, "tipus": tipus, "detall": detall})

        # Ordenar categories per prioritat
        # Trobar índex de categoria buscant quin set de ORDRE_PRIORITATS conté el nom
        def get_categoria_index(nom_categoria):
            for idx, cat_set in enumerate(ORDRE_PRIORITATS):
                if nom_categoria in cat_set:
                    return idx
            return 999  # Si no es troba, al final

        resultat[hora] = dict(sorted(agrupats.items(), key=lambda x: get_categoria_index(x[0])))

    return {"data": data, "dia": dia_name, "disponibles": resultat}


@router.get("/{data}/resum")
async def get_resum_disponibles(data: DataISO, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Retorna un resum del nombre de disponibles per hora i categoria.
    """
    disponibles = await get_disponibles_dia(data, db, current_user)

    resum = {}
    for hora, categories in disponibles["disponibles"].items():
        resum[hora] = {
            categoria: sum(len(profs) for profs in tipus.values()) for categoria, tipus in categories.items()
        }

    return {
        "data": data,
        "dia": disponibles["dia"],
        "resum": resum,
        "total_per_hora": {hora: sum(resum[hora].values()) for hora in resum},
    }
