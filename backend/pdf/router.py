"""
Routes per generació i validació de PDFs:
- Validació abans de generar PDF
- PDF complet (substitucions + vigilàncies)
- PDF vigilàncies per un dia
- PDF vigilàncies per interval de dates
- PDF de professors disponibles

Només HTTP: els casos d'ús són a pdf/generacio.py i pdf/disponibles.py.
"""

import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from auth.dependencies import get_current_user
from dependencies import dia_de_la_peticio, get_db
from parametres import DataISO, data_iso
from pdf import disponibles, generacio
from pdf.domain import OpcionsPdf
from pdf.repositories import PreferenciesPdfRepository
from pdf.schemas import PDFPreferencesRequest
from serveis.dia import Dia
from substitucions.schemas import OrdreSubstitucions

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.get("/preferences")
def get_pdf_preferences(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retorna les preferències PDF desades per institució
    """
    return PreferenciesPdfRepository.get_all(db)


@router.put("/preferences")
def update_pdf_preferences(
    prefs: PDFPreferencesRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Desa les preferències PDF per institució
    """
    PreferenciesPdfRepository.update(db, prefs.model_dump())

    return {"success": True}


@router.get("/{data}/validacions")
def validar_abans_pdf(
    data: DataISO,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia_peticio: Dia = Depends(dia_de_la_peticio),
):
    """Conflictes i avisos d'un dia abans de generar el PDF (pdf/validacions.py)."""
    data_iso(data)
    return generacio.validacions(db, data, current_user.institucio, dia_peticio)


# Les rutes que generen PDF són síncrones: FastAPI les atén en un fil a part i
# el backend continua responent la resta de peticions mentre es generen.


def _resposta_pdf(export_dir: Path, filename: str, pdf_filename: str) -> FileResponse:
    """El PDF de `export_dir` (temporal), que s'esborra un cop enviat."""
    return FileResponse(
        str(export_dir / filename),
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f"attachment; filename={pdf_filename}"},
        background=BackgroundTask(shutil.rmtree, str(export_dir), True),
    )


def _marca_de_temps() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@router.get("/complete/{data}")
def generar_pdf_complet(
    data: DataISO,
    include_substitutions: bool = True,
    include_vigilancies: bool = True,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    show_conflicts: bool = True,
    blank_rows: bool = False,
    format: str = "hores",  # "hores" (una secció per hora) o "dia" (una taula per al dia)
    mida_lletra: Optional[float] = None,  # normal (1), gran (1.2) o molt gran (1.35); sense: veure _exportador
    ordre: OrdreSubstitucions = "curs",  # les substitucions dins de cada hora, com a la pantalla
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Genera PDF complet del dia amb substitucions i/o vigilàncies (TOTS els nivells) (SQLite)
    """
    if not include_substitutions and not include_vigilancies:
        raise HTTPException(status_code=400, detail="Cal incloure almenys una secció al PDF")
    data_iso(data)

    pdf = generacio.genera_pdf_complet(
        db,
        dia,
        data,
        current_user.institucio,
        OpcionsPdf(format, mida_lletra, compress, show_comments, show_hours),
        amb_substitucions=include_substitutions,
        amb_vigilancies=include_vigilancies,
        mostra_conflictes=show_conflicts,
        files_en_blanc=blank_rows,
        ordre=ordre,
    )
    if not pdf.nom:
        shutil.rmtree(pdf.directori, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
    return _resposta_pdf(pdf.directori, pdf.nom, f"complet_{data}_{_marca_de_temps()}.pdf")


# ===== PDF VIGILÀNCIES =====


@router.get("/vigilancies/interval")
def generar_pdf_interval(
    data_inici: DataISO,
    data_final: DataISO,
    nivells: str = "",
    include_weekends: bool = False,
    include_empty_days: bool = False,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    include_substitucions: bool = False,
    format: str = "hores",  # dins de cada dia: "hores" (una secció per hora) o "dia" (una taula)
    mida_lletra: Optional[float] = None,
    dia_per_pagina: bool = False,  # cada dia en una pàgina nova
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Genera PDF d'interval de dates per vigilàncies (SQLite)
    """
    pdf = generacio.genera_pdf_interval(
        db,
        current_user.institucio,
        data_inici,
        data_final,
        OpcionsPdf(format, mida_lletra, compress, show_comments, show_hours),
        nivells=nivells,
        amb_caps_de_setmana=include_weekends,
        amb_dies_buits=include_empty_days,
        amb_substitucions=include_substitucions,
        dia_per_pagina=dia_per_pagina,
    )
    if not pdf.nom:
        shutil.rmtree(pdf.directori, ignore_errors=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "No s'ha generat el fitxer PDF de l'interval"},
        )
    return _resposta_pdf(
        pdf.directori, pdf.nom, f"vigilancies_interval_{data_inici}_a_{data_final}_{_marca_de_temps()}.pdf"
    )


@router.get("/vigilancies/{data}")
def generar_pdf_vigilancies(
    data: DataISO,
    nivells: str = "",  # Comma-separated: "1-BATX,2-BATX"
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    include_substitucions: bool = False,
    format: str = "hores",  # "hores" (una secció per hora) o "dia" (una taula per al dia)
    mida_lletra: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Genera PDF de vigilàncies per un dia amb selecció de nivells (SQLite)
    """
    data_iso(data)  # valida la data (400 si no és vàlida)

    pdf = generacio.genera_pdf_vigilancies(
        db,
        dia,
        data,
        OpcionsPdf(format, mida_lletra, compress, show_comments, show_hours),
        nivells=nivells,
        amb_substitucions=include_substitucions,
    )
    if not pdf.nom:
        shutil.rmtree(pdf.directori, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
    return _resposta_pdf(pdf.directori, pdf.nom, f"vigilancies_{data}_{_marca_de_temps()}.pdf")


@router.post("/disponibles-tots-dies")
def generar_pdf_disponibles_tots_dies(
    data_inici: Optional[DataISO] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Genera un PDF amb professors disponibles per N dies laborables consecutius,
    un full per dia. Comença des de data_inici (o avui si no s'especifica).
    """
    # Data d'inici: la proporcionada (la pantalla hi posa la del calendari) o avui
    primer_dia = data_iso(data_inici) if data_inici else date.today()

    temp_dir = Path(tempfile.mkdtemp())
    pdf_filename = f"disponibles_tots_dies_{_marca_de_temps()}.pdf"
    try:
        disponibles.genera_pdf_disponibles(db, current_user.institucio, primer_dia, str(temp_dir / pdf_filename))
    except disponibles.DiaNoGenerat as error:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"No s'ha pogut generar el PDF de disponibles per al dia {error.dia}"},
        )
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return _resposta_pdf(temp_dir, pdf_filename, pdf_filename)
