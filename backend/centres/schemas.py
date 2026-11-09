"""Esquemes d'entrada de les rutes dels centres."""

from pydantic import BaseModel


class InstitucioCreate(BaseModel):
    nom: str
    display_name: str | None = None


class InstitucioUpdate(BaseModel):
    display_name: str


class InstitucioStatus(BaseModel):
    active: bool


class InstitucioDelete(BaseModel):
    mode: str = "soft"  # «hard», 400: l'esborrat definitiu es fa des del servidor
    confirm: str


class Centre(BaseModel):
    slug: str
    display_name: str
    active: bool


class CentresResponse(BaseModel):
    institucions: list[Centre]
    actual: str  # el centre de qui ho demana


class CentreCreatResponse(BaseModel):
    success: bool
    institucio: str


class NomVisibleResponse(BaseModel):
    success: bool
    slug: str
    display_name: str


class EstatCentreResponse(BaseModel):
    success: bool
    slug: str
    active: bool


class CentreEsborratResponse(BaseModel):
    success: bool
    slug: str
    mode: str
