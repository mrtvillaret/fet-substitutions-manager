"""
Routes per accedir a dades de l'horari (XML de FET):
- Professors (tots, sense límit)
- Grups (detectar del XML)
- Assignatures (detectar del XML)
"""
import logging

from fastapi import APIRouter, Depends

from dependencies import dia_del_calendari
from helpers import MissingXmlError
from routes.parametres import DataISO
from serveis.dia import Dia

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/horari", tags=["Horari"])



@router.get("/professors/all")
async def get_all_professors(dia: Dia = Depends(dia_del_calendari)):
    """
    Retorna TOTS els professors de l'XML vigent a `data` (o, sense, avui),
    sense aplicar límit ultim_professor_subs. Per als desplegables de configuració.
    """
    try:
        horari = dia.horari

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


@router.get("/professors")
async def get_professors_filtered(data: DataISO = None, dia: Dia = Depends(dia_del_calendari)):
    """
    Retorna professors amb el límit ultim_professor_subs aplicat. Amb `data`
    (AAAA-MM-DD), els de l'horari vigent aquell dia i els que hi estan de
    baixa (no se'ls posen absències); sense, els de l'horari vigent avui.
    """
    try:
        horari = dia.horari

        resposta = {
            "professors": horari.professors,
            "total": len(horari.professors)
        }
        if data:
            from config.constants import PROFESSORS_BAIXA
            from core.baixes import professors_de_baixa
            resposta["de_baixa"] = sorted(professors_de_baixa(PROFESSORS_BAIXA, data))
        return resposta
    except MissingXmlError:
        return {
            "professors": [],
            "total": 0,
            "xml_missing": True
        }


@router.get("/grups/detectar")
async def detectar_grups(dia: Dia = Depends(dia_del_calendari)):
    """
    Detecta tots els grups del XML vigent per una data (o l'actual si no se'n dóna).
    Usar la data fa que la configuració treballi sobre el MATEIX XML que veurà la
    vista de grups sense classe per aquella data (evita barreges entre cursos).

    Retorna:
    - grups_raw: Grups tal com apareixen al XML (ex: "1-BATX-A,1-BATX-B")
    - grups: Grups amb abreviatures aplicades (ex: "1-BATX-AB")
    - xml_data_inici: data d'inici de la versió d'XML carregada (per indicar-la)
    """
    try:
        horari = dia.horari

        # Detecció: TOTS els grups de l'XML (no només els visibles), perquè el
        # selector de configuració els pugui oferir tots.
        grups_raw = sorted(list(horari.tots_grups_raw))
        grups_abreviats = sorted(list(horari.tots_grups))

        # Versió d'XML carregada, per poder-la indicar a la configuració
        xml_data_inici = dia.versio_des_de

        return {
            "grups_raw": grups_raw,
            "grups": grups_abreviats,
            "total_raw": len(grups_raw),
            "total_abreviats": len(grups_abreviats),
            "xml_data_inici": xml_data_inici,
        }
    except MissingXmlError:
        return {
            "grups_raw": [],
            "grups": [],
            "total_raw": 0,
            "total_abreviats": 0,
            "xml_missing": True
        }


@router.get("/assignatures/detectar")
async def detectar_assignatures(dia: Dia = Depends(dia_del_calendari)):
    """
    Detecta totes les assignatures de l'XML vigent per una data (o l'actual si
    no se'n dóna). Igual que la detecció de grups, usar la data fa que la
    configuració treballi sobre el MATEIX XML vigent per aquella data.

    Retorna també:
    - te_buits: si hi ha hores amb Subject buit (que NO s'han de substituir)
    - xml_data_inici: data d'inici de la versió d'XML carregada (per indicar-la)
    """
    try:
        horari = dia.horari

        # Obtenir totes les assignatures úniques
        assignatures = horari.get_all_subjects()

        # Detectar si hi ha hores amb Subject buit (hores lliures): en aquest cas
        # la config de "no substituir" ha de poder seleccionar l'opció buida.
        te_buits = any(
            not (dades.get("assignatura") or "").strip()
            for dia_hores in horari.horari.values()
            for hora_profs in dia_hores.values()
            for dades in hora_profs.values()
        )

        # Versió d'XML carregada, per poder-la indicar a la configuració
        xml_data_inici = dia.versio_des_de

        return {
            "assignatures": sorted(list(assignatures)),
            "total": len(assignatures),
            "te_buits": te_buits,
            "xml_data_inici": xml_data_inici,
        }
    except MissingXmlError:
        return {
            "assignatures": [],
            "total": 0,
            "xml_missing": True
        }

