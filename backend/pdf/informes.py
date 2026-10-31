"""
Endpoints per generar informes PDF de direcció i per professor. Els càlculs
són a pdf/services.py; el dibuix, a informe_direccio.py i informe_professors.py.
"""

import shutil
import tempfile

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from auth.dependencies import require_admin
from database import get_data_dir_for_institucio
from dependencies import get_db
from noms import NomNet
from pdf import services
from pdf.domain import SenseProfessors
from pdf.informe_direccio import generar_informe_pdf
from pdf.informe_professors import generar_informe_professors_pdf
from recomptes.services import valida_interval
from routes.parametres import DataISO, HoresTriades

router = APIRouter(prefix="/api/informes", tags=["informes"])


def _fitxer_temporal(pdf_path: str, temp_dir: str, filename: str) -> FileResponse:
    """El PDF es genera en un directori temporal per petició (no es desa al
    servidor) i s'esborra un cop enviada la resposta."""
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
    )


def _hores_dels_informes(db: Session, institucio: str, data_inici: str, data_final: str, hores) -> tuple:
    """(les hores de les taules, les triades): amb el filtre per hores, les
    triades en l'ordre de l'horari; sense, les de l'horari de l'inici del
    període, i cap de triada."""
    if hores:
        triades = services.hores_triades_en_ordre(db, institucio, data_inici, data_final, hores)
        return triades, triades
    return services.hores_xml(institucio, data_inici), None


@router.get("/direccio")
def informe_direccio(
    hores: HoresTriades,
    data_inici: DataISO = Query(...),
    data_final: DataISO = Query(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    valida_interval(data_inici, data_final)
    institucio = current_user.institucio
    nom_centre = services.nom_centre(db, institucio)
    lang = services.idioma(db)
    hores_xml, triades = _hores_dels_informes(db, institucio, data_inici, data_final, hores)
    dades = services.dades_direccio(db, data_inici, data_final, hores_xml, lang, hores)
    temp_dir = tempfile.mkdtemp()
    logo_path = get_data_dir_for_institucio(institucio) / "logo.png"
    pdf_path = generar_informe_pdf(
        dades=dades,
        nom_centre=nom_centre,
        data_inici=data_inici,
        data_final=data_final,
        export_dir=temp_dir,
        logo_path=str(logo_path) if logo_path.exists() else None,
        lang=lang,
        hores_triades=triades,
    )
    return _fitxer_temporal(pdf_path, temp_dir, f"informe_direccio_{data_inici}_{data_final}.pdf")


def _dma(data: str) -> str:
    """2026-04-20 → 20/04/2026"""
    any_, mes, dia = data.split("-")
    return f"{dia}/{mes}/{any_}"


@router.get("/professor")
def informe_professor(
    hores: HoresTriades,
    data_inici: DataISO = Query(...),
    data_final: DataISO = Query(...),
    professor: NomNet = None,
    mostrar_taules: bool = Query(default=False),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    valida_interval(data_inici, data_final)
    institucio = current_user.institucio
    nom_centre = services.nom_centre(db, institucio)
    lang = services.idioma(db)
    hores_xml, triades = _hores_dels_informes(db, institucio, data_inici, data_final, hores)
    professors_data = services.dades_professors(db, data_inici, data_final, professor, hores)
    if not professors_data:
        # Només hi surt qui té absències o substitucions fetes a l'interval
        periode = f"entre el {_dma(data_inici)} i el {_dma(data_final)}"
        if hores:
            periode += " a les hores triades"
        if professor:
            missatge = f"{professor} no té absències ni substitucions fetes {periode}"
        else:
            missatge = f"Cap professor no té absències ni substitucions fetes {periode}"
        raise SenseProfessors(missatge, codi="cap_professor")

    temp_dir = tempfile.mkdtemp()
    pdf_path = generar_informe_professors_pdf(
        professors_data=professors_data,
        nom_centre=nom_centre,
        data_inici=data_inici,
        data_final=data_final,
        hores_xml=hores_xml,
        mostrar_taules=mostrar_taules,
        export_dir=temp_dir,
        lang=lang,
        hores_triades=triades,
    )
    nom_fitxer = (
        f"informe_{professor}_{data_inici}_{data_final}.pdf"
        if professor
        else f"informe_professors_{data_inici}_{data_final}.pdf"
    )
    return _fitxer_temporal(pdf_path, temp_dir, nom_fitxer)


@router.get("/professors-llista")
def llista_professors(
    hores: HoresTriades,
    data_inici: DataISO = Query(...),
    data_final: DataISO = Query(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retorna la llista de professors amb activitat al període"""
    valida_interval(data_inici, data_final)
    return {"professors": services.professors_amb_activitat(db, data_inici, data_final, hores)}
