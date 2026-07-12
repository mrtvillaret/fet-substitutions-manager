"""
Routes per accedir a dades de l'horari (XML de FET):
- Professors (tots, sense límit)
- Grups (detectar del XML)
- Assignatures (detectar del XML)
"""

from fastapi import APIRouter, HTTPException
from typing import List
from helpers import get_horari, MissingXmlError

router = APIRouter(prefix="/api/horari", tags=["Horari"])


@router.get("/professors/all")
async def get_all_professors():
    """
    Retorna TOTS els professors de l'XML, sense aplicar límit ultim_professor_subs
    Útil per mostrar-los al dropdown de configuració
    """
    try:
        horari = get_horari()

        # Llegir professors directament del XML sense límit
        import xml.etree.ElementTree as ET
        tree = ET.parse(horari.xml_path)
        root = tree.getroot()

        # En ORDRE del document XML (és l'ordre que fa servir el límit
        # ultim_professor_subs a horari_web.py), amb el nom cru (amb els espais
        # inicials, que a FET distingeixen secundària de primària) i el net.
        professors_ordenats = []
        for teacher in root.findall("Teacher"):
            nom_cru = teacher.get("name", "")
            nom = nom_cru.strip()
            if nom:
                professors_ordenats.append({"nom": nom, "nom_cru": nom_cru})

        # Llista plana ordenada alfabèticament (compatibilitat: professors de baixa)
        professors = sorted(p["nom"] for p in professors_ordenats)

        return {
            "professors": professors,
            "professors_ordenats": professors_ordenats,
            "total": len(professors)
        }
    except MissingXmlError:
        return {
            "professors": [],
            "total": 0,
            "xml_missing": True
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir professors: {str(e)}")


@router.get("/professors")
async def get_professors_filtered():
    """
    Retorna professors amb el límit ultim_professor_subs aplicat
    (els que s'utilitzen actualment al sistema)
    """
    try:
        horari = get_horari()

        return {
            "professors": horari.professors,
            "total": len(horari.professors)
        }
    except MissingXmlError:
        return {
            "professors": [],
            "total": 0,
            "xml_missing": True
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir professors: {str(e)}")


@router.get("/grups/detectar")
async def detectar_grups():
    """
    Detecta tots els grups del XML
    Retorna:
    - grups_raw: Grups tal com apareixen al XML (ex: "1-BATX-A,1-BATX-B")
    - grups: Grups amb abreviatures aplicades (ex: "1-BATX-AB")
    """
    try:
        horari = get_horari()

        # Grups detectats amb i sense abreviatures
        grups_raw = sorted(list(horari.grups_raw))
        grups_abreviats = sorted(list(horari.grups))

        return {
            "grups_raw": grups_raw,
            "grups": grups_abreviats,
            "total_raw": len(grups_raw),
            "total_abreviats": len(grups_abreviats)
        }
    except MissingXmlError:
        return {
            "grups_raw": [],
            "grups": [],
            "total_raw": 0,
            "total_abreviats": 0,
            "xml_missing": True
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en detectar grups: {str(e)}")


@router.get("/assignatures/detectar")
async def detectar_assignatures():
    """
    Detecta totes les assignatures del XML
    """
    try:
        horari = get_horari()

        # Obtenir totes les assignatures úniques
        assignatures = horari.get_all_subjects()

        return {
            "assignatures": sorted(list(assignatures)),
            "total": len(assignatures)
        }
    except MissingXmlError:
        return {
            "assignatures": [],
            "total": 0,
            "xml_missing": True
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en detectar assignatures: {str(e)}")


@router.get("/aules/detectar")
async def detectar_aules():
    """
    Detecta totes les aules del XML
    """
    try:
        horari = get_horari()

        # Obtenir totes les aules úniques
        if hasattr(horari, 'get_all_rooms'):
            aules = horari.get_all_rooms()
        else:
            # Fallback si el mètode no existeix
            aules = set()
            for dia_hores in horari.horari.values():
                for hora_profs in dia_hores.values():
                    for dades in hora_profs.values():
                        aula = dades.get("aula", "")
                        if aula and aula.strip():
                            aules.add(aula.strip())

        return {
            "aules": sorted(list(aules)),
            "total": len(aules)
        }
    except MissingXmlError:
        return {
            "aules": [],
            "total": 0,
            "xml_missing": True
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en detectar aules: {str(e)}")
