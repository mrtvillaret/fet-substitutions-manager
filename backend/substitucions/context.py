"""Gestors de substitucions nous per a cada petició."""

from grups.disponibilitat import GestorAlliberats
from horari.context import _get_institucio_actual, get_horari
from prioritats.memoria import no_substituir_a
from substitucions.assignacio import GestorSubstitucions
from substitucions.necessitats import GestorAbsencies


def get_gestors(institucio: str = None, *, data_iso: str, horari=None):
    """Retorna (substitucions, horari, alliberats, absencies) per a una petició.

    L'horari surt de la memòria cau (get_horari). Els altres tres gestors es
    creen nous a cada crida: són lleugers (només guarden referències a
    l'horari) i cada petició hi fixa el seu estat (data, vigilants, grups sense
    classe), que no s'ha de compartir amb cap altra. «No substituir» és la
    llista vigent a `data_iso`."""
    institucio = institucio or _get_institucio_actual()
    horari = horari or get_horari(institucio, data_iso=data_iso)
    no_substituir = no_substituir_a(data_iso)
    alliberats = GestorAlliberats(horari)
    absencies = GestorAbsencies(horari, no_substituir=no_substituir)
    substitucions_mgr = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)

    return substitucions_mgr, horari, alliberats, absencies
