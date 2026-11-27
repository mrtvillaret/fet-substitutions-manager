"""Rutes d'Estadístiques: només HTTP. Els recomptes, a services.py."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from dependencies import get_db
from estadistiques import services
from estadistiques.schemas import (
    BatchResponse,
    ClassesDetallResponse,
    DetallProfessorResponse,
    FrangesResponse,
)
from noms import NomNet
from parametres import Data, HoresTriades

router = APIRouter(prefix="/api/estadistiques", tags=["Estadístiques"])


@router.get("/classes/detall", response_model=ClassesDetallResponse)
def get_estadistiques_classes_detall(
    hores: HoresTriades,
    data_inici: Data | None = None,
    data_final: Data | None = None,
    grups: list[str] | None = Query(None),
    grups_bracket: list[str] | None = Query(None, alias="grups[]"),
    db: Session = Depends(get_db),
):
    return services.classes_detall(db, data_inici, data_final, (grups or []) + (grups_bracket or []), hores)


@router.get("/professor/{professor:path}", response_model=DetallProfessorResponse)
def get_estadistiques_professor_detall(
    professor: NomNet,
    hores: HoresTriades,
    data_inici: Data | None = None,
    data_final: Data | None = None,
    db: Session = Depends(get_db),
):
    return services.detall_professor(db, professor, *services.interval(data_inici, data_final), hores)


@router.get("/franges", response_model=FrangesResponse)
def get_resum_franges(
    dia: str,
    hora: str,
    hores: HoresTriades,
    data_inici: Data | None = None,
    data_final: Data | None = None,
    db: Session = Depends(get_db),
):
    return services.franges(db, dia, hora, *services.interval(data_inici, data_final), hores)


@router.get("/batch", response_model=BatchResponse)
def get_estadistiques_batch(
    hores: HoresTriades,
    data_inici: Data | None = None,
    data_final: Data | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return services.batch(db, current_user.institucio, *services.interval(data_inici, data_final), hores)
