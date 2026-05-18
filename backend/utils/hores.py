from functools import lru_cache

@lru_cache(maxsize=256)
def normalitzar_hora(hora: str) -> str:
    """Normalitza una hora a format HH:MM amb zero padding."""
    if not hora or ":" not in hora:
        return hora
    parts = hora.split(":")
    if len(parts) < 2:
        return hora
    try:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    except Exception:
        return hora
