"""
Routes per gestió de substitucions:
- Obtenir substitucions per data
- Generar substitucions automàticament
- Actualitzar absències de professor
- Actualitzar substitut específic
- Eliminar substitució
- Obtenir professors disponibles per hora
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dependencies import dia_de_la_peticio, get_db
from helpers import MissingXmlError
from noms import NomNet
from parametres import DataISO
from serveis.dia import Dia
from substitucions import services
from substitucions.schemas import (
    ActualitzacioAbsenciesResponse,
    ActualitzacioSubstitutResponse,
    ActualitzarAbsenciesRequest,
    DisponiblesResponse,
    GeneracioSubstitucionsResponse,
    HoresProfessorResponse,
    OrdreSubstitucions,
    ReassignacioSubstitucionsResponse,
    SubstitucioResponse,
    SubstitucioUpdate,
)

router = APIRouter(prefix="/api/substitucions", tags=["Substitucions"])


def _raise_missing_xml(exc: MissingXmlError):
    raise HTTPException(status_code=400, detail={"xml_missing": True, "message": str(exc)})


def _conflicte(exc: services.ConflicteSubstitucions) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "error": "conflict",
            "message": exc.missatge,
            "current_data": exc.current_data,
        },
    )


@router.get("/{data}", response_model=List[SubstitucioResponse])
def get_substitucions(
    data: DataISO,
    include_all: bool = False,
    ordre: OrdreSubstitucions = "curs",
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Retorna totes les substitucions per una data específica (SQLite)

    IMPORTANT: Per defecte només retorna les que generen substitució (tenen grup I no alliberat).
    Les absències sense grup (Guàrdia, Reforç, etc.) i amb grup alliberat es desen per estadístiques
    però NO es mostren a la taula per defecte.

    Args:
        data: Format ISO (YYYY-MM-DD), ex: 2025-12-23
        include_all: Si True, retorna TOTES les absències (amb i sense grup, alliberat o no)
        ordre: dins de cada hora, per «curs» (per defecte) o per «professor» absent
               (SubstitucioRepository.ORDRES)
                     Útil per editar absències i veure totes les hores marcades
    """
    try:
        return services.llista_substitucions(db, dia, data, include_all=include_all, ordre=ordre)
    except MissingXmlError as exc:
        _raise_missing_xml(exc)


@router.post("/{data}/generar", response_model=GeneracioSubstitucionsResponse)
def generar_substitucions(
    data: DataISO,
    regenerar_tot: bool = False,
    db: Session = Depends(get_db),
    omplir: bool = True,
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Genera automàticament les substitucions d'un dia (veure
    substitucions/generacio.py). `regenerar_tot`: des de zero;
    si no, es conserven les files que ja tenen substitut.
    """
    try:
        return services.genera_substitucions(
            db,
            dia,
            data,
            regenerar_tot=regenerar_tot,
            omplir=omplir,
        )
    except MissingXmlError as exc:
        _raise_missing_xml(exc)


@router.put(
    "/{data}/absencies/{professor}",
    response_model=ActualitzacioAbsenciesResponse,
    response_model_exclude_unset=True,
)
def actualitzar_absencies_professor(
    data: DataISO,
    professor: NomNet,
    update: ActualitzarAbsenciesRequest,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Actualitza les absències d'un professor (SQLite):
    - Elimina substitucions de les hores que s'han tret
    - Manté les hores seleccionades
    - Actualitza el tipus d'absència per totes les hores
    """
    try:
        return services.actualitza_absencies(db, dia, data, professor, update)
    except services.ConflicteSubstitucions as exc:
        raise _conflicte(exc) from None
    except MissingXmlError as exc:
        _raise_missing_xml(exc)


@router.put("/{data}/{hora}/{professor}", response_model=ActualitzacioSubstitutResponse)
def update_substitucio(
    data: DataISO,
    hora: str,
    professor: NomNet,
    update: SubstitucioUpdate,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Actualitza el substitut d'una substitució específica (SQLite)
    Valida que el substitut NO estigui ocupat, absent o amb classe
    """
    try:
        return services.actualitza_substitut(db, dia, data, hora, professor, update)
    except services.ConflicteSubstitucions as exc:
        raise _conflicte(exc) from None


@router.post("/{data}/reassign-problematics", response_model=ReassignacioSubstitucionsResponse)
def reassignar_problematics(
    data: DataISO,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Reassigna substitucions problemàtiques (vigilant, absent, de baixa o amb classe).
    """
    try:
        return services.reassigna_problematiques(db, dia, data)
    except MissingXmlError as exc:
        _raise_missing_xml(exc)


@router.get("/{data}/hores-professor/{professor}", response_model=HoresProfessorResponse)
def get_hores_professor(
    data: DataISO,
    professor: NomNet,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """Retorna les hores on el professor té classe, i les hores que és al centre sense classe."""
    try:
        return services.hores_professor(db, dia, data, professor)
    except MissingXmlError as exc:
        _raise_missing_xml(exc)


@router.get("/{data}/{hora}/disponibles", response_model=DisponiblesResponse)
def get_disponibles(
    data: DataISO,
    hora: str,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Retorna professors disponibles per una hora específica,
    ordenats per prioritat amb informació del que estan fent.
    """
    try:
        return services.disponibles(db, dia, data, hora)
    except MissingXmlError as exc:
        _raise_missing_xml(exc)
