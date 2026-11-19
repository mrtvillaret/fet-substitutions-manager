"""Accés a l’XML resolt per data, compartit pels dos camins del planificador."""

import os

from errors_domini import NoValid
from horari.domain import Dia


def xml_del_dia(dia: Dia) -> str:
    """El fitxer de l'horari (XML) vigent un dia; si no n'hi ha, NoValid."""
    if not dia.xml_path or not os.path.exists(dia.xml_path):
        data = f"{dia.data:%d/%m/%Y}"
        raise NoValid(f"No hi ha cap horari (XML) per al {data}", codi="planificacio_sense_xml", params={"data": data})
    return dia.xml_path
