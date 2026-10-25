"""
Routes per generació i validació de PDFs:
- Validació abans de generar PDF
- PDF complet (substitucions + vigilàncies)
- PDF vigilàncies per un dia
- PDF vigilàncies per interval de dates
"""

import json
import logging
import os
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from auth.dependencies import get_current_user
from core.alliberats import sense_classe
from dependencies import dia_de_la_peticio, get_db
from export.pdf.engine import PDFCompletExporter
from i18n_setup import translate
from repositories import (
    ConfiguracioRepository,
    GrupsAlliberatsRepository,
    SubstitucioRepository,
)
from routes.parametres import DataISO, data_iso
from serveis.dia import Dia
from serveis.prioritat import MillorsSubstituts
from serveis.validacions_pdf import valida_dia
from vigilancies.repositories import VigilanciaRepository
from vigilancies.services import en_ordre

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


class PDFPreferencesUpdate(BaseModel):
    substitucions: Optional[Dict[str, Any]] = None
    vigilancies: Optional[Dict[str, Any]] = None
    vigilancies_interval: Optional[Dict[str, Any]] = None


@router.get("/preferences")
async def get_pdf_preferences(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retorna les preferències PDF desades per institució
    """
    prefs_subs = ConfiguracioRepository.get(db, "pdf_prefs_substitucions")
    prefs_vigs = ConfiguracioRepository.get(db, "pdf_prefs_vigilancies")
    prefs_vigs_interval = ConfiguracioRepository.get(db, "pdf_prefs_vigilancies_interval")

    return {
        "substitucions": json.loads(prefs_subs) if prefs_subs else None,
        "vigilancies": json.loads(prefs_vigs) if prefs_vigs else None,
        "vigilancies_interval": json.loads(prefs_vigs_interval) if prefs_vigs_interval else None,
    }


@router.put("/preferences")
async def update_pdf_preferences(
    prefs: PDFPreferencesUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Desa les preferències PDF per institució
    """
    if prefs.substitucions is not None:
        ConfiguracioRepository.set(
            db,
            "pdf_prefs_substitucions",
            json.dumps(prefs.substitucions),
            tipus="json",
            descripcio="Preferències PDF de substitucions",
        )
    if prefs.vigilancies is not None:
        ConfiguracioRepository.set(
            db,
            "pdf_prefs_vigilancies",
            json.dumps(prefs.vigilancies),
            tipus="json",
            descripcio="Preferències PDF de vigilàncies",
        )
    if prefs.vigilancies_interval is not None:
        ConfiguracioRepository.set(
            db,
            "pdf_prefs_vigilancies_interval",
            json.dumps(prefs.vigilancies_interval),
            tipus="json",
            descripcio="Preferències PDF interval de vigilàncies",
        )

    return {"success": True}


def _hores_amb_possible_substitucio(horari_mgr, dia_name: str, no_substituir) -> set:
    """Hores en què algun professor configurat té classe amb un grup visible
    (no amagat) o una activitat sense grup que no és a «no substituir»: on hi
    pot haver alguna substitució."""
    grups_visibles = set(horari_mgr.grups)
    no_substituir = set(no_substituir)
    hores = set()
    for hora in horari_mgr.hores:
        for professor in horari_mgr.professors:
            activitat = horari_mgr.get_activitat(dia_name, hora, professor) or {}
            grup = activitat.get("grup") or ""
            assignatura = activitat.get("assignatura") or ""
            if (grup in grups_visibles) if grup else (assignatura and assignatura not in no_substituir):
                hores.add(hora)
                break
    return hores


def _omplir_aula_substitucions(substitucions_data: list, horari_mgr, date_obj: datetime) -> None:
    """Omple l'aula de les substitucions si falta (només per al PDF)."""
    dia_name = horari_mgr.get_dia_name(date_obj.weekday())
    for sub in substitucions_data:
        if sub.get("aula"):
            continue
        hora = sub.get("hora", "")
        professor = sub.get("professor_absent", "") or sub.get("professor", "")
        if not hora or not professor:
            continue
        activitat = horari_mgr.get_activitat(dia_name, hora, professor)
        if activitat:
            aula = activitat.get("aula", "")
            if aula:
                sub["aula"] = aula


@router.get("/{data}/validacions")
def validar_abans_pdf(
    data: DataISO,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia_peticio: Dia = Depends(dia_de_la_peticio),
):
    """Conflictes i avisos d'un dia abans de generar el PDF (serveis/validacions_pdf.py)."""
    data_iso(data)
    return _validacions(db, data, current_user.institucio, dia_peticio)


def _validacions(db: Session, data: str, institucio: str, dia_peticio: Dia) -> dict:
    """La validació de la ruta de validacions i del PDF complet (que la fa
    abans de generar-lo). Una funció normal: una ruta no n'ha de cridar una
    altra, perquè els seus Depends no s'hi resolen (abans el PDF complet
    passava sense el Dia i en perdia els avisos de prioritat)."""

    def avisos_prioritat(dia, vigilancies_per_hora):
        try:
            millors = MillorsSubstituts(dia, dia_peticio.gestors())
            avisos = []
            for sub in dia.files:
                if sub.get("separador"):
                    continue
                millor = millors.millor(sub)
                if millor:
                    prof, tipus, _, tipus_actual = millor
                    avisos.append(
                        translate("• {time}: {prof} ({type_disp}) disponible en lloc de {sub} ({type_curr})").format(
                            time=sub.get("hora", ""),
                            prof=prof,
                            type_disp=tipus,
                            sub=sub.get("substitut", ""),
                            type_curr=tipus_actual,
                        )
                    )
            return avisos
        except Exception:
            log.warning("No s'han pogut comprovar els substituts de més prioritat", exc_info=True)
            return []

    return valida_dia(db, data, institucio, avisos_prioritat)


# Les rutes que generen PDF són síncrones: FastAPI les atén en un fil a part i
# el backend continua responent la resta de peticions mentre es generen.
MIDES_LLETRA = (1.0, 1.2, 1.35)


def _format_i_mida(exporter, format: str, mida_lletra: Optional[float]) -> None:
    """El format (taula del dia o una secció per hora) i la mida de la lletra,
    els mateixos per a tots els PDF. Sense mida: ×1,2 per hores (la lletra
    d'abans d'aquest format) i ×1 per a la taula del dia."""
    if format not in ("hores", "dia"):
        raise HTTPException(status_code=400, detail="Format de PDF desconegut")
    if mida_lletra is None:
        mida_lletra = 1.0 if format == "dia" else 1.2
    if mida_lletra not in MIDES_LLETRA:
        raise HTTPException(status_code=400, detail="Mida de lletra desconeguda")
    exporter.format_dia = format == "dia"
    exporter.mida_lletra = mida_lletra


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
    mida_lletra: Optional[float] = None,  # normal (1), gran (1.2) o molt gran (1.35); sense: veure _format_i_mida
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Genera PDF complet del dia amb substitucions i/o vigilàncies (TOTS els nivells) (SQLite)
    """
    # Validar data
    date_obj = data_iso(data)

    from utils.date_context import DateContext

    data_text = DateContext.from_iso(data).full_format

    # Carregar dades
    substitucions_data = []
    vigilancies_list = []

    if include_substitutions:
        # Carregar substitucions des de SQLite
        substitucions_raw = SubstitucioRepository.get_by_date(db, data)

        # FILTRAR: només mostrar al PDF les que generen substitució real
        # Criteri:
        # 1. Té grup I el grup NO està alliberat, O
        # 2. NO té grup però l'assignatura NO està a no_substituir
        grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)

        from prioritats.repositories import NoSubstituirRepository

        no_substituir = NoSubstituirRepository.get_all(db)

        for sub in substitucions_raw:
            grup = sub.get("grup", "")
            hora = sub.get("hora", "")
            assignatura = sub.get("assignatura", "")
            tipus_absencia = sub.get("tipus_absencia", "")

            mostrar = False

            # VIGILANCIA_ABSENT: sempre mostrar (substitució de vigilant absent)
            # El grup pot estar alliberat perquè fa examen, però igualment cal el substitut
            if tipus_absencia == "VIGILANCIA_ABSENT":
                mostrar = True
            elif grup and grup.strip():
                # CAS 1: Té grup → comprovar si està alliberat
                grups_hora = grups_sense_classe.get(hora, [])
                professor = sub.get("professor_absent") or sub.get("professor", "")
                if not sense_classe(professor, grup, grups_hora):
                    mostrar = True
            else:
                # CAS 2: NO té grup → comprovar si l'assignatura necessita substitució
                # (i que el professor no estigui alliberat, p.ex. un reforç alliberat)
                professor = sub.get("professor_absent") or sub.get("professor", "")
                if assignatura not in no_substituir and not sense_classe(
                    professor, "", grups_sense_classe.get(hora, [])
                ):
                    mostrar = True

            if mostrar:
                substitucions_data.append(sub)

    if include_vigilancies:
        # Carregar vigilàncies (TOTS els nivells) des de SQLite i flatten a llista
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
        # Flatten: combinar totes les vigilàncies de tots els nivells
        for nivell_vigs in vigilancies_dict.values():
            vigilancies_list.extend(nivell_vigs)
        vigilancies_list = en_ordre(vigilancies_list)  # l'ordre de la pantalla dins de cada hora

    # Determinar tipus de PDF
    if include_substitutions and include_vigilancies:
        tipus_pdf = "complet"
    elif include_substitutions:
        tipus_pdf = "substitucions"
    elif include_vigilancies:
        tipus_pdf = "vigilancies"
    else:
        tipus_pdf = "complet"

    # Inicialitzar exporter amb hores
    horari_mgr = dia.horari
    hores = horari_mgr.hores

    if include_substitutions and substitucions_data:
        _omplir_aula_substitucions(substitucions_data, horari_mgr, date_obj)
        # Dins de cada hora, el mateix ordre fix que la llista de substitucions
        substitucions_data.sort(key=SubstitucioRepository.clau_ordre)

    # Directori temporal per petició: el PDF no es desa al servidor.
    export_dir = Path(tempfile.mkdtemp())
    exporter = PDFCompletExporter(hores=hores, export_dir=str(export_dir))

    # Configurar opcions via atributs
    exporter.show_comments_column = show_comments
    exporter.show_hours_column = show_hours
    _format_i_mida(exporter, format, mida_lletra)
    exporter.espai_a_ma = blank_rows and include_substitutions
    if exporter.espai_a_ma or exporter.format_dia:
        from prioritats.repositories import NoSubstituirRepository

        exporter.hores_amb_classe = _hores_amb_possible_substitucio(
            horari_mgr, horari_mgr.get_dia_name(date_obj.weekday()), NoSubstituirRepository.get_all(db)
        )
    if compress:
        exporter._auto_compression_active = True

    # Obtenir conflictes i avisos
    validacio_response = _validacions(db, data, current_user.institucio, dia)
    all_issues = []
    if show_conflicts:
        all_issues = (validacio_response.get("conflicts") or []) + (validacio_response.get("warnings") or [])

    # Generar PDF al directori temporal
    filename = exporter.exportar(
        substitucions=substitucions_data,
        vigilancies=vigilancies_list,
        data_text=data_text,
        data_iso=data,
        tipus_pdf=tipus_pdf,
        conflictes=all_issues,  # Passar conflictes al PDF
    )

    if not filename:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
    exports_path = export_dir / filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"complet_{data}_{timestamp}.pdf"

    # Retornar el fitxer i esborrar el temporal un cop enviat
    return FileResponse(
        str(exports_path),
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f"attachment; filename={pdf_filename}"},
        background=BackgroundTask(shutil.rmtree, str(export_dir), True),
    )


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

    # Debug logging

    # Validar dates
    date_inici = datetime.strptime(data_inici, "%Y-%m-%d")
    date_final = datetime.strptime(data_final, "%Y-%m-%d")

    if date_inici > date_final:
        raise HTTPException(status_code=400, detail="La data inicial ha de ser anterior a la final")

    # Parsejar nivells
    nivells_list = [n.strip() for n in nivells.split(",") if n.strip()] if nivells else []
    nivells_specified = bool(nivells_list)

    # Generar llista de dates
    dates_list = []
    current_date = date_inici

    while current_date <= date_final:
        # Si no volem caps de setmana, saltar dissabte (5) i diumenge (6)
        if include_weekends or current_date.weekday() < 5:
            dates_list.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    # Inicialitzar exporter amb hores (només una vegada)
    horari_mgr = Dia.de_text(data_inici, current_user.institucio).horari
    hores = horari_mgr.hores

    # Recopilar totes les vigilàncies de tots els dies
    from utils.date_context import DateContext

    interval_vigilancies = []
    interval_substitucions = []

    for data_str in dates_list:
        # Carregar vigilàncies per aquest dia des de SQLite
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data_str)

        if not vigilancies_dict:
            if include_empty_days:
                date_ctx = DateContext.from_iso(data_str)
                interval_vigilancies.append(
                    {"_dia_interval": date_ctx.full_format, "_data_iso": data_str, "_empty_day": True}
                )
            if not include_empty_days:
                continue  # Saltar dies sense vigilàncies
            day_vigilancies = []
        else:
            # Filtrar nivells i flatten a llista
            day_vigilancies = []
            for nivell, vigs in vigilancies_dict.items():
                if not nivells_specified or nivell in nivells_list:
                    # Copiar cada vigilància i marcar amb dia
                    for vig in vigs:
                        vig_copy = vig.copy()
                        # Marcar amb data per generar format correcte
                        date_ctx = DateContext.from_iso(data_str)
                        vig_copy["_dia_interval"] = date_ctx.full_format
                        vig_copy["_data_iso"] = data_str
                        day_vigilancies.append(vig_copy)

            # Si no hi ha vigilàncies per aquest dia als nivells seleccionats
            if not include_empty_days and not day_vigilancies:
                continue
            if include_empty_days and not day_vigilancies:
                date_ctx = DateContext.from_iso(data_str)
                interval_vigilancies.append(
                    {"_dia_interval": date_ctx.full_format, "_data_iso": data_str, "_empty_day": True}
                )
        if day_vigilancies:
            interval_vigilancies.extend(en_ordre(day_vigilancies))  # l'ordre de la pantalla dins de cada hora

        if include_substitucions:
            subs_raw = SubstitucioRepository.get_by_date(db, data_str)
            TIPUS_VIGILANCIA = {"VIGILANCIA", "VIGILANCIA_ABSENT"}
            date_ctx_sub = DateContext.from_iso(data_str)
            for sub in subs_raw:
                if sub.get("tipus_absencia", "") in TIPUS_VIGILANCIA:
                    sub_copy = sub.copy()
                    sub_copy["_dia_interval"] = date_ctx_sub.full_format
                    sub_copy["_data_iso"] = data_str
                    interval_substitucions.append(sub_copy)

    if not interval_vigilancies:
        raise HTTPException(status_code=404, detail="No hi ha vigilàncies a l'interval seleccionat")

    # Format títol interval
    data_inici_obj = datetime.strptime(data_inici, "%Y-%m-%d")
    data_final_obj = datetime.strptime(data_final, "%Y-%m-%d")
    data_inici_curta = data_inici_obj.strftime("%d/%m/%Y")
    data_final_curta = data_final_obj.strftime("%d/%m/%Y")
    interval_title = f"{data_inici_curta} - {data_final_curta}"

    # Afegir nivells al títol si no són tots
    if nivells_specified:
        nivells_text = " - ".join(nivells_list)
        interval_title = f"{interval_title} ({nivells_text})"

    # Generar PDF UNA SOLA VEGADA amb totes les vigilàncies
    # Directori temporal per petició: el PDF no es desa al servidor.
    export_dir = Path(tempfile.mkdtemp())
    exporter = PDFCompletExporter(hores=hores, export_dir=str(export_dir), horari_mgr=horari_mgr)

    # Configurar opcions via atributs
    exporter.show_comments_column = show_comments
    exporter.show_hours_column = show_hours
    if compress:
        exporter._auto_compression_active = True
    _format_i_mida(exporter, format, mida_lletra)
    exporter.dia_per_pagina = dia_per_pagina

    # Cridar exportar() una sola vegada amb tipus especial "vigilancies_interval"
    filename = exporter.exportar(
        substitucions=interval_substitucions,
        vigilancies=interval_vigilancies,
        data_text=interval_title,
        data_iso=data_inici,
        tipus_pdf="vigilancies_interval",
    )

    exports_path = export_dir / filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"vigilancies_interval_{data_inici}_a_{data_final}_{timestamp}.pdf"

    return FileResponse(
        str(exports_path),
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f"attachment; filename={pdf_filename}"},
        background=BackgroundTask(shutil.rmtree, str(export_dir), True),
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

    from utils.date_context import DateContext

    data_text = DateContext.from_iso(data).full_format

    # Parsejar nivells seleccionats
    nivells_list = [n.strip() for n in nivells.split(",") if n.strip()] if nivells else []

    # Carregar vigilàncies des de SQLite
    vigilancies_dict = VigilanciaRepository.get_by_date(db, data)

    if not vigilancies_dict:
        raise HTTPException(status_code=404, detail=f"No hi ha vigilàncies per {data}")

    if not nivells_list:
        nivells_list = list(vigilancies_dict.keys())

    # Filtrar només nivells seleccionats i flatten a llista
    vigilancies_list = []
    for nivell, vigs in vigilancies_dict.items():
        if nivell in nivells_list:
            vigilancies_list.extend(vigs)
    vigilancies_list = en_ordre(vigilancies_list)  # l'ordre de la pantalla dins de cada hora

    # Inicialitzar exporter amb hores
    horari_mgr = dia.horari
    hores = horari_mgr.hores

    # Directori temporal per petició: el PDF no es desa al servidor.
    export_dir = Path(tempfile.mkdtemp())
    exporter = PDFCompletExporter(hores=hores, export_dir=str(export_dir))

    # Configurar opcions via atributs
    exporter.show_comments_column = show_comments
    exporter.show_hours_column = show_hours
    if compress:
        exporter._auto_compression_active = True
    _format_i_mida(exporter, format, mida_lletra)

    # Carregar substitucions de vigilància si cal
    subs_pdf = []
    if include_substitucions:
        subs_raw = SubstitucioRepository.get_by_date(db, data)
        TIPUS_VIGILANCIA = {"VIGILANCIA", "VIGILANCIA_ABSENT"}
        subs_pdf = [s for s in subs_raw if s.get("tipus_absencia", "") in TIPUS_VIGILANCIA]

    # Generar PDF (conflictes=None → engine els calcula automàticament)
    filename = exporter.exportar(
        substitucions=subs_pdf,
        vigilancies=vigilancies_list,
        data_text=data_text,
        data_iso=data,
        tipus_pdf="vigilancies",
    )

    if not filename:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
    exports_path = export_dir / filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"vigilancies_{data}_{timestamp}.pdf"

    return FileResponse(
        str(exports_path),
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f"attachment; filename={pdf_filename}"},
        background=BackgroundTask(shutil.rmtree, str(export_dir), True),
    )


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
    import tempfile
    from datetime import date, timedelta

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    # Data d'inici: la proporcionada (la pantalla hi posa la del calendari) o avui
    primer_dia = data_iso(data_inici) if data_inici else date.today()

    # Configurar idioma per traduccions
    from i18n_setup import setup_translation
    from repositories import ConfiguracioRepository

    config_db = ConfiguracioRepository.get_all_as_dict(db)
    idioma = config_db.get("idioma", "ca")  # Default català
    setup_translation(idioma)

    # Carregar horari per obtenir els dies configurats
    try:
        horari_temp = Dia(primer_dia, current_user.institucio).horari
        dies_xml = horari_temp.dies if hasattr(horari_temp, "dies") else []
    except Exception:
        log.warning("No s'ha pogut carregar l'horari per als dies del PDF", exc_info=True)
        dies_xml = []

    # Si no hi ha dies a l'XML, usar 5 dies laborables per defecte
    num_dies_laborables = len(dies_xml) if dies_xml else 5

    # Generar N dies laborables consecutius des de primer_dia (salta cap de setmana)
    dies_setmana = []
    actual = primer_dia
    while len(dies_setmana) < num_dies_laborables:
        if actual.weekday() < 5:  # 0=Dl, 4=Dv
            dies_setmana.append(actual)
        actual += timedelta(days=1)

    # Crear PDF temporal
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"disponibles_tots_dies_{timestamp}.pdf"
    pdf_path = os.path.join(temp_dir, pdf_filename)

    # Crear document PDF
    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1 * cm, bottomMargin=2 * cm
    )

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    date_style = ParagraphStyle(
        "CustomDate",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#1e40af"),
        spaceAfter=16,
        leading=24,
        alignment=TA_CENTER,
    )

    from babel.dates import format_date

    import i18n_setup

    idioma_actual = i18n_setup.CURRENT_LANGUAGE

    story = []

    # Iterar per cada dia de la setmana
    for idx, current_date in enumerate(dies_setmana):
        dia_iso = current_date.strftime("%Y-%m-%d")
        dia_idx = current_date.weekday()

        # Obtenir nom del dia de l'XML per usar amb get_tots_disponibles()
        if dia_idx < len(dies_xml):
            dia_name_xml = dies_xml[dia_idx]
        else:
            # Fallback: si no hi ha XML, usar Babel segons idioma configurat
            dia_name_xml = format_date(current_date, "EEEE", locale=idioma_actual)
            dia_name_xml = dia_name_xml[:1].upper() + dia_name_xml[1:]

        # Capçalera: label petit + data del dia destacada
        titol = translate("📋 Llistat de Professors Substituts").replace("📋 ", "")
        data_dia = format_date(current_date, "full", locale=idioma_actual)
        data_dia = data_dia[:1].upper() + data_dia[1:]
        story.append(Paragraph(titol, title_style))
        story.append(Paragraph(f"<b>{data_dia}</b>", date_style))
        story.append(Spacer(1, 0.5 * cm))

        try:
            # Obtenir disponibles del dia
            substitucions_mgr, horari_mgr, alliberats_mgr, absencies_mgr = Dia.de_text(
                dia_iso, current_user.institucio
            ).gestors()

            # Obtenir substitucions del dia
            from repositories import (
                GrupsAlliberatsRepository,
                SubstitucioRepository,
            )
            from vigilancies.repositories import VigilanciaRepository

            substitucions_data = SubstitucioRepository.get_by_date(db, dia_iso)

            # Mapa de substituts per hora (ocupats fent substitució)
            substituts_per_hora = defaultdict(set)
            # Mapa de professors absents per hora
            absents_per_hora = defaultdict(set)
            for sub in substitucions_data:
                h = sub.get("hora", "")
                substitut = sub.get("substitut", "")
                absent = sub.get("professor_absent", "")
                if h and substitut:
                    substituts_per_hora[h].add(substitut)
                if h and absent:
                    absents_per_hora[h].add(absent)

            # Mapa de vigilants per hora (ocupats fent vigilància)
            vigilants_per_hora = defaultdict(set)
            try:
                vigilancies_data = VigilanciaRepository.get_by_date(db, dia_iso)
                for nivell_vigs in vigilancies_data.values():
                    for vig in nivell_vigs:
                        h = vig.get("hora", "")
                        vigilant = vig.get("vigilant", "")
                        if h and vigilant:
                            vigilants_per_hora[h].add(vigilant)
            except Exception:
                log.warning("No s'han pogut llegir les vigilàncies del dia", exc_info=True)

            # Obtenir grups alliberats
            grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, dia_iso)

            # Import necessari per categories
            from config.constants import ORDRE_PRIORITATS, PRIORITATS

            hora_header_style = ParagraphStyle(
                "HoraHeader",
                parent=styles["Normal"],
                fontSize=10,
                leading=14,
                fontName="Courier-Bold",
                leftIndent=10,
                spaceAfter=2,
            )
            content_style = ParagraphStyle(
                "Content",
                parent=styles["Normal"],
                fontSize=9,
                leading=12,
                fontName="Courier",
                leftIndent=10,
                spaceAfter=6,
            )

            hi_ha_contingut = False

            # Per cada hora — cada bloc va amb KeepTogether
            for hora in horari_mgr.hores:
                grups_hora = grups_alliberats_data.get(hora, [])
                # Llista completa (sense filtrar) per mostrar tots amb estat
                disponibles_tots = alliberats_mgr.get_tots_disponibles(dia_name_xml, hora, grups_hora)

                if not disponibles_tots:
                    continue

                hi_ha_contingut = True

                per_categoria_tipus = defaultdict(lambda: defaultdict(list))

                for prof, tipus, _detall in disponibles_tots:
                    categoria_idx = len(ORDRE_PRIORITATS)
                    for i, categoria in enumerate(ORDRE_PRIORITATS):
                        if tipus in categoria:
                            categoria_idx = i
                            break
                    # Determinar estat del professor
                    if prof in absents_per_hora.get(hora, set()):
                        estat = "absent"
                    elif prof in substituts_per_hora.get(hora, set()) or prof in vigilants_per_hora.get(hora, set()):
                        estat = "ocupat"
                    else:
                        estat = "disponible"
                    per_categoria_tipus[categoria_idx][tipus].append((prof, estat))

                lines = []
                for categoria_idx in sorted(per_categoria_tipus.keys()):
                    cat_label = f"Cat.{categoria_idx}" if categoria_idx < len(ORDRE_PRIORITATS) else "Cat.99"
                    for tipus in sorted(per_categoria_tipus[categoria_idx].keys()):
                        profs_amb_estat = per_categoria_tipus[categoria_idx][tipus]
                        pes = PRIORITATS.get(tipus, 1)
                        parts = []
                        for prof, estat in sorted(profs_amb_estat, key=lambda x: x[0]):
                            if estat == "absent":
                                parts.append(f'<strike><font color="#d97706">{prof}</font></strike>')
                            elif estat == "ocupat":
                                parts.append(f'<strike><font color="#9ca3af">{prof}</font></strike>')
                            else:
                                parts.append(prof)
                        profs_text = ", ".join(parts)
                        meta = f'<font color="#94a3b8">  - {cat_label}:</font>'
                        suffix = f'<font color="#94a3b8"> ({tipus} [{pes}])</font>'
                        lines.append(f"{meta} {profs_text}{suffix}")

                hora_block = [
                    Paragraph(hora, hora_header_style),
                    Paragraph("<br/>".join(lines), content_style),
                ]
                story.append(KeepTogether(hora_block))

            if not hi_ha_contingut:
                story.append(Paragraph("<i>No hi ha professors disponibles</i>", styles["Normal"]))

        except Exception as e:
            log.warning(f"Error processant dia {dia_iso}: {e}")
            story.append(Paragraph("<i>Error carregant dades per aquest dia</i>", styles["Normal"]))

        # Page break entre dies (excepte l'últim)
        if idx < len(dies_setmana) - 1:
            story.append(PageBreak())

    # Generar PDF
    doc.build(story)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f"attachment; filename={pdf_filename}"},
    )
