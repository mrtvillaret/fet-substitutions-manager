"""Esquemes d'entrada de les rutes de configuració del centre."""

from datetime import date

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

from noms import NomNet
from parametres import Data


class SettingsUpdate(BaseModel):
    """Model per actualitzar configuració. La pantalla també hi envia
    `institucio`, que s'ignora (el centre per defecte no es canvia d'aquí)."""

    idioma: str | None = None
    data_inici_estadistiques: Data | None = None
    data_final_estadistiques: Data | None = None
    ultim_professor_subs: NomNet | None = None
    institucio_display_name: str | None = None

    @field_validator("data_inici_estadistiques", "data_final_estadistiques", mode="before")
    @classmethod
    def _tipus_dates_estadistiques(cls, valor: object) -> object:
        # Contracte de /api/settings per a una data textual: un número en JSON dona 422.
        if valor is not None and not isinstance(valor, (str, date)):
            raise PydanticCustomError("string_type", "Input should be a valid string")
        return valor


class ConfiguracioResponse(BaseModel):
    institucio: str
    idioma: str
    xml_horari_path: str | None
    data_inici_estadistiques: date | str | None
    data_final_estadistiques: date | str | None
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
