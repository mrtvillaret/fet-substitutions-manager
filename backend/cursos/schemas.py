"""Esquemes d'entrada i de sortida de les rutes dels cursos."""

from datetime import date
from typing import Optional

from pydantic import BaseModel


class CursInput(BaseModel):
    nom: str
    data_inici: date


class CursResponse(BaseModel):
    id: int
    nom: str
    data_inici: Optional[str]
    data_fi: Optional[str]  # derivada pel sistema; None = últim curs (obert)


class AvisXmlCursResponse(BaseModel):
    """Un curs que començaria amb l'horari d'un curs anterior."""

    curs_id: int
    curs_nom: str
    curs_inici: str
    xml_inici: str
    xml_path: str


class CursEsborratResponse(BaseModel):
    success: bool
    message: str
