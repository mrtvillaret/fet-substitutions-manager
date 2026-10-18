"""
Endpoints d'autenticació
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from auth_utils import (
    clear_auth_cookie,
    set_auth_cookie,
    testimoni_de_sessio,
    verify_password,
)
from config.auth import LOGIN_DELEGACIO_URL, LOGIN_DELEGACIO_USUARIS
from database import get_auth_db
from rate_limit import limiter
from repositories import UserRepository
from schemas import LoginRequest

router = APIRouter(tags=["auth"])


@router.post("/api/login")
@limiter.limit("5/minute")
def login(request: Request, credentials: LoginRequest, response: Response, db: Session = Depends(get_auth_db)):
    if credentials.username in LOGIN_DELEGACIO_USUARIS:
        # Usuari d'una altra instal·lació del mateix domini: no es valida res
        # aquí; el frontend hi reenvia les credencials.
        return {"ok": False, "redirect": LOGIN_DELEGACIO_URL}

    user = UserRepository.get_by_username(db, credentials.username)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencials incorrectes")

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencials incorrectes")

    set_auth_cookie(response, testimoni_de_sessio(user))
    return {"ok": True}


@router.post("/api/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}
