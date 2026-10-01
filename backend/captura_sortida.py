"""
Captura dels missatges (print) d'una sola petició.

contextlib.redirect_stdout canvia sys.stdout per a tot el procés: si dues
peticions s'atenen alhora en fils diferents, cadascuna capturaria els
missatges de l'altra (i els logs del planificador d'un centre podrien
mostrar missatges d'un altre). Aquí sys.stdout es substitueix un sol cop per
un objecte que escriu al destí de la petició en curs (ContextVar) o, fora
d'una captura, a la sortida original.
"""
import io
import sys
from contextlib import contextmanager
from contextvars import ContextVar

_desti: ContextVar = ContextVar("desti_stdout", default=None)


class _SortidaPerPeticio(io.TextIOBase):
    def __init__(self, original):
        self.original = original

    def write(self, text):
        return (_desti.get() or self.original).write(text)

    def flush(self):
        (_desti.get() or self.original).flush()


@contextmanager
def captura_stdout():
    """Com redirect_stdout(io.StringIO()), però només per a la petició en curs."""
    if not isinstance(sys.stdout, _SortidaPerPeticio):
        sys.stdout = _SortidaPerPeticio(sys.stdout)
    buffer = io.StringIO()
    testimoni = _desti.set(buffer)
    try:
        yield buffer
    finally:
        _desti.reset(testimoni)
