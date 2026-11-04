"""Ocupació d'altres files, amb la identitat de la fila també al lot."""

from test_pdf_api import DATA, centre, client  # noqa: F401


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


def professor(client, id, nom="Prof 21"):
    r = client.get(f"/api/vigilancies/{DATA}/10:00/disponibles", params={"vigilancia_id": id})
    assert r.status_code == 200, r.text
    return next(p for p in r.json() if p["value"] == nom)


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
    q = {"hora": "10:00", "tipus": "Prova", "grups": "1-ESO-A", "aula": "A1"}
    r = client.post(
        f"/api/vigilancies/{DATA}/disponibles-batch", json={"queries": [{**q, "vigilancia_id": i} for i in [id, altre]]}
    )
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert len(results) == 2
    for i, esperat in [(id, False), (altre, True)]:
        p = next(p for p in results[f"10:00|Prova|1-ESO-A|A1|fila:{i}"] if p["value"] == "Prof 21")
        assert p["ja_assignat"] == esperat


def test_amb_classe_conserva_informacio_i_color_encara_que_ja_vigili(client):
    id = crea(client, "Prof 30")
    p = professor(client, id, "Prof 30")
    assert p["estat"] == "CLASSE" and p["color"] == "#FFDCB4"
    assert "JA ASSIGNAT" not in p["info"] and "1-ESO-A" in p["info"]
    altre = crea(client, "")
    p = professor(client, altre, "Prof 30")
    assert p["ja_assignat"] and p["estat"] == "CLASSE" and p["color"] == "#FFDCB4"
