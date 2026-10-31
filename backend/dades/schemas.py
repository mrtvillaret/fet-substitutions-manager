"""Esquemes d'entrada de les rutes de governança de dades."""

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


class AnalisiPurgaRequest(BaseModel):
    data_inici: date
    data_final: date


class ExecutarPurgaRequest(BaseModel):
    data_inici: date
    data_final: date
    confirmar: bool = False


class ReanomenaRequest(BaseModel):
    nom_actual: str
    nom_nou: str


class Interval(BaseModel):
    inici: str
    final: str


class FilesBd(BaseModel):
    substitucions: int
    vigilancies: int
    grups_alliberats: int
    baixes: int


class AbsenciaCobertaAPurgar(BaseModel):
    professor: str
    data_inici: str
    data_final: str
    s_esten_fora: bool


class UltimHorari(BaseModel):
    desat: Optional[str]
    dates: List[str]
    s_esten_fora: bool


class PlanificadorAPurgar(BaseModel):
    dates_seleccionades: int
    ultim_horari: Optional[UltimHorari]


class PdfAPurgar(BaseModel):
    fitxer: str
    data: str


class VersioXmlAPurgar(BaseModel):
    id: int
    path: str
    data_inici: str
    data_fi: Optional[str]
    activa: bool
    s_esten_fora: bool
    bloquejat: bool


class AnalisiPurgaResponse(BaseModel):
    interval: Interval
    bd: FilesBd
    total_bd: int
    baixes: List[AbsenciaCobertaAPurgar]
    planificador: PlanificadorAPurgar
    pdfs_a_esborrar: List[PdfAPurgar]
    pdfs_revisio_manual: List[str]
    xml_versions: List[VersioXmlAPurgar]


class PlanificadorPurgat(BaseModel):
    dates_tretes: int
    ultim_horari_esborrat: bool


class VersioXmlEsborrada(BaseModel):
    id: int
    data_inici: str
    data_fi: Optional[str]


class PurgaResponse(BaseModel):
    interval: Interval
    planificador: PlanificadorPurgat
    bd: FilesBd
    total_bd: int
    pdfs_esborrats: List[str]
    pdfs_revisio_manual: List[str]
    xml_esborrats: List[VersioXmlEsborrada]
    xml_bloquejats: List[VersioXmlAPurgar]
    errors: List[str]


class ProfessorDeLaBd(BaseModel):
    nom: str
    actiu: bool


class ProfessorsDeLaBdResponse(BaseModel):
    professors: List[ProfessorDeLaBd]


class ReanomenaResponse(BaseModel):
    ok: bool
    counts: Dict[str, int]  # files canviades de cada taula
    total: int
