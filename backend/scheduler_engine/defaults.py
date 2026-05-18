"""
Constants centralitzades per al scheduler d'exàmens.
Punt únic de veritat per a tots els defaults del sistema.
"""

from scheduler_engine.core.normalitzacio import DIES_MAPEJAT, normalitzar_dia

DIES_SETMANA = ['Dilluns', 'Dimarts', 'Dimecres', 'Dijous', 'Divendres']


# Costos globals de professors (percentatge 0-100)
# Usat per la ruta i el motor V3
DEFAULT_COST_PROFESSORS = {
    "substitucio": 80,
    "abans_jornada": 30,
    "despres_jornada": 30,
    "no_treballa_dia": 60,
}

# Paràmetres Simulated Annealing (motor V3)
# factor_refredament=0.9 → refredament molt ràpid; T inicial alta (8000) compensa amb bona exploració inicial
# 0.9^passos: 8000→0.01 en ~107 passos → amb 500 iter/T = 53500 iteracions efectives
DEFAULT_SA_PARAMS = {
    "temperatura_inicial": 8000.0,
    "temperatura_final": 0.01,
    "factor_refredament": 0.9,
    "iteracions_per_temperatura": 500,
    "max_iteracions": 200000,
    "intents_solucio_inicial": 50,
}

# Paràmetres Greedy (motor V2)
DEFAULT_GREEDY_PARAMS = {
    "max_intents_validacio": 250,
    "estrategia": "ponderada",
    "epsilon": 0.2,
}

# Nivells per defecte
DEFAULT_NIVELLS_ACTIUS = ["1-BATX", "2-BATX"]
DEFAULT_DURADA_TITULAR = 1  # Nombre d'hores lectives que dura l'examen

# Pesos de restriccions per al càlcul de costos
DEFAULT_PES_ZONA_EXAMEN = 5               # Soft cost per conflicte a la zona d'examen sense titular
DEFAULT_PES_RESTRICCIO_DURA = 10000       # Cost base per restricció dura
DEFAULT_PES_RESTRICCIO_VIOLADA = 20000    # Cost per restricció dura violada
DEFAULT_PES_RESTRICCIO_PROHIBITIU = 10000000  # Cost prohibitiu (mandatori absolut)

# Etiquetes llegibles per a cada clau de restricció (backend → frontend)
ETIQUETES_RESTRICCIONS: dict[str, str] = {
    "substitucio": "Substitució",
    "abans_jornada": "Arriba abans de la jornada",
    "despres_jornada": "Queda més estona",
    "no_treballa_dia": "No treballa aquest dia",
    "zona_examen": "En zona d'examen",
    "no_mateix_slot": "No al mateix moment",
    "no_mateix_dia": "Dies distints",
    "dia_hora_fix": "Dia/hora fixat",
    "limit_dies_professor": "Límit exàmens professor",
    "combinacions_permeses": "Combinació no permesa",
    "preferencia_dia": "Preferència de dia",
    "professors_estrictes": "Horari estricte professor",
}

# Estructura de restriccions per defecte
DEFAULT_RESTRICCIONS = {
    "restriccions_dures": {
        "mateix_slot": [],
        "no_mateix_slot": {},
        "no_mateix_dia": [],
        "combinacions_permeses": [],
        "assignatures_dia_fix": {},
        "assignatures_hora_fix": {},
    },
    "preferencies": {
        "dies_diferents": [],
        "mateix_dia": [],
    },
    "costos_professors": {
        "globals": {
            "substitucio": DEFAULT_COST_PROFESSORS["substitucio"],
            "abans_jornada": DEFAULT_COST_PROFESSORS["abans_jornada"],
            "despres_jornada": DEFAULT_COST_PROFESSORS["despres_jornada"],
            "no_treballa_dia": DEFAULT_COST_PROFESSORS["no_treballa_dia"],
        },
        "individuals": {},
    },
    "pesos_optimitzacio": {
        "restriccio_dura": DEFAULT_PES_RESTRICCIO_DURA,
        "restriccio_dura_violada": DEFAULT_PES_RESTRICCIO_VIOLADA,
    },
}
