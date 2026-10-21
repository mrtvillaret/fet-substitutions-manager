"""Entrades i sortides de les rutes d'auth i del perfil."""

from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class CanviContrasenyaRequest(BaseModel):
    current_password: str
    new_password: str


class CanviInstitucioRequest(BaseModel):
    institucio: str


# Sortides


class LoginResponse(BaseModel):
    ok: bool
    # Només quan l'usuari és d'una altra instal·lació (delegació del login)
    redirect: Optional[str] = None


class OkResponse(BaseModel):
    ok: bool


class SuccessResponse(BaseModel):
    success: bool


class PerfilResponse(BaseModel):
    username: str
    role: str
    institucio: str
    institucio_display_name: str
    idioma: str
