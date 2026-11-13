"""Generar l'horari d'exàmens amb un motor (POST /api/scheduler/generate) i
l'anàlisi de disponibilitat (POST /api/scheduler/analisi): la planificació
(planificacio.py), el motor (scheduler_engine/), el precheck i, si no és
viable, el diagnòstic (diagnostic.py)."""

import time
from collections import defaultdict
from datetime import datetime

from errors_domini import NoValid
from errors_servidor import registra_excepcio
from grups.abreviatures import aplicar_abreviatura_grup
from planificador.diagnostic import (
    _afegir_recompte_nivells,
    _diagnosticar_incompatibilitats,
    _identificar_sessions_no_collocades,
    _precheck_incompatibilitats_deterministes,
)
from planificador.planificacio import prepara_planificacio
from planificador.schemas import SchedulerGenerateRequest
from planificador.services import desa_ultim_resultat
from scheduler_engine.core.missatges import missatge, unics
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.informe import captura_informe
from scheduler_engine.validacio import ValidadorHorari

PARAMETRES_V3 = (
    "temperatura_inicial",
    "temperatura_final",
    "factor_refredament",
    "iteracions_per_temperatura",
    "max_iteracions",
)


def _executa_motor(gen, metode: str, motor: str, payload: SchedulerGenerateRequest, pla) -> dict:
    """Genera l'horari amb el motor (els paràmetres propis de cada motor) i
    n'apunta el temps."""
    kwargs = {
        "data_inici": datetime.strptime(payload.data_inici, "%Y-%m-%d").strftime("%d/%m/%Y"),
        "data_inici_iso": payload.data_inici,
        "dies_utilitzar": pla.dies,
        "dia_a_data_iso": pla.dia_a_data_iso,
        "max_dies": payload.max_dies,
        "selected_dates": pla.dates,
    }
    if motor == "v2":
        kwargs.update(
            max_intents_validacio=payload.max_intents_validacio,
            estrategia=payload.estrategia,
            track_intents=True,
        )
    elif motor == "v2-backtrack":
        for clau in ("random_seed", "seeds_count", "max_nodes", "shuffle_top_n"):
            if getattr(payload, clau) is not None:
                kwargs[clau] = getattr(payload, clau)

    t0 = time.monotonic()
    resultat = getattr(gen, metode)(**kwargs)
    temps_ms = int((time.monotonic() - t0) * 1000)

    if motor == "v2-backtrack":
        # Retorna una llista amb un sol horari (el millor de totes les llavors)
        if resultat:
            horari = resultat[0]
            if horari.get("metadata", {}).get("viable", True):
                horari["metadata"]["motor"] = "v2-backtrack"
        else:
            horari = {
                "metadata": {
                    "viable": False,
                    "error": missatge("backtrack_sense_solucio"),
                    "motor": "v2-backtrack",
                },
                "dies": [],
            }
    else:
        horari = resultat
    if isinstance(horari, dict):
        horari.setdefault("metadata", {})["temps_generacio_ms"] = temps_ms
    return horari


def _marca_sessions_pendents(horari: dict, gen) -> None:
    """Recompte per nivell de les sessions col·locades; si en falta alguna,
    l'horari no és viable."""
    sessions_per_nivell = getattr(gen, "sessions_per_nivell", {}) or {}
    if not isinstance(sessions_per_nivell, dict):
        sessions_per_nivell = {}
    sessions = getattr(gen, "sessions", None)
    if sessions and not any(isinstance(v, (list, tuple, set, dict)) and v for v in sessions_per_nivell.values()):
        # El motor no les té per nivell: s'agrupen a partir de la llista
        per_nivell = defaultdict(list)
        for sessio in sessions:
            nivell = sessio.get("curs") if isinstance(sessio, dict) else getattr(sessio, "curs", None)
            if nivell:
                per_nivell[nivell].append(sessio)
        sessions_per_nivell = per_nivell
    _afegir_recompte_nivells(horari, sessions_per_nivell)
    recompte = (horari.get("metadata") or {}).get("recompte_nivells") or {}
    pendents = sum((info or {}).get("pendents", 0) for info in recompte.values())
    if pendents > 0:
        meta = horari.setdefault("metadata", {})
        meta.setdefault("logs", []).append(missatge("sessions_pendents", count=pendents))
        if meta.get("viable", True):
            meta["viable"] = False
            meta["error"] = missatge("examens_pendents")


def _explicacio_no_disponible(meta: dict) -> None:
    """No s'ha pogut preparar (tota) l'explicació de per què no és viable: la
    generació continua, i la resposta ho diu amb la referència del registre
    (la pantalla en mostra l'avís). Es crida des d'un `except`."""
    ref = registra_excepcio("No s'ha pogut preparar l'explicació de l'horari no viable")
    meta.setdefault("explicacio_no_disponible", {"ref": ref})


def _explica_no_viable(horari: dict, gen, pla, del_precheck: bool = False) -> None:
    """Per què no s'han pogut col·locar tots els exàmens: primer el
    diagnòstic de restriccions i després el que n'ha dit el motor, sense
    repetir-los. Si el motor no s'ha executat perquè el precheck ja ho ha
    vist, el precheck només es mostra quan el diagnòstic no diu res: tots dos
    analitzen el mateix i es repetirien amb paraules diferents."""
    meta = horari["metadata"]
    error = meta.get("error", missatge("examens_pendents"))
    try:
        diagnostic = _diagnosticar_incompatibilitats(
            gen=gen,
            restriccions=pla.restriccions,
            dies_utilitzar=pla.dies,
            dia_a_data_iso=pla.dia_a_data_iso,
            alliberaments_cfg=pla.cfg.alliberaments,
            nivells_actius=pla.nivells,
        )
    except Exception:
        _explicacio_no_disponible(meta)
        diagnostic = []
    if diagnostic and del_precheck:
        incompat = diagnostic
    else:
        del_motor = meta.get("incompatibilitats") or getattr(gen, "_incompatibilitats_bt", [])
        if not del_motor:
            try:
                del_motor = _identificar_sessions_no_collocades(horari, gen)
            except Exception:
                _explicacio_no_disponible(meta)
                del_motor = []
        incompat = unics(diagnostic + list(del_motor))
    if meta.get("motiu_aturada"):
        # La cerca s'ha aturat per un límit (temps o nodes), no perquè les
        # restriccions siguin incompatibles: és el primer que s'ha de llegir
        incompat = unics([error] + incompat)
    if incompat:
        meta["incompatibilitats"] = incompat
    meta["logs"] = unics(pla.cfg.avisos(pla.nivells) + meta.get("logs", []) + [error])


def genera(payload: SchedulerGenerateRequest, institucio: str) -> dict:
    """Genera l'horari d'exàmens amb el motor triat i el desa com a últim
    resultat (si és viable). Si no ho és, diu per què."""
    with prepara_planificacio(payload, institucio) as pla:
        if not pla.dates:
            # La pantalla no ho permet: els motors col·loquen exàmens en dates concretes
            raise NoValid("Cal triar les dates dels exàmens", codi="planificacio_sense_dates")
        motor = (payload.motor or "v3").lower()
        parametres = {
            k: getattr(payload, k, None)
            for k in PARAMETRES_V3
            if motor == "v3" and getattr(payload, k, None) is not None
        }
        parametres["segons_maxims"] = payload.segons_maxims

        with captura_informe() as sortida:
            gen, metode = pla.motor(motor, **parametres)
            try:
                incompatibilitats = _precheck_incompatibilitats_deterministes(
                    gen=gen,
                    restriccions=pla.restriccions,
                    dies_utilitzar=pla.dies,
                    nivells_actius=pla.nivells,
                    selected_dates=pla.dates,
                )
            except Exception:
                # La comprovació prèvia només avança el que veuria el motor:
                # si falla, es genera igualment (el detall, al registre)
                registra_excepcio("No s'ha pogut fer la comprovació prèvia de viabilitat")
                incompatibilitats = []
            if incompatibilitats:
                horari = {
                    "dies": [],
                    "metadata": {
                        "viable": False,
                        "error": missatge("examens_pendents"),
                        "incompatibilitats": incompatibilitats,
                        "motor": motor,
                        "logs": [missatge("precheck_detectat")],
                    },
                }
            else:
                horari = _executa_motor(gen, metode, motor, payload, pla)

        if isinstance(horari, dict):
            _marca_sessions_pendents(horari, gen)

        if horari and "metadata" in horari:
            meta = horari["metadata"]
            if not meta.get("viable", True):
                _explica_no_viable(horari, gen, pla, del_precheck=bool(incompatibilitats))
                return {"status": "ok", "horari": horari}

            # Incidències: les del motor, la sortida capturada i la validació

            validacio = ValidadorHorari(horari, pla.restriccions, pla.cfg.no_substituir, pla.dia_a_data_iso).validar()
            logs = [linia.strip() for linia in meta.get("logs", []) if linia.strip()]
            logs += [linia.strip() for linia in sortida.getvalue().splitlines() if linia.strip()]
            logs += validacio["logs"]
            meta["logs"] = pla.cfg.avisos(pla.nivells) + list(dict.fromkeys(logs))

        desa_ultim_resultat(institucio, horari, pla.dies)
        return {"dies_utilitzar": pla.dies, "horari": horari}


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
    """Els tres informes de l'anàlisi de disponibilitat (per franja, per
    examen i professors per franja) amb el motor v2.
    Les dates són les desades a la configuració (no les de la petició)."""
    with prepara_planificacio(payload, institucio, dates_de_la_peticio=False) as pla:
        gen, _ = pla.motor("v2")
        gen.dia_a_data_iso = {normalitzar_dia(k): v for k, v in (pla.dia_a_data_iso or {}).items() if v}
        dies_analisi = _expandir_dies_per_analisi(pla.dies, gen.dia_a_data_iso)
        matriu_costos = gen._analitzar_tots_slots(dies_analisi)
        return {
            "per_slots": gen.generar_informe_per_slots(matriu_costos, dies_analisi),
            "per_sessio": gen.generar_informe_disponibilitat(matriu_costos, dies_analisi),
            "professors_slot": gen.generar_informe_professors_per_slot(
                dies_analisi, aplicar_abreviatura_grup=aplicar_abreviatura_grup
            ),
            "avisos": pla.cfg.avisos_de_grups(),
        }
