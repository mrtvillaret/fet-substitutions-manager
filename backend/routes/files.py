"""
Routes per gestió de fitxers:
- Pujada de fitxer XML
- Llistat de PDFs generats
- Descàrrega de PDFs
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime, date, timedelta
import hashlib
import os
import shutil
from pathlib import Path

from auth_utils import get_current_user
from database import get_data_dir_for_institucio, get_data_db_session

router = APIRouter(prefix="/api/files", tags=["Fitxers"])


@router.post("/upload-xml")
async def upload_xml(
    file: UploadFile = File(...),
    data_inici: Optional[str] = Form(None),
    current_user=Depends(get_current_user)
):
    """
    Puja un fitxer XML de FET i el versiona a partir d'una data de vigència.

    `data_inici` (YYYY-MM-DD, per defecte avui) permet **preparar** l'horari d'un curs
    futur sense que passi a ser vigent immediatament: la versió anterior es tanca el dia
    abans, i el punter "actual" (`xml_horari_path`) només es mou si la nova versió ja és
    vigent avui.
    """
    try:
        # Validar que és un fitxer XML
        if not file.filename.endswith('.xml'):
            raise HTTPException(status_code=400, detail="El fitxer ha de ser XML")

        # Data de vigència de la nova versió
        if data_inici:
            try:
                vigent_des_de = date.fromisoformat(data_inici)
            except ValueError:
                raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")
        else:
            vigent_des_de = date.today()

        data_dir = str(get_data_dir_for_institucio(current_user.institucio))
        os.makedirs(data_dir, exist_ok=True)

        # Guardar fitxer
        file_path = os.path.join(data_dir, file.filename)

        with open(file_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Actualitzar configuració amb el nou path i versionar XML
        from repositories import ConfiguracioRepository, XMLVersionRepository

        with get_data_db_session(current_user.institucio) as db:
            # Calcular hash del fitxer
            sha = hashlib.sha256()
            with open(file_path, 'rb') as fh:
                for chunk in iter(lambda: fh.read(8192), b''):
                    sha.update(chunk)
            hash_contingut = sha.hexdigest()

            # Preparar directori d'històric
            history_dir = Path(data_dir) / "xml_history"
            history_dir.mkdir(parents=True, exist_ok=True)

            # Informació de l'XML actual (si existeix)
            current_version = XMLVersionRepository.get_current(db)

            # La cadena de versions ha de ser creixent: no es pot inserir una versió
            # que comenci abans (o el mateix dia) que la vigent.
            if current_version and vigent_des_de <= current_version.data_inici:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"La data de vigència ({vigent_des_de.isoformat()}) ha de ser posterior "
                        f"a la de la versió actual ({current_version.data_inici.isoformat()})"
                    )
                )

            previous_path = ConfiguracioRepository.get(db, 'xml_horari_path')

            if previous_path and not os.path.isabs(previous_path):
                previous_path = os.path.join(str(data_dir), previous_path)

            previous_hash = None
            if previous_path and os.path.exists(previous_path):
                sha_prev = hashlib.sha256()
                with open(previous_path, 'rb') as fh:
                    for chunk in iter(lambda: fh.read(8192), b''):
                        sha_prev.update(chunk)
                previous_hash = sha_prev.hexdigest()

            # Si és el mateix XML que l'actual, no crear nova versió
            if current_version and current_version.hash_contingut == hash_contingut:
                ConfiguracioRepository.set(
                    db, 'xml_horari_path', current_version.path,
                    'Path del fitxer XML de FET'
                )
                return {
                    "success": True,
                    "filename": file.filename,
                    "path": current_version.path,
                    "message": "XML idèntic a l'actual; no s'ha creat nova versió"
                }

            # Si no hi ha versions prèvies, crear versió inicial amb l'XML anterior (si existeix)
            if not current_version and previous_path and previous_hash:
                timestamp_prev = datetime.now().strftime("%Y%m%d_%H%M%S")
                history_prev_filename = f"horari_inicial_{timestamp_prev}.xml"
                history_prev_path = history_dir / history_prev_filename
                shutil.copy2(previous_path, history_prev_path)

                stored_prev_path = str(history_prev_path)
                try:
                    stored_prev_path = str(history_prev_path.relative_to(Path(data_dir)))
                except ValueError:
                    pass

                if previous_hash == hash_contingut:
                    XMLVersionRepository.create(
                        db,
                        path=stored_prev_path,
                        data_inici=date(2000, 1, 1),
                        hash_contingut=previous_hash
                    )

                    ConfiguracioRepository.set(
                        db, 'xml_horari_path', stored_prev_path,
                        'Path del fitxer XML de FET'
                    )

                    return {
                        "success": True,
                        "filename": file.filename,
                        "path": stored_prev_path,
                        "message": "XML idèntic a l'anterior; s'ha creat la versió inicial"
                    }

                XMLVersionRepository.create(
                    db,
                    path=stored_prev_path,
                    data_inici=date(2000, 1, 1),
                    data_fi=vigent_des_de - timedelta(days=1),
                    hash_contingut=previous_hash
                )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_filename = f"horari_{timestamp}.xml"
            history_path = history_dir / history_filename
            shutil.copy2(file_path, history_path)

            stored_path = str(history_path)
            try:
                stored_path = str(history_path.relative_to(Path(data_dir)))
            except ValueError:
                pass

            # Tancar versió anterior el dia abans que entri en vigor la nova
            if current_version:
                XMLVersionRepository.close_current(db, vigent_des_de - timedelta(days=1))

            XMLVersionRepository.create(
                db,
                path=stored_path,
                data_inici=vigent_des_de,
                hash_contingut=hash_contingut
            )

            # El punter "actual" només es mou si la nova versió ja és vigent avui.
            # Si es prepara un horari futur, l'XML vigent continua sent l'anterior.
            es_vigent_avui = vigent_des_de <= date.today()
            if es_vigent_avui:
                ConfiguracioRepository.set(
                    db, 'xml_horari_path', stored_path,
                    'Path del fitxer XML de FET'
                )

        # IMPORTANT: Invalidar cache del horari per forçar recàrrega del nou XML
        from helpers import invalidar_horari
        invalidar_horari(current_user.institucio)
        print(f"✅ Cache del horari invalidada - nou XML carregat: {file_path}")

        return {
            "success": True,
            "filename": file.filename,
            "path": stored_path,
            "data_inici": vigent_des_de.isoformat(),
            "vigent_avui": es_vigent_avui,
            "message": f"Fitxer '{file.filename}' pujat correctament"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error pujant fitxer: {str(e)}")


@router.post("/upload-logo")
async def upload_logo(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    """
    Puja un logo de la institució i el guarda al directori de dades
    """
    try:
        allowed_exts = {".png", ".jpg", ".jpeg"}
        filename = file.filename or ""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail="El logo ha de ser PNG o JPG")

        data_dir = str(get_data_dir_for_institucio(current_user.institucio))
        os.makedirs(data_dir, exist_ok=True)

        logo_filename = f"logo{ext}"
        file_path = os.path.join(data_dir, logo_filename)

        with open(file_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)

        from repositories import ConfiguracioRepository
        with get_data_db_session(current_user.institucio) as db:
            ConfiguracioRepository.set(
                db, "logo_path", file_path,
                "Path del logo de la institució"
            )

        return {
            "success": True,
            "filename": logo_filename,
            "path": file_path,
            "message": f"Logo '{logo_filename}' pujat correctament"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error pujant logo: {str(e)}")


@router.get("/logo")
async def get_logo(current_user=Depends(get_current_user)):
    """
    Retorna el logo configurat de la institució
    """
    try:
        data_dir = get_data_dir_for_institucio(current_user.institucio)
        logo_path = None
        try:
            from repositories import ConfiguracioRepository
            with get_data_db_session(current_user.institucio) as db:
                logo_path = ConfiguracioRepository.get(db, "logo_path")
        except Exception:
            logo_path = None

        if not logo_path:
            for ext in (".png", ".jpg", ".jpeg"):
                candidate = data_dir / f"logo{ext}"
                if candidate.exists():
                    logo_path = str(candidate)
                    break

        if not logo_path or not os.path.exists(logo_path):
            raise HTTPException(status_code=404, detail="Logo no trobat")

        media_type = "image/png"
        ext = os.path.splitext(logo_path)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"

        return FileResponse(
            path=logo_path,
            media_type=media_type,
            filename=os.path.basename(logo_path)
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error retornant logo: {str(e)}")

