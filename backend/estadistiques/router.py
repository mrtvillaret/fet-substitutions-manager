"""Rutes d'Estadístiques: només HTTP. Els recomptes, a services.py."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from dependencies import get_db
from estadistiques import services
from estadistiques.schemas import (
    ClassesDetallResponse,
    ClassesResponse,
    DetallProfessorResponse,
    FrangesResponse,
    HoresResponse,
    ProfessorsResponse,
    ResumResponse,
    TaulaProfessorsResponse,
    TemporalResponse,
)
from noms import NomNet
from routes.parametres import DataISO, HoresTriades

router = APIRouter(prefix="/api/estadistiques", tags=["Estadístiques"])


@router.get("/resum", response_model=ResumResponse)
def get_resum_estadistiques(
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
):
    return services.resum(db, *services.interval(data_inici, data_final), hores)


@router.get("/professors", response_model=ProfessorsResponse)
def get_estadistiques_professors(
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
):
    return services.professors(db, *services.interval(data_inici, data_final), hores)


@router.get("/temporal", response_model=TemporalResponse)
def get_estadistiques_temporals(
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return services.temporal(db, current_user.institucio, *services.interval(data_inici, data_final), hores)


@router.get("/classes", response_model=ClassesResponse)
def get_estadistiques_classes(
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
):
    return services.classes(db, *services.interval(data_inici, data_final), hores)


@router.get("/classes/detall", response_model=ClassesDetallResponse)
def get_estadistiques_classes_detall(
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    grups: Optional[List[str]] = Query(None),
    grups_bracket: Optional[List[str]] = Query(None, alias="grups[]"),
    db: Session = Depends(get_db),
):
    return services.classes_detall(db, data_inici, data_final, (grups or []) + (grups_bracket or []), hores)


@router.get("/taula", response_model=TaulaProfessorsResponse)
def get_estadistiques_taula_professors(
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
):
    return services.taula_professors(db, *services.interval(data_inici, data_final), hores)


@router.get("/professor/{professor}", response_model=DetallProfessorResponse)
def get_estadistiques_professor_detall(
    professor: NomNet,
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
):
    return services.detall_professor(db, professor, *services.interval(data_inici, data_final), hores)


@router.get("/franges", response_model=FrangesResponse)
def get_resum_franges(
    dia: str,
    hora: str,
    hores: HoresTriades,
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
):
    return services.franges(db, dia, hora, *services.interval(data_inici, data_final), hores)


@router.get("/hores", response_model=HoresResponse)
def get_hores_estadistiques(
    data_inici: Optional[DataISO] = None,
    data_final: Optional[DataISO] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Les franges de l'horari a l'interval, per al filtre per hores."""
    return services.hores_de_l_horari(db, current_user.institucio, *services.interval(data_inici, data_final))
