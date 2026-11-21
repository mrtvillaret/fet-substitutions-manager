"""Lectura de les incidències dels logs (missatges {codi, params, punts}) als tests."""


def es_incidencia(m) -> bool:
    return isinstance(m, dict) and str(m.get("codi", "")).startswith("inc_")


def punts(logs) -> int:
    """La suma dels punts de les incidències (el cost total)."""
    return sum(m.get("punts", 0) for m in logs or [] if es_incidencia(m))


def amb_codi(logs, codi, **params) -> list[dict]:
    """Les incidències d'aquest codi amb aquests paràmetres (els que es donen)."""
    return [
        m
        for m in logs or []
        if es_incidencia(m) and m["codi"] == codi and all(m["params"].get(k) == v for k, v in params.items())
    ]
