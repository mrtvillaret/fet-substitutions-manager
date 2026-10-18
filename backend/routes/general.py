"""
Rutes generals de l'aplicació: estat de l'horari carregat, professors i hores
de l'horari vigent (avui o en una data) i activitats que no se substitueixen.
"""
from datetime import datetime

from fastapi import APIRouter, Depends

from dependencies import dia_del_calendari
from helpers import MissingXmlError
from schemas import ConfigResponse
from serveis.dia import Dia

router = APIRouter(tags=["General"])


@router.get("/api/config", response_model=ConfigResponse)
async def get_config(dia: Dia = Depends(dia_del_calendari)):
    """Estat de l'horari vigent a `data` (o, sense, avui): professors i hores"""
    try:
        horari = dia.horari
    except MissingXmlError:
        return ConfigResponse(
            data_actual=datetime.now().strftime("%Y-%m-%d"),
            horari_carregat=False,
            num_professors=0,
            num_hores=0,
            xml_missing=True
        )

    return ConfigResponse(
        data_actual=datetime.now().strftime("%Y-%m-%d"),
        horari_carregat=True,
        num_professors=len(horari.professors),
        num_hores=len(horari.hores)
    )


@router.get("/api/professors")
async def get_professors(dia: Dia = Depends(dia_del_calendari)):
    """Professors de l'horari vigent a `data` (o, sense, avui), fins a l'últim configurat"""
    try:
        horari = dia.horari
    except MissingXmlError:
        return {
            "professors": [],
            "xml_missing": True
        }
    # horari.professors ja té el límit aplicat (veure core/horari.py línia 50-62)
    return {
        "professors": sorted(horari.professors)
    }


@router.get("/api/hores")
async def get_hores(dia: Dia = Depends(dia_del_calendari)):
    """Hores del dia en l'ordre de l'XML (no alfabètic), de l'horari vigent a
    `data` (AAAA-MM-DD) o, sense, avui."""
    try:
        horari = dia.horari
    except MissingXmlError:
        return {
            "hores": [],
            "xml_missing": True
        }
    return {
        "hores": horari.hores  # Ja estan en l'ordre correcte de l'XML
    }


@router.get("/api/config/no-substituir")
async def get_no_substituir():
    """Retorna llista d'activitats que no necessiten substitució"""
    from config.constants import NO_SUBST
    return {
        "no_substituir": list(NO_SUBST)
    }
