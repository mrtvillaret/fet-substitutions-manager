"""Les llistes de les peticions tenen sostre: una de massa llarga és un 422."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from parametres import MAX_DATES
from planificador.schemas import SchedulerDatesRequest, SchedulerGenerateRequest
from vigilancies.schemas import MAX_CONSULTES_DISPONIBLES, DisponiblesEnBlocRequest


def _dates(n):
    return [(date(2027, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]


@pytest.mark.parametrize(
    "crea",
    [
        lambda dates: SchedulerDatesRequest(selected_dates=dates),
        lambda dates: SchedulerGenerateRequest(data_inici=dates[0], selected_dates=dates),
    ],
)
def test_llista_de_dates_fins_a_un_any(crea):
    crea(_dates(MAX_DATES))
    with pytest.raises(ValidationError):
        crea(_dates(MAX_DATES + 1))


def test_lot_de_disponibles_amb_sostre():
    consulta = {"hora": "08:00"}
    DisponiblesEnBlocRequest(queries=[consulta] * MAX_CONSULTES_DISPONIBLES)
    with pytest.raises(ValidationError):
        DisponiblesEnBlocRequest(queries=[consulta] * (MAX_CONSULTES_DISPONIBLES + 1))
