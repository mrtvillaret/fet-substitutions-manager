"""Servei nou del recàlcul: prepara, avalua, formata i usa la persistència comuna."""

from errors_domini import NoValid
from horari.domain import Dia
from planificador.alliberaments import extreure_hores_examen_des_alliberaments
from planificador.compartit.horari import xml_del_dia
from planificador.config import carrega_config
from planificador.motor.avaluador import cost
from planificador.motor.compatibilitat import RECALCUL
from planificador.motor.construccio import construeix_problema, mapa_dies
from planificador.motor.disponibilitat import Disponibilitat
from planificador.motor.model import HorariEditable
from planificador.motor.sortida import finalitza_recalcul
from planificador.services import desa_ultim_resultat


def recalcula(payload, institucio: str, dia_planificacio: Dia) -> dict:
    document = payload.horari.model_dump(exclude_unset=True, by_alias=True)
    if not document or not document.get("dies"):
        raise NoValid("L'horari no conté dies", codi="horari_sense_dies")
    cfg = carrega_config(institucio)
    nivells = cfg.nivells_actius()
    dates = cfg.dates(payload.selected_dates, nivells)
    hores, _ = extreure_hores_examen_des_alliberaments(cfg.alliberaments)
    referencia = payload.data_referencia or (document.get("metadata") or {}).get("data_inici")
    dia = Dia.de_text(referencia, institucio) if referencia else dia_planificacio
    dies = [d.get("dia") for d in document.get("dies", []) if d.get("dia")]
    mapa = mapa_dies(dies, dates, dia.iso)
    problema = construeix_problema(cfg, xml_del_dia(dia), nivells, dies, dates, mapa, hores, RECALCUL)
    editable = HorariEditable(document)
    disponible = Disponibilitat(problema)
    resultat_cost = cost(editable, problema, disponible)
    # Els avisos de configuració es formaten després de les anàlisis, com al motor antic.
    horari_desat, resposta = finalitza_recalcul(
        editable, problema, resultat_cost, disponible, lambda: cfg.avisos(nivells)
    )
    desa_ultim_resultat(institucio, horari_desat)
    return resposta
