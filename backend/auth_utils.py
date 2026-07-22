"""
Utilitats d'autenticació i dependències FastAPI
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from fastapi import Depends, HTTPException, Request, Response, status
import jwt
from jwt import PyJWTError
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.orm import Session

from config.auth import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_HOURS,
    COOKIE_SECURE,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    ADMIN_INSTITUCIO,
    DEFAULT_USERS
)
from config.settings import config
from database import get_auth_db_session, get_auth_db
from repositories import UserRepository

# Argon2 per evitar problemes amb bcrypt a Python 3.13.
# S'usa argon2-cffi directament: passlib només feia de capa intermèdia i porta
# des del 2020 sense cap versió nova. Els paràmetres per defecte són els
# mateixos que aplicava passlib (m=65536, t=3, p=4), i el format del hash és
# l'estàndard PHC, de manera que les contrasenyes ja desades continuen valent.
_hasher = PasswordHasher()
_prioritats_loaded_for = None

COOKIE_NAME = "gestor_token"


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, httponly=True, secure=COOKIE_SECURE, samesite="lax")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    # Compte amb l'ordre dels arguments: argon2-cffi rep (hash, contrasenya),
    # a l'inrevés que passlib. I `verify` no retorna mai False: o retorna True
    # o llança, també si el hash desat està malmès (InvalidHashError, que hereta
    # de ValueError i no d'Argon2Error).
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(data: Dict[str, Any], expires_hours: int = ACCESS_TOKEN_EXPIRE_HOURS) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def ensure_default_users() -> None:
    """Crea usuaris per defecte (admin/user) si no existeixen."""
    defaults = [{"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
                 "institucio": ADMIN_INSTITUCIO, "role": "super_admin"}]
    defaults.extend(DEFAULT_USERS)

    with get_auth_db_session() as db:
        for entry in defaults:
            username = entry["username"]
            password = entry["password"]
            institucio = entry["institucio"]
            role = entry["role"]

            existing = UserRepository.get_by_username(db, username)
            if existing:
                if not existing.password_hash.startswith("$argon2"):
                    existing.password_hash = hash_password(password)
                existing.role = role
                existing.active = True
                existing.institucio = institucio
                db.commit()
                continue

            UserRepository.create(
                db=db,
                username=username,
                password_hash=hash_password(password),
                institucio=institucio,
                role=role,
                active=True
            )


def _apply_institucio(institucio: str) -> None:
    """Assigna institució global per la petició actual."""
    global _prioritats_loaded_for
    if not institucio:
        return
    if config.global_data.get("institucio") != institucio:
        config.global_data["institucio"] = institucio
        config.load_institucio()
    try:
        from i18n_setup import setup_translation
        idioma = config.institucio_data.get("idioma") or config.global_data.get("idioma", "ca")
        setup_translation(idioma)
    except Exception:
        pass
    if _prioritats_loaded_for != institucio:
        try:
            from routes.prioritats import _recarregar_prioritats_desde_bd
            from database import get_data_db_session
            with get_data_db_session(institucio) as db:
                _recarregar_prioritats_desde_bd(db)
            _prioritats_loaded_for = institucio
        except Exception as exc:
            print(f"⚠️ No s'han pogut recarregar prioritats per {institucio}: {exc}")


def get_current_user(
    request: Request,
    db: Session = Depends(get_auth_db)
):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticat")
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        institucio = payload.get("institucio")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")
    except PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid") from exc

    user = UserRepository.get_by_username(db, username)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuari inactiu o inexistent")

    if user.role == "super_admin":
        institucio_activa = institucio or user.institucio
        if not institucio_activa:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")
        if not config.is_institucio_activa(institucio_activa):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Institució inactiva")
        _apply_institucio(institucio_activa)
        user.institucio = institucio_activa
        return user

    if not institucio or user.institucio != institucio:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")

    if user.role != "super_admin" and not config.is_institucio_activa(user.institucio):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Institució inactiva")

    _apply_institucio(user.institucio)
    return user


def require_user(current_user=Depends(get_current_user)):
    return current_user


def require_admin(current_user=Depends(get_current_user)):
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficients")
    return current_user


def require_super_admin(current_user=Depends(get_current_user)):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficients")
    return current_user
