"""
Les rutes que fan feina pesada (PDF, informes, motor del planificador) han de
ser síncrones: FastAPI les executa en un fil a part i el backend continua
atenent la resta de peticions mentre es generen. Una ruta `async` sense cap
`await` atura totes les peticions del backend (de tots els centres) mentre dura.
"""

import inspect

import pytest

from pdf import informes
from pdf import router as pdf
from routes import scheduler

RUTES_PESADES = [
    (pdf, "get_pdf_preferences"),  # (llegeixen la BD amb la sessió síncrona)
    (pdf, "update_pdf_preferences"),
    (pdf, "validar_abans_pdf"),
    (pdf, "generar_pdf_complet"),
    (pdf, "generar_pdf_interval"),
    (pdf, "generar_pdf_vigilancies"),
    (pdf, "generar_pdf_disponibles_tots_dies"),
    (informes, "informe_direccio"),
    (informes, "informe_professor"),
    (informes, "llista_professors"),
    (scheduler, "scheduler_generate"),
    (scheduler, "scheduler_analisi"),
    (scheduler, "scheduler_analisi_pdf"),
    (scheduler, "recalcular_cost"),
]


@pytest.mark.parametrize("modul, nom", RUTES_PESADES, ids=[n for _, n in RUTES_PESADES])
def test_les_rutes_pesades_no_aturen_el_backend(modul, nom):
    assert not inspect.iscoroutinefunction(getattr(modul, nom))
