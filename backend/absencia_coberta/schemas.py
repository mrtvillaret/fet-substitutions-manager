"""Entrades i sortides de les rutes de les absències cobertes."""

from datetime import date

from pydantic import BaseModel

from noms import NomNet
from parametres import DataTextual


class AbsenciaCobertaRequest(BaseModel):
    professor: NomNet
    data_inici: DataTextual  # AAAA-MM-DD; si no, 400
    data_final: DataTextual
    motiu: str = ""


class EdicioAbsenciaCobertaRequest(BaseModel):
    professor: NomNet | None = None
    data_inici: DataTextual | None = None
    data_final: DataTextual | None = None
    motiu: str | None = None


# Sortides


class AbsenciaCobertaResponse(BaseModel):
    id: int
    professor: str
    data_inici: date
    data_final: date
    motiu: str


class AbsenciesCobertesResponse(BaseModel):
    absencies_cobertes: list[AbsenciaCobertaResponse]


class Avis(BaseModel):
    codi: str
    params: dict


class DesadaResponse(BaseModel):
    success: bool
    id: int | None = None
    message: str
    canvis: dict | None = None  # el que s'ha tret en aplicar-la (aplica_absencia_coberta)
    avisos: list[Avis] | None = None


class EsborradaResponse(BaseModel):
    success: bool
    message: str
