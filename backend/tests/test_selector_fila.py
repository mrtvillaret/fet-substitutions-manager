"""Identitat de la fila, marques d'ocupació i paritat del selector en lot."""

import pytest
from test_pdf_api import DATA, DATA_DIA, _limiter_net, centre, client  # noqa: F401

from database import get_data_db_session
from models import ConfiguracioExamen, Substitucio


def crea(client, vigilant):
    r = client.post(
        f"/api/vigilancies/{DATA}",
        json={
            "hora": "10:00",
            "tipus": "Prova",
            "nivell": "1-ESO",
            "grups": "1-ESO-A",
            "aula": "A1",
            "vigilant": vigilant,
        },
    )
    assert r.status_code == 200
    return r.json()["vigilancia"]["id"]


def disponibles(client, id, **params):
    r = client.get(f"/api/vigilancies/{DATA}/10:00/disponibles", params={"vigilancia_id": id, **params})
    assert r.status_code == 200, r.text
    return r.json()


def professor(client, id, nom="Prof 21", **params):
    return next(p for p in disponibles(client, id, **params) if p["value"] == nom)


def test_el_vigilant_de_la_mateixa_fila_no_diu_ja_assignat(client):
    id = crea(client, "Prof 21")
    p = professor(client, id)
    assert not p["ja_assignat"] and "JA ASSIGNAT" not in p["label"]
    altre = crea(client, "")
    assert professor(client, altre)["ja_assignat"]
    crea(client, "Prof 21")
    assert professor(client, id)["ja_assignat"]


def test_el_lot_diferencia_dues_files_amb_exactament_la_mateixa_consulta(client):
    id = crea(client, "Prof 21")
    altre = crea(client, "")
    q = {"tipus": "Prova", "grups": "1-ESO-A", "aula": "A1"}
    r = client.post(
        f"/api/vigilancies/{DATA}/disponibles-batch",
        json={"queries": [{**q, "hora": "10:00", "vigilancia_id": i} for i in [id, altre]]},
    )
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert len(results) == 2
    for i, esperat in [(id, False), (altre, True)]:
        candidats = results[f"10:00|Prova|1-ESO-A|A1|fila:{i}"]
        assert candidats == disponibles(client, i, **q)
        p = next(p for p in candidats if p["value"] == "Prof 21")
        assert p["ja_assignat"] == esperat


@pytest.mark.parametrize(
    "nom,estat,categoria,colors",
    [
        ("Prof 21", "DISPONIBLE", 1, ("#8B8B8B", "#A9A9A9", "#ADD8E6")),
        ("Prof 30", "CLASSE", 2, ("#FFDCB4", "#FFDCB4", "#FFDCB4")),
    ],
)
def test_colors_i_marques_quan_el_professor_substitueix(client, centre, nom, estat, categoria, colors):
    id = crea(client, nom)
    abans = professor(client, id, nom)
    assert "JA ASSIGNAT" not in abans["info"] and "SUBSTITUCIÓ" not in abans["info"]
    if estat == "CLASSE":
        assert "1-ESO-A" in abans["info"] and abans["color"] == "#FFDCB4"
    altre = crea(client, "")
    with get_data_db_session(centre) as db:
        db.add(ConfiguracioExamen(assignatura="Prova", grup="1-ESO-A", aula="A1", titular=nom))
        # Una fila de substitució desada permet comprovar marques simultànies al selector.
        db.add(Substitucio(data=DATA_DIA, hora="10:00", professor_absent="Prof 15", substitut=nom))
        db.commit()
    consultes = (
        (id, {}, False, False),
        (altre, {}, True, False),
        (altre, {"tipus": "Prova", "grups": "1-ESO-A", "aula": "A1"}, True, True),
    )
    for (fila, params, ocupat, titular), color in zip(consultes, colors, strict=True):
        p = professor(client, fila, nom, **params)
        assert (p["estat"], p["categoria"], p["color"], p["ja_assignat"], p["es_titular"]) == (
            estat,
            categoria,
            color,
            ocupat,
            titular,
        )
        assert p["info"].startswith(abans["info"])
        assert ("[JA ASSIGNAT]" in p["info"]) == ocupat
        assert "[SUBSTITUCIÓ]" in p["info"]
        assert ("(TITULAR Prova)" in p["label"]) == titular
