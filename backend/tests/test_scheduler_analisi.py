"""
Anàlisi de possibilitats del planificador (POST /api/scheduler/analisi i
/analisi/pdf): per a cada examen i franja, quins professors s'haurien de
substituir. Els informes són text; el PDF en fa una o totes les seccions.
"""
import glob
import os
import tempfile

import pytest

from rate_limit import limiter
from suport_planificador import DATES, DIES, alliberaments, centre_amb_examens, configura

PETICIO = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    _, client = centre_amb_examens()
    configura(client)
    return client


def test_l_analisi_dona_els_tres_informes_amb_els_examens_del_nivell(client):
    resp = client.post("/api/scheduler/analisi", json=PETICIO)
    assert resp.status_code == 200, resp.text
    informes = resp.json()
    assert set(informes) == {"per_slots", "per_sessio", "professors_slot"}
    for examen in ("Anglès (1-BAT)", "Català (1-BAT)", "Filosofia (1-BAT)"):
        assert examen in informes["per_sessio"]
    assert "Prof 25" in informes["per_sessio"]          # titular d'Anglès


def _pdfs_temporals():
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "*.pdf")))


def test_el_pdf_de_l_analisi_no_deixa_fitxers_temporals(client):
    abans = _pdfs_temporals()
    resp = client.post("/api/scheduler/analisi/pdf", json=PETICIO)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert _pdfs_temporals() - abans == set()


def test_el_pdf_pot_ser_d_una_sola_seccio(client):
    tot = client.post("/api/scheduler/analisi/pdf", json=PETICIO).content
    una = client.post("/api/scheduler/analisi/pdf", json=dict(PETICIO, analisi_tab="per_slots")).content
    assert una.startswith(b"%PDF") and len(una) < len(tot)


# ---------------------------------------- examens més llargs que la durada general

def _files_de(informe, examen):
    """Files (dia | hora | ...) de la secció d'un examen a l'informe per agrupacions."""
    files, dins = [], False
    for linia in informe.splitlines():
        if linia.startswith("📝 "):
            dins = linia == f"📝 {examen}"
        elif dins and " | " in linia and not linia.startswith("Dia |"):
            files.append(linia)
    return files


def _analisi_filosofia(durades_grups=None):
    _, client = centre_amb_examens()
    camps = {"alliberaments_per_nivell": alliberaments(hores_inici=("09:00", "10:00", "11:30"))}
    if durades_grups:
        camps["durades_grups"] = durades_grups
    configura(client, **camps)
    return _files_de(client.post("/api/scheduler/analisi", json=PETICIO).json()["per_sessio"], "Filosofia (1-BAT)")


def test_un_examen_que_dura_mes_que_la_durada_general_s_analitza_sencer():
    # Durada general d'1 hora; Filosofia en dura 2: es miren les dues hores
    una_hora = _analisi_filosofia()
    dues_hores = _analisi_filosofia([{"assignatures": ["Filosofia (1-BAT)"], "durada": 2, "durada_examen": 2}])
    assert una_hora and len(dues_hores) > len(una_hora)
