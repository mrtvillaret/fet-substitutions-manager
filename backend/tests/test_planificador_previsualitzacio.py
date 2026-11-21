"""L'editor previsualitza sense desar i l'horari editat es desa en aplicar. Generar ja
porta el desglossament i els recomptes del recàlcul."""

import pytest
from test_planificador_llavor import DATES, PETICIO, client  # noqa: F401


def test_el_recalcul_de_previsualitzacio_no_desa_l_horari(client):  # noqa: F811
    """L'editor recalcula a cada moviment sense desar (`desa: false`); l'horari editat
    només es desa en aplicar (`desa` per defecte)."""
    horari = client.post("/api/scheduler/generate", json={**PETICIO, "motor": "v2", "random_seed": 1}).json()["horari"]
    desat = client.get("/api/scheduler/ultim-resultat").json()["resultat"]["horari"]
    editat = {**horari, "dies": horari["dies"][:1]}  # un horari diferent
    cos = {"horari": editat, "selected_dates": DATES}
    assert client.post("/api/scheduler/recalcular-cost", json={**cos, "desa": False}).status_code == 200
    assert client.get("/api/scheduler/ultim-resultat").json()["resultat"]["horari"]["dies"] == desat["dies"]
    assert client.post("/api/scheduler/recalcular-cost", json=cos).status_code == 200
    assert client.get("/api/scheduler/ultim-resultat").json()["resultat"]["horari"]["dies"] == editat["dies"]


@pytest.mark.parametrize("motor", ["v2", "v2-backtrack", "v3"])
def test_generar_ja_porta_el_desglossament_i_els_recomptes_del_recalcul(client, motor):  # noqa: F811
    """La pantalla ja no recalcula just després de generar."""
    params = {"max_iteracions": 300} if motor == "v3" else {}
    meta = client.post("/api/scheduler/generate", json={**PETICIO, "motor": motor, "random_seed": 1, **params}).json()[
        "horari"
    ]["metadata"]
    horari = client.get("/api/scheduler/ultim-resultat").json()["resultat"]["horari"]
    recalcul = client.post(
        "/api/scheduler/recalcular-cost", json={"horari": horari, "selected_dates": DATES, "desa": False}
    ).json()
    assert meta["cost_total"] == recalcul["cost_total"]
    assert meta["cost_desglossament"] == recalcul["cost_desglossament"]
    assert {k: meta[k] for k in recalcul["stats"]} == recalcul["stats"]
