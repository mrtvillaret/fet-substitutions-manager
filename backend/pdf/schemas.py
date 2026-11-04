"""Esquemes d'entrada i sortida de les rutes PDF."""

from typing import Any

from pydantic import BaseModel

from vigilancies.schemas import ProblemaVigilancia


class PDFPreferencesRequest(BaseModel):
    substitucions: dict[str, Any] | None = None
    vigilancies: dict[str, Any] | None = None
    vigilancies_interval: dict[str, Any] | None = None


class PDFPreferencesResponse(BaseModel):
    substitucions: dict[str, Any] | None = None
    vigilancies: dict[str, Any] | None = None
    vigilancies_interval: dict[str, Any] | None = None


class DesatResponse(BaseModel):
    success: bool


class ProfessorsLlistaResponse(BaseModel):
    professors: list[str]


class ValidacionsPdfResponse(BaseModel):
    avisos_encadenades: list[str]
    problemes_vigilancies: list[ProblemaVigilancia]
    conflicts: list[str]
    warnings: list[str]
    total: int
    has_critical: bool


class VigilanciesSenseNivellResponse(BaseModel):
    sense_nivell: int


class DisponiblesTotsDiesRequest(BaseModel):
    data_inici: str | None = None
