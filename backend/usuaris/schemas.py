"""Entrades i sortides de la gestió d'usuaris."""

from typing import Optional

from pydantic import BaseModel


class NouUsuariRequest(BaseModel):
    username: str
    password: str
    institucio: Optional[str] = None
    role: str = "user"


class EdicioUsuariRequest(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    institucio: Optional[str] = None
    password: Optional[str] = None


class UsuariResponse(BaseModel):
    id: int
    username: str
    institucio: str
    institucio_display_name: Optional[str] = None
    role: str
    active: bool
