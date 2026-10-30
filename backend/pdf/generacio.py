"""Casos d'ús dels PDF del dia (complet), de vigilàncies (d'un dia i d'un
interval) i les validacions d'abans de generar-los, sense HTTP.

Cada funció de generació escriu el PDF en un directori temporal nou (per
petició: el PDF no es desa al servidor) i retorna un PdfGenerat."""

import logging
import tempfile
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.alliberats import sense_classe
from i18n_setup import translate
from pdf.domain import FormatPdfNoValid, IntervalNoValid, MidaPdfNoValida, OpcionsPdf, PdfGenerat, SenseVigilancies
from pdf.engine import PDFCompletExporter
from pdf.validacions import valida_dia
from prioritats.repositories import NoSubstituirRepository
from repositories import GrupsAlliberatsRepository
from serveis.dia import Dia
from substitucions.prioritat import MillorsSubstituts
from substitucions.repositories import SubstitucioRepository
from utils.date_context import DateContext
from vigilancies.repositories import VigilanciaRepository
from vigilancies.services import en_ordre

log = logging.getLogger(__name__)

MIDES_LLETRA = (1.0, 1.2, 1.35)
# Les substitucions que acompanyen les vigilàncies als PDF de vigilàncies
TIPUS_VIGILANCIA = {"VIGILANCIA", "VIGILANCIA_ABSENT"}


# ===== Validacions =====


def validacions(db: Session, data: str, institucio: str, dia_peticio: Dia) -> dict:
    """Conflictes i avisos d'un dia (pdf/validacions.py), amb els substituts
    de més prioritat que estan disponibles. La fan servir la ruta de
    validacions i el PDF complet (abans de generar-lo)."""

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


# ===== Peces comunes =====


def _exportador(hores: list, opcions: OpcionsPdf, horari_mgr=None) -> PDFCompletExporter:
    """L'exportador, amb el seu directori temporal, i les opcions comunes:
    columnes de comentaris i d'hores, compressió, format (taula del dia o una
    secció per hora) i mida de la lletra. Sense mida: ×1,2 per hores (la
    lletra d'abans d'aquest format) i ×1 per a la taula del dia. Les opcions
    es validen abans de crear el directori, perquè un 400 no en deixi cap."""
    if opcions.format not in ("hores", "dia"):
        raise FormatPdfNoValid("Format de PDF desconegut", codi="format_pdf")
    mida_lletra = opcions.mida_lletra
    if mida_lletra is None:
        mida_lletra = 1.0 if opcions.format == "dia" else 1.2
    if mida_lletra not in MIDES_LLETRA:
        raise MidaPdfNoValida("Mida de lletra desconeguda", codi="mida_lletra")
    exporter = PDFCompletExporter(hores=hores, export_dir=tempfile.mkdtemp(), horari_mgr=horari_mgr)
    exporter.show_comments_column = opcions.mostra_comentaris
    exporter.show_hours_column = opcions.mostra_hores
    if opcions.compressio:
        exporter._auto_compression_active = True
    exporter.format_dia = opcions.format == "dia"
    exporter.mida_lletra = mida_lletra
    return exporter


def _nivells(nivells: str) -> list[str]:
    """Els nivells triats («1-BATX,2-BATX»); cap vol dir tots."""
    return [n.strip() for n in nivells.split(",") if n.strip()] if nivells else []


def _substitucions_de_vigilancia(db: Session, data: str) -> list[dict]:
    return [s for s in SubstitucioRepository.get_by_date(db, data) if s.get("tipus_absencia", "") in TIPUS_VIGILANCIA]


# ===== PDF complet del dia =====


def hores_amb_possible_substitucio(horari_mgr, dia_name: str, no_substituir) -> set:
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


def omple_aula_substitucions(substitucions_data: list, horari_mgr, date_obj: datetime) -> None:
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


def es_substitucio_del_pdf(sub: dict, grups_sense_classe: dict, no_substituir) -> bool:
    """Les substitucions que surten al PDF del dia:
    - les de vigilant absent, sempre (el grup pot estar alliberat perquè fa
      examen, però igualment cal el substitut);
    - les que tenen grup, si el professor tenia classe (el grup no estava
      sense classe ni ell alliberat);
    - les que no tenen grup, si l'activitat no és a «No substituir» i el
      professor no estava alliberat (p.ex. un reforç alliberat)."""
    if sub.get("tipus_absencia", "") == "VIGILANCIA_ABSENT":
        return True
    grup = sub.get("grup", "")
    grups_hora = grups_sense_classe.get(sub.get("hora", ""), [])
    professor = sub.get("professor_absent") or sub.get("professor", "")
    if grup and grup.strip():
        return not sense_classe(professor, grup, grups_hora)
    return sub.get("assignatura", "") not in no_substituir and not sense_classe(professor, "", grups_hora)


def substitucions_del_pdf(db: Session, data: str) -> list[dict]:
    grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
    no_substituir = NoSubstituirRepository.get_all(db)
    return [
        sub
        for sub in SubstitucioRepository.get_by_date(db, data)
        if es_substitucio_del_pdf(sub, grups_sense_classe, no_substituir)
    ]


def vigilancies_dels_nivells(per_nivell: dict, nivells: list[str]) -> list[dict]:
    """Les vigilàncies d'un dia (`per_nivell`, com les retorna el repositori)
    dels `nivells` (totes si no se'n diu cap), en l'ordre de la pantalla dins
    de cada hora."""
    vigilancies = []
    for nivell, vigs in per_nivell.items():
        if not nivells or nivell in nivells:
            vigilancies.extend(vigs)
    return en_ordre(vigilancies)


def genera_pdf_complet(
    db: Session,
    dia: Dia,
    data: str,
    institucio: str,
    opcions: OpcionsPdf,
    *,
    amb_substitucions: bool,
    amb_vigilancies: bool,
    mostra_conflictes: bool,
    files_en_blanc: bool,
    ordre: str,
) -> PdfGenerat:
    """Substitucions i/o vigilàncies del dia (de tots els nivells), amb els
    conflictes i avisos de les validacions."""
    date_obj = datetime.strptime(data, "%Y-%m-%d")
    data_text = DateContext.from_iso(data).full_format

    substitucions_data = substitucions_del_pdf(db, data) if amb_substitucions else []
    vigilancies_list = (
        vigilancies_dels_nivells(VigilanciaRepository.get_by_date(db, data), []) if amb_vigilancies else []
    )

    if amb_substitucions and amb_vigilancies:
        tipus_pdf = "complet"
    elif amb_substitucions:
        tipus_pdf = "substitucions"
    else:
        tipus_pdf = "vigilancies"

    horari_mgr = dia.horari
    if amb_substitucions and substitucions_data:
        omple_aula_substitucions(substitucions_data, horari_mgr, date_obj)
        # El mateix ordre que la llista de substitucions de la pantalla
        substitucions_data = SubstitucioRepository.ordena(substitucions_data, horari_mgr.hores, ordre=ordre)

    exporter = _exportador(horari_mgr.hores, opcions)
    exporter.espai_a_ma = files_en_blanc and amb_substitucions
    if exporter.espai_a_ma or exporter.format_dia:
        exporter.hores_amb_classe = hores_amb_possible_substitucio(
            horari_mgr, horari_mgr.get_dia_name(date_obj.weekday()), NoSubstituirRepository.get_all(db)
        )

    validacio = validacions(db, data, institucio, dia)
    conflictes = []
    if mostra_conflictes:
        conflictes = (validacio.get("conflicts") or []) + (validacio.get("warnings") or [])

    nom = exporter.exportar(
        substitucions=substitucions_data,
        vigilancies=vigilancies_list,
        data_text=data_text,
        data_iso=data,
        tipus_pdf=tipus_pdf,
        conflictes=conflictes,
    )
    return PdfGenerat(exporter.export_dir, nom)


# ===== PDF de vigilàncies d'un dia =====


def genera_pdf_vigilancies(
    db: Session, dia: Dia, data: str, opcions: OpcionsPdf, *, nivells: str, amb_substitucions: bool
) -> PdfGenerat:
    """Les vigilàncies del dia dels nivells triats (tots si no se'n tria cap)
    i, si es vol, les substitucions de vigilància. Els conflictes, els calcula
    el renderitzador."""
    data_text = DateContext.from_iso(data).full_format
    per_nivell = VigilanciaRepository.get_by_date(db, data)
    if not per_nivell:
        raise SenseVigilancies(f"No hi ha vigilàncies per {data}", codi="sense_vigilancies")
    vigilancies_list = vigilancies_dels_nivells(per_nivell, _nivells(nivells))

    horari_mgr = dia.horari
    exporter = _exportador(horari_mgr.hores, opcions)
    subs_pdf = _substitucions_de_vigilancia(db, data) if amb_substitucions else []
    nom = exporter.exportar(
        substitucions=subs_pdf,
        vigilancies=vigilancies_list,
        data_text=data_text,
        data_iso=data,
        tipus_pdf="vigilancies",
    )
    return PdfGenerat(exporter.export_dir, nom)


# ===== PDF de vigilàncies d'un interval =====


def dates_de_l_interval(data_inici: str, data_final: str, amb_caps_de_setmana: bool) -> list[str]:
    date_inici = datetime.strptime(data_inici, "%Y-%m-%d")
    date_final = datetime.strptime(data_final, "%Y-%m-%d")
    if date_inici > date_final:
        raise IntervalNoValid("La data inicial ha de ser anterior a la final", codi="interval_invertit")
    dates = []
    actual = date_inici
    while actual <= date_final:
        # Sense caps de setmana: es salten el dissabte (5) i el diumenge (6)
        if amb_caps_de_setmana or actual.weekday() < 5:
            dates.append(actual.strftime("%Y-%m-%d"))
        actual += timedelta(days=1)
    return dates


def _marca_dia(fila: dict, data: str) -> dict:
    """Una còpia de la fila amb el dia, perquè el renderitzador la posi al seu dia."""
    return {**fila, "_dia_interval": DateContext.from_iso(data).full_format, "_data_iso": data}


def _dia_buit(data: str) -> dict:
    return {"_dia_interval": DateContext.from_iso(data).full_format, "_data_iso": data, "_empty_day": True}


def vigilancies_i_substitucions_de_l_interval(
    db: Session, dates: list[str], nivells: list[str], amb_dies_buits: bool, amb_substitucions: bool
) -> tuple[list[dict], list[dict]]:
    """Les vigilàncies de cada dia dels nivells triats i (si es volen) les
    substitucions de vigilància, marcades amb el seu dia. Un dia sense
    vigilàncies d'aquests nivells no hi surt, ni amb les seves substitucions,
    tret que es demanin els dies buits: llavors hi va amb una fila buida."""
    vigilancies, substitucions = [], []
    for data in dates:
        del_dia = [
            _marca_dia(vig, data)
            for nivell, vigs in VigilanciaRepository.get_by_date(db, data).items()
            if not nivells or nivell in nivells
            for vig in vigs
        ]
        if del_dia:
            vigilancies.extend(en_ordre(del_dia))  # l'ordre de la pantalla dins de cada hora
        elif amb_dies_buits:
            vigilancies.append(_dia_buit(data))
        else:
            continue
        if amb_substitucions:
            substitucions.extend(_marca_dia(sub, data) for sub in _substitucions_de_vigilancia(db, data))
    return vigilancies, substitucions


def titol_de_l_interval(data_inici: str, data_final: str, nivells: list[str]) -> str:
    """«dd/mm/aaaa - dd/mm/aaaa», amb els nivells si no són tots."""
    inici = datetime.strptime(data_inici, "%Y-%m-%d").strftime("%d/%m/%Y")
    final = datetime.strptime(data_final, "%Y-%m-%d").strftime("%d/%m/%Y")
    titol = f"{inici} - {final}"
    if nivells:
        titol = f"{titol} ({' - '.join(nivells)})"
    return titol


def genera_pdf_interval(
    db: Session,
    institucio: str,
    data_inici: str,
    data_final: str,
    opcions: OpcionsPdf,
    *,
    nivells: str,
    amb_caps_de_setmana: bool,
    amb_dies_buits: bool,
    amb_substitucions: bool,
    dia_per_pagina: bool,
) -> PdfGenerat:
    """Les vigilàncies de tots els dies de l'interval en un sol PDF."""
    dates = dates_de_l_interval(data_inici, data_final, amb_caps_de_setmana)
    nivells_list = _nivells(nivells)

    # Cada dia pot tenir una versió diferent de l'XML i, per tant, franges
    # diferents. Es conserven per data perquè el render les ordeni amb
    # l'horari que era vigent aquell dia.
    horaris_per_data = {data: Dia.de_text(data, institucio).horari for data in dates}
    horari_mgr = horaris_per_data[dates[0]] if dates else Dia.de_text(data_inici, institucio).horari

    vigilancies, substitucions = vigilancies_i_substitucions_de_l_interval(
        db, dates, nivells_list, amb_dies_buits, amb_substitucions
    )
    if not vigilancies:
        raise SenseVigilancies("No hi ha vigilàncies a l'interval seleccionat", codi="sense_vigilancies")

    exporter = _exportador(horari_mgr.hores, opcions, horari_mgr=horari_mgr)
    exporter.hores_per_data = {data: horari.hores for data, horari in horaris_per_data.items()}
    exporter.dia_per_pagina = dia_per_pagina
    nom = exporter.exportar(
        substitucions=substitucions,
        vigilancies=vigilancies,
        data_text=titol_de_l_interval(data_inici, data_final, nivells_list),
        data_iso=data_inici,
        tipus_pdf="vigilancies_interval",
    )
    return PdfGenerat(exporter.export_dir, nom)
