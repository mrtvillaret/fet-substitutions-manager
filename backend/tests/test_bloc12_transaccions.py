"""Cap repositori no tanca una operació abans que el servei l'hagi acabada."""

import ast
import uuid
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from centres.router import router as centres_router
from configuracio.repositories import ConfiguracioRepository
from configuracio.router import router as configuracio_router
from configuracio_examens.repositories import ConfiguracioExamenRepository, MasterConfigRepository
from configuracio_examens.router import router as examens_router
from database import get_data_db_session
from grups.repositories import AbreviaturaGrupRepository
from grups.router import router_admin as grups_router
from models import AbreviaturaGrup, Assignatura, Aula, Configuracio, ConfiguracioExamen, Grup, Nivell
from pdf.router import router as pdf_router
from planificador.router import router as planificador_router
from rate_limit import limiter
from vigilancies.router import router_admin as vigilancies_router

MODELS = (Nivell, Assignatura, Grup, Aula, ConfiguracioExamen, AbreviaturaGrup, Configuracio)


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        return {
            model.__tablename__: [
                tuple(getattr(fila, c.name) for c in model.__table__.columns)
                for fila in db.query(model).order_by(*model.__table__.primary_key.columns).all()
            ]
            for model in MODELS
        }


@pytest.fixture
def entorn():
    limiter.reset()
    centre = nova_institucio()
    app = crea_app()
    app.include_router(examens_router, dependencies=[Depends(require_admin)])
    app.include_router(grups_router, dependencies=[Depends(require_admin)])
    for router in (centres_router, configuracio_router, pdf_router, planificador_router, vigilancies_router):
        app.include_router(router, dependencies=[Depends(require_admin)])
    usuari = f"admin_{uuid.uuid4().hex}"
    crea_usuari(usuari, centre, "super_admin")
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
        entra(client, usuari)
        for url, cos in [
            ("nivells", {"codi": "1-ESO"}),
            ("assignatures/1-ESO", {"nom": "Mates"}),
            ("grups/1-ESO", {"codi": "1-ESO-A"}),
            ("aules", {"codi": "A1"}),
            ("assignacions", {"assignatura": "Mates", "grup": "1-ESO-A", "aula": "A1"}),
            ("abreviatures", {"grups_originals": "1-ESO-A,1-ESO-B", "abreviatura": "1-ESO-AB"}),
        ]:
            resposta = client.post(f"/api/config/{url.format(centre=centre)}", json=cos)
            assert resposta.status_code == 200, resposta.text
        yield centre, client


CASOS = [
    (MasterConfigRepository, "rename_assignatura", "PUT", "assignatures/1-ESO/Mates", {"nou_nom": "Matemàtiques"}),
    (MasterConfigRepository, "delete_assignatura", "DELETE", "assignatures/1-ESO/Mates", None),
    (MasterConfigRepository, "rename_grup", "PUT", "grups/1-ESO-A", {"nou_nom": "1-ESO-B"}),
    (MasterConfigRepository, "rename_aula", "PUT", "aules/A1", {"nou_nom": "A2"}),
    (MasterConfigRepository, "delete_aula", "DELETE", "aules/A1", None),
    (ConfiguracioExamenRepository, "update", "PUT", "assignacions/1", {"titular": "Prof 1", "aula": "A2"}),
    (ConfiguracioExamenRepository, "delete", "DELETE", "assignacions/1", None),
    (AbreviaturaGrupRepository, "create", "POST", "abreviatures", {"grups_originals": "G1,G2", "abreviatura": "G"}),
    (AbreviaturaGrupRepository, "update", "PUT", "abreviatures/1", {"abreviatura": "AB"}),
    (AbreviaturaGrupRepository, "delete", "DELETE", "abreviatures/1", None),
    (
        ConfiguracioRepository,
        "set",
        "PUT",
        "../prioritats/activitats-alliberables",
        {"activitats": ["Reforç"], "per_defecte": ["Reforç"]},
    ),
]

CASOS += [
    (ConfiguracioRepository, "set", "PUT", "../scheduler/dates", {"selected_dates": ["2026-04-20"]}),
    (ConfiguracioRepository, "set", "PUT", "afinitats", {"afinitats": [{"base": "1-ESO", "ordre": ["2-ESO"]}]}),
    (
        ConfiguracioRepository,
        "set",
        "PUT",
        "../pdf/preferences",
        {"substitucions": {"fontSize": 10}, "vigilancies": {"fontSize": 11}},
    ),
    (ConfiguracioRepository, "set", "PUT", "../settings/institucions/{centre}", {"display_name": "Centre temporal"}),
]


@pytest.mark.parametrize("repo,metode,verb,url,cos", CASOS, ids=[f"{r.__name__}.{m}" for r, m, *_ in CASOS])
def test_error_posterior_al_repositori_desfa_tota_operacio(entorn, monkeypatch, repo, metode, verb, url, cos):
    centre, client = entorn
    abans = _bolcat(centre)
    real = getattr(repo, metode)

    def escriu_i_falla(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError("fallada simulada després de l'escriptura")

    monkeypatch.setattr(repo, metode, escriu_i_falla)
    resposta = client.request(verb, f"/api/config/{url.format(centre=centre)}", json=cos)
    assert resposta.status_code == 500, resposta.text
    assert _bolcat(centre) == abans


def test_esborrat_massiu_abreviatures_no_fa_commit(entorn):
    """No té cap consumidor, però segueix el mateix contracte transaccional."""
    centre, _ = entorn
    abans = _bolcat(centre)
    with pytest.raises(RuntimeError), get_data_db_session(centre) as db:
        assert AbreviaturaGrupRepository.delete_all(db) == 1
        raise RuntimeError("fallada posterior")
    assert _bolcat(centre) == abans


def test_cap_commit_als_repositoris():
    backend = Path(__file__).resolve().parents[1]
    trobats = []
    for cami in backend.glob("*/repositories.py"):
        for node in ast.walk(ast.parse(cami.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "commit":
                trobats.append(f"{cami.relative_to(backend)}:{node.lineno}")
    assert trobats == []


@pytest.mark.parametrize("repo,metode,verb,url,cos", CASOS, ids=[f"{r.__name__}.{m}" for r, m, *_ in CASOS])
def test_operacio_correcta_te_un_sol_commit(entorn, repo, metode, verb, url, cos):
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    centre, client = entorn
    commits = []

    def compta(db):
        if db.info.get("institucio") == centre:
            commits.append(db)

    event.listen(Session, "after_commit", compta)
    try:
        resposta = client.request(verb, f"/api/config/{url.format(centre=centre)}", json=cos)
        assert resposta.status_code == 200, resposta.text
        assert len(commits) == 1
    finally:
        event.remove(Session, "after_commit", compta)


def test_logo_no_desa_configuracio_si_falla_despres_del_repositori(entorn, monkeypatch):
    import io

    from PIL import Image

    centre, client = entorn
    abans = _bolcat(centre)
    imatge = io.BytesIO()
    Image.new("RGB", (2, 2)).save(imatge, format="PNG")
    real = ConfiguracioRepository.set

    def escriu_i_falla(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError("fallada posterior")

    monkeypatch.setattr(ConfiguracioRepository, "set", escriu_i_falla)
    resposta = client.post("/api/files/upload-logo", files={"file": ("logo.png", imatge.getvalue(), "image/png")})
    assert resposta.status_code == 500
    assert _bolcat(centre) == abans


def test_ultim_resultat_no_es_desa_si_falla_despres_del_repositori(entorn, monkeypatch):
    from planificador.services import desa_ultim_resultat

    centre, _ = entorn
    abans = _bolcat(centre)
    real = ConfiguracioRepository.set

    def escriu_i_falla(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError("fallada posterior")

    monkeypatch.setattr(ConfiguracioRepository, "set", escriu_i_falla)
    with pytest.raises(RuntimeError):
        desa_ultim_resultat(centre, {"dies": [{"dia": "Dilluns"}]})
    assert _bolcat(centre) == abans
