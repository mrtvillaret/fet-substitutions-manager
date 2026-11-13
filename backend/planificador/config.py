"""
Configuració del planificador d'exàmens d'un centre, tal com la fan servir
generar, analitzar i recalcular el cost: es llegeix d'un sol lloc.
"""

from dataclasses import dataclass, field

import rellotge
from configuracio.repositories import ConfiguracioRepository
from configuracio_examens.repositories import ConfiguracioExamenRepository
from database import get_data_db_session
from horari.repositories import XMLVersionRepository
from planificador import restriccions
from planificador.alliberaments import (
    _build_slots_valids_from_alliberaments,
    _build_slots_valids_iso_from_alliberaments,
    _merge_slots_valids,
    _selected_dates_from_alliberaments,
)
from planificador.examens import nivells_dels_grups, nivells_master
from planificador.repositories import (
    SCHEDULER_ALLIBERAMENTS_KEY,
    SCHEDULER_DATES_KEY,
    SCHEDULER_DURADA_EXAMEN_KEY,
    SCHEDULER_DURADA_KEY,
    SCHEDULER_DURADES_GRUPS_KEY,
    SCHEDULER_NIVELLS_KEY,
    llegeix_json,
)
from prioritats.repositories import NoSubstituirRepository
from scheduler_engine.core.missatges import missatge
from scheduler_engine.core.nivells import NivellsDelsGrups
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
    no_substituir: frozenset  # la llista vigent a la data de l'horari del planificador
    ultim_professor: str
    # El nivell de cada grup: les taules de la configuració d'exàmens (també dins de `config`)
    nivells_dels_grups: NivellsDelsGrups = field(default_factory=NivellsDelsGrups)

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

    def avisos(self, nivells: list | None = None) -> list:
        """Avisos de la configuració que la pantalla mostra amb el resultat:
        - sense cap alliberament definit, cada nivell actiu (`nivells`): l'anàlisi
          el considera lliure tot el dia (availability._nivell_alliberat_a_slot;
          no es canvia, només s'avisa);
        - si n'hi ha, cada nivell actiu que hi surt però no té cap hora «a»:
          l'anàlisi no el considera lliure a cap hora (tampoc no es canvia);
        - cada grup de les assignacions que no és a cap nivell (els seus
          exàmens no es planifiquen; no es dedueix el nivell del nom)."""
        avisos = []
        if not self.alliberaments:
            avisos += [missatge("nivell_sense_hores_alliberades", nivell=nivell) for nivell in nivells or []]
        else:
            avisos += [
                missatge("nivell_alliberaments_sense_hores", nivell=nivell)
                for nivell in nivells or []
                if nivell in self.alliberaments and not _te_alguna_hora_alliberada(self.alliberaments[nivell])
            ]
        return avisos + self.avisos_de_grups()

    def avisos_de_grups(self) -> list:
        """Un avís per a cada grup de les assignacions que no és a cap nivell,
        amb les seves assignatures (també al diàleg de no viable i a l'anàlisi)."""
        per_grup: dict[str, list] = {}
        for assignatura, dades in (self.config.get("assignatures") or {}).items():
            for assignacio in dades.get("assignacions", []):
                for grup in self.nivells_dels_grups.sense_nivell(assignacio.get("grup") or ""):
                    noms = per_grup.setdefault(grup, [])
                    if assignatura not in noms:
                        noms.append(assignatura)
        return [
            missatge("grup_sense_nivell", grup=grup, assignatures=sorted(noms))
            for grup, noms in sorted(per_grup.items())
        ]

    def dates(self, demanades, nivells) -> list:
        """Les dates dels alliberaments dels nivells si n'hi ha; si no, les
        demanades o les desades a la configuració."""
        return (
            _selected_dates_from_alliberaments(self.alliberaments, nivells)
            or demanades
            or self.dates_configurades
            or []
        )


def _te_alguna_hora_alliberada(dades) -> bool:
    """Si algun dia del nivell té una hora «a» (la mateixa marca que mira
    availability._nivell_alliberat_a_slot)."""
    config = dades.get("config") if isinstance(dades, dict) else None
    if not isinstance(config, dict):
        return False
    return any(
        isinstance(marques, dict) and marques.get("a") is True
        for hores in config.values()
        if isinstance(hores, dict)
        for marques in hores.values()
    )


def _positiu(valor) -> int | None:
    try:
        return int(valor) if valor is not None and int(valor) > 0 else None
    except (TypeError, ValueError):
        return None


def _durades(db) -> tuple[dict, dict]:
    """(vigilància, examen) per assignatura, dels grups de durada."""
    vigilancia, examen = {}, {}
    for grup in llegeix_json(db, SCHEDULER_DURADES_GRUPS_KEY, None) or []:
        for assignatura in grup.get("assignatures", []):
            vigilancia[assignatura] = grup.get("durada", 1)
            examen[assignatura] = grup.get("durada_examen", grup.get("durada", 1))
    return vigilancia, examen


def _config_dels_motors(assignacions, taules: NivellsDelsGrups) -> dict:
    """Les assignacions per assignatura i les taules dels nivells, com les
    llegeixen els motors."""
    config = {"assignatures": {}, **taules.a_config()}
    for a in assignacions:
        nom = a.get("assignatura") if isinstance(a, dict) else a.assignatura
        if nom not in config["assignatures"]:
            config["assignatures"][nom] = {"assignacions": []}
        config["assignatures"][nom]["assignacions"].append(
            {
                "grup": a.get("grup") if isinstance(a, dict) else a.grup,
                "titular": a.get("titular") if isinstance(a, dict) else a.titular or "",
                "aula": a.get("aula") if isinstance(a, dict) else a.aula or "",
            }
        )
    return config


def carrega_config(institucio: str) -> ConfigPlanificador:
    with get_data_db_session(institucio, lectura=True) as db:
        durada = ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY)
        durada_titular = int(durada) if durada else DEFAULT_DURADA_TITULAR
        durada_examen = _positiu(ConfiguracioRepository.get(db, SCHEDULER_DURADA_EXAMEN_KEY)) or durada_titular
        durades_per_sessio, durades_examen_per_sessio = _durades(db)
        alliberaments = llegeix_json(db, SCHEDULER_ALLIBERAMENTS_KEY, {})
        nivells_configurats = llegeix_json(db, SCHEDULER_NIVELLS_KEY, [])
        nivells = nivells_configurats or nivells_master(db)
        dates_configurades = llegeix_json(db, SCHEDULER_DATES_KEY, [])
        # «No substituir», el de la mateixa data que l'horari (XML) del
        # planificador: la primera data planificada o, sense dates, avui.
        dates = _selected_dates_from_alliberaments(alliberaments, nivells) or dates_configurades
        taules = nivells_dels_grups(db)
        return ConfigPlanificador(
            config=_config_dels_motors(ConfiguracioExamenRepository.get_all(db), taules),
            restriccions=restriccions.llegeix(db),
            durada_titular=durada_titular,
            durada_examen=durada_examen,
            nivells_configurats=nivells_configurats,
            nivells_master=nivells_master(db),
            dates_configurades=dates_configurades,
            alliberaments=alliberaments,
            durades_per_sessio=durades_per_sessio,
            durades_examen_per_sessio=durades_examen_per_sessio,
            no_substituir=NoSubstituirRepository.vigents_a(db, _data_de_referencia(dates)),
            ultim_professor=ConfiguracioRepository.get(db, "ultim_professor_subs") or "",
            nivells_dels_grups=taules,
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


def _data_de_referencia(dates) -> str:
    """La data de l'horari del planificador: la primera de les planificades;
    sense dates, avui."""
    dates = sorted(d for d in (dates or []) if d)
    return dates[0] if dates else rellotge.avui().isoformat()


def horari_de_la_planificacio(institucio: str, dates: list | None = None) -> dict:
    """Quin horari (XML) fa servir el planificador: el vigent a la primera de
    les dates planificades (les donades o, si no, les desades); sense dates,
    el d'avui. També si les dates cauen en més d'un horari: es planifica amb
    el de la primera i cal avisar-ho."""
    if not dates:
        cfg = carrega_config(institucio)
        dates = cfg.dates(None, cfg.nivells_actius())
    dates = sorted(d for d in (dates or []) if d)
    referencia = _data_de_referencia(dates)
    with get_data_db_session(institucio, lectura=True) as db:
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
