"""Entrades i sortides de la gestió d'usuaris."""

from pydantic import BaseModel


class NouUsuariRequest(BaseModel):
    username: str
    password: str
    institucio: str | None = None
    role: str = "user"


class EdicioUsuariRequest(BaseModel):
    username: str | None = None
    role: str | None = None
    active: bool | None = None
    institucio: str | None = None
    password: str | None = None


class UsuariResponse(BaseModel):
    id: int
    username: str
    institucio: str
    institucio_display_name: str | None = None
    role: str
    active: bool
