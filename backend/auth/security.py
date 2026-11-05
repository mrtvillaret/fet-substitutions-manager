"""Contrasenyes (Argon2), testimonis de sessió (JWT) i la cookie que els porta."""

from datetime import datetime, timedelta, timezone
from functools import cache
from typing import Any, Dict

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request, Response
from jwt import PyJWTError

import rellotge
from config.auth import get_config_auth

# Argon2 per evitar problemes amb bcrypt a Python 3.13.
# S'usa argon2-cffi directament: passlib només feia de capa intermèdia i porta
# des del 2020 sense cap versió nova. Els paràmetres per defecte són els
# mateixos que aplicava passlib (m=65536, t=3, p=4), i el format del hash és
# l'estàndard PHC, de manera que les contrasenyes ja desades continuen valent.
_hasher = PasswordHasher()


def get_auth_token(request: Request) -> str | None:
    """Llegeix el testimoni amb el mateix nom de galeta que en entrar i sortir."""
    return request.cookies.get(get_config_auth().cookie_name)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=get_config_auth().cookie_name,
        value=token,
        httponly=True,
        secure=get_config_auth().cookie_secure,
        samesite="lax",
        max_age=get_config_auth().sessio_inactivitat_minuts * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=get_config_auth().cookie_name,
        httponly=True,
        secure=get_config_auth().cookie_secure,
        samesite="lax",
    )


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


@cache
def hash_fictici() -> str:
    """Un hash per comprovar-hi la contrasenya quan l'usuari no existeix: així
    el login triga el mateix (un Argon2) i el temps no diu si l'usuari existeix.
    Es calcula el primer cop que cal, no en arrencar."""
    return _hasher.hash("contrasenya fictícia per igualar el temps del login")


def create_access_token(data: Dict[str, Any], expira: datetime = None) -> str:
    """`expira`: per defecte, d'aquí a SESSIO_INACTIVITAT_MINUTS."""
    ara = rellotge.ara(timezone.utc)
    to_encode = data.copy()
    to_encode["iat"] = ara
    to_encode["exp"] = expira or ara + timedelta(minutes=get_config_auth().sessio_inactivitat_minuts)
    return jwt.encode(to_encode, get_config_auth().secret_key, algorithm=get_config_auth().algorithm)


def _caducitat(inici: float, ara: datetime) -> datetime:
    """La primera de: d'aquí a la inactivitat màxima o el màxim des de l'entrada."""
    limit = datetime.fromtimestamp(inici, timezone.utc) + timedelta(hours=get_config_auth().sessio_maxima_hores)
    return min(ara + timedelta(minutes=get_config_auth().sessio_inactivitat_minuts), limit)


def testimoni_de_sessio(user, institucio: str = None) -> str:
    """Testimoni de sessió d'un usuari, amb el seu id («uid», que l'identifica:
    el nom pot canviar o passar a un altre usuari), la versió de sessió actual
    i l'hora d'entrada («ini»), que fixa el màxim de la sessió."""
    ara = rellotge.ara(timezone.utc)
    return create_access_token(
        {
            "sub": user.username,
            "uid": user.id,
            "institucio": institucio or user.institucio,
            "role": user.role,
            "sv": user.versio_sessio or 0,
            "ini": ara.timestamp(),
        },
        expira=_caducitat(ara.timestamp(), ara),
    )


def registra_renovacio_sessio(app) -> None:
    """Afegeix a `app` la renovació de la sessió: a cada petició a l'API que va
    bé, si cal (renova_testimoni), la resposta porta la cookie renovada. No es
    toca si la mateixa resposta ja en porta una (entrar, sortir, canviar de
    centre o de contrasenya)."""

    @app.middleware("http")
    async def renova_sessio(request: Request, call_next):
        response = await call_next(request)
        token = get_auth_token(request)
        if (
            token
            and response.status_code < 400
            and request.url.path.startswith("/api/")
            and not any(get_config_auth().cookie_name in v for v in response.headers.getlist("set-cookie"))
        ):
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
    ara = rellotge.ara(timezone.utc)
    emes = payload.get("iat")
    if emes and ara.timestamp() - emes < get_config_auth().sessio_renovacio_minuts * 60:
        return None
    inici = payload.get("ini") or ara.timestamp()  # testimonis d'abans d'aquest canvi
    caduca = _caducitat(inici, ara)
    if caduca <= ara:
        return None
    nou = {k: v for k, v in payload.items() if k not in ("iat", "exp")}
    nou["ini"] = inici
    return create_access_token(nou, expira=caduca)


def decode_access_token(token: str) -> Dict[str, Any]:
    return _JWT(rellotge.ara(timezone.utc).timestamp()).decode(
        token, get_config_auth().secret_key, algorithms=[get_config_auth().algorithm]
    )


class _JWT(jwt.PyJWT):
    """Manté totes les validacions de PyJWT amb l'hora del nostre rellotge.

    Una instància per lectura: cap estat temporal compartit entre peticions.
    """

    def __init__(self, ara: float):
        super().__init__()
        self._ara = ara

    def _validate_iat(self, payload, now, leeway):
        return super()._validate_iat(payload, self._ara, leeway)

    def _validate_nbf(self, payload, now, leeway):
        return super()._validate_nbf(payload, self._ara, leeway)

    def _validate_exp(self, payload, now, leeway):
        return super()._validate_exp(payload, self._ara, leeway)
