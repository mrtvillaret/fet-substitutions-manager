"""Esquemes d'entrada de les rutes de configuració del centre."""

from typing import List, Optional

from pydantic import BaseModel

from noms import NomNet
from parametres import DataISO


class SettingsUpdate(BaseModel):
    """Model per actualitzar configuració. La pantalla també hi envia
    `institucio`, que s'ignora (el centre per defecte no es canvia d'aquí)."""

    idioma: Optional[str] = None
    data_inici_estadistiques: Optional[DataISO] = None  # 400 si no és AAAA-MM-DD
    data_final_estadistiques: Optional[DataISO] = None
    ultim_professor_subs: Optional[NomNet] = None
    institucio_display_name: Optional[str] = None


class ConfiguracioResponse(BaseModel):
    institucio: str
    idioma: str
    xml_horari_path: Optional[str]
    data_inici_estadistiques: Optional[str]
    data_final_estadistiques: Optional[str]
    logo_path: Optional[str]
    te_logo: bool
    institucio_display_name: str
    ultim_professor_subs: str
    xml_missing: bool


class ConfiguracioDesadaResponse(BaseModel):
    success: bool
    message: str
    changed: List[str]


class Idioma(BaseModel):
    code: str
    name: str


class IdiomesResponse(BaseModel):
    idiomes: List[Idioma]
    actual: str


class LogoDesatResponse(BaseModel):
    success: bool
    filename: str
    path: str
    message: str
