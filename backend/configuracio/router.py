"""
Rutes de la configuració del centre (només admins; les URL de sempre): només
HTTP; la lògica, a services.py.
- /api/settings: configuració general del centre (idioma, nom visible,
  dates d'Estadístiques, últim professor) i /api/settings/idiomes
- /api/files/upload-logo i /api/files/logo: el logo del centre
"""

import os

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth.dependencies import require_admin
from configuracio import services
from configuracio.schemas import (
    ConfiguracioDesadaResponse,
    ConfiguracioResponse,
    IdiomesResponse,
    LogoDesatResponse,
    SettingsUpdate,
)
from dependencies import get_db

router = APIRouter()


@router.get(
    "/api/settings",
    tags=["Configuració General"],
    response_model=ConfiguracioResponse,
    response_model_exclude_unset=True,
)
def get_settings(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """
    Retorna tota la configuració del sistema
    """
    return services.configuracio_del_centre(db, current_user.institucio)


@router.put(
    "/api/settings",
    tags=["Configuració General"],
    response_model=ConfiguracioDesadaResponse,
    response_model_exclude_unset=True,
)
def update_settings(settings: SettingsUpdate, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    """
    Actualitza la configuració del sistema
    """
    changed = services.desa_configuracio(db, settings, current_user)
    return {"success": True, "message": f"Configuració actualitzada: {', '.join(changed)}", "changed": changed}


@router.get(
    "/api/settings/idiomes",
    tags=["Configuració General"],
    response_model=IdiomesResponse,
    response_model_exclude_unset=True,
)
def get_idiomes(db: Session = Depends(get_db)):
    """
    Retorna llista d'idiomes disponibles
    """
    return services.idiomes(db)


@router.post(
    "/api/files/upload-logo", tags=["Fitxers"], response_model=LogoDesatResponse, response_model_exclude_unset=True
)
def upload_logo(file: UploadFile = File(...), current_user=Depends(require_admin)):
    """
    Puja un logo de la institució i el guarda al directori de dades
    """
    file_path = services.desa_logo(current_user.institucio, file.filename or "", file.file.read())
    return {
        "success": True,
        "filename": "logo.png",
        "path": file_path,
        "message": "Logo 'logo.png' pujat correctament",
    }


@router.get("/api/files/logo", tags=["Fitxers"])
def get_logo(current_user=Depends(require_admin)):
    """
    Retorna el logo configurat de la institució
    """
    logo_path, media_type = services.logo_del_centre(current_user.institucio)
    return FileResponse(path=logo_path, media_type=media_type, filename=os.path.basename(logo_path))
