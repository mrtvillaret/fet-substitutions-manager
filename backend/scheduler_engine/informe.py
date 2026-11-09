"""Informe del motor: missatges de logging aïllats per execució."""

import io
import logging
from contextlib import contextmanager
from contextvars import ContextVar

_desti: ContextVar[io.StringIO | None] = ContextVar("informe_motor", default=None)


class _RecullInforme(logging.Handler):
    def emit(self, record):
        desti = _desti.get()
        if desti is not None:
            desti.write(self.format(record) + "\n")


log = logging.getLogger("scheduler_engine.informe")
log.setLevel(logging.INFO)
log.propagate = False
log.addHandler(_RecullInforme())


@contextmanager
def captura_informe():
    """Recull només els missatges d'aquesta execució, també en fils concurrents."""
    sortida = io.StringIO()
    testimoni = _desti.set(sortida)
    try:
        yield sortida
    finally:
        _desti.reset(testimoni)
