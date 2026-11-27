"""Casos d'ús dels PDF del dia (complet), de vigilàncies (d'un dia i d'un
interval) i les validacions d'abans de generar-los, sense HTTP.

Cada funció de generació escriu el PDF en un directori temporal nou (per
petició: el PDF no es desa al servidor) i retorna un PdfGenerat; si falla
abans d'acabar, el directori s'esborra (pdf.domain.directori_temporal)."""

import logging
from dataclasses import asdict, replace
from datetime import date, timedelta

from sqlalchemy.orm import Session

from dates import data_completa
from grups.lectures import AlliberatsDelDia
from horari.domain import Dia
from i18n_setup import translate
from pdf.domain import (
    FormatPdfNoValid,
    IntervalNoValid,
    MidaPdfNoValida,
    OpcionsPdf,
    PdfGenerat,
    SenseVigilancies,
    directori_temporal,
)
from pdf.engine import PDFCompletExporter
from pdf.files import SubstitucioPdf, VigilanciaPdf
from pdf.validacions import valida_dia
from prioritats.repositories import NoSubstituirRepository
from substitucions.domain import DiaEscolar
from substitucions.files import FilaSubstitucio
from substitucions.prioritat import MillorsSubstituts
from substitucions.repositories import SubstitucioRepository
from substitucions.visibilitat import es_visible_a_substitucions
from vigilancies.analisi import analitza_vigilancies, selecciona_problemes
from vigilancies.files import FilaVigilancia
from vigilancies.repositories import VigilanciaRepository
from vigilancies.services import en_ordre

log = logging.getLogger(__name__)

MIDES_LLETRA = (1.0, 1.2, 1.35)
# Les substitucions que acompanyen les vigilàncies als PDF de vigilàncies
TIPUS_VIGILANCIA = {"VIGILANCIA", "VIGILANCIA_ABSENT"}


# ===== Validacions =====


def validacions(db: Session, dia_peticio: Dia) -> dict:
    """Conflictes i avisos d'un dia (pdf/validacions.py), amb els substituts
    de més prioritat que estan disponibles. La fan servir la ruta de
    validacions i el PDF complet (abans de generar-lo)."""

    def avisos_prioritat(dia):
        try:
            millors = MillorsSubstituts(dia, dia_peticio.gestors())
            avisos = []
            for sub in dia.files:
                millor = millors.millor(sub)
                if millor:
                    prof, tipus, _, tipus_actual = millor
                    avisos.append(
                        translate("• {time}: {prof} ({type_disp}) disponible en lloc de {sub} ({type_curr})").format(
                            time=sub.hora,
                            prof=prof,
                            type_disp=tipus,
                            sub=sub.substitut,
                            type_curr=tipus_actual,
                        )
                    )
            return avisos
        except Exception:
            log.warning("No s'han pogut comprovar els substituts de més prioritat", exc_info=True)
            return []

    return valida_dia(db, dia_peticio.data, dia_peticio.institucio, avisos_prioritat)


# ===== Peces comunes =====


def _exportador(hores: list, opcions: OpcionsPdf, institucio: str, directori) -> PDFCompletExporter:
    """L'exportador, que escriu a `directori`, i les opcions comunes:
    columnes de comentaris i d'hores, compressió, format (taula del dia o una
    secció per hora) i mida de la lletra. Sense mida: ×1,2 per hores (la
    lletra d'abans d'aquest format) i ×1 per a la taula del dia."""
    if opcions.format not in ("hores", "dia"):
        raise FormatPdfNoValid("Format de PDF desconegut", codi="format_pdf")
    mida_lletra = opcions.mida_lletra
    if mida_lletra is None:
        mida_lletra = 1.0 if opcions.format == "dia" else 1.2
    if mida_lletra not in MIDES_LLETRA:
        raise MidaPdfNoValida("Mida de lletra desconeguda", codi="mida_lletra")
    exporter = PDFCompletExporter(hores=hores, export_dir=directori, institucio=institucio)
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


def _substitucions_de_vigilancia(db: Session, data: date) -> list[FilaSubstitucio]:
    return [s for s in SubstitucioRepository.get_by_date(db, data) if s.tipus_absencia in TIPUS_VIGILANCIA]


# ===== PDF complet del dia =====


def hores_amb_possible_substitucio(horari_mgr, dia_name: str, no_substituir) -> set[str]:
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


def omple_aula_substitucions(substitucions_data: list, horari_mgr, data: date) -> None:
    """Omple l'aula de les substitucions si falta (només per al PDF)."""
    dia_name = horari_mgr.get_dia_name(data.weekday())
    for index, sub in enumerate(substitucions_data):
        if sub.aula:
            continue
        hora = sub.hora
        professor = sub.professor_absent or ""
        if not hora or not professor:
            continue
        activitat = horari_mgr.get_activitat(dia_name, hora, professor)
        if activitat:
            aula = activitat.get("aula", "")
            if aula:
                substitucions_data[index] = replace(sub, aula=aula)


def substitucions_del_pdf(db: Session, data: date) -> list[FilaSubstitucio]:
    grups_sense_classe = AlliberatsDelDia.get_by_date(db, data)
    no_substituir = NoSubstituirRepository.vigents_a(db, data)
    return [
        sub
        for sub in SubstitucioRepository.get_by_date(db, data)
        if es_visible_a_substitucions(sub, no_substituir, grups_sense_classe.get(sub.hora, ()))
    ]


def vigilancies_dels_nivells(
    per_nivell: dict[str, list[FilaVigilancia]], nivells: list[str], *, inclou_sense_nivell: bool | None = None
) -> list[FilaVigilancia]:
    """Les vigilàncies d'un dia (`per_nivell`, com les retorna el repositori)
    dels `nivells` (totes si no se'n diu cap), en l'ordre de la pantalla dins
    de cada hora."""
    if inclou_sense_nivell is None:
        # Compatibilitat: sense filtre s'incloïa tot; amb nivells triats, només
        # aquests nivells. La pantalla nova sempre envia la tria explícita.
        inclou_sense_nivell = not nivells
    vigilancies = []
    for nivell, vigs in per_nivell.items():
        if (not nivell and inclou_sense_nivell) or (nivell and (not nivells or nivell in nivells)):
            vigilancies.extend(vigs)
    return en_ordre(vigilancies)


def genera_pdf_complet(
    db: Session,
    dia: Dia,
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
    data = dia.data
    data_text = data_completa(data)

    substitucions_data = substitucions_del_pdf(db, dia.data) if amb_substitucions else []
    vigilancies_list = (
        vigilancies_dels_nivells(VigilanciaRepository.get_by_date(db, dia.data), []) if amb_vigilancies else []
    )

    if amb_substitucions and amb_vigilancies:
        tipus_pdf = "complet"
    elif amb_substitucions:
        tipus_pdf = "substitucions"
    else:
        tipus_pdf = "vigilancies"

    horari_mgr = dia.horari
    if amb_substitucions and substitucions_data:
        omple_aula_substitucions(substitucions_data, horari_mgr, data)
        # El mateix ordre que la llista de substitucions de la pantalla
        substitucions_data = SubstitucioRepository.ordena(substitucions_data, horari_mgr.hores, ordre=ordre)

    with directori_temporal() as directori:
        exporter = _exportador(horari_mgr.hores, opcions, dia.institucio, directori)
        exporter.espai_a_ma = files_en_blanc and amb_substitucions
        if exporter.espai_a_ma or exporter.format_dia:
            exporter.hores_amb_classe = hores_amb_possible_substitucio(
                horari_mgr, horari_mgr.get_dia_name(data.weekday()), NoSubstituirRepository.vigents_a(db, data)
            )

        validacio = validacions(db, dia)
        conflictes: list[str] = []
        if mostra_conflictes:
            # L'avís del límit d'encadenades és de gestió: pantalla i revisió prèvia.
            # No afegeix contingut a la taula impresa ni als seus avisos.
            avisos_gestio = set(validacio["avisos_encadenades"]) | {
                p["missatge"] for p in validacio["problemes_vigilancies"] if p["gravetat"] == "informacio"
            }
            conflictes = (validacio.get("conflicts") or []) + [
                avis for avis in (validacio.get("warnings") or []) if avis not in avisos_gestio
            ]

        nom = exporter.exportar(
            substitucions=substitucions_data,
            vigilancies=vigilancies_list,
            data_text=data_text,
            data=data,
            tipus_pdf=tipus_pdf,
            conflictes=conflictes,
        )
        return PdfGenerat(exporter.export_dir, nom)


# ===== PDF de vigilàncies d'un dia =====


def genera_pdf_vigilancies(
    db: Session,
    dia: Dia,
    opcions: OpcionsPdf,
    *,
    nivells: str,
    inclou_sense_nivell: bool | None,
    amb_substitucions: bool,
) -> PdfGenerat:
    """Les vigilàncies del dia dels nivells triats (tots si no se'n tria cap)
    i, si es vol, les substitucions de vigilància. Els conflictes, els calcula
    la funció comuna d’anàlisi."""
    data = dia.data
    data_text = data_completa(data)
    per_nivell = VigilanciaRepository.get_by_date(db, dia.data)
    if not per_nivell:
        data_iso = data.isoformat()
        raise SenseVigilancies(
            f"No hi ha vigilàncies per {data_iso}", codi="sense_vigilancies", params={"data": data_iso}
        )
    vigilancies_list = vigilancies_dels_nivells(per_nivell, _nivells(nivells), inclou_sense_nivell=inclou_sense_nivell)

    horari_mgr = dia.horari
    with directori_temporal() as directori:
        exporter = _exportador(horari_mgr.hores, opcions, dia.institucio, directori)
        subs_pdf = _substitucions_de_vigilancia(db, dia.data) if amb_substitucions else []
        nom = exporter.exportar(
            substitucions=subs_pdf,
            vigilancies=vigilancies_list,
            data_text=data_text,
            data=data,
            tipus_pdf="vigilancies",
            conflictes=[
                p["missatge"]
                for p in selecciona_problemes(analitza_vigilancies(DiaEscolar(db, dia)), vigilancies_list)
                if p["gravetat"] != "informacio"
            ],
        )
        return PdfGenerat(exporter.export_dir, nom)


# ===== PDF de vigilàncies d'un interval =====


def dates_de_l_interval(data_inici: date, data_final: date, amb_caps_de_setmana: bool) -> list[date]:
    if data_inici > data_final:
        raise IntervalNoValid("La data inicial ha de ser anterior a la final", codi="interval_vigilancies_invertit")
    dates = []
    actual = data_inici
    while actual <= data_final:
        # Sense caps de setmana: es salten el dissabte (5) i el diumenge (6)
        if amb_caps_de_setmana or actual.weekday() < 5:
            dates.append(actual)
        actual += timedelta(days=1)
    return dates


def _marca_substitucio(fila: FilaSubstitucio, data: date) -> SubstitucioPdf:
    return SubstitucioPdf(**{**asdict(fila), "dia_interval": data_completa(data), "data": data})


def _marca_dia(fila: FilaVigilancia, data: date) -> VigilanciaPdf:
    """Una còpia de la fila amb el dia, perquè el renderitzador la posi al seu dia."""
    return VigilanciaPdf(**{**asdict(fila), "dia_interval": data_completa(data), "data": data})


def _dia_buit(data: date) -> VigilanciaPdf:
    return VigilanciaPdf(dia_interval=data_completa(data), data=data, dia_buit=True)


def vigilancies_i_substitucions_de_l_interval(
    db: Session,
    dates: list[date],
    nivells: list[str],
    amb_dies_buits: bool,
    amb_substitucions: bool,
    inclou_sense_nivell: bool | None = None,
) -> tuple[list[VigilanciaPdf], list[SubstitucioPdf]]:
    """Les vigilàncies de cada dia dels nivells triats i (si es volen) les
    substitucions de vigilància, marcades amb el seu dia. Un dia sense
    vigilàncies d'aquests nivells no hi surt, ni amb les seves substitucions,
    tret que es demanin els dies buits: llavors hi va amb una fila buida."""
    vigilancies: list[VigilanciaPdf] = []
    substitucions: list[SubstitucioPdf] = []
    for data in dates:
        del_dia = [
            _marca_dia(vig, data)
            for vig in vigilancies_dels_nivells(
                VigilanciaRepository.get_by_date(db, data),
                nivells,
                inclou_sense_nivell=inclou_sense_nivell,
            )
        ]
        if del_dia:
            vigilancies.extend(del_dia)
        elif amb_dies_buits:
            vigilancies.append(_dia_buit(data))
        else:
            continue
        if amb_substitucions:
            substitucions.extend(_marca_substitucio(sub, data) for sub in _substitucions_de_vigilancia(db, data))
    return vigilancies, substitucions


def titol_de_l_interval(data_inici: date, data_final: date, nivells: list[str]) -> str:
    """«dd/mm/aaaa - dd/mm/aaaa», amb els nivells si no són tots."""
    inici = data_inici.strftime("%d/%m/%Y")
    final = data_final.strftime("%d/%m/%Y")
    titol = f"{inici} - {final}"
    if nivells:
        titol = f"{titol} ({' - '.join(nivells)})"
    return titol


def genera_pdf_interval(
    db: Session,
    institucio: str,
    data_inici: date,
    data_final: date,
    opcions: OpcionsPdf,
    *,
    nivells: str,
    inclou_sense_nivell: bool | None,
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
    horaris_per_data = {data: Dia.del_centre(data, institucio).horari for data in dates}
    horari_mgr = horaris_per_data[dates[0]] if dates else Dia.del_centre(data_inici, institucio).horari

    vigilancies, substitucions = vigilancies_i_substitucions_de_l_interval(
        db,
        dates,
        nivells_list,
        amb_dies_buits,
        amb_substitucions,
        inclou_sense_nivell,
    )
    if not vigilancies:
        raise SenseVigilancies("No hi ha vigilàncies a l'interval seleccionat", codi="sense_vigilancies_interval")

    with directori_temporal() as directori:
        exporter = _exportador(horari_mgr.hores, opcions, institucio, directori)
        exporter.hores_per_data = {data: horari.hores for data, horari in horaris_per_data.items()}
        exporter.dia_per_pagina = dia_per_pagina
        nom = exporter.exportar(
            substitucions=substitucions,
            vigilancies=vigilancies,
            data_text=titol_de_l_interval(data_inici, data_final, nivells_list),
            data=data_inici,
            tipus_pdf="vigilancies_interval",
            conflictes=_avisos_interval(db, institucio, dates, vigilancies),
        )
        return PdfGenerat(exporter.export_dir, nom)


def _avisos_interval(db: Session, institucio: str, dates: list[date], vigilancies: list[VigilanciaPdf]) -> list[str]:
    avisos = []
    for data in dates:
        files: list[FilaVigilancia] = [v for v in vigilancies if v.data == data and not v.dia_buit]
        if not files:
            continue
        problemes = selecciona_problemes(analitza_vigilancies(DiaEscolar(db, Dia.del_centre(data, institucio))), files)
        problemes = [p for p in problemes if p["gravetat"] != "informacio"]
        if problemes:
            avisos.append(data_completa(data) + ":")
            avisos.extend(p["missatge"] for p in problemes)
    return avisos
