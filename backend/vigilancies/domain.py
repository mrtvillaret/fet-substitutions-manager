"""Regles pròpies d'una vigilància."""

from errors_domini import NoValid


def nivell_obligatori(nivell: str | None) -> str:
    """Retorna el nivell si té contingut; una vigilància nova o editada no
    pot quedar sense nivell."""
    if not nivell or not nivell.strip():
        raise NoValid("Cal indicar el nivell de la vigilància", codi="vigilancia_sense_nivell")
    return nivell
