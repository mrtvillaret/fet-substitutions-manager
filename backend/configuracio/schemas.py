"""Esquemes d'entrada de les rutes de configuració del centre."""

from pydantic import BaseModel

from noms import NomNet
from parametres import DataISO


class SettingsUpdate(BaseModel):
    """Model per actualitzar configuració. La pantalla també hi envia
    `institucio`, que s'ignora (el centre per defecte no es canvia d'aquí)."""

    idioma: str | None = None
    data_inici_estadistiques: DataISO | None = None  # 400 si no és AAAA-MM-DD
    data_final_estadistiques: DataISO | None = None
    ultim_professor_subs: NomNet | None = None
    institucio_display_name: str | None = None


class ConfiguracioResponse(BaseModel):
    institucio: str
    idioma: str
    xml_horari_path: str | None
    data_inici_estadistiques: str | None
    data_final_estadistiques: str | None
    logo_path: str | None
    te_logo: bool
    institucio_display_name: str
    ultim_professor_subs: str
    xml_missing: bool


class ConfiguracioDesadaResponse(BaseModel):
    success: bool
    message: str
    changed: list[str]


class Idioma(BaseModel):
    code: str
    name: str


class IdiomesResponse(BaseModel):
    idiomes: list[Idioma]
    actual: str


class LogoDesatResponse(BaseModel):
    success: bool
    filename: str
    path: str
    message: str
