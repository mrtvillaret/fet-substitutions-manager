"""
Factory de motors del scheduler d'exàmens.
Registre centralitzat de motors amb metadades per l'API.
"""

from typing import List, Tuple, Any
from scheduler_engine.defaults import DEFAULT_SA_PARAMS, DEFAULT_GREEDY_PARAMS


# Registre de motors disponibles
MOTORS = {
    "v3": {
        "module": "scheduler_engine.generators.v3_sa",
        "class_name": "GeneradorV3SA",
        "label": "Optimització progressiva (SA)",
        "method": "generar_horari_optimitzat",
        "params": DEFAULT_SA_PARAMS,
        "param_labels": {
            "temperatura_inicial": {
                "label": "Temperatura inicial",
                "help": "Controla l'exploració inicial (més alt = més exploració)",
                "type": "number", "min": 1, "max": 10000, "step": 100,
            },
            "temperatura_final": {
                "label": "Temperatura final",
                "help": "Punt on s'atura el refinament",
                "type": "number", "min": 0.001, "max": 1, "step": 0.01,
            },
            "factor_refredament": {
                "label": "Factor de refredament",
                "help": "0.9 = ràpid, 0.999 = lent (valors lents necessiten més iteracions per convergir)",
                "type": "number", "min": 0.5, "max": 0.9999, "step": 0.0001,
            },
            "iteracions_per_temperatura": {
                "label": "Iteracions per temperatura",
                "help": "Proves per cada nivell de temperatura",
                "type": "number", "min": 10, "max": 5000, "step": 10,
            },
            "max_iteracions": {
                "label": "Límit global d'iteracions",
                "help": "Nombre màxim total d'iteracions",
                "type": "number", "min": 1000, "max": 1000000, "step": 1000,
            },
        },
    },
    "v2": {
        "module": "scheduler_engine.generators.v2_intents",
        "class_name": "GeneradorV2Intents",
        "label": "Millor de molts intents (Greedy)",
        "method": "generar_horari_optimitzat",
        "params": DEFAULT_GREEDY_PARAMS,
        "param_labels": {
            "estrategia": {
                "label": "Estratègia",
                "help": "Com es prioritza la cerca",
                "type": "select",
                "options": [
                    {"label": "Ponderada", "value": "ponderada"},
                    {"label": "Epsilon Greedy", "value": "epsilon_greedy"},
                    {"label": "Greedy", "value": "greedy"},
                ],
                "main": True,
            },
            "max_intents_validacio": {
                "label": "Nombre d'intents",
                "help": "Quantes solucions es proven per trobar la millor",
                "type": "number", "min": 10, "max": 5000, "step": 10,
                "main": True,
            },
            "epsilon": {
                "label": "Epsilon",
                "help": "Probabilitat d'acceptar pitjors solucions (exploració)",
                "type": "number", "min": 0, "max": 1, "step": 0.05,
            },
        },
    },
    "v2-backtrack": {
        "module": "scheduler_engine.generators.v2_backtrack",
        "class_name": "GeneradorV2Backtrack",
        "label": "Exploració exhaustiva (Backtracking)",
        "method": "generar_totes_solucions_optimes",
        "params": {
            "random_seed": None,
            "seeds_count": 1,
            "max_nodes": 100000,
            "shuffle_top_n": 0,
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
        },
    },
}


def crear_motor(motor_id: str, config_path: str, xml_path: str,
                restriccions_path: str = None, ultim_professor: str = "",
                nivells_actius: List[str] = None, hores_examen: List[str] = None,
                hores_per_nivell: dict = None,
                durada_titular: int = 1, no_substituir: set = None,
                alliberaments_per_nivell: dict = None,
                durades_per_sessio: dict = None,
                durades_examen_per_sessio: dict = None,
                **override_params) -> Tuple[Any, str]:
    """
    Crea una instància del motor especificat.

    Args:
        motor_id: Identificador del motor ('v2', 'v3', 'v2-backtrack')
        config_path: Ruta al fitxer de configuració d'exàmens
        xml_path: Ruta al fitxer XML d'horaris
        restriccions_path: Ruta al fitxer de restriccions (opcional)
        ultim_professor: Últim professor a processar
        nivells_actius: Nivells actius per l'scheduler
        hores_examen: Hores d'examen globals
        hores_per_nivell: Hores d'examen específiques per nivell (opcional)
        durada_titular: Durada titular en hores
        no_substituir: Assignatures que no necessiten substitució
        alliberaments_per_nivell: Dict amb estructura per nivell i data/hora d'alliberaments
        durades_per_sessio: Durades de supervisió per sessió {"Nom (NIVELL)": hores}
        durades_examen_per_sessio: Durades de l'examen per l'alumne {"Nom (NIVELL)": hores}
        **override_params: Paràmetres específics del motor a sobreescriure

    Returns:
        Tuple (instància_motor, nom_mètode_a_cridar)

    Raises:
        ValueError: Si el motor_id no és vàlid
    """
    motor_info = MOTORS.get(motor_id)
    if not motor_info:
        raise ValueError(f"Motor no suportat: {motor_id}. Disponibles: {list(MOTORS.keys())}")

    # Import dinàmic
    import importlib
    module = importlib.import_module(motor_info["module"])
    cls = getattr(module, motor_info["class_name"])

    gen = cls(
        config_path, xml_path,
        restriccions_path=restriccions_path,
        ultim_professor=ultim_professor,
        nivells_actius=nivells_actius,
        hores_examen=hores_examen,
        hores_per_nivell=hores_per_nivell,
        durada_titular=durada_titular,
        no_substituir=no_substituir,
        alliberaments_per_nivell=alliberaments_per_nivell,
        durades_per_sessio=durades_per_sessio,
        durades_examen_per_sessio=durades_examen_per_sessio,
    )

    # Aplicar paràmetres específics del motor
    for key, value in override_params.items():
        if value is not None and hasattr(gen, key):
            setattr(gen, key, value)

    return gen, motor_info["method"]


def get_motors_info() -> list:
    """
    Retorna informació dels motors disponibles per l'API.
    Usat per l'endpoint GET /api/scheduler/motors.
    """
    result = []
    for motor_id, info in MOTORS.items():
        result.append({
            "id": motor_id,
            "label": info["label"],
            "params": info["params"],
            "param_labels": info["param_labels"],
        })
    return result
