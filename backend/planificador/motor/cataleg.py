"""Contracte públic dels motors: etiquetes i paràmetres."""

from planificador.compartit.constants import (
    DEFAULT_GREEDY_PARAMS,
    DEFAULT_SA_PARAMS,
    SEGONS_MAXIMS_LIMIT,
    SEGONS_MAXIMS_PER_DEFECTE,
)

PARAM_SEGONS_MAXIMS = {
    "segons_maxims": {
        "label": "Temps màxim (segons)",
        "help": "Quant pot durar la cerca com a màxim; si s'acaba el temps, es queda amb la millor solució trobada",
        "type": "number",
        "min": 1,
        "max": SEGONS_MAXIMS_LIMIT,
        "step": 5,
    }
}

MOTORS = {
    "v3": {
        "label": "Optimització progressiva (SA)",
        "params": {**DEFAULT_SA_PARAMS, "segons_maxims": SEGONS_MAXIMS_PER_DEFECTE},
        "param_labels": {
            "temperatura_inicial": {
                "label": "Temperatura inicial",
                "help": "Controla l'exploració inicial (més alt = més exploració)",
                "type": "number",
                "min": 1,
                "max": 10000,
                "step": 10,
            },
            "temperatura_final": {
                "label": "Temperatura final",
                "help": "Punt on s'atura el refinament",
                "type": "number",
                "min": 0.001,
                "max": 1,
                "step": 0.01,
            },
            "factor_refredament": {
                "label": "Factor de refredament",
                "help": "0.9 = ràpid, 0.999 = lent (valors lents necessiten més iteracions per convergir)",
                "type": "number",
                "min": 0.5,
                "max": 0.9999,
                "step": 0.0001,
            },
            "iteracions_per_temperatura": {
                "label": "Iteracions per temperatura",
                "help": "Proves per cada nivell de temperatura",
                "type": "number",
                "min": 10,
                "max": 5000,
                "step": 10,
            },
            "max_iteracions": {
                "label": "Límit global d'iteracions",
                "help": "Nombre màxim total d'iteracions",
                "type": "number",
                "min": 1000,
                "max": 1000000,
                "step": 1000,
            },
            **PARAM_SEGONS_MAXIMS,
        },
    },
    "v2": {
        "label": "Millor de molts intents (Greedy)",
        "params": {**DEFAULT_GREEDY_PARAMS, "segons_maxims": SEGONS_MAXIMS_PER_DEFECTE},
        "param_labels": {
            "estrategia": {
                "label": "Estratègia",
                "help": "Com es prioritza la cerca",
                "type": "select",
                "options": [{"label": "Ponderada", "value": "ponderada"}, {"label": "Greedy", "value": "greedy"}],
                "main": True,
            },
            "max_intents_validacio": {
                "label": "Nombre d'intents",
                "help": "Quantes solucions es proven per trobar la millor",
                "type": "number",
                "min": 10,
                "max": 5000,
                "step": 10,
                "main": True,
            },
            **PARAM_SEGONS_MAXIMS,
        },
    },
    "v2-backtrack": {
        "label": "Exploració exhaustiva (Backtracking)",
        "params": {
            "random_seed": None,
            "seeds_count": 1,
            "max_nodes": 100000,
            "shuffle_top_n": 0,
            "segons_maxims": SEGONS_MAXIMS_PER_DEFECTE,
        },
        "param_labels": {
            "random_seed": {
                "label": "Seed aleatòria",
                "help": "Canvia el resultat del backtracking (mateixa seed = mateixa solució)",
                "type": "number",
                "min": 0,
                "max": 1000000,
                "step": 1,
            },
            "seeds_count": {
                "label": "Nombre de seeds",
                "help": "Provar múltiples seeds i quedar-se amb la millor solució",
                "type": "number",
                "min": 1,
                "max": 50,
                "step": 1,
                "main": True,
            },
            "max_nodes": {
                "label": "Límit de nodes",
                "help": "Nodes màxims a explorar (més alt = més exhaustiu però més lent)",
                "type": "number",
                "min": 1000,
                "max": 10000000,
                "step": 10000,
                "main": True,
            },
            "shuffle_top_n": {
                "label": "Aleatorietat (top-N)",
                "help": "Quants dels millors slots es barregen per seed (0 = determinista i ràpid, 3 = equilibrat, 5 = molt aleatori)",
                "type": "number",
                "min": 0,
                "max": 10,
                "step": 1,
                "main": True,
            },
            **PARAM_SEGONS_MAXIMS,
        },
    },
}


def informacio_motors() -> list:
    """
    Retorna informació dels motors disponibles per l'API.
    Usat per l'endpoint GET /api/scheduler/motors.
    """
    resultat = []
    for motor_id, info in MOTORS.items():
        resultat.append(
            {
                "id": motor_id,
                "label": info["label"],
                "params": info["params"],
                "param_labels": info["param_labels"],
            }
        )
    return resultat
