"""Preparació de les dades d'una petició del planificador (generar i analitzar).

Aquesta frontera d'accés a configuració i XML no és una primitiva pura.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from horari.domain import Dia
from planificador.alliberaments import _hores_lectives_des_de_xml, extreure_hores_examen_des_alliberaments
from planificador.compartit.constants import DIES_SETMANA
from planificador.compartit.dates import construir_mapa_dia_data_iso
from planificador.compartit.horari import xml_del_dia
from planificador.config import ConfigPlanificador, aplica_restriccions_derivades, carrega_config


@dataclass
class Preparacio:
    cfg: ConfigPlanificador
    restriccions: dict
    xml_path: str
    dies: list
    nivells: list
    dates: list
    dia_a_data_iso: dict
    hores_examen: list
    hores_per_nivell: dict

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def _dies_entre_dates(data_inici: str, data_final: str) -> list[str]:
    """Els dies feiners entre les dues dates (AAAA-MM-DD), sense repetir: el cap
    de setmana no hi entra."""
    inici = datetime.strptime(data_inici, "%Y-%m-%d").date()
    final = datetime.strptime(data_final, "%Y-%m-%d").date()
    dies = []
    actual = inici
    while actual <= final:
        if actual.weekday() < len(DIES_SETMANA):
            dia_nom = DIES_SETMANA[actual.weekday()]
            if dia_nom not in dies:
                dies.append(dia_nom)
        actual += timedelta(days=1)
    return dies


def prepara_planificacio(payload, institucio: str, dates_de_la_peticio: bool = True) -> Preparacio:
    """`payload`: SchedulerGenerateRequest. Sense `dates_de_la_peticio` (anàlisi),
    les dates són les desades a la configuració, no les de la petició."""
    cfg = carrega_config(institucio)
    hores_examen, hores_per_nivell = extreure_hores_examen_des_alliberaments(cfg.alliberaments)

    xml_path = xml_del_dia(Dia.de_text(payload.data_inici, institucio))

    dies = payload.dies_utilitzar or _dies_entre_dates(payload.data_inici, payload.data_final or payload.data_inici)
    nivells = cfg.nivells_actius(payload.nivells_actius)
    dates = cfg.dates(payload.selected_dates if dates_de_la_peticio else None, nivells)
    dia_a_data_iso = construir_mapa_dia_data_iso(
        dies_utilitzar=dies, selected_dates=dates, data_inici_iso=payload.data_inici
    )

    # Restriccions derivades de les marques del calendari (on pot començar cada examen)
    restriccions = cfg.restriccions
    hores_xml = _hores_lectives_des_de_xml(xml_path, fallback=hores_examen)
    aplica_restriccions_derivades(restriccions, cfg.alliberaments, nivells, dies, dia_a_data_iso, hores_xml)

    return Preparacio(
        cfg=cfg,
        restriccions=restriccions,
        xml_path=xml_path,
        dies=dies,
        nivells=nivells,
        dates=dates,
        dia_a_data_iso=dia_a_data_iso,
        hores_examen=hores_examen,
        hores_per_nivell=hores_per_nivell,
    )
