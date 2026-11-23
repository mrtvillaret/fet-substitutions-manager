"""Configuració i XML inventats per a les proves del motor nou."""

import pytest

from planificador.compartit.nivells import NivellsDelsGrups
from planificador.config import ConfigPlanificador
from planificador.motor import compatibilitat as p
from planificador.motor.construccio import construeix_problema


@pytest.fixture
def config_inventada():
    return ConfigPlanificador(
        config={
            "assignatures": {
                nom: {"assignacions": [{"grup": "N1-A", "titular": "Prof 01", "aula": ""}]} for nom in ("A", "B", "C")
            }
        },
        restriccions={},
        durada_titular=1,
        durada_examen=1,
        nivells_configurats=["N1"],
        nivells_master=["N1"],
        dates_configurades=["2027-03-01"],
        alliberaments={},
        durades_per_sessio={},
        durades_examen_per_sessio={},
        no_substituir=frozenset(),
        ultim_professor="",
        nivells_dels_grups=NivellsDelsGrups({"N1": ["N1-A"]}),
    )


@pytest.fixture
def xml_inventat(tmp_path):
    fitxer = tmp_path / "horari.xml"
    fitxer.write_text(
        '<Teachers_Timetable><Teacher name="Prof 01"><Day name="Dilluns">'
        '<Hour name="09:00"><Subject name="Activitat"/><Students name="N1-A"/></Hour>'
        '<Hour name="PATI"/><Hour name="11:00"/>'
        "</Day></Teacher></Teachers_Timetable>"
    )
    return str(fitxer)


def problema_inventat(cfg, xml):
    return construeix_problema(
        cfg, xml, ["N1"], ["Dilluns"], ["2027-03-01"], {"dilluns": ["2027-03-01"]}, ["09:00", "11:00"], p.RECALCUL
    )
