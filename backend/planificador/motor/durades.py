"""Tres regles de durada d'examen, conservades segons el camí de càlcul."""

from planificador.motor.compatibilitat import DuradaExamen, Politiques


def _positiu(valor) -> int | None:
    try:
        return int(valor) if valor is not None and int(valor) > 0 else None
    except (TypeError, ValueError):
        return None


def vigilancia(nom: str | None, propies, general: int) -> int:
    return (_positiu(propies.get(nom)) if nom and propies else None) or general


def examen_config(nom, propies, vigilancies, general_examen, general_titular) -> int:
    return max(vigilancia(nom, propies, general_examen), vigilancia(nom, vigilancies, general_titular))


def examen_recalcul(nom, propies, vigilancies, general_titular) -> int:
    return max(vigilancia(nom, propies, general_titular), vigilancia(nom, vigilancies, general_titular))


def examen_motor(nom, propies, vigilancies, general_titular) -> int:
    # Una durada pròpia positiva pot ser menor que la vigilància.
    return vigilancia(nom, propies, vigilancia(nom, vigilancies, general_titular))


def examen(nom, propies, vigilancies, general_examen, general_titular, politiques: Politiques) -> int:
    if politiques.durada_examen == DuradaExamen.CONFIG:
        return examen_config(nom, propies, vigilancies, general_examen, general_titular)
    if politiques.durada_examen == DuradaExamen.RECALCUL:
        return examen_recalcul(nom, propies, vigilancies, general_titular)
    return examen_motor(nom, propies, vigilancies, general_titular)


def per_nivell(nivell: str | None, alliberaments, general: int) -> int:
    dades = alliberaments.get(nivell) if nivell and alliberaments else None
    if not hasattr(dades, "get"):
        return general
    # El motor antic captura qualsevol error de conversió en aquest camí.
    try:
        valor = int(dades.get("durada"))
    except Exception:
        return general
    return valor if valor > 0 else general


def hores_ocupades(hora: str, graella, durada: int) -> list[str]:
    if hora not in graella:
        return [hora]
    inici = graella.index(hora)
    return list(graella[inici : min(inici + max(1, durada), len(graella))])
