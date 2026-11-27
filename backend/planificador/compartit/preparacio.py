"""Preparació de les dades d'una petició del planificador (generar i analitzar).

Aquesta frontera d'accés a configuració i XML no és una primitiva pura.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace

from horari.domain import Dia
from planificador.alliberaments import _hores_lectives_des_de_xml, extreure_hores_examen_des_alliberaments
from planificador.compartit.constants import DIES_SETMANA
from planificador.compartit.dates import construir_mapa_dia_data, mapa_per_al_motor
from planificador.compartit.horari import xml_del_dia
from planificador.config import ConfigMotor, ConfigPlanificador, deriva_restriccions, llegeix_config
from planificador.documents import document_iso
from planificador.schemas import SchedulerGenerateRequest


@dataclass
class Preparacio:
    cfg: ConfigPlanificador
    restriccions: dict
    xml_path: str
    dies: list[str]
    nivells: list[str]
    dates: list[date]
    dia_a_data: dict[str, list[date]]
    hores_examen: list[str]
    hores_per_nivell: dict[str, list[str]]

    def per_al_motor(self) -> SimpleNamespace:
        return SimpleNamespace(
            cfg=ConfigMotor(self.cfg),
            restriccions=document_iso(self.restriccions),
            xml_path=self.xml_path,
            dies=self.dies,
            nivells=self.nivells,
            dates=document_iso(self.dates),
            dia_a_data_iso=mapa_per_al_motor(self.dia_a_data),
            hores_examen=self.hores_examen,
            hores_per_nivell=self.hores_per_nivell,
        )


def _dies_entre_dates(data_inici: date, data_final: date) -> list[str]:
    """Els dies feiners entre les dues dates (AAAA-MM-DD), sense repetir: el cap
    de setmana no hi entra."""
    dies = []
    actual = data_inici
    while actual <= data_final:
        if actual.weekday() < len(DIES_SETMANA):
            dia_nom = DIES_SETMANA[actual.weekday()]
            if dia_nom not in dies:
                dies.append(dia_nom)
        actual += timedelta(days=1)
    return dies


def prepara_planificacio(
    payload: SchedulerGenerateRequest, institucio: str, dates_de_la_peticio: bool = True
) -> Preparacio:
    """`payload`: SchedulerGenerateRequest. Sense `dates_de_la_peticio` (anàlisi),
    les dates són les desades a la configuració, no les de la petició."""
    cfg = llegeix_config(institucio)
    hores_examen, hores_per_nivell = extreure_hores_examen_des_alliberaments(cfg.alliberaments)

    xml_path = xml_del_dia(Dia(payload.data_inici, institucio))

    dies = payload.dies_utilitzar or _dies_entre_dates(payload.data_inici, payload.data_final or payload.data_inici)
    nivells = cfg.nivells_actius(payload.nivells_actius)
    dates = cfg.dates(payload.selected_dates if dates_de_la_peticio else None, nivells)
    dia_a_data = construir_mapa_dia_data(dies, dates, payload.data_inici)

    # Restriccions derivades de les marques del calendari (on pot començar cada examen)
    restriccions = cfg.restriccions
    hores_xml = _hores_lectives_des_de_xml(xml_path, fallback=hores_examen)
    deriva_restriccions(restriccions, cfg.alliberaments, nivells, dies, dia_a_data, hores_xml)

    return Preparacio(
        cfg=cfg,
        restriccions=restriccions,
        xml_path=xml_path,
        dies=dies,
        nivells=nivells,
        dates=dates,
        dia_a_data=dia_a_data,
        hores_examen=hores_examen,
        hores_per_nivell=hores_per_nivell,
    )
