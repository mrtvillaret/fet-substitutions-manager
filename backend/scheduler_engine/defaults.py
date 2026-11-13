"""
Constants centralitzades per al scheduler d'exàmens.
Punt únic de veritat per a tots els defaults del sistema.
"""

DIES_SETMANA = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres"]


# Costos globals de professors (percentatge 0-100)
# Usat per la ruta i el motor V3
DEFAULT_COST_PROFESSORS = {
    "substitucio": 80,
    "abans_jornada": 30,
    "despres_jornada": 30,
    "no_treballa_dia": 60,
}

# Temps màxim de la cerca dels tres motors, en segons: el per defecte i el
# màxim que admet el servidor (es tria a la pantalla, als paràmetres del motor).
# El màxim ha de cabre amb marge als temps límit de la cadena de producció
# (nginx del frontend, Caddy, client de la pantalla): vegeu DESPLEGAMENT.md.
SEGONS_MAXIMS_PER_DEFECTE = 20
SEGONS_MAXIMS_LIMIT = 120

# Paràmetres Simulated Annealing (motor V3)
# La temperatura inicial ha d'anar d'acord amb els costos: una substitució en
# val 80. Amb 8000 la primera part de la cerca acceptava qualsevol canvi i, en
# un problema ajustat (molts exàmens per poques franges i incompatibilitats),
# acabava en horaris pitjors: amb la configuració de la demo, cost mitjà 226
# (8000) davant de 98 (100), en el mateix temps. Els reinicis: veure
# REINICIS i SEGONS_MAXIMS_REINICIS a generators/v3_sa.py.
DEFAULT_SA_PARAMS = {
    "temperatura_inicial": 100.0,
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
}

# Nivells per defecte
DEFAULT_NIVELLS_ACTIUS = ["1-BATX", "2-BATX"]
DEFAULT_DURADA_TITULAR = 1  # Nombre d'hores lectives que dura l'examen

# Pesos de restriccions per al càlcul de costos
DEFAULT_PES_ZONA_EXAMEN = 5  # Soft cost per conflicte a la zona d'examen sense titular
DEFAULT_PES_RESTRICCIO_DURA = 10000  # Cost base per restricció dura
DEFAULT_PES_RESTRICCIO_VIOLADA = 20000  # Cost per restricció dura violada
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

# Les causes per les quals un examen no pot anar a una franja (diagnòstic i
# missatges dels motors): les de dalt i les tres de «dia_hora_fix» per separat.
# El desglossament del cost continua amb «dia_hora_fix» junt.
ETIQUETES_CAUSES: dict[str, str] = {
    **ETIQUETES_RESTRICCIONS,
    "examen_fixat": "Examen fixat a una altra franja",
    "franja_prohibida": "Franja prohibida",
    "nivell_sense_inici": "Hora sense inici d'examen per al nivell",
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
