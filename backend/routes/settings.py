"""
Routes per configuració general del sistema
"""

import logging
import os
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from auth_utils import require_admin, require_super_admin
from config.constants import NO_SUBST
from config.settings import config
from database import get_auth_db, get_data_dir_for_institucio, get_engine_for_institucio
from dependencies import get_db
from models import XMLVersion
from repositories import ConfiguracioRepository, UserRepository, XMLVersionRepository
from routes.parametres import data_iso
from serveis.dia import Dia

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["Configuració General"])


class SettingsUpdate(BaseModel):
    """Model per actualitzar configuració"""
    institucio: Optional[str] = None
    idioma: Optional[str] = None
    data_inici_estadistiques: Optional[str] = None
    data_final_estadistiques: Optional[str] = None
    ultim_professor_subs: Optional[str] = None
    institucio_display_name: Optional[str] = None


class XMLVersionUpdate(BaseModel):
    data_inici: Optional[str] = None   # la data de fi es calcula (no s'accepta)


@router.get("")
async def get_settings(db: Session = Depends(get_db)):
    """
    Retorna tota la configuració del sistema
    """
    config_db = ConfiguracioRepository.get_all_as_dict(db)
    # Buit ('') = sense límit ("Tots"). None (mai desat) → també buit.
    ultim_professor_subs = config_db.get('ultim_professor_subs') or ""
    from helpers import _get_institucio_actual
    institucio = _get_institucio_actual()
    idioma_institucio = config_db.get("idioma") or config.global_data.get("idioma", "ca")
    display_name = config_db.get("institucio_display_name") or institucio
    xml_path = Dia.avui(institucio).xml_path   # la versió vigent avui
    xml_missing = not xml_path or not os.path.exists(xml_path)

    return {
        # Institució de la petició (la de l'usuari)
        "institucio": institucio,
        "idioma": idioma_institucio,

        # Configuració per institució (SQLite)
        "xml_horari_path": config_db.get("xml_horari_path"),
        "data_inici_estadistiques": config_db.get("data_inici_estadistiques"),
        "data_final_estadistiques": config_db.get("data_final_estadistiques"),
        "logo_path": config_db.get("logo_path"),
        "institucio_display_name": display_name,

        # Configuració per institució (SQLite)
        "ultim_professor_subs": ultim_professor_subs,

        # Paths computats
        "data_dir": str(get_data_dir_for_institucio(institucio)),
        "xml_missing": xml_missing,

        # Llistes de no substituïbles
        "no_substituir": list(NO_SUBST),
    }


@router.put("")
async def update_settings(
    settings: SettingsUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Actualitza la configuració del sistema
    """
    changed = []

    # Flag per saber si cal invalidar horari
    invalidar_cache = False

    # Actualitzar configuració global
    # La institució per defecte del servidor només la pot canviar el
    # superadmin. El frontend envia sempre aquest camp: per a la resta
    # s'ignora (no decideix res de les peticions, que van per usuari).
    if settings.institucio is not None and current_user.role == "super_admin" \
            and settings.institucio != config.global_data.get("institucio"):
        config.global_data["institucio"] = settings.institucio
        config.save_global()
        config.load_institucio()  # Recarregar config de la nova institució
        changed.append(f"Institucio → {settings.institucio}")
        invalidar_cache = True  # Canvi d'institució requereix recarregar horari

    if settings.idioma is not None:
        ConfiguracioRepository.set(
            db,
            'idioma',
            settings.idioma,
            tipus='string',
            descripcio='Idioma per defecte de la institució'
        )
        changed.append(f"Idioma → {settings.idioma}")

    # Les rutes de l'XML i dels PDF no es poden canviar d'aquí: l'XML es puja
    # (/api/files/upload-xml) i les carpetes són sempre les del centre. Una ruta
    # escrita a mà podia apuntar als fitxers d'un altre centre.

    if settings.institucio_display_name is not None:
        if current_user.role != "super_admin":
            raise HTTPException(status_code=403, detail="Només el superadmin pot editar el nom visible")
        ConfiguracioRepository.set(
            db,
            'institucio_display_name',
            settings.institucio_display_name,
            tipus='string',
            descripcio='Nom visible de la institució'
        )
        changed.append(f"Nom visible → {settings.institucio_display_name}")

    if settings.data_inici_estadistiques is not None:
        ConfiguracioRepository.set(
            db,
            'data_inici_estadistiques',
            settings.data_inici_estadistiques,
            tipus='string',
            descripcio='Data d\'inici per estadístiques'
        )
        changed.append(f"Data estadístiques → {settings.data_inici_estadistiques}")

    if settings.data_final_estadistiques is not None:
        ConfiguracioRepository.set(
            db,
            'data_final_estadistiques',
            settings.data_final_estadistiques,
            tipus='string',
            descripcio='Data de fi per estadístiques'
        )
        changed.append(f"Data fi estadístiques → {settings.data_final_estadistiques}")

    # Actualitzar configuració per institució (SQLite)
    if settings.ultim_professor_subs is not None:
        ConfiguracioRepository.set(
            db,
            'ultim_professor_subs',
            settings.ultim_professor_subs,
            tipus='string',
            descripcio='Últim professor a considerar per substitucions (limita la llista de professors disponibles)'
        )
        changed.append(f"Últim professor → {settings.ultim_professor_subs}")
        invalidar_cache = True  # Canvi de límit de professors requereix recarregar horari

    # Recarregar configuració d'institució si s'ha modificat
    if any(s is not None for s in [settings.idioma, settings.data_inici_estadistiques, settings.data_final_estadistiques,
                                   settings.ultim_professor_subs]):
        config.load_institucio()

    # Invalidar cache del horari si s'ha canviat la institució o el límit de professors
    if invalidar_cache:
        from helpers import invalidar_horari
        invalidar_horari()
        log.debug("✅ Cache del horari invalidada - configuració canviada")

    return {
        "success": True,
        "message": f"Configuració actualitzada: {', '.join(changed)}",
        "changed": changed
    }


def _get_institucio_display_name(slug: str) -> str:
    from database import get_engine_for_institucio
    engine = get_engine_for_institucio(slug)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        name = ConfiguracioRepository.get(db, "institucio_display_name")
        return name or slug
    finally:
        db.close()


@router.get("/institucions")
async def get_institucions(current_user=Depends(require_admin)):
    """
    Retorna llista d'institucions disponibles a data/
    """
    institucions = config.get_institucions_disponibles(
        include_inactive=current_user.role == "super_admin"
    )
    if current_user.role != "super_admin":
        institucions = [inst for inst in institucions if inst == current_user.institucio]

    institucions_info = []
    for inst in institucions:
        institucions_info.append({
            "slug": inst,
            "display_name": _get_institucio_display_name(inst),
            "active": config.is_institucio_activa(inst)
        })
    return {
        "institucions": institucions_info,
        "actual": current_user.institucio
    }


class InstitucioCreate(BaseModel):
    nom: str
    display_name: Optional[str] = None


@router.post("/institucions")
async def create_institucio(
    payload: InstitucioCreate,
    current_user=Depends(require_super_admin)
):
    """
    Crea una nova institució (directori i BD buida)
    """
    from database import get_data_dir_for_institucio
    data_dir = get_data_dir_for_institucio(payload.nom)
    if data_dir.exists():
        raise HTTPException(status_code=409, detail="La institució ja existeix")

    get_engine_for_institucio(payload.nom)
    if payload.display_name:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine_for_institucio(payload.nom))
        db = SessionLocal()
        try:
            ConfiguracioRepository.set(
                db,
                'institucio_display_name',
                payload.display_name,
                tipus='string',
                descripcio='Nom visible de la institució'
            )
        finally:
            db.close()
    return {"success": True, "institucio": payload.nom}


class InstitucioUpdate(BaseModel):
    display_name: str


@router.put("/institucions/{slug}")
async def update_institucio(
    slug: str,
    payload: InstitucioUpdate,
    current_user=Depends(require_super_admin)
):
    """
    Actualitza el nom visible d'una institució
    """
    disponibles = config.get_institucions_disponibles()
    if slug not in disponibles:
        raise HTTPException(status_code=404, detail="Institució no trobada")

    from database import get_engine_for_institucio
    engine = get_engine_for_institucio(slug)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        ConfiguracioRepository.set(
            db,
            'institucio_display_name',
            payload.display_name,
            tipus='string',
            descripcio='Nom visible de la institució'
        )
    finally:
        db.close()

    return {"success": True, "slug": slug, "display_name": payload.display_name}


class InstitucioStatus(BaseModel):
    active: bool


@router.put("/institucions/{slug}/status")
async def update_institucio_status(
    slug: str,
    payload: InstitucioStatus,
    current_user=Depends(require_super_admin),
    auth_db: Session = Depends(get_auth_db)
):
    """
    Activa o desactiva una institució
    """
    disponibles = config.get_institucions_disponibles(include_inactive=True)
    if slug not in disponibles:
        raise HTTPException(status_code=404, detail="Institució no trobada")

    config.set_institucio_activa(slug, payload.active)

    # Desactivar usuaris si es desactiva la institució
    if not payload.active:
        for user in UserRepository.list_by_institucio(auth_db, slug):
            if user.role != "super_admin":
                UserRepository.update(auth_db, user, active=False)

    return {"success": True, "slug": slug, "active": payload.active}


class InstitucioDelete(BaseModel):
    mode: str = "soft"  # soft | hard
    confirm: str


@router.delete("/institucions/{slug}")
async def delete_institucio(
    slug: str,
    payload: InstitucioDelete,
    current_user=Depends(require_super_admin),
    auth_db: Session = Depends(get_auth_db)
):
    """
    Desactiva o elimina una institució amb confirmació forta
    """
    disponibles = config.get_institucions_disponibles(include_inactive=True)
    if slug not in disponibles:
        raise HTTPException(status_code=404, detail="Institució no trobada")

    mode = payload.mode or "soft"
    if mode not in ("soft", "hard"):
        raise HTTPException(status_code=400, detail="Mode invàlid")

    if mode == "hard":
        expected = f"ELIMINA {slug}"
        if payload.confirm != expected:
            raise HTTPException(status_code=400, detail="Confirmació incorrecta")
    else:
        if payload.confirm != slug:
            raise HTTPException(status_code=400, detail="Confirmació incorrecta")

    if mode == "soft":
        config.set_institucio_activa(slug, False)
        for user in UserRepository.list_by_institucio(auth_db, slug):
            if user.role != "super_admin":
                UserRepository.update(auth_db, user, active=False)
    else:
        data_dir = config._institucions_base_path() / slug
        if data_dir.exists():
            shutil.rmtree(data_dir)
        for user in UserRepository.list_by_institucio(auth_db, slug):
            if user.role != "super_admin":
                auth_db.delete(user)
        auth_db.commit()

    return {"success": True, "slug": slug, "mode": mode}


@router.get("/idiomes")
async def get_idiomes(db: Session = Depends(get_db)):
    """
    Retorna llista d'idiomes disponibles
    """
    return {
        "idiomes": [
            {"code": "ca", "name": "Català"},
            {"code": "es", "name": "Español"},
            {"code": "en", "name": "English"},
            {"code": "it", "name": "Italiano"}
        ],
        "actual": ConfiguracioRepository.get(db, "idioma") or config.global_data.get("idioma", "ca")
    }


@router.get("/xml-versions")
async def get_xml_versions(db: Session = Depends(get_db)):
    """
    Retorna l'històric d'XMLs per la institució actual
    """
    versions = XMLVersionRepository.list_all(db)
    return {
        "versions": [
            {
                "id": v.id,
                "path": v.path,
                "data_inici": v.data_inici.isoformat(),
                "data_fi": v.data_fi.isoformat() if v.data_fi else None,
                "hash_contingut": v.hash_contingut
            }
            for v in versions
        ]
    }


@router.put("/xml-versions/{version_id}")
async def update_xml_version(
    version_id: int,
    payload: XMLVersionUpdate,
    db: Session = Depends(get_db)
):
    """
    Canvia quan comença una versió d'XML. Les dates de fi es recalculen totes
    (el dia abans que comenci la següent): no es poden posar a mà.
    """
    version = db.query(XMLVersion).filter(XMLVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Versió XML no trobada")
    if not payload.data_inici:
        return {"success": True}

    data_inici = data_iso(payload.data_inici)
    if db.query(XMLVersion).filter(XMLVersion.id != version_id, XMLVersion.data_inici == data_inici).first():
        raise HTTPException(status_code=400, detail="Ja hi ha una altra versió d'XML que comença aquest dia")

    version.data_inici = data_inici
    XMLVersionRepository.encadena(db)
    db.commit()
    return {"success": True}


@router.delete("/xml-versions/{version_id}")
async def delete_xml_version(version_id: int, db: Session = Depends(get_db)):
    """
    Elimina una versió d'XML; les altres s'encadenen de nou (sense forats).
    """
    version = db.query(XMLVersion).filter(XMLVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Versió XML no trobada")
    db.delete(version)
    XMLVersionRepository.encadena(db)
    db.commit()
    return {"success": True}
