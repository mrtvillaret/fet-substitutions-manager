"""Un examen no allibera: només les marques manuals permeten assignar."""

import pytest
from test_vigilancies_assignacio import DATA, URL, _centre, _pendents, _titulars, _vigilants

from database import get_data_db_session
from grups.disponibilitat import clau_professor
from horari.domain import Dia
from substitucions.domain import DiaEscolar
from vigilancies.analisi import analitza_vigilancies


@pytest.mark.parametrize("marca", [None, "1-ESO-A", clau_professor("Prof 30")])
def test_examen_no_allibera_automatic_ni_revisio_ni_selector(marca):
    centre, client = _centre(
        config=[("Prova", "1-ESO-A", "A1", "Prof 30")],
        alliberats=[marca] if marca else [],
    )
    r = client.post(
        URL,
        json={
            "hora": "10:00",
            "tipus": "Prova",
            "grups": "1-ESO-A",
            "aula": "A1",
            "vigilant": "",
            "nivell": "1-ESO",
        },
    )
    assert r.status_code == 200
    assert _titulars(client)["assigned_count"] == int(bool(marca))
    assert _pendents(client)["assigned_count"] == 0
    assert _vigilants(client)[("1-ESO-A", "A1")] == ("Prof 30" if marca else "")
    disponibles = client.get(f"{URL}/10:00/disponibles").json()
    p = next(p for p in disponibles if p["value"] == "Prof 30")
    assert p["estat"] == ("ALLIBERAT" if marca else "CLASSE")
    # Assignació manual permesa, encara que tingui classe.
    fila = client.get(URL).json()[0]
    assert (
        client.put(
            f"{URL}/{fila['id']}",
            json={
                "vigilant": "Prof 30",
                "updated_at": fila["updated_at"],
            },
        ).status_code
        == 200
    )
    # Sense fila de cobertura, la revisió ha de veure la classe real.
    with get_data_db_session(centre) as db:
        dia = DiaEscolar(db, Dia.de_text(DATA, centre))
        dia.files = []
        problemes = analitza_vigilancies(dia)
        assert any(p["tipus"] == "classe_sense_cobertura" for p in problemes) == (marca is None)
