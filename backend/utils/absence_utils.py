"""
Utilitats per gestionar tipus d'absència i text de visualització
"""

def get_tipus_absencia(professor: str, hora: str, data_iso: str = None) -> str:
    """
    Obté el tipus d'absència per un professor i hora específics

    Args:
        professor: Nom del professor
        hora: Hora (format "08:00", "Pati", etc.)
        data_iso: Data en format ISO (opcional, usa actual si no s'especifica)

    Returns:
        str: "SERVEI", "ABSENCIA", "VIGILANCIA"
    """
    try:
        from data.storage import storage

        # Si no s'especifica data, usa la data actual del context
        if not data_iso:
            try:
                from utils.date_context import DateContext
                data_iso = DateContext().iso_format
            except:
                return "ABSENCIA"  # Fallback segur

        substitucions_data = storage.carregar_substitucions(data_iso)

        for substitucio in substitucions_data:
            if isinstance(substitucio, dict):
                professor_absent = substitucio.get("professor_absent", "").strip()
                hora_substitucio = substitucio.get("hora", "").strip()
                tipus_absencia = substitucio.get("tipus_absencia", "ABSENCIA")

                if professor_absent == professor and hora_substitucio == hora:
                    return tipus_absencia

        return "ABSENCIA"  # Default si no es troba
    except:
        return "ABSENCIA"  # Fallback segur


def get_absence_display_text(tipus_absencia: str) -> str:
    """
    Converteix tipus d'absència a text de visualització

    Args:
        tipus_absencia: "SERVEI", "ABSENCIA", "VIGILANCIA", etc.

    Returns:
        str: "SERVEI" per SERVEI, "ABSENT" per qualsevol altre
    """
    return "SERVEI" if tipus_absencia == "SERVEI" else "ABSENT"


def get_professor_absence_text(professor: str, hora: str, data_iso: str = None) -> str:
    """
    Obté directament el text de visualització per un professor absent

    Args:
        professor: Nom del professor
        hora: Hora
        data_iso: Data ISO (opcional)

    Returns:
        str: "SERVEI" o "ABSENT"
    """
    tipus = get_tipus_absencia(professor, hora, data_iso)
    return get_absence_display_text(tipus)