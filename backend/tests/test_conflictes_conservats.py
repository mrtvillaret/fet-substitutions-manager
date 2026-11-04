"""Els avisos de repetició no bloquegen desar, fins i tot en el mateix examen."""

import pytest
from test_pdf_api import DATA, centre, client  # noqa: F401


@pytest.mark.parametrize("aula,espera_aula", [("A1", True), ("ENLLAÇ", False)])
@pytest.mark.parametrize("grup2", ["1-ESO-A", "1-ESO-B"])
def test_vigilant_repetit_sempre_avis_i_aula_enllac_exempt(client, aula, espera_aula, grup2):
    url = f"/api/vigilancies/{DATA}"
    for grup in ["1-ESO-A", grup2]:
        r = client.post(
            url,
            json={
                "hora": "10:00",
                "tipus": "Prova",
                "nivell": "1-ESO",
                "grups": grup,
                "aula": aula,
                "vigilant": "Prof 21",
            },
        )
        assert r.status_code == 200, r.text
    r = client.get(url + "/analisi")
    assert r.status_code == 200, r.text
    ps = r.json()
    repetits = [p for p in ps if p["tipus"] == "vigilant_repetit"]
    assert len(repetits) == 1 and repetits[0]["gravetat"] == "avis"
    assert len(repetits[0]["files"]) == 2
    assert any(p["tipus"] == "aula_repetida" for p in ps) == espera_aula
    fila = client.get(url).json()[0]
    # També es permet deixar feina incompleta després de desar una repetició.
    r = client.put(f"{url}/{fila['id']}", json={"aula": "", "updated_at": fila["updated_at"]})
    assert r.status_code == 200, r.text
    ps = client.get(url + "/analisi").json()
    assert any(p["tipus"] == "sense_aula" and p["gravetat"] == "important" for p in ps)
    assert any(p["tipus"] == "vigilant_repetit" for p in ps)
