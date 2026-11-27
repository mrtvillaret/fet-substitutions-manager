"""Esquemes d'entrada i de sortida de les rutes dels cursos."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from parametres import Data


class CursInput(BaseModel):
    nom: str
    data_inici: Data


class CursResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    data_inici: date | None
    data_fi: date | None  # derivada pel sistema; None = últim curs (obert)


class AvisXmlCursResponse(BaseModel):
    """Un curs que començaria amb l'horari d'un curs anterior."""

    curs_id: int
    curs_nom: str
    curs_inici: date
    xml_inici: date
    xml_path: str


class CursEsborratResponse(BaseModel):
    success: bool
    message: str
