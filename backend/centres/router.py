"""
Rutes dels centres (institucions): només HTTP; la lògica, a services.py.
Llistar-los (admins: només el seu) i, només el superadmin, crear-los,
canviar-ne el nom visible, activar-los o desactivar-los i esborrar-los. Les
URL de sempre, /api/settings/institucions.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import require_admin, require_super_admin
from centres import services
from centres.schemas import (
    CentreCreatResponse,
    CentreEsborratResponse,
    CentresResponse,
    EstatCentreResponse,
    InstitucioCreate,
    InstitucioDelete,
    InstitucioStatus,
    InstitucioUpdate,
    NomVisibleResponse,
)
from database import get_auth_db

router = APIRouter(prefix="/api/settings", tags=["Configuració General"])


@router.get("/institucions", response_model=CentresResponse, response_model_exclude_unset=True)
def get_institucions(current_user=Depends(require_admin)):
    """
    Retorna llista d'institucions disponibles a data/
    """
    return services.llista(current_user)


@router.post("/institucions", response_model=CentreCreatResponse, response_model_exclude_unset=True)
def create_institucio(payload: InstitucioCreate, current_user=Depends(require_super_admin)):
    """
    Crea una nova institució (directori i BD buida)
    """
    services.crea(payload.nom, payload.display_name)
    return {"success": True, "institucio": payload.nom}


@router.put("/institucions/{slug}", response_model=NomVisibleResponse, response_model_exclude_unset=True)
def update_institucio(slug: str, payload: InstitucioUpdate, current_user=Depends(require_super_admin)):
    """
    Actualitza el nom visible d'una institució
    """
    services.canvia_nom_visible(slug, payload.display_name)
    return {"success": True, "slug": slug, "display_name": payload.display_name}


@router.put("/institucions/{slug}/status", response_model=EstatCentreResponse, response_model_exclude_unset=True)
def update_institucio_status(
    slug: str,
    payload: InstitucioStatus,
    current_user=Depends(require_super_admin),
):
    """
    Activa o desactiva una institució
    """
    services.canvia_estat(slug, payload.active)
    return {"success": True, "slug": slug, "active": payload.active}


@router.delete("/institucions/{slug}", response_model=CentreEsborratResponse, response_model_exclude_unset=True)
def delete_institucio(
    slug: str,
    payload: InstitucioDelete,
    current_user=Depends(require_super_admin),
    auth_db: Session = Depends(get_auth_db),
):
    """
    Desactiva o elimina una institució amb confirmació forta
    """
    mode = services.esborra(auth_db, slug, payload.mode, payload.confirm)
    return {"success": True, "slug": slug, "mode": mode}
