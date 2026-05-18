"""
Gestió d'usuaris i perfil
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_utils import require_admin, require_super_admin, require_user, hash_password, verify_password, create_access_token, set_auth_cookie
from database import get_auth_db, get_engine_for_institucio
from repositories import UserRepository, ConfiguracioRepository
from config.settings import config
from sqlalchemy.orm import sessionmaker

router = APIRouter(prefix="/api/users", tags=["Usuaris"])


class UserCreate(BaseModel):
    username: str
    password: str
    institucio: Optional[str] = None
    role: str = "user"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    institucio: Optional[str] = None
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    institucio: str
    institucio_display_name: Optional[str] = None
    role: str
    active: bool


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


class SwitchInstitucioRequest(BaseModel):
    institucio: str


@router.get("", response_model=List[UserResponse])
def list_users(
    current_user=Depends(require_admin),
    db: Session = Depends(get_auth_db)
):
    def display_map(slugs):
        mapping = {}
        for slug in slugs:
            engine = get_engine_for_institucio(slug)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            data_db = SessionLocal()
            try:
                mapping[slug] = ConfiguracioRepository.get(data_db, "institucio_display_name") or slug
            finally:
                data_db.close()
        return mapping

    if current_user.role == "super_admin":
        users = UserRepository.list_all(db)
    else:
        users = [
            u for u in UserRepository.list_by_institucio(db, current_user.institucio)
            if u.role != "super_admin"
        ]

    inst_map = display_map({u.institucio for u in users})
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            institucio=u.institucio,
            institucio_display_name=inst_map.get(u.institucio, u.institucio),
            role=u.role,
            active=u.active
        )
        for u in users
    ]


@router.post("", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_auth_db)
):
    role = payload.role or "user"
    if role not in ("super_admin", "admin", "user"):
        raise HTTPException(status_code=400, detail="Rol invàlid")

    institucio = payload.institucio or current_user.institucio
    disponibles = config.get_institucions_disponibles()
    if institucio not in disponibles:
        raise HTTPException(status_code=400, detail="Institució inexistent")
    if current_user.role != "super_admin":
        if institucio != current_user.institucio:
            raise HTTPException(status_code=403, detail="No pots crear usuaris d'una altra institució")
        if role == "super_admin":
            raise HTTPException(status_code=403, detail="No pots crear superadmins")

    existing = UserRepository.get_by_username(db, payload.username)
    if existing:
        raise HTTPException(status_code=409, detail="Ja existeix un usuari amb aquest nom")

    user = UserRepository.create(
        db=db,
        username=payload.username,
        password_hash=hash_password(payload.password),
        institucio=institucio,
        role=role,
        active=True
    )
    engine = get_engine_for_institucio(institucio)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    data_db = SessionLocal()
    try:
        display_name = ConfiguracioRepository.get(data_db, "institucio_display_name") or institucio
    finally:
        data_db.close()
    return UserResponse(
        id=user.id,
        username=user.username,
        institucio=user.institucio,
        institucio_display_name=display_name,
        role=user.role,
        active=user.active
    )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_auth_db)
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    if user.role == "super_admin":
        raise HTTPException(status_code=403, detail="No es pot editar el superadmin")

    if current_user.role != "super_admin":
        if user.institucio != current_user.institucio:
            raise HTTPException(status_code=403, detail="No pots editar usuaris d'una altra institució")
        if payload.institucio and payload.institucio != current_user.institucio:
            raise HTTPException(status_code=403, detail="No pots canviar la institució")
        if payload.role == "super_admin":
            raise HTTPException(status_code=403, detail="No pots assignar el rol superadmin")

    if payload.role and payload.role not in ("super_admin", "admin", "user"):
        raise HTTPException(status_code=400, detail="Rol invàlid")

    updates = {}
    if payload.username is not None:
        updates["username"] = payload.username
    if payload.role is not None:
        updates["role"] = payload.role
    if payload.active is not None:
        updates["active"] = payload.active
    if payload.institucio is not None:
        disponibles = config.get_institucions_disponibles()
        if payload.institucio not in disponibles:
            raise HTTPException(status_code=400, detail="Institució inexistent")
        updates["institucio"] = payload.institucio
    if payload.password:
        updates["password_hash"] = hash_password(payload.password)

    user = UserRepository.update(db, user, **updates)
    engine = get_engine_for_institucio(user.institucio)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    data_db = SessionLocal()
    try:
        display_name = ConfiguracioRepository.get(data_db, "institucio_display_name") or user.institucio
    finally:
        data_db.close()
    return UserResponse(
        id=user.id,
        username=user.username,
        institucio=user.institucio,
        institucio_display_name=display_name,
        role=user.role,
        active=user.active
    )


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_auth_db)
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    if user.role == "super_admin":
        raise HTTPException(status_code=403, detail="No es pot desactivar el superadmin")

    if current_user.role != "super_admin":
        if user.institucio != current_user.institucio:
            raise HTTPException(status_code=403, detail="No pots editar usuaris d'una altra institució")

    user = UserRepository.update(db, user, active=False)
    return {"success": True}


@router.delete("/{user_id}/hard")
def delete_user(
    user_id: int,
    current_user=Depends(require_super_admin),
    db: Session = Depends(get_auth_db)
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    if user.role == "super_admin":
        raise HTTPException(status_code=403, detail="No es pot eliminar el superadmin")

    UserRepository.delete(db, user)
    return {"success": True}


@router.get("/profile")
def get_profile(current_user=Depends(require_user)):
    idioma = config.institucio_data.get("idioma", "ca")
    display_name = config.institucio_data.get("institucio_display_name", current_user.institucio)
    return {
        "username": current_user.username,
        "role": current_user.role,
        "institucio": current_user.institucio,
        "institucio_display_name": display_name,
        "idioma": idioma
    }


@router.put("/profile/password")
def update_password(
    payload: PasswordUpdate,
    current_user=Depends(require_user),
    db: Session = Depends(get_auth_db)
):
    user = UserRepository.get_by_username(db, current_user.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuari no trobat")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contrasenya actual incorrecta")

    user = UserRepository.update(db, user, password_hash=hash_password(payload.new_password))
    return {"success": True}


@router.post("/profile/institucio")
def switch_institucio(
    payload: SwitchInstitucioRequest,
    response: Response,
    current_user=Depends(require_super_admin),
    db: Session = Depends(get_auth_db)
):
    disponibles = config.get_institucions_disponibles(include_inactive=True)
    if payload.institucio not in disponibles:
        raise HTTPException(status_code=400, detail="Institució inexistent")
    if not config.is_institucio_activa(payload.institucio):
        raise HTTPException(status_code=403, detail="Institució inactiva")

    token = create_access_token({
        "sub": current_user.username,
        "institucio": payload.institucio,
        "role": current_user.role
    })
    set_auth_cookie(response, token)
    return {"ok": True}
