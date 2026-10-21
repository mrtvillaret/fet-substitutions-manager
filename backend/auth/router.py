"""Rutes d'auth: entrar, sortir i el perfil propi (/api/users/profile...)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from auth import services
from auth.dependencies import require_super_admin, require_user
from auth.domain import UsuariActual
from auth.schemas import (
    CanviContrasenyaRequest,
    CanviInstitucioRequest,
    LoginRequest,
    LoginResponse,
    OkResponse,
    PerfilResponse,
    SuccessResponse,
)
from auth.security import clear_auth_cookie, set_auth_cookie, testimoni_de_sessio
from database import get_auth_db
from rate_limit import LIMIT_LOGIN_PER_IP, comprova_limit_login_usuari, limiter

router = APIRouter()

# Etiquetes de la documentació de l'API (per ruta: FastAPI suma les del router).
# Les rutes del perfil són sota /api/users (com les d'usuaris/) i amb la seva etiqueta.
ETIQUETA_AUTH = ["auth"]
PERFIL = "/api/users/profile"
ETIQUETA_PERFIL = ["Usuaris"]


# exclude_unset: sense delegació, la resposta és {"ok": true}, sense "redirect"
@router.post("/api/login", tags=ETIQUETA_AUTH, response_model=LoginResponse, response_model_exclude_unset=True)
@limiter.limit(LIMIT_LOGIN_PER_IP)
def login(request: Request, credentials: LoginRequest, response: Response, db: Session = Depends(get_auth_db)):
    comprova_limit_login_usuari(request, credentials.username)
    redirect = services.delegacio_de_login(credentials.username)
    if redirect:
        return {"ok": False, "redirect": redirect}

    user = services.autentica(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencials incorrectes")

    set_auth_cookie(response, testimoni_de_sessio(user))
    return {"ok": True}


@router.post("/api/logout", tags=ETIQUETA_AUTH, response_model=OkResponse)
def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@router.get(PERFIL, tags=ETIQUETA_PERFIL, response_model=PerfilResponse)
def get_profile(current_user: UsuariActual = Depends(require_user)):
    return services.perfil(current_user)


@router.put(f"{PERFIL}/password", tags=ETIQUETA_PERFIL, response_model=SuccessResponse)
@limiter.limit("5/minute")  # comprova la contrasenya actual: com el login
def update_password(
    request: Request,
    payload: CanviContrasenyaRequest,
    response: Response,
    current_user: UsuariActual = Depends(require_user),
    db: Session = Depends(get_auth_db),
):
    user = services.canvia_contrasenya(db, current_user, payload.current_password, payload.new_password)
    set_auth_cookie(response, testimoni_de_sessio(user, current_user.institucio))
    return {"success": True}


@router.post(f"{PERFIL}/tancar-altres-sessions", tags=ETIQUETA_PERFIL, response_model=SuccessResponse)
def tancar_altres_sessions(
    response: Response, current_user: UsuariActual = Depends(require_user), db: Session = Depends(get_auth_db)
):
    """Tanca la sessió a tots els altres dispositius (p.ex. un ordinador
    compartit on no es va tancar). Aquesta sessió continua oberta."""
    user = services.tanca_altres_sessions(db, current_user)
    set_auth_cookie(response, testimoni_de_sessio(user, current_user.institucio))
    return {"success": True}


@router.post(f"{PERFIL}/institucio", tags=ETIQUETA_PERFIL, response_model=OkResponse)
def switch_institucio(
    payload: CanviInstitucioRequest, response: Response, current_user: UsuariActual = Depends(require_super_admin)
):
    services.comprova_institucio_accessible(payload.institucio)
    set_auth_cookie(response, testimoni_de_sessio(current_user, payload.institucio))
    return {"ok": True}
