"""
Routes per generació i validació de PDFs:
- Validació abans de generar PDF
- PDF complet (substitucions + vigilàncies)
- PDF vigilàncies per un dia
- PDF vigilàncies per interval de dates
- PDF de professors disponibles

Només HTTP: els casos d'ús són a pdf/generacio.py i pdf/disponibles.py.
"""

from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

import rellotge
from auth.dependencies import get_current_user
from dependencies import dia_de_la_peticio, get_db, get_db_lectura
from horari.domain import Dia
from parametres import Data, DataTextual
from pdf import disponibles, generacio, services
from pdf.domain import OpcionsPdf, directori_temporal, esborra_directori
from pdf.schemas import (
    DesatResponse,
    PDFPreferencesRequest,
    PDFPreferencesResponse,
    ValidacionsPdfResponse,
    VigilanciesSenseNivellResponse,
)
from substitucions.schemas import OrdreSubstitucions

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.get("/preferences", response_model=PDFPreferencesResponse)
def get_pdf_preferences(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retorna les preferències PDF desades per institució
    """
    return services.preferencies(db)


@router.put("/preferences", response_model=DesatResponse)
def update_pdf_preferences(
    prefs: PDFPreferencesRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Desa les preferències PDF per institució
    """
    services.desa_preferencies(db, prefs.model_dump())

    return {"success": True}


@router.get("/{data}/validacions", response_model=ValidacionsPdfResponse)
def validar_abans_pdf(
    include_substitutions: bool = True,  # les seccions del PDF complet, com a /complete
    include_vigilancies: bool = True,
    nivells: str | None = None,  # la tria del PDF de vigilàncies, com a /vigilancies/{data}
    inclou_sense_nivell: bool | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia_peticio: Dia = Depends(dia_de_la_peticio),
):
    """Conflictes i avisos d'un dia abans de generar el PDF (pdf/validacions.py):
    els que imprimirà el PDF complet amb aquestes seccions (sense seccions, tots)
    o, amb una tria de nivells, els problemes de vigilàncies del PDF de vigilàncies."""
    return generacio.validacions(
        db,
        dia_peticio,
        amb_substitucions=include_substitutions,
        amb_vigilancies=include_vigilancies,
        nivells=nivells,
        inclou_sense_nivell=inclou_sense_nivell,
    )


# Les rutes que generen PDF són síncrones: FastAPI les atén en un fil a part i
# el backend continua responent la resta de peticions mentre es generen.


def _resposta_pdf(export_dir: Path, filename: str, pdf_filename: str) -> FileResponse:
    """El PDF de `export_dir` (temporal), que s'esborra un cop enviat."""
    return FileResponse(
        str(export_dir / filename),
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f"attachment; filename={pdf_filename}"},
        background=BackgroundTask(esborra_directori, export_dir),
    )


def _marca_de_temps() -> str:
    return rellotge.ara().strftime("%Y%m%d_%H%M%S")


@router.get("/complete/{data}")
def generar_pdf_complet(
    include_substitutions: bool = True,
    include_vigilancies: bool = True,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    show_conflicts: bool = True,
    blank_rows: bool = False,
    format: str = "hores",  # "hores" (una secció per hora) o "dia" (una taula per al dia)
    mida_lletra: float | None = None,  # normal (1), gran (1.2) o molt gran (1.35); sense: veure _exportador
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

    pdf = generacio.genera_pdf_complet(
        db,
        dia,
        OpcionsPdf(format, mida_lletra, compress, show_comments, show_hours),
        amb_substitucions=include_substitutions,
        amb_vigilancies=include_vigilancies,
        mostra_conflictes=show_conflicts,
        files_en_blanc=blank_rows,
        ordre=ordre,
    )
    if not pdf.nom:
        esborra_directori(pdf.directori)
        raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
    return _resposta_pdf(pdf.directori, pdf.nom, f"complet_{dia.iso}_{_marca_de_temps()}.pdf")


# ===== PDF VIGILÀNCIES =====


@router.get("/vigilancies/comptes-sense-nivell", response_model=VigilanciesSenseNivellResponse)
def comptar_vigilancies_sense_nivell(
    data_inici: Data,
    data_final: Data,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Recompte per mostrar l'opció «Sense nivell» al selector del PDF."""
    return {"sense_nivell": services.compta_vigilancies_sense_nivell(db, data_inici, data_final)}


@router.get("/vigilancies/interval")
def generar_pdf_interval(
    data_inici: Data,
    data_final: Data,
    nivells: str = "",
    inclou_sense_nivell: bool | None = None,
    include_weekends: bool = False,
    include_empty_days: bool = False,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    include_substitucions: bool = False,
    format: str = "hores",  # dins de cada dia: "hores" (una secció per hora) o "dia" (una taula)
    mida_lletra: float | None = None,
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
        inclou_sense_nivell=inclou_sense_nivell,
        amb_caps_de_setmana=include_weekends,
        amb_dies_buits=include_empty_days,
        amb_substitucions=include_substitucions,
        dia_per_pagina=dia_per_pagina,
    )
    if not pdf.nom:
        esborra_directori(pdf.directori)
        return JSONResponse(
            status_code=500,
            content={"detail": "No s'ha generat el fitxer PDF de l'interval"},
        )
    return _resposta_pdf(
        pdf.directori, pdf.nom, f"vigilancies_interval_{data_inici}_a_{data_final}_{_marca_de_temps()}.pdf"
    )


@router.get("/vigilancies/{data}")
def generar_pdf_vigilancies(
    nivells: str = "",  # Comma-separated: "1-BATX,2-BATX"
    inclou_sense_nivell: bool | None = None,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    include_substitucions: bool = False,
    format: str = "hores",  # "hores" (una secció per hora) o "dia" (una taula per al dia)
    mida_lletra: float | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Genera PDF de vigilàncies per un dia amb selecció de nivells (SQLite)
    """

    pdf = generacio.genera_pdf_vigilancies(
        db,
        dia,
        OpcionsPdf(format, mida_lletra, compress, show_comments, show_hours),
        nivells=nivells,
        inclou_sense_nivell=inclou_sense_nivell,
        amb_substitucions=include_substitucions,
    )
    if not pdf.nom:
        esborra_directori(pdf.directori)
        raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
    return _resposta_pdf(pdf.directori, pdf.nom, f"vigilancies_{dia.iso}_{_marca_de_temps()}.pdf")


@router.post("/disponibles-tots-dies")
def generar_pdf_disponibles_tots_dies(
    data_inici: DataTextual | None = Body(None, embed=True),
    db: Session = Depends(get_db_lectura),
    current_user=Depends(get_current_user),
):
    """
    Genera un PDF amb professors disponibles per N dies laborables consecutius,
    un full per dia. Comença des de data_inici (o avui si no s'especifica).
    """
    # Data d'inici: la proporcionada (la pantalla hi posa la del calendari) o avui
    primer_dia = data_inici or rellotge.avui()

    pdf_filename = f"disponibles_tots_dies_{_marca_de_temps()}.pdf"
    try:
        with directori_temporal() as temp_dir:
            disponibles.genera_pdf_disponibles(db, current_user.institucio, primer_dia, str(temp_dir / pdf_filename))
    except disponibles.DiaNoGenerat as error:
        return JSONResponse(
            status_code=500,
            content={"detail": f"No s'ha pogut generar el PDF de disponibles per al dia {error.dia:%Y-%m-%d}"},
        )
    return _resposta_pdf(temp_dir, pdf_filename, pdf_filename)
