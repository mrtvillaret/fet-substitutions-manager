"""Contracte HTTP de les dates, amb centres temporals i el rellotge de prova."""

from datetime import date

import pytest
from fastapi import Depends
from suport_api import XML_EXEMPLE, client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from absencia_coberta.router import router as absencies_cobertes_router
from auth.dependencies import get_current_user, require_admin
from configuracio import router as configuracio
from cursos import router as cursos
from dades import router as dades
from database import get_data_db_session
from estadistiques.router import router as estadistiques_router
from grups import router as grups
from horari import router as horari
from models import XMLVersion
from pdf import router as pdf
from planificador import router as scheduler
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from substitucions import router as substitucions
from vigilancies.router import router as vigilancies_router

APP = crea_app(configuracio.router)
for _router in (
    absencies_cobertes_router,
    cursos.router,
    grups.router,
    horari.router,
    pdf.router,
    substitucions.router,
    vigilancies_router,
):
    APP.include_router(_router, dependencies=[Depends(get_current_user)])
for _router in (dades.router, estadistiques_router, horari.router_admin, prioritats_router, scheduler.router):
    APP.include_router(_router, dependencies=[Depends(require_admin)])

DATA = "2026-03-01"
DATA_CURTA = "2026-3-1"
DATA_AMB_HORA = "2026-03-01T00:00:00"
DATES_INVALIDES = ("2026-02-31", DATA_AMB_HORA, "0")
ERROR_DATA = {"detail": "Format de data invàlid. Usa YYYY-MM-DD"}
OMESA = object()


@pytest.fixture
def centre(request):
    return nova_institucio(amb_xml=getattr(request, "param", False))


@pytest.fixture
def client(centre):
    limiter.reset()
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    with client_per(APP) as client:
        yield entra(client, nom)


def _comprova(resposta, estat, cos):
    assert resposta.status_code == estat, resposta.text
    assert resposta.json() == cos


@pytest.mark.parametrize(
    "modul, centre",
    [("substitucions", True), ("vigilancies", False)],
    indirect=["centre"],
    ids=["substitucions", "vigilancies"],
)
@pytest.mark.parametrize(
    "data, estat, cos",
    [
        (DATA, 200, []),
        (DATA_CURTA, 200, []),
        *((data, 400, ERROR_DATA) for data in (*DATES_INVALIDES, "null")),
        pytest.param("", 404, {"detail": "Not Found"}, id="buit"),
        pytest.param(OMESA, 404, {"detail": "Not Found"}, id="omes"),
    ],
)
def test_data_al_cami(client, modul, data, estat, cos):
    ruta = f"/api/{modul}" if data is OMESA else f"/api/{modul}/{data}"
    _comprova(client.get(ruta), estat, cos)


@pytest.mark.parametrize(
    "data, valida",
    [
        (DATA, True),
        (DATA_CURTA, True),
        *((d, False) for d in (*DATES_INVALIDES, "", "null")),
        pytest.param(OMESA, True, id="omesa"),
    ],
)
def test_data_a_la_consulta_d_estadistiques(client, data, valida):
    params = {"grups": "1-ESO-A", "data_final": "2026-11-05"}
    if data is not OMESA:
        params["data_inici"] = data
    resposta = client.get("/api/estadistiques/classes/detall", params=params)
    if not valida:
        _comprova(resposta, 400, ERROR_DATA)
        return
    _comprova(
        resposta,
        200,
        {
            "periode": {"data_inici": "2026-10-05" if data is OMESA else DATA, "data_final": "2026-11-05"},
            "grups": ["1-ESO-A"],
            "resultats": [],
            "resum": {
                "total": 0,
                "per_grup": [],
                "top_assignatura": None,
                "top_professor": None,
                "top_substitut": None,
            },
        },
    )


@pytest.mark.parametrize(
    "data, inici",
    [
        (DATA, DATA),
        (DATA_CURTA, DATA),
        *((d, None) for d in (*DATES_INVALIDES, "null")),
        pytest.param("", "2026-11-04", id="buit"),
        pytest.param(OMESA, "2026-11-04", id="omes"),
    ],
)
def test_data_al_formulari_de_pujada_xml(client, data, inici):
    camps = {} if data is OMESA else {"data_inici": data}
    with XML_EXEMPLE.open("rb") as fitxer:
        resposta = client.post("/api/files/upload-xml", data=camps, files={"file": ("prova.xml", fitxer)})
    if inici is None:
        _comprova(resposta, 400, ERROR_DATA)
        return
    assert resposta.status_code == 200, resposta.text
    _comprova(
        resposta,
        200,
        {
            "success": True,
            "filename": "prova.xml",
            "path": resposta.json()["path"],
            "data_inici": inici,
            "vigent_avui": True,
            "message": "Fitxer 'prova.xml' pujat correctament",
            "avisos": [],
            "recomptes": {"dies": 0, "substitucions": 0, "vigilancies": 0},
        },
    )


@pytest.mark.parametrize(
    "data, estat",
    [
        (DATA, 200),
        (DATA_CURTA, 200),
        *((d, 400) for d in (*DATES_INVALIDES, "")),
        (0, 422),
        (None, 422),
        pytest.param(OMESA, 422, id="omesa"),
    ],
)
@pytest.mark.parametrize(
    "modul, centre",
    [("absencies-cobertes", False), ("grups/periode", True)],
    indirect=["centre"],
    ids=["absencies-cobertes", "grups"],
)
def test_data_obligatoria_al_cos_json(client, modul, data, estat):
    if modul == "absencies-cobertes":
        camp = "data_inici"
        cos = {"professor": "Prof 1", "data_final": "2026-03-02"}
    else:
        camp = "data"
        cos = {"tipus": "professor", "clau": "Prof 1", "hores": ["10:00"]}
    if data is not OMESA:
        cos[camp] = data
    resposta = client.post(f"/api/{modul}", json=cos)
    if estat == 400:
        _comprova(resposta, 400, ERROR_DATA)
    elif estat == 422:
        error = (
            {"type": "missing", "msg": "Field required", "input": cos}
            if data is OMESA
            else {"type": "string_type", "msg": "Input should be a valid string", "input": data}
        )
        _comprova(resposta, 422, {"detail": [{**error, "loc": ["body", camp]}]})
    elif modul == "absencies-cobertes":
        _comprova(
            resposta,
            200,
            {
                "success": True,
                "id": 1,
                "message": "Absència coberta afegida",
                "canvis": {"absencies_esborrades": [], "vigilancies_buidades": [], "substituts_trets": []},
                "avisos": None,
            },
        )
        _comprova(
            client.get("/api/absencies-cobertes"),
            200,
            {
                "absencies_cobertes": [
                    {
                        "id": 1,
                        "professor": "Prof 1",
                        "data_inici": DATA,
                        "data_final": "2026-03-02",
                        "motiu": "",
                    }
                ]
            },
        )
    else:
        _comprova(resposta, 200, {"success": True, "dia_setmana": "Diumenge", "substituts_trets": []})


@pytest.mark.parametrize(
    "dates, referencia",
    [
        (DATA, DATA),
        (DATA_CURTA, DATA),
        (" 2026-11-05, , 2026-3-1, ", DATA),
        *((d, None) for d in (*DATES_INVALIDES, "null")),
        pytest.param("", "2026-11-04", id="buit"),
        pytest.param(OMESA, "2026-11-04", id="omes"),
    ],
)
def test_llista_csv_del_planificador(client, dates, referencia):
    params = {} if dates is OMESA else {"dates": dates}
    resposta = client.get("/api/scheduler/horari", params=params)
    if referencia is None:
        _comprova(resposta, 400, ERROR_DATA)
    else:
        _comprova(
            resposta,
            200,
            {
                "data_referencia": referencia,
                "sense_dates": referencia != DATA,
                "versio_des_de": None,
                "canvi_horari": None,
            },
        )


@pytest.mark.parametrize(
    "data, esperada",
    [
        (DATA, DATA),
        (DATA_CURTA, DATA),
        *((d, None) for d in (*DATES_INVALIDES, "")),
        (0, None),
        (None, None),
        pytest.param(OMESA, None, id="omesa"),
    ],
)
def test_configuracio_desa_i_retorna_les_dates_d_estadistiques(client, centre, data, esperada):
    cos = {"data_final_estadistiques": "2026-3-31"}
    camp = "data_inici_estadistiques"
    if data is not OMESA:
        cos[camp] = data
    resposta = client.put("/api/settings", json=cos)
    if data is not OMESA and data in (*DATES_INVALIDES, ""):
        _comprova(resposta, 400, ERROR_DATA)
        final = None
    elif data == 0:
        _comprova(
            resposta,
            422,
            {
                "detail": [
                    {
                        "type": "string_type",
                        "loc": ["body", camp],
                        "msg": "Input should be a valid string",
                        "input": 0,
                    }
                ]
            },
        )
        final = None
    else:
        final = "2026-03-31"
        canvis = ([f"Data estadístiques → {esperada}"] if esperada else []) + [f"Data fi estadístiques → {final}"]
        _comprova(
            resposta,
            200,
            {
                "success": True,
                "message": f"Configuració actualitzada: {', '.join(canvis)}",
                "changed": canvis,
            },
        )
    _comprova(
        client.get("/api/settings"),
        200,
        {
            "institucio": centre,
            "idioma": "ca",
            "xml_horari_path": None,
            camp: esperada,
            "data_final_estadistiques": final,
            "logo_path": None,
            "te_logo": False,
            "institucio_display_name": centre,
            "ultim_professor_subs": "",
            "xml_missing": True,
        },
    )


@pytest.mark.parametrize("ruta", ["/api/cursos", "/api/dades/purga/analitzar"])
@pytest.mark.parametrize(
    "data",
    [DATA, DATA_AMB_HORA, 0, "0", DATA_CURTA, "2026-02-31", "", None, pytest.param(OMESA, id="omesa")],
)
def test_dates_de_cursos_i_purga_al_cos_json(client, ruta, data):
    cursos = ruta == "/api/cursos"
    cos = {"nom": "Curs de prova"} if cursos else {"data_final": "2026-03-31"}
    if data is not OMESA:
        cos["data_inici"] = data
    resposta = client.post(ruta, json=cos)
    if data is OMESA:
        error = {"type": "missing", "msg": "Field required", "input": cos}
    elif data is None:
        error = {"type": "date_type", "msg": "Input should be a valid date", "input": None}
    elif data not in (DATA, DATA_CURTA):
        _comprova(resposta, 400, ERROR_DATA)
        return
    else:
        if cursos:
            _comprova(resposta, 200, {"id": 1, **cos, "data_inici": DATA, "data_fi": None})
        else:
            _comprova(
                resposta,
                200,
                {
                    "interval": {"inici": DATA, "final": "2026-03-31"},
                    "bd": {"substitucions": 0, "vigilancies": 0, "grups_alliberats": 0, "baixes": 0},
                    "total_bd": 0,
                    "baixes": [],
                    "planificador": {"dates_seleccionades": 0, "ultim_horari": None},
                    "xml_versions": [],
                },
            )
        return
    _comprova(resposta, 422, {"detail": [{**error, "loc": ["body", "data_inici"]}]})


def test_edicio_de_la_data_de_versio_xml(client, centre):
    with get_data_db_session(centre) as db:
        db.add(XMLVersion(path="prova.xml", data_inici=date(2026, 3, 1)))
        db.commit()
    ruta = "/api/settings/xml-versions"
    _comprova(client.put(f"{ruta}/1", json={"data_inici": ""}), 200, {"success": True})
    _comprova(client.put(f"{ruta}/1", json={"data_inici": "2026-02-31"}), 400, ERROR_DATA)
    _comprova(
        client.put(f"{ruta}/2", json={"data_inici": "2026-02-31"}),
        404,
        {
            "detail": "Versió XML no trobada",
            "codi": "versio_xml_no_trobada",
            "params": {},
        },
    )
    _comprova(
        client.get(ruta),
        200,
        {
            "versions": [{"id": 1, "path": "prova.xml", "data_inici": DATA, "data_fi": None, "hash_contingut": None}],
        },
    )


@pytest.mark.parametrize("data", [DATA, DATA_CURTA, *DATES_INVALIDES, "", "null", pytest.param(OMESA, id="omesa")])
def test_data_a_la_consulta_pdf(client, data):
    params = {"data_final": DATA}
    if data is not OMESA:
        params["data_inici"] = data
    resposta = client.get("/api/pdf/vigilancies/comptes-sense-nivell", params=params)
    if data is OMESA:
        _comprova(
            resposta,
            422,
            {
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["query", "data_inici"],
                        "msg": "Field required",
                        "input": None,
                    }
                ]
            },
        )
    elif data in (DATA, DATA_CURTA):
        _comprova(resposta, 200, {"sense_nivell": 0})
    else:
        _comprova(resposta, 400, ERROR_DATA)


@pytest.mark.parametrize("data", [DATA, DATA_CURTA, *DATES_INVALIDES, "", 0, None, pytest.param(OMESA, id="omesa")])
def test_data_opcional_de_no_substituir(client, data):
    ruta = "/api/prioritats/no-substituir"
    cos = {"assignatura": "Pares"}
    if data is not OMESA:
        cos["data"] = data
    resposta = client.post(ruta, json=cos)
    if data in (*DATES_INVALIDES, ""):
        _comprova(resposta, 400, ERROR_DATA)
    elif data == 0:
        _comprova(
            resposta,
            422,
            {
                "detail": [
                    {
                        "type": "string_type",
                        "loc": ["body", "data"],
                        "msg": "Input should be a valid string",
                        "input": 0,
                    }
                ]
            },
        )
    else:
        inici = DATA if data in (DATA, DATA_CURTA) else "2026-11-04"
        _comprova(
            resposta,
            200,
            {
                "success": True,
                "id": 1,
                "message": "Assignatura 'Pares' afegida a no substituir",
            },
        )
        _comprova(
            client.get(ruta),
            200,
            {
                "assignatures": ["Pares"],
                "entrades": [{"assignatura": "Pares", "vigent_des_de": inici, "vigent_fins_a": None}],
            },
        )


@pytest.mark.parametrize("data", [DATA, DATA_CURTA, *DATES_INVALIDES, "", 0, None, pytest.param(OMESA, id="omesa")])
def test_data_a_la_llista_json_del_planificador(client, data):
    ruta = "/api/scheduler/dates"
    cos = {} if data is OMESA else {"selected_dates": ["2026-04-20", data, DATA]}
    resposta = client.put(ruta, json=cos)
    if data is OMESA:
        _comprova(
            resposta,
            422,
            {
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["body", "selected_dates"],
                        "msg": "Field required",
                        "input": {},
                    }
                ]
            },
        )
    elif data in (*DATES_INVALIDES, ""):
        _comprova(resposta, 400, ERROR_DATA)
    elif data in (0, None):
        _comprova(
            resposta,
            422,
            {
                "detail": [
                    {
                        "type": "string_type",
                        "loc": ["body", "selected_dates", 1],
                        "msg": "Input should be a valid string",
                        "input": data,
                    }
                ]
            },
        )
    else:
        _comprova(resposta, 200, {"success": True})
        _comprova(client.get(ruta), 200, {"selected_dates": ["2026-04-20", DATA, DATA]})


@pytest.mark.parametrize("amb_curs", [False, True])
def test_curs_dates_valida_el_csv_tambe_sense_curs_actual(client, amb_curs):
    if amb_curs:
        _comprova(
            client.post("/api/cursos", json={"nom": "Actual", "data_inici": "2026-09-01"}),
            200,
            {
                "id": 1,
                "nom": "Actual",
                "data_inici": "2026-09-01",
                "data_fi": None,
            },
        )
    ruta = "/api/scheduler/curs-dates"
    _comprova(client.get(ruta, params={"dates": "ahir"}), 400, ERROR_DATA)
    _comprova(client.get(ruta, params={"dates": "2026-11-4"}), 200, {"curs_anterior": None})
