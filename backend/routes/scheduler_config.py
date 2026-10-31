"""
Configuració del planificador d'exàmens d'un centre, tal com la fan servir
generar, analitzar i recalcular el cost: es llegeix d'un sol lloc.
"""

from dataclasses import dataclass
from datetime import date

from database import get_data_db_session
from horari.repositories import XMLVersionRepository
from prioritats.repositories import NoSubstituirRepository
from repositories import (
    ConfiguracioExamenRepository,
    ConfiguracioRepository,
)
from routes.scheduler_helpers import (
    _build_slots_valids_from_alliberaments,
    _build_slots_valids_iso_from_alliberaments,
    _merge_slots_valids,
    _nivells_master,
    _selected_dates_from_alliberaments,
)
from routes.scheduler_service import (
    SCHEDULER_ALLIBERAMENTS_KEY,
    SCHEDULER_DATES_KEY,
    SCHEDULER_DURADA_EXAMEN_KEY,
    SCHEDULER_DURADA_KEY,
    SCHEDULER_DURADES_GRUPS_KEY,
    SCHEDULER_DURADES_SESSIO_KEY,
    SCHEDULER_NIVELLS_KEY,
    _build_config_from_db,
    _build_restriccions_from_db,
    _load_json,
)
from scheduler_engine.defaults import DEFAULT_DURADA_TITULAR


@dataclass
class ConfigPlanificador:
    config: dict  # assignacions d'exàmens per nivell (per al motor)
    restriccions: dict
    durada_titular: int  # hores que el titular vigila (general)
    durada_examen: int  # hores que dura l'examen per a l'alumnat (general)
    nivells_configurats: list
    nivells_master: list
    dates_configurades: list
    alliberaments: dict  # per nivell: dates, hores sense classe i d'inici
    durades_per_sessio: dict  # hores de vigilància de cada examen amb durada pròpia
    durades_examen_per_sessio: dict  # hores d'examen (≥ les de vigilància)
    no_substituir: set
    ultim_professor: str

    def durada_titular_de(self, examen: str) -> int:
        """Hores que el titular vigila un examen: les del seu grup de durada
        o, si no en té, la durada general del titular."""
        return _positiu(self.durades_per_sessio.get(examen)) or self.durada_titular

    def durada_examen_de(self, examen: str) -> int:
        """Hores que dura un examen per a l'alumnat: les del seu grup de durada
        o, si no en té, la durada general de l'examen; mai menys que les del titular."""
        durada = _positiu(self.durades_examen_per_sessio.get(examen)) or self.durada_examen
        return max(durada, self.durada_titular_de(examen))

    def nivells_actius(self, demanats=None) -> list:
        return demanats or self.nivells_configurats or self.nivells_master

    def dates(self, demanades, nivells) -> list:
        """Les dates dels alliberaments dels nivells si n'hi ha; si no, les
        demanades o les desades a la configuració."""
        return (
            _selected_dates_from_alliberaments(self.alliberaments, nivells)
            or demanades
            or self.dates_configurades
            or []
        )


def _positiu(valor) -> int | None:
    try:
        return int(valor) if valor is not None and int(valor) > 0 else None
    except (TypeError, ValueError):
        return None


def _durades(db) -> tuple[dict, dict]:
    """(vigilància, examen) per assignatura, dels grups de durada; sense
    grups, el format antic (una sola durada, la mateixa per a tots dos)."""
    grups = _load_json(ConfiguracioRepository.get(db, SCHEDULER_DURADES_GRUPS_KEY), None)
    if not grups:
        durades = _load_json(ConfiguracioRepository.get(db, SCHEDULER_DURADES_SESSIO_KEY), {})
        return durades, dict(durades)
    vigilancia, examen = {}, {}
    for grup in grups:
        for assignatura in grup.get("assignatures", []):
            vigilancia[assignatura] = grup.get("durada", 1)
            examen[assignatura] = grup.get("durada_examen", grup.get("durada", 1))
    return vigilancia, examen


def carrega_config(institucio: str) -> ConfigPlanificador:
    with get_data_db_session(institucio) as db:
        durada = ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY)
        durada_titular = int(durada) if durada else DEFAULT_DURADA_TITULAR
        durada_examen = _positiu(ConfiguracioRepository.get(db, SCHEDULER_DURADA_EXAMEN_KEY)) or durada_titular
        durades_per_sessio, durades_examen_per_sessio = _durades(db)
        return ConfigPlanificador(
            config=_build_config_from_db(ConfiguracioExamenRepository.get_all(db)),
            restriccions=_build_restriccions_from_db(db),
            durada_titular=durada_titular,
            durada_examen=durada_examen,
            nivells_configurats=_load_json(ConfiguracioRepository.get(db, SCHEDULER_NIVELLS_KEY), []),
            nivells_master=_nivells_master(db),
            dates_configurades=_load_json(ConfiguracioRepository.get(db, SCHEDULER_DATES_KEY), []),
            alliberaments=_load_json(ConfiguracioRepository.get(db, SCHEDULER_ALLIBERAMENTS_KEY), {}),
            durades_per_sessio=durades_per_sessio,
            durades_examen_per_sessio=durades_examen_per_sessio,
            no_substituir=set(NoSubstituirRepository.get_all(db)),
            ultim_professor=ConfiguracioRepository.get(db, "ultim_professor_subs") or "",
        )


def aplica_restriccions_derivades(
    restriccions: dict, alliberaments: dict, nivells: list, dies: list, dia_a_data_iso: dict, hores: list
) -> None:
    """Afegeix a les restriccions dures les que surten dels alliberaments: on
    pot començar l'examen de cada nivell (per dia i per data) i les dates de
    cada nivell."""
    dures = restriccions.setdefault("restriccions_dures", {})
    derivats = _build_slots_valids_from_alliberaments(
        alliberaments_cfg=alliberaments,
        nivells_actius=nivells,
        dies_utilitzar=dies,
        dia_a_data_iso=dia_a_data_iso,
        hores_disponibles=hores,
    )
    dures["slots_valids_per_nivell"] = _merge_slots_valids(dures.get("slots_valids_per_nivell") or {}, derivats)
    dates_per_nivell = {
        niv: [d for d in (alliberaments.get(niv) or {}).get("dates", []) if isinstance(d, str)]
        for niv in (nivells or [])
        if isinstance((alliberaments or {}).get(niv), dict) and (alliberaments[niv].get("dates") or [])
    }
    if dates_per_nivell:
        dures["dates_per_nivell"] = dates_per_nivell
    slots_iso = _build_slots_valids_iso_from_alliberaments(alliberaments, nivells, hores)
    if slots_iso:
        dures["slots_valids_iso_per_nivell"] = slots_iso


def horari_de_la_planificacio(institucio: str, dates: list | None = None) -> dict:
    """Quin horari (XML) fa servir el planificador: el vigent a la primera de
    les dates planificades (les donades o, si no, les desades); sense dates,
    el d'avui. També si les dates cauen en més d'un horari: es planifica amb
    el de la primera i cal avisar-ho."""
    if not dates:
        cfg = carrega_config(institucio)
        dates = cfg.dates(None, cfg.nivells_actius())
    dates = sorted(d for d in (dates or []) if d)
    referencia = dates[0] if dates else date.today().isoformat()
    with get_data_db_session(institucio) as db:
        versions = {}
        for d in dates or [referencia]:
            versio = XMLVersionRepository.vigent(db, d)
            if versio and versio.id not in versions:
                versions[versio.id] = versio
    inicis = sorted(v.data_inici for v in versions.values())
    return {
        "data_referencia": referencia,
        "sense_dates": not dates,
        "versio_des_de": inicis[0].isoformat() if inicis else None,
        # Data en què comença un altre horari dins les dates planificades
        "canvi_horari": inicis[1].isoformat() if len(inicis) > 1 else None,
    }


def data_referencia(institucio: str) -> str:
    """La data de l'horari del planificador (primera data planificada o avui)."""
    return horari_de_la_planificacio(institucio)["data_referencia"]
