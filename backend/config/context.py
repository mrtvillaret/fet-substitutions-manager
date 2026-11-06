"""
Institució de la petició en curs.

Un mateix backend pot servir diverses institucions. La institució activa no
es pot desar en una variable global: dues peticions simultànies de centres
diferents se la trepitjarien i una podria rebre dades de l'altra. Una
ContextVar té un valor propi per a cada petició (cada tasca d'asyncio, i els
fils on s'executa el codi síncron en copien el context).

La fixa get_current_user un cop validat l'usuari. Fora d'una petició (arrencada,
scripts, tests unitaris) no té valor: qui necessita un centre l'ha de passar
explícitament o fixar-lo al context. No se'n tria cap per defecte en llegir l'horari.
"""

from contextvars import ContextVar
from typing import Optional

_institucio: ContextVar[Optional[str]] = ContextVar("institucio_peticio", default=None)


def institucio_peticio() -> Optional[str]:
    return _institucio.get()


def fixa_institucio_peticio(institucio: Optional[str]):
    return _institucio.set(institucio)
