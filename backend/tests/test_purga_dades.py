"""
Purga de dades per interval (/api/dades/purga/...): esborra registres de BD,
PDF exportats i versions d'XML d'un interval de dates, sense tocar res de fora
de l'interval ni de cap altre centre.
"""
import uuid
from datetime import date

import pytest
from fastapi import Depends

from auth_utils import require_admin
from database import get_data_db_session, get_data_dir_for_institucio, get_export_dir_for_institucio
from models import GrupAlliberat, ProfessorBaixa, Substitucio, Vigilancia, XMLVersion
from rate_limit import limiter
from routes import dades
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app()
APP.include_router(dades.router, dependencies=[Depends(require_admin)])   # com a main.py

INICI, FINAL = date(2026, 3, 1), date(2026, 3, 31)
INTERVAL = {"data_inici": INICI.isoformat(), "data_final": FINAL.isoformat()}
DINS, ABANS, DESPRES = date(2026, 3, 15), date(2026, 2, 27), date(2026, 4, 2)


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _omple(centre):
    """Un registre de cada tipus dins l'interval, abans i després; versions
    d'XML contingudes, que s'estenen fora i l'activa; PDF datats i sense data."""
    with get_data_db_session(centre) as db:
        for d in (DINS, ABANS, DESPRES):
            db.add(Substitucio(data=d, hora="10:00", professor_absent="Prof 1", substitut="Prof 2"))
            db.add(Vigilancia(data=d, hora="10:00", tipus="Examen", grups="1A", aula="A1", nivell="ESO"))
            db.add(GrupAlliberat(data=d, hora="10:00", grups="1A"))
        db.add(ProfessorBaixa(professor="Prof 3", data_inici=date(2026, 3, 10), data_final=date(2026, 3, 12)))
        db.add(ProfessorBaixa(professor="Prof 4", data_inici=date(2026, 2, 20), data_final=date(2026, 3, 5)))
        db.add(ProfessorBaixa(professor="Prof 5", data_inici=date(2026, 4, 10), data_final=date(2026, 4, 20)))
        carpeta = get_data_dir_for_institucio(centre)
        for nom, inici, fi in [("dins.xml", date(2026, 3, 2), date(2026, 3, 20)),
                               ("solapa.xml", date(2026, 2, 1), date(2026, 3, 1)),
                               ("activa.xml", date(2026, 3, 21), None)]:
            (carpeta / nom).write_text("<fet/>")
            db.add(XMLVersion(path=nom, data_inici=inici, data_fi=fi))
        db.commit()
    exports = get_export_dir_for_institucio(centre)
    for nom in ("260315_substitucions_260315_101010.pdf", "260402_vigilancies_260402_101010.pdf",
                "informe_direccio.pdf"):
        (exports / nom).write_bytes(b"%PDF-1.4")


def _queda(centre):
    with get_data_db_session(centre) as db:
        return {
            "substitucions": sorted(s.data for s in db.query(Substitucio)),
            "vigilancies": sorted(v.data for v in db.query(Vigilancia)),
            "grups_alliberats": sorted(g.data for g in db.query(GrupAlliberat)),
            "baixes": sorted(b.professor for b in db.query(ProfessorBaixa)),
            "xml": sorted(v.path for v in db.query(XMLVersion)),
        }


@pytest.fixture
def centre():
    nom_centre = nova_institucio()
    _omple(nom_centre)
    return nom_centre


@pytest.fixture
def admin(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


INTACTE = {
    "substitucions": [ABANS, DINS, DESPRES],
    "vigilancies": [ABANS, DINS, DESPRES],
    "grups_alliberats": [ABANS, DINS, DESPRES],
    "baixes": ["Prof 3", "Prof 4", "Prof 5"],
    "xml": ["activa.xml", "dins.xml", "solapa.xml"],
}


def test_l_analisi_diu_que_s_esborraria_sense_esborrar_res(admin, centre):
    resp = admin.post("/api/dades/purga/analitzar", json=INTERVAL)
    assert resp.status_code == 200, resp.text
    m = resp.json()
    assert m["bd"] == {"substitucions": 1, "vigilancies": 1, "grups_alliberats": 1, "baixes": 2}
    assert [p["fitxer"] for p in m["pdfs_a_esborrar"]] == ["260315_substitucions_260315_101010.pdf"]
    assert m["pdfs_revisio_manual"] == ["informe_direccio.pdf"]
    assert {v["path"]: v["bloquejat"] for v in m["xml_versions"]} == {
        "dins.xml": False, "solapa.xml": True, "activa.xml": True}
    assert _queda(centre) == INTACTE


def test_sense_confirmar_no_s_esborra_res(admin, centre):
    assert admin.post("/api/dades/purga/executar", json=INTERVAL).status_code == 400
    assert admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": False}).status_code == 400
    assert _queda(centre) == INTACTE


def test_esborra_el_de_dins_l_interval_i_res_mes(admin, centre):
    resp = admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True})
    assert resp.status_code == 200, resp.text
    informe = resp.json()
    assert informe["total_bd"] == 5 and informe["errors"] == []
    assert _queda(centre) == {
        "substitucions": [ABANS, DESPRES],
        "vigilancies": [ABANS, DESPRES],
        "grups_alliberats": [ABANS, DESPRES],
        # Les baixes que toquen l'interval s'esborren senceres, també la part de fora
        "baixes": ["Prof 5"],
        "xml": ["activa.xml", "solapa.xml"],
    }
    carpeta = get_data_dir_for_institucio(centre)
    assert not (carpeta / "dins.xml").exists()
    assert (carpeta / "solapa.xml").exists() and (carpeta / "activa.xml").exists()
    pdfs = sorted(p.name for p in get_export_dir_for_institucio(centre).iterdir())
    assert pdfs == ["260402_vigilancies_260402_101010.pdf", "informe_direccio.pdf"]


def test_no_toca_les_dades_d_un_altre_centre(admin):
    altre = nova_institucio()
    _omple(altre)
    assert admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True}).status_code == 200
    assert _queda(altre) == INTACTE
    assert len(list(get_export_dir_for_institucio(altre).iterdir())) == 3


def test_un_fitxer_compartit_amb_una_versio_que_es_queda_no_s_esborra(admin, centre):
    with get_data_db_session(centre) as db:
        db.query(XMLVersion).filter(XMLVersion.path == "dins.xml").update({XMLVersion.path: "activa.xml"})
        db.commit()
    assert admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True}).status_code == 200
    assert (get_data_dir_for_institucio(centre) / "activa.xml").exists()
    assert _queda(centre)["xml"] == ["activa.xml", "solapa.xml"]


def test_no_esborra_un_xml_de_fora_de_la_carpeta_del_centre(admin, centre):
    altre = nova_institucio()
    fitxer = get_data_dir_for_institucio(altre) / "teachers.xml"
    fitxer.write_text("<fet/>")
    with get_data_db_session(centre) as db:
        db.query(XMLVersion).filter(XMLVersion.path == "dins.xml").update({XMLVersion.path: str(fitxer)})
        db.commit()
    resp = admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True})
    assert resp.status_code == 200
    assert fitxer.exists()


def test_un_interval_al_reves_dona_400(admin, centre):
    al_reves = {"data_inici": FINAL.isoformat(), "data_final": INICI.isoformat(), "confirmar": True}
    assert admin.post("/api/dades/purga/analitzar", json=al_reves).status_code == 400
    assert admin.post("/api/dades/purga/executar", json=al_reves).status_code == 400
    assert _queda(centre) == INTACTE


def test_un_usuari_no_admin_no_pot_purgar(centre):
    nom = f"user_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "user")
    client = entra(client_per(APP), nom)
    assert client.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True}).status_code == 403
    assert _queda(centre) == INTACTE


# ------------------------------------------------ baixes i planificador

def test_l_analisi_detalla_les_baixes_i_avisa_de_les_que_surten_de_l_interval(admin):
    m = admin.post("/api/dades/purga/analitzar", json=INTERVAL).json()
    assert m["baixes"] == [
        {"professor": "Prof 4", "data_inici": "2026-02-20", "data_final": "2026-03-05", "s_esten_fora": True},
        {"professor": "Prof 3", "data_inici": "2026-03-10", "data_final": "2026-03-12", "s_esten_fora": False},
    ]


def _planificador(centre, dates, dies_horari, desat="2026-03-20T10:00:00"):
    import json
    from repositories import ConfiguracioRepository
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "scheduler_selected_dates", json.dumps(dates), tipus="json")
        ConfiguracioRepository.set(db, "scheduler_ultim_resultat", json.dumps({
            "desat": desat,
            "resultat": {"dies_utilitzar": ["Dilluns"], "horari": {"dies": dies_horari, "metadata": {}}},
        }), tipus="json")


def _config_planificador(centre):
    import json
    from repositories import ConfiguracioRepository
    with get_data_db_session(centre) as db:
        dates = ConfiguracioRepository.get(db, "scheduler_selected_dates")
        return json.loads(dates) if dates else None, ConfiguracioRepository.get(db, "scheduler_ultim_resultat")


def test_esborra_les_dates_i_l_ultim_horari_del_planificador_de_l_interval(admin, centre):
    _planificador(centre, ["2026-02-27", "2026-03-16", "2026-03-17", "2026-04-02"],
                  [{"dia": "Dilluns", "data": "2026-03-16", "sessions": []},
                   {"dia": "Dimarts", "data": "2026-03-17", "sessions": []}])
    m = admin.post("/api/dades/purga/analitzar", json=INTERVAL).json()["planificador"]
    assert m == {"dates_seleccionades": 2, "ultim_horari": {
        "desat": "2026-03-20T10:00:00", "dates": ["2026-03-16", "2026-03-17"], "s_esten_fora": False}}

    informe = admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True}).json()
    assert informe["planificador"] == {"dates_tretes": 2, "ultim_horari_esborrat": True}
    assert _config_planificador(centre) == (["2026-02-27", "2026-04-02"], None)


def test_un_ultim_horari_que_toca_l_interval_s_esborra_sencer_i_s_avisa(admin, centre):
    _planificador(centre, [], [{"dia": "Dimarts", "data": "2026-03-31", "sessions": []},
                               {"dia": "Dimecres", "data": "2026-04-01", "sessions": []}])
    ultim = admin.post("/api/dades/purga/analitzar", json=INTERVAL).json()["planificador"]["ultim_horari"]
    assert ultim["s_esten_fora"] is True
    admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True})
    assert _config_planificador(centre)[1] is None


def test_un_ultim_horari_de_fora_de_l_interval_es_conserva(admin, centre):
    _planificador(centre, ["2026-04-20"], [{"dia": "Dilluns", "data": "2026-04-20", "sessions": []}])
    m = admin.post("/api/dades/purga/analitzar", json=INTERVAL).json()["planificador"]
    assert m == {"dates_seleccionades": 0, "ultim_horari": None}
    informe = admin.post("/api/dades/purga/executar", json={**INTERVAL, "confirmar": True}).json()
    assert informe["planificador"] == {"dates_tretes": 0, "ultim_horari_esborrat": False}
    dates, ultim = _config_planificador(centre)
    assert dates == ["2026-04-20"] and ultim is not None

