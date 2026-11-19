"""Generació nova dels tres motors amb una instantània coherent per petició."""

import random
import time
from dataclasses import replace

from errors_domini import NoValid
from errors_servidor import registra_excepcio
from planificador.compartit.constants import DEFAULT_NIVELLS_ACTIUS, SEGONS_MAXIMS_PER_DEFECTE
from planificador.compartit.missatges import missatge
from planificador.compartit.preparacio import prepara_planificacio
from planificador.motor.avaluador import cost
from planificador.motor.compatibilitat import BACKTRACKING, COST_MOSTRAT, GREEDY, RECUIT
from planificador.motor.construccio import construeix_problema, graella_cost_de_hores
from planificador.motor.cost_cerca import CostCercaBacktracking, CostCercaGreedy, CostCercaRecuit
from planificador.motor.diagnostic import Diagnostic
from planificador.motor.disponibilitat import Disponibilitat
from planificador.motor.estrategies.backtracking import Backtracking
from planificador.motor.estrategies.base import Pressupost
from planificador.motor.estrategies.greedy import Greedy
from planificador.motor.estrategies.recuit import Recuit
from planificador.motor.model import HorariEditable, congela
from planificador.motor.registre import ValidadorHorari
from planificador.motor.regles import construeix_regles
from planificador.motor.sortida import horari_backtracking, horari_greedy, horari_recuit
from planificador.services import desa_ultim_resultat
from textos import normalitzar_hora

PARAMETRES_V3 = (
    "temperatura_inicial",
    "temperatura_final",
    "factor_refredament",
    "iteracions_per_temperatura",
    "max_iteracions",
)


def _problema_cost_mostrat(problema):
    """Projecció de la mateixa instantània a la graella i l'horari del cost.

    En normalitzar claus de l'XML el cost es queda l'última, com el lector
    antic amb normalitza_hores=True; la cerca es queda la primera.
    """
    return replace(
        problema,
        graella=tuple(graella_cost_de_hores(problema.graella, problema.hores_inici)),
        regles=construeix_regles(problema.regles.a_diccionari(), problema.examens, COST_MOSTRAT),
        horaris_professors=congela(
            {
                professor: {
                    dia: {normalitzar_hora(hora): activitat for hora, activitat in hores.items()}
                    for dia, hores in dies.items()
                }
                for professor, dies in problema.horaris_professors.items()
            }
        ),
    )


def genera(payload, institucio):
    motor = (payload.motor or "v3").lower()
    with prepara_planificacio(payload, institucio) as pla:
        if not pla.dates:
            raise NoValid("Cal triar les dates dels exàmens", codi="planificacio_sense_dates")
        if motor not in ("v2", "v3", "v2-backtrack"):
            raise ValueError(f"Motor no suportat: {motor}. Disponibles: {['v3', 'v2', 'v2-backtrack']}")
        politiques = {"v2": GREEDY, "v2-backtrack": BACKTRACKING, "v3": RECUIT}[motor]
        problema = construeix_problema(
            pla.cfg,
            pla.xml_path,
            pla.nivells or list(DEFAULT_NIVELLS_ACTIUS),
            pla.dies,
            sorted(pla.dates),
            pla.dia_a_data_iso,
            pla.hores_examen,
            politiques,
            restriccions_resoltes=pla.restriccions,
        )
        diagnostic = Diagnostic(problema, politiques)
        try:
            incompatibilitats = diagnostic.precheck(pla)
        except Exception:
            registra_excepcio("No s'ha pogut fer la comprovació prèvia de viabilitat")
            incompatibilitats = []
        resultat = None
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
            segons = payload.segons_maxims if payload.segons_maxims is not None else SEGONS_MAXIMS_PER_DEFECTE
            pressupost = Pressupost(segons)
            t0 = time.monotonic()
            if motor == "v2":
                resultat = Greedy().cerca(
                    problema,
                    politiques,
                    CostCercaGreedy(problema),
                    {
                        "max_intents_validacio": payload.max_intents_validacio,
                        "estrategia": payload.estrategia,
                        "track_intents": True,
                    },
                    pressupost,
                    random,
                )
                horari = horari_greedy(resultat, segons, True)
            elif motor == "v3":
                parametres = {
                    clau: getattr(payload, clau) for clau in PARAMETRES_V3 if getattr(payload, clau) is not None
                }
                resultat = Recuit().cerca(
                    problema, politiques, CostCercaRecuit(problema), parametres, pressupost, random
                )
                horari = horari_recuit(resultat, problema, Disponibilitat(problema))
            else:
                parametres = {
                    clau: getattr(payload, clau)
                    for clau in ("seeds_count", "max_nodes", "shuffle_top_n")
                    if getattr(payload, clau) is not None
                }
                resultat = Backtracking().cerca(
                    problema,
                    politiques,
                    CostCercaBacktracking(problema),
                    parametres,
                    pressupost,
                    random.SystemRandom() if payload.random_seed is None else random.Random(payload.random_seed),
                )
                horari = horari_backtracking(
                    resultat,
                    problema,
                    politiques,
                    Disponibilitat(problema),
                    segons,
                    parametres.get("max_nodes", 100000),
                )
            horari["metadata"]["temps_generacio_ms"] = int((time.monotonic() - t0) * 1000)
        diagnostic.marca_pendents(horari)
        meta = horari["metadata"]
        if not meta.get("viable", True):
            diagnostic.explica_no_viable(horari, pla, resultat.causes if resultat else [], bool(incompatibilitats))
            return {"status": "ok", "horari": horari}
        meta["cost_total"] = cost(HorariEditable(horari), _problema_cost_mostrat(problema)).total
        validacio = ValidadorHorari(
            horari, problema.regles.a_diccionari(), problema.no_substituir, pla.dia_a_data_iso
        ).validar()
        logs = [linia.strip() for linia in meta.get("logs", []) if linia.strip()]
        logs += [linia.strip() for linia in resultat.registre if linia.strip()]
        logs += validacio["logs"]
        meta["logs"] = pla.cfg.avisos(pla.nivells) + list(dict.fromkeys(logs))
        desa_ultim_resultat(institucio, horari, pla.dies)
        return {"dies_utilitzar": pla.dies, "horari": horari}
