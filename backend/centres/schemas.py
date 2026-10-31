"""Esquemes d'entrada de les rutes dels centres."""

from typing import List, Optional

from pydantic import BaseModel


class InstitucioCreate(BaseModel):
    nom: str
    display_name: Optional[str] = None


class InstitucioUpdate(BaseModel):
    display_name: str


class InstitucioStatus(BaseModel):
    active: bool


class InstitucioDelete(BaseModel):
    mode: str = "soft"  # soft | hard
    confirm: str


class Centre(BaseModel):
    slug: str
    display_name: str
    active: bool


class CentresResponse(BaseModel):
    institucions: List[Centre]
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
