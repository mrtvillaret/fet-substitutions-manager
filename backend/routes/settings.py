"""
Routes per configuració general del sistema
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, sessionmaker
from typing import Dict, List, Any, Optional
from datetime import date
from pydantic import BaseModel
import json

from config.settings import config
import os
from auth_utils import require_admin, require_super_admin, get_current_user
from database import get_auth_db, get_engine_for_institucio
from repositories import UserRepository
import shutil
from config.constants import NO_SUBST
from dependencies import get_db
from repositories import ConfiguracioRepository, XMLVersionRepository, parse_date
from models import XMLVersion

router = APIRouter(prefix="/api/settings", tags=["Configuració General"])


class SettingsUpdate(BaseModel):
    """Model per actualitzar configuració"""
    institucio: Optional[str] = None
    idioma: Optional[str] = None
    xml_horari_path: Optional[str] = None
    export_dir: Optional[str] = None
    data_inici_estadistiques: Optional[str] = None
    data_final_estadistiques: Optional[str] = None
    ultim_professor_subs: Optional[str] = None
    institucio_display_name: Optional[str] = None


class XMLVersionUpdate(BaseModel):
    data_inici: Optional[str] = None
    data_fi: Optional[str] = None


class PDFPreferencesUpdate(BaseModel):
    substitucions: Optional[Dict[str, Any]] = None
    vigilancies: Optional[Dict[str, Any]] = None
    vigilancies_interval: Optional[Dict[str, Any]] = None


@router.get("")
async def get_settings(db: Session = Depends(get_db)):
    """
    Retorna tota la configuració del sistema
    """
    try:
        config_db = ConfiguracioRepository.get_all_as_dict(db)
        ultim_professor_subs = config_db.get('ultim_professor_subs') or ""
        idioma_institucio = config_db.get("idioma") or config.global_data.get("idioma", "ca")
        display_name = config_db.get("institucio_display_name") or config.global_data.get("institucio")
        from helpers import get_xml_path_for_date
        xml_path = get_xml_path_for_date(config.global_data.get("institucio"))
        xml_missing = not xml_path or not os.path.exists(xml_path)

        return {
            # Configuració global
            "institucio": config.global_data.get("institucio"),
            "idioma": idioma_institucio,

            # Configuració per institució (SQLite)
            "xml_horari_path": config_db.get("xml_horari_path"),
            "export_dir": config_db.get("export_dir", "exports"),
            "data_inici_estadistiques": config_db.get("data_inici_estadistiques"),
            "data_final_estadistiques": config_db.get("data_final_estadistiques"),
            "logo_path": config_db.get("logo_path"),
            "institucio_display_name": display_name,

            # Configuració per institució (SQLite)
            "ultim_professor_subs": ultim_professor_subs,

            # Paths computats
            "data_dir": config.data_dir,
            "xml_missing": xml_missing,

            # Llistes de no substituïbles
            "no_substituir": list(NO_SUBST),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir configuració: {str(e)}")


@router.put("")
async def update_settings(
    settings: SettingsUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Actualitza la configuració del sistema
    """
    try:
        changed = []

        # Flag per saber si cal invalidar horari
        invalidar_cache = False

        # Actualitzar configuració global
        if settings.institucio is not None:
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

        # Actualitzar configuració per institució (SQLite)
        if settings.xml_horari_path is not None:
            ConfiguracioRepository.set(
                db,
                'xml_horari_path',
                settings.xml_horari_path,
                tipus='string',
                descripcio='Path del fitxer XML de FET'
            )
            changed.append(f"XML → {settings.xml_horari_path}")
            invalidar_cache = True  # Canvi d'XML requereix recarregar horari

        if settings.export_dir is not None:
            ConfiguracioRepository.set(
                db,
                'export_dir',
                settings.export_dir,
                tipus='string',
                descripcio='Directori d\'exportació PDFs'
            )
            changed.append(f"Export dir → {settings.export_dir}")

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
        if any(s is not None for s in [settings.idioma, settings.xml_horari_path, settings.export_dir,
                                       settings.data_inici_estadistiques, settings.data_final_estadistiques,
                                       settings.ultim_professor_subs]):
            config.load_institucio()

        # Invalidar cache del horari si s'ha canviat XML, institució o límit de professors
        if invalidar_cache:
            from helpers import invalidar_horari
            invalidar_horari()
            print(f"✅ Cache del horari invalidada - configuració canviada")

        return {
            "success": True,
            "message": f"Configuració actualitzada: {', '.join(changed)}",
            "changed": changed
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar configuració: {str(e)}")


@router.get("/pdf-preferences")
async def get_pdf_preferences(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna les preferències PDF desades per institució
    """
    try:
        prefs_subs = ConfiguracioRepository.get(db, "pdf_prefs_substitucions")
        prefs_vigs = ConfiguracioRepository.get(db, "pdf_prefs_vigilancies")
        prefs_vigs_interval = ConfiguracioRepository.get(db, "pdf_prefs_vigilancies_interval")

        return {
            "substitucions": json.loads(prefs_subs) if prefs_subs else None,
            "vigilancies": json.loads(prefs_vigs) if prefs_vigs else None,
            "vigilancies_interval": json.loads(prefs_vigs_interval) if prefs_vigs_interval else None
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir preferències PDF: {str(e)}")


@router.put("/pdf-preferences")
async def update_pdf_preferences(
    prefs: PDFPreferencesUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Desa les preferències PDF per institució
    """
    try:
        if prefs.substitucions is not None:
            ConfiguracioRepository.set(
                db,
                "pdf_prefs_substitucions",
                json.dumps(prefs.substitucions),
                tipus="json",
                descripcio="Preferències PDF de substitucions"
            )
        if prefs.vigilancies is not None:
            ConfiguracioRepository.set(
                db,
                "pdf_prefs_vigilancies",
                json.dumps(prefs.vigilancies),
                tipus="json",
                descripcio="Preferències PDF de vigilàncies"
            )
        if prefs.vigilancies_interval is not None:
            ConfiguracioRepository.set(
                db,
                "pdf_prefs_vigilancies_interval",
                json.dumps(prefs.vigilancies_interval),
                tipus="json",
                descripcio="Preferències PDF interval de vigilàncies"
            )

        return {"success": True}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en desar preferències PDF: {str(e)}")


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
    try:
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
            "actual": config.global_data.get("institucio")
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir institucions: {str(e)}")


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
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear institució: {str(e)}")


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
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar institució: {str(e)}")


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
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar estat: {str(e)}")


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
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar institució: {str(e)}")


@router.get("/idiomes")
async def get_idiomes():
    """
    Retorna llista d'idiomes disponibles
    """
    return {
        "idiomes": [
            {"code": "ca", "name": "Català"},
            {"code": "es", "name": "Español"},
            {"code": "en", "name": "English"}
        ],
        "actual": config.institucio_data.get("idioma", config.global_data.get("idioma", "ca"))
    }


@router.get("/xml-versions")
async def get_xml_versions(db: Session = Depends(get_db)):
    """
    Retorna l'històric d'XMLs per la institució actual
    """
    try:
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir versions XML: {str(e)}")


@router.put("/xml-versions/{version_id}")
async def update_xml_version(
    version_id: int,
    payload: XMLVersionUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualitza les dates d'una versió d'XML
    """
    try:
        version = db.query(XMLVersion).filter(XMLVersion.id == version_id).first()
        if not version:
            raise HTTPException(status_code=404, detail="Versió XML no trobada")

        data_inici = parse_date(payload.data_inici) if payload.data_inici else version.data_inici
        data_fi = parse_date(payload.data_fi) if payload.data_fi else None

        if data_fi and data_fi < data_inici:
            raise HTTPException(status_code=400, detail="La data final no pot ser anterior a la inicial")

        # Evitar solapaments
        versions = XMLVersionRepository.list_all(db)
        for other in versions:
            if other.id == version_id:
                continue
            other_start = other.data_inici
            other_end = other.data_fi
            end = data_fi or date(2999, 12, 31)
            other_end_cmp = other_end or date(2999, 12, 31)
            if not (end < other_start or data_inici > other_end_cmp):
                raise HTTPException(status_code=400, detail="Solapament amb una altra versió d'XML")

        # Evitar dues versions obertes
        if data_fi is None:
            for other in versions:
                if other.id != version_id and other.data_fi is None:
                    raise HTTPException(status_code=400, detail="Ja hi ha una versió actual oberta")

        version.data_inici = data_inici
        version.data_fi = data_fi
        db.commit()

        if data_fi is None:
            ConfiguracioRepository.set(
                db, 'xml_horari_path', version.path,
                tipus='string',
                descripcio='Path del fitxer XML de FET'
            )

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar versió XML: {str(e)}")


@router.delete("/xml-versions/{version_id}")
async def delete_xml_version(version_id: int, db: Session = Depends(get_db)):
    """
    Elimina una versió d'XML (si és l'actual, obre la versió anterior si existeix)
    """
    try:
        versions = XMLVersionRepository.list_all(db)
        version = next((v for v in versions if v.id == version_id), None)
        if not version:
            raise HTTPException(status_code=404, detail="Versió XML no trobada")

        deleting_open = version.data_fi is None
        db.delete(version)
        db.commit()

        if deleting_open:
            remaining = XMLVersionRepository.list_all(db)
            remaining_sorted = sorted(remaining, key=lambda v: v.data_inici or date.min)
            previous = next((v for v in reversed(remaining_sorted) if v.data_inici and v.data_inici < version.data_inici), None)

            if previous:
                previous.data_fi = None
                db.commit()
                ConfiguracioRepository.set(
                    db, 'xml_horari_path', previous.path,
                    tipus='string',
                    descripcio='Path del fitxer XML de FET'
                )
            else:
                ConfiguracioRepository.set(
                    db, 'xml_horari_path', '',
                    tipus='string',
                    descripcio='Path del fitxer XML de FET'
                )

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar versió XML: {str(e)}")
