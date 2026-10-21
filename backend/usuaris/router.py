"""Rutes de la gestió d'usuaris (admin i superadmin). El perfil propi és a
auth/router.py."""

from typing import List

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from auth.dependencies import require_admin, require_super_admin
from auth.domain import UsuariActual
from auth.schemas import SuccessResponse
from auth.security import set_auth_cookie, testimoni_de_sessio
from database import get_auth_db
from usuaris import services
from usuaris.schemas import EdicioUsuariRequest, NouUsuariRequest, UsuariResponse

router = APIRouter(prefix="/api/users", tags=["Usuaris"])


@router.get("", response_model=List[UsuariResponse])
def list_users(current_user: UsuariActual = Depends(require_admin), db: Session = Depends(get_auth_db)):
    return services.llista_usuaris(db, current_user)


@router.post("", response_model=UsuariResponse)
def create_user(
    payload: NouUsuariRequest, current_user: UsuariActual = Depends(require_admin), db: Session = Depends(get_auth_db)
):
    user = services.crea_usuari(db, current_user, payload.username, payload.password, payload.institucio, payload.role)
    return services.fitxa(user)


@router.put("/{user_id}", response_model=UsuariResponse)
def update_user(
    user_id: int,
    payload: EdicioUsuariRequest,
    response: Response,
    current_user: UsuariActual = Depends(require_admin),
    db: Session = Depends(get_auth_db),
):
    user, renova_sessio = services.edita_usuari(db, current_user, user_id, payload.model_dump())
    if renova_sessio:
        set_auth_cookie(response, testimoni_de_sessio(user, current_user.institucio))
    return services.fitxa(user)


@router.delete("/{user_id}", response_model=SuccessResponse)
def deactivate_user(
    user_id: int, current_user: UsuariActual = Depends(require_admin), db: Session = Depends(get_auth_db)
):
    services.desactiva_usuari(db, current_user, user_id)
    return {"success": True}


@router.delete("/{user_id}/hard", response_model=SuccessResponse)
def delete_user(
    user_id: int, current_user: UsuariActual = Depends(require_super_admin), db: Session = Depends(get_auth_db)
):
    services.elimina_usuari(db, current_user, user_id)
    return {"success": True}
