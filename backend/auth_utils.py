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
from starlette.concurrency import run_in_threadpool

from config.auth import (
    COOKIE_NAME,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_HOURS,
    COOKIE_SECURE,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    ADMIN_INSTITUCIO,
    DEFAULT_USERS
)
from config.context import fixa_institucio_peticio
from config.settings import config
from database import get_auth_db_session, get_auth_db
from repositories import UserRepository

# Argon2 per evitar problemes amb bcrypt a Python 3.13.
# S'usa argon2-cffi directament: passlib només feia de capa intermèdia i porta
# des del 2020 sense cap versió nova. Els paràmetres per defecte són els
# mateixos que aplicava passlib (m=65536, t=3, p=4), i el format del hash és
# l'estàndard PHC, de manera que les contrasenyes ja desades continuen valent.
_hasher = PasswordHasher()


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


def testimoni_de_sessio(user, institucio: str = None) -> str:
    """Testimoni de sessió d'un usuari, amb la seva versió de sessió actual."""
    return create_access_token({
        "sub": user.username,
        "institucio": institucio or user.institucio,
        "role": user.role,
        "sv": user.versio_sessio or 0,
    })


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def ensure_default_users() -> None:
    """Crea els usuaris inicials si no existeixen.

    Les contrasenyes han de venir per variable d'entorn: si en falta alguna,
    l'aplicació s'atura en lloc d'usar un valor fix. Un valor per defecte al
    codi és públic per definició, i una instal·lació que no llegís les
    instruccions quedaria oberta amb credencials conegudes.
    """
    defaults = [{"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
                 "institucio": ADMIN_INSTITUCIO, "role": "super_admin",
                 "obligatori": True}]
    defaults.extend(DEFAULT_USERS)

    with get_auth_db_session() as db:
        for entry in defaults:
            username = entry["username"]
            password = entry["password"]
            institucio = entry["institucio"]
            role = entry["role"]

            existing = UserRepository.get_by_username(db, username)
            if existing:
                # Rehash d'un format antic: només és possible si sabem la
                # contrasenya, o sigui si ve de la variable d'entorn.
                if password and not existing.password_hash.startswith("$argon2"):
                    existing.password_hash = hash_password(password)
                existing.role = role
                existing.active = True
                existing.institucio = institucio
                db.commit()
                continue

            if not password:
                if entry.get("obligatori"):
                    raise SystemExit(
                        f"\nERROR: cal definir ADMIN_PASSWORD per crear l'usuari "
                        f"'{username}'.\n"
                        f"Afegeix-la al fitxer .env i torna a arrencar.\n"
                    )
                # Els altres usuaris de mostra són opcionals: sense contrasenya
                # definida, simplement no es creen.
                continue

            UserRepository.create(
                db=db,
                username=username,
                password_hash=hash_password(password),
                institucio=institucio,
                role=role,
                active=True
            )


def _prepara_institucio(institucio: str) -> str:
    """Deixa a punt la institució de la petició en curs: traduccions del seu
    idioma i prioritats (es carreguen un cop per institució i es recorden).
    Retorna l'idioma, que fixa get_current_user: s'executa en un fil i una
    ContextVar fixada aquí no arribaria a la ruta."""
    from database import get_data_db_session
    from repositories import ConfiguracioRepository
    import config.constants as constants

    idioma = config.global_data.get("idioma", "ca")
    try:
        import i18n_setup
        with get_data_db_session(institucio) as db:
            idioma = ConfiguracioRepository.get(db, "idioma") or idioma
        i18n_setup.carrega_idioma(idioma)
    except Exception:
        pass
    if not constants.te_prioritats(institucio):
        try:
            from routes.prioritats import _recarregar_prioritats_desde_bd
            with get_data_db_session(institucio) as db:
                _recarregar_prioritats_desde_bd(db)
        except Exception as exc:
            print(f"⚠️ No s'han pogut carregar prioritats per {institucio}: {exc}")
    return idioma


def _valida_usuari(request: Request, db: Session):
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

    # Testimoni d'abans d'un canvi de contrasenya o d'un "tancar les altres
    # sessions". Els testimonis antics sense "sv" valen com a versió 0.
    if payload.get("sv", 0) != (user.versio_sessio or 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessió tancada")

    if user.role == "super_admin":
        institucio_activa = institucio or user.institucio
        if not institucio_activa:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")
        if not config.is_institucio_activa(institucio_activa):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Institució inactiva")
        # La institució activa només val per a aquesta petició: es desvincula
        # l'usuari de la sessió perquè cap commit posterior la desi a auth.db.
        db.expunge(user)
        user.institucio = institucio_activa
        return user

    if not institucio or user.institucio != institucio:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")

    if user.role != "super_admin" and not config.is_institucio_activa(user.institucio):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Institució inactiva")

    return user


async def get_current_user(
    request: Request,
    db: Session = Depends(get_auth_db)
):
    """Usuari autenticat de la petició. També fixa la institució de la petició
    (config.context), que és la que fa servir tot el codi que no rep la
    institució explícitament. Ha de ser async: una ContextVar fixada dins d'un
    fil (on FastAPI executa les dependències síncrones) no arribaria a la ruta."""
    user = await run_in_threadpool(_valida_usuari, request, db)
    fixa_institucio_peticio(user.institucio)
    idioma = await run_in_threadpool(_prepara_institucio, user.institucio)
    import i18n_setup
    i18n_setup.setup_translation(idioma)
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
