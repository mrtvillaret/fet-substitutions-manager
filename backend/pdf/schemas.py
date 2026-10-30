"""Esquemes d'entrada i sortida de les rutes PDF."""

from typing import Any

from pydantic import BaseModel


class PDFPreferencesRequest(BaseModel):
    substitucions: dict[str, Any] | None = None
    vigilancies: dict[str, Any] | None = None
    vigilancies_interval: dict[str, Any] | None = None


class PDFPreferencesResponse(BaseModel):
    substitucions: dict[str, Any] | None = None
    vigilancies: dict[str, Any] | None = None
    vigilancies_interval: dict[str, Any] | None = None


class ValidacionsPdfResponse(BaseModel):
    conflicts: list[str]
    warnings: list[str]
    total: int
    has_critical: bool


class DisponiblesTotsDiesRequest(BaseModel):
    data_inici: str | None = None
