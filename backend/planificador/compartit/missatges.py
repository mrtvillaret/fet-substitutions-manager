"""Missatges del planificador: dades de domini, text a la interfície."""


def missatge(codi: str, **params) -> dict:
    return {"codi": codi, "params": params}


def unics(missatges: list) -> list:
    """Elimina duplicats conservant l'ordre, també amb paràmetres compostos."""
    resultat = []
    for valor in missatges:
        if valor not in resultat:
            resultat.append(valor)
    return resultat
