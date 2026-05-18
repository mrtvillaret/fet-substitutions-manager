"""
Endpoints d'autenticació
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from sqlalchemy.orm import Session

from auth_utils import create_access_token, verify_password, set_auth_cookie, clear_auth_cookie
from database import get_auth_db
from rate_limit import limiter
from repositories import UserRepository
from schemas import LoginRequest

router = APIRouter(tags=["auth"])


@router.post("/api/login")
@limiter.limit("5/minute")
def login(request: Request, credentials: LoginRequest, response: Response, db: Session = Depends(get_auth_db)):
    user = UserRepository.get_by_username(db, credentials.username)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencials incorrectes")

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencials incorrectes")

    token = create_access_token({
        "sub": user.username,
        "institucio": user.institucio,
        "role": user.role
    })
    set_auth_cookie(response, token)
    return {"ok": True}


@router.post("/api/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}
