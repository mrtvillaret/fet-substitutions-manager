"""Gestors de substitucions nous per a cada petició."""

from grups.disponibilitat import GestorAlliberats
from horari.context import _get_institucio_actual, get_horari
from substitucions.assignacio import GestorSubstitucions
from substitucions.necessitats import GestorAbsencies


def get_gestors(institucio: str = None, *, data_iso: str, horari=None):
    """Retorna (substitucions, horari, alliberats, absencies) per a una petició.

    L'horari surt de la memòria cau (get_horari). Els altres tres gestors es
    creen nous a cada crida: són lleugers (només guarden referències a
    l'horari) i cada petició hi fixa el seu estat (data, vigilants, grups sense
    classe), que no s'ha de compartir amb cap altra."""
    institucio = institucio or _get_institucio_actual()
    horari = horari or get_horari(institucio, data_iso=data_iso)
    alliberats = GestorAlliberats(horari)
    absencies = GestorAbsencies(horari)
    substitucions_mgr = GestorSubstitucions(horari, alliberats, absencies)

    return substitucions_mgr, horari, alliberats, absencies
