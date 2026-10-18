"""
Utilitats d'autenticació i dependències FastAPI
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from jwt import ExpiredSignatureError, PyJWTError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from config.auth import (
    ADMIN_INSTITUCIO,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    ALGORITHM,
    COOKIE_NAME,
    COOKIE_SECURE,
    DEFAULT_USERS,
    SECRET_KEY,
    SESSIO_INACTIVITAT_MINUTS,
    SESSIO_MAXIMA_HORES,
    SESSIO_RENOVACIO_MINUTS,
)
from config.context import fixa_institucio_peticio
from config.settings import config
from database import get_auth_db, get_auth_db_session
from repositories import UserRepository

log = logging.getLogger(__name__)

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
        max_age=SESSIO_INACTIVITAT_MINUTS * 60,
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


def create_access_token(data: Dict[str, Any], expira: datetime = None) -> str:
    """`expira`: per defecte, d'aquí a SESSIO_INACTIVITAT_MINUTS."""
    ara = datetime.now(timezone.utc)
    to_encode = data.copy()
    to_encode["iat"] = ara
    to_encode["exp"] = expira or ara + timedelta(minutes=SESSIO_INACTIVITAT_MINUTS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _caducitat(inici: float, ara: datetime) -> datetime:
    """La primera de: d'aquí a la inactivitat màxima o el màxim des de l'entrada."""
    limit = datetime.fromtimestamp(inici, timezone.utc) + timedelta(hours=SESSIO_MAXIMA_HORES)
    return min(ara + timedelta(minutes=SESSIO_INACTIVITAT_MINUTS), limit)


def testimoni_de_sessio(user, institucio: str = None) -> str:
    """Testimoni de sessió d'un usuari, amb la seva versió de sessió actual i
    l'hora d'entrada («ini»), que fixa el màxim de la sessió."""
    ara = datetime.now(timezone.utc)
    return create_access_token({
        "sub": user.username,
        "institucio": institucio or user.institucio,
        "role": user.role,
        "sv": user.versio_sessio or 0,
        "ini": ara.timestamp(),
    }, expira=_caducitat(ara.timestamp(), ara))


def registra_renovacio_sessio(app) -> None:
    """Afegeix a `app` la renovació de la sessió: a cada petició a l'API que va
    bé, si cal (renova_testimoni), la resposta porta la cookie renovada. No es
    toca si la mateixa resposta ja en porta una (entrar, sortir, canviar de
    centre o de contrasenya)."""
    @app.middleware("http")
    async def renova_sessio(request: Request, call_next):
        response = await call_next(request)
        token = request.cookies.get(COOKIE_NAME)
        if (token and response.status_code < 400 and request.url.path.startswith("/api/")
                and not any(COOKIE_NAME in v for v in response.headers.getlist("set-cookie"))):
            nou = renova_testimoni(token)
            if nou:
                set_auth_cookie(response, nou)
        return response


def renova_testimoni(token: str):
    """Si el testimoni és vàlid i fa més de SESSIO_RENOVACIO_MINUTS que es va
    emetre, un de nou que caduca d'aquí a la inactivitat màxima (sense passar
    del màxim des de l'entrada). Si no cal o no es pot renovar, None."""
    try:
        payload = decode_access_token(token)
    except PyJWTError:
        return None
    ara = datetime.now(timezone.utc)
    emes = payload.get("iat")
    if emes and ara.timestamp() - emes < SESSIO_RENOVACIO_MINUTS * 60:
        return None
    inici = payload.get("ini") or ara.timestamp()   # testimonis d'abans d'aquest canvi
    caduca = _caducitat(inici, ara)
    if caduca <= ara:
        return None
    nou = {k: v for k, v in payload.items() if k not in ("iat", "exp")}
    nou["ini"] = inici
    return create_access_token(nou, expira=caduca)


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
    import config.constants as constants
    from database import get_data_db_session
    from repositories import ConfiguracioRepository

    idioma = config.global_data.get("idioma", "ca")
    try:
        import i18n_setup
        with get_data_db_session(institucio) as db:
            idioma = ConfiguracioRepository.get(db, "idioma") or idioma
        i18n_setup.carrega_idioma(idioma)
    except Exception:
        log.warning("No s'ha pogut carregar l'idioma del centre", exc_info=True)
    if not constants.te_prioritats(institucio):
        try:
            from routes.prioritats import _recarregar_prioritats_desde_bd
            with get_data_db_session(institucio) as db:
                _recarregar_prioritats_desde_bd(db)
        except Exception as exc:
            log.warning(f"⚠️ No s'han pogut carregar prioritats per {institucio}: {exc}")
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
    except ExpiredSignatureError as exc:
        # Sense activitat durant SESSIO_INACTIVITAT_MINUTS, o passat el màxim
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessió caducada") from exc
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
