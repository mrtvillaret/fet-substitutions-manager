"""
Suport per als tests del planificador d'exàmens: una institució amb l'horari
d'exemple i la configuració d'exàmens de 1-BAT importada amb la mateixa
funció de l'aplicació (Importar assignacions).
"""
import uuid

from routes import config_examens, scheduler
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(scheduler.router, config_examens.router)

# Dilluns i dimarts de la setmana de l'horari d'exemple
DATES = ["2026-04-20", "2026-04-21"]
DIES = ["Dilluns", "Dimarts"]
ASSIGNATURES = ("Anglès", "Català", "Filosofia")  # 1-BAT-A i 1-BAT-B


def admin_de(institucio, role="admin"):
    nom = f"{role}_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, role)
    return entra(client_per(APP), nom)


def centre_amb_examens(assignatures=ASSIGNATURES, nivells=("1-BAT",)):
    """Institució amb els nivells i les assignatures indicades (grups A i B)."""
    institucio = nova_institucio(amb_xml=True)
    client = admin_de(institucio)
    propostes = client.get("/api/config/importar-assignacions/preview").json()["propostes"]
    triades = [p for p in propostes if p["nivell"] in nivells and p["assignatura"] in assignatures]
    resp = client.post("/api/config/importar-assignacions", json={"propostes": triades, "overwrite": True})
    assert resp.status_code == 200, resp.text
    return institucio, client


def alliberaments(dates=DATES, hores_inici=("09:00", "11:30"), nivells=("1-BAT",)):
    """Hores sense classe de cada nivell; les d'inici són on pot començar un examen."""
    return {nivell: {"durada": 1, "dates": list(dates), "config": {
        d: {h: {"a": True, "i": True} for h in hores_inici} for d in dates}} for nivell in nivells}


def configura(client, **camps):
    cos = {"nivells_actius": ["1-BAT"], "alliberaments_per_nivell": alliberaments(),
           "durada_titular": 1, "durada_examen": 1}
    cos.update(camps)
    resp = client.put("/api/scheduler/config", json=cos)
    assert resp.status_code == 200, resp.text
