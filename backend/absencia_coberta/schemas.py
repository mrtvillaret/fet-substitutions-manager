"""Entrades i sortides de les rutes de les absències cobertes."""

from typing import List, Optional

from pydantic import BaseModel

from noms import NomNet
from parametres import DataISO


class AbsenciaCobertaRequest(BaseModel):
    professor: NomNet
    data_inici: DataISO  # AAAA-MM-DD; si no, 400
    data_final: DataISO
    motiu: str = ""


class EdicioAbsenciaCobertaRequest(BaseModel):
    professor: Optional[NomNet] = None
    data_inici: Optional[DataISO] = None
    data_final: Optional[DataISO] = None
    motiu: Optional[str] = None


# Sortides


class AbsenciaCobertaResponse(BaseModel):
    id: int
    professor: str
    data_inici: str
    data_final: str
    motiu: str


class AbsenciesCobertesResponse(BaseModel):
    absencies_cobertes: List[AbsenciaCobertaResponse]


class Avis(BaseModel):
    codi: str
    params: dict


class DesadaResponse(BaseModel):
    success: bool
    id: Optional[int] = None
    message: str
    canvis: Optional[dict] = None  # el que s'ha tret en aplicar-la (aplica_absencia_coberta)
    avisos: Optional[List[Avis]] = None


class EsborradaResponse(BaseModel):
    success: bool
    message: str
