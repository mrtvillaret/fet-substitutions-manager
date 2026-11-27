"""Anàlisi nova: les dates desades i els tres textos del mateix problema."""

from grups.abreviatures import aplicar_abreviatura_grup
from planificador.compartit.constants import DEFAULT_NIVELLS_ACTIUS
from planificador.compartit.normalitzacio import normalitzar_dia
from planificador.compartit.preparacio import prepara_planificacio
from planificador.motor.compatibilitat import ANALISI
from planificador.motor.construccio import construeix_problema
from planificador.motor.textos_analisi import TextosAnalisi
from planificador.schemas import SchedulerGenerateRequest


def _expandir_dies_per_analisi(dies_util: list, dia_a_data_iso: dict) -> list:
    """Expandeix dies_util a dates ISO quan hi ha múltiples setmanes per dia."""
    result = []
    for dia in dies_util:
        dates = dia_a_data_iso.get(normalitzar_dia(dia), [])
        if isinstance(dates, str):
            dates = [dates]
        if len(dates) > 1:
            result.extend(dates)
        else:
            result.append(dia)
    return result


def analitza(payload: SchedulerGenerateRequest, institucio: str) -> dict:
    pla = prepara_planificacio(payload, institucio, dates_de_la_peticio=False).per_al_motor()
    problema = construeix_problema(
        pla.cfg,
        pla.xml_path,
        pla.nivells or list(DEFAULT_NIVELLS_ACTIUS),
        pla.dies,
        pla.dates,
        pla.dia_a_data_iso,
        pla.hores_examen,
        ANALISI,
        restriccions_resoltes=pla.restriccions,
    )
    dies = _expandir_dies_per_analisi(pla.dies, pla.dia_a_data_iso)
    return {**TextosAnalisi(problema).informes(dies, aplicar_abreviatura_grup), "avisos": pla.cfg.avisos_de_grups()}
