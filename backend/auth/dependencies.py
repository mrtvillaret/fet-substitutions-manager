"""Dependències de FastAPI: l'usuari que fa la petició i el rol que se li demana."""

import logging

from fastapi import Depends, HTTPException, Request, status
from jwt import ExpiredSignatureError, PyJWTError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from auth import security
from auth.domain import Rol, UsuariActual
from auth.repositories import UserRepository
from config.context import fixa_institucio_peticio
from config.settings import config
from database import get_auth_db

log = logging.getLogger(__name__)


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
        except Exception:
            log.warning("No s'han pogut carregar les prioritats de %s", institucio, exc_info=True)
    return idioma


def _valida_usuari(request: Request, db: Session) -> UsuariActual:
    # security.COOKIE_NAME (i no una còpia importada): el nom de la galeta es
    # llegeix d'un sol lloc, el mateix que fa servir set_auth_cookie
    token = request.cookies.get(security.COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticat")
    try:
        payload = security.decode_access_token(token)
        username = payload.get("sub")
        institucio = payload.get("institucio")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")
    except ExpiredSignatureError as exc:
        # Sense activitat durant SESSIO_INACTIVITAT_MINUTS, o passat el màxim
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessió caducada") from exc
    except PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid") from exc

    # Per l'id: si l'usuari s'esborra o es reanomena i un altre pren el seu nom,
    # la sessió no passa al nou. Els testimonis d'abans, sense "uid" (duren com
    # a molt SESSIO_MAXIMA_HORES), encara es busquen pel nom.
    uid = payload.get("uid")
    user = UserRepository.get_by_id(db, uid) if uid is not None else UserRepository.get_by_username(db, username)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuari inactiu o inexistent")

    # Testimoni d'abans d'un canvi de contrasenya o d'un "tancar les altres
    # sessions". Els testimonis antics sense "sv" valen com a versió 0.
    if payload.get("sv", 0) != (user.versio_sessio or 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessió tancada")

    if user.role == Rol.SUPER_ADMIN:
        # Treballa amb la institució del testimoni (la que ha triat), no la seva
        institucio_activa = institucio or user.institucio
        if not institucio_activa:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")
    else:
        if not institucio or user.institucio != institucio:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")
        institucio_activa = user.institucio

    if not config.is_institucio_activa(institucio_activa):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Institució inactiva")

    return UsuariActual(
        id=user.id,
        username=user.username,
        role=user.role,
        institucio=institucio_activa,
        versio_sessio=user.versio_sessio or 0,
    )


async def get_current_user(request: Request, db: Session = Depends(get_auth_db)) -> UsuariActual:
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


def require_user(current_user: UsuariActual = Depends(get_current_user)) -> UsuariActual:
    return current_user


def require_admin(current_user: UsuariActual = Depends(get_current_user)) -> UsuariActual:
    if not current_user.es_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficients")
    return current_user


def require_super_admin(current_user: UsuariActual = Depends(get_current_user)) -> UsuariActual:
    if not current_user.es_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficients")
    return current_user
