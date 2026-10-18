"""
Preparació d'una planificació d'exàmens (generar i analitzar): la
configuració, l'horari (XML) de les dates, els dies i nivells, les
restriccions que surten dels alliberaments i el motor ja carregat.

    with prepara_planificacio(payload, institucio) as pla:
        gen, metode = pla.motor("v3")
        ...
"""
import json
import os
import tempfile
from dataclasses import dataclass, field

from fastapi import HTTPException

from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso
from serveis.dia import Dia

from routes.scheduler_config import ConfigPlanificador, aplica_restriccions_derivades, carrega_config
from routes.scheduler_helpers import _hores_lectives_des_de_xml, extreure_hores_examen_des_alliberaments
from routes.scheduler_service import _dies_entre_dates


@dataclass
class Planificacio:
    cfg: ConfigPlanificador
    restriccions: dict               # les de la configuració + les derivades dels alliberaments
    xml_path: str
    dies: list                       # dies de la setmana a planificar («Dilluns», ...)
    nivells: list
    dates: list                      # dates triades (AAAA-MM-DD)
    dia_a_data_iso: dict
    hores_examen: list               # hores on pot començar un examen (marques «i»)
    hores_per_nivell: dict
    _fitxers: list = field(default_factory=list)

    def motor(self, nom: str, **parametres):
        """El motor `nom` amb les dades i l'horari dels professors carregats:
        (generador, nom del mètode que genera)."""
        from scheduler_engine.factory import crear_motor
        gen, metode = crear_motor(
            nom, self._fitxer(self.cfg.config), self.xml_path,
            restriccions_path=self._fitxer(self.restriccions),
            ultim_professor=self.cfg.ultim_professor,
            nivells_actius=self.nivells,
            hores_examen=self.hores_examen,
            hores_per_nivell=self.hores_per_nivell,
            durada_titular=self.cfg.durada_titular,
            no_substituir=self.cfg.no_substituir,
            alliberaments_per_nivell=self.cfg.alliberaments,
            durades_per_sessio=self.cfg.durades_per_sessio,
            durades_examen_per_sessio=self.cfg.durades_examen_per_sessio,
            **parametres,
        )
        gen.carregar_dades()
        gen.carregar_horaris_professors()
        return gen, metode

    def _fitxer(self, dades) -> str:
        """Els motors llegeixen la configuració i les restriccions de fitxers JSON temporals."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(dades, f, ensure_ascii=False)
        self._fitxers.append(f.name)
        return f.name

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for ruta in self._fitxers:
            try:
                os.remove(ruta)
            except OSError:
                pass


def prepara_planificacio(payload, institucio: str, dates_de_la_peticio: bool = True) -> Planificacio:
    """`payload`: SchedulerGenerateRequest. Sense `dates_de_la_peticio` (anàlisi),
    les dates són les desades a la configuració, no les de la petició."""
    cfg = carrega_config(institucio)
    hores_examen, hores_per_nivell = extreure_hores_examen_des_alliberaments(cfg.alliberaments)

    xml_path = Dia.de_text(payload.data_inici, institucio).xml_path
    if not xml_path or not os.path.exists(xml_path):
        raise HTTPException(status_code=400, detail="XML missing")

    dies = payload.dies_utilitzar or _dies_entre_dates(payload.data_inici, payload.data_final or payload.data_inici)
    nivells = cfg.nivells_actius(payload.nivells_actius)
    dates = cfg.dates(payload.selected_dates if dates_de_la_peticio else None, nivells)
    dia_a_data_iso = construir_mapa_dia_data_iso(dies_utilitzar=dies, selected_dates=dates,
                                                 data_inici_iso=payload.data_inici)

    # Restriccions derivades de les marques del calendari (on pot començar cada examen)
    restriccions = cfg.restriccions
    hores_xml = _hores_lectives_des_de_xml(xml_path, fallback=hores_examen)
    aplica_restriccions_derivades(restriccions, cfg.alliberaments, nivells, dies, dia_a_data_iso, hores_xml)

    return Planificacio(cfg=cfg, restriccions=restriccions, xml_path=xml_path, dies=dies, nivells=nivells,
                        dates=dates, dia_a_data_iso=dia_a_data_iso, hores_examen=hores_examen,
                        hores_per_nivell=hores_per_nivell)
