"""Els canvis d'alliberats i la reconciliació formen una sola transacció."""

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from database import get_data_db_session
from grups import router as grups
from grups import services as grups_services
from grups.repositories import GrupsAlliberatsRepository
from models import AlliberamentPeriode, GrupAlliberat
from prioritats.repositories import NoSubstituirRepository
from substitucions import cobertures
from substitucions import router as substitucions_router
from substitucions.reconciliacio import treu_substituts_no_valids
from substitucions.repositories import SubstitucioRepository
from vigilancies.repositories import VigilanciaRepository

DATA = "2026-04-20"
APP = crea_app(grups.router, substitucions_router.router)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre, rellotge_fix):
    rellotge_fix.moment = datetime(2026, 4, 20, 12, tzinfo=UTC)
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    client_sense_excepcions = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    return entra(client_sense_excepcions, nom)


def _prepara_dia_afectat(client):
    resposta = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 15",
        json={"hores_absencia": ["10:00"], "updated_at_map": {}},
    )
    assert resposta.status_code == 200, resposta.text


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        alliberats = db.query(GrupAlliberat).order_by(GrupAlliberat.id).all()
        periode = db.query(AlliberamentPeriode).order_by(AlliberamentPeriode.id).all()
        return {
            "grups": [(fila.id, fila.data.isoformat(), fila.hora, fila.grups) for fila in alliberats],
            "periode": [
                (
                    fila.id,
                    fila.tipus,
                    fila.clau,
                    fila.dia_setmana,
                    fila.hora,
                    fila.des_de.isoformat(),
                    bool(fila.alliberat),
                )
                for fila in periode
            ],
            "substitucions": sorted(
                SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA)), key=lambda fila: fila.id
            ),
        }


def _reconciliacio_que_falla(monkeypatch):
    def genera_i_falla(*_args, **_kwargs):
        raise RuntimeError("error simulat reconciliant substitucions")

    monkeypatch.setattr(grups_services, "genera_substitucions_dia", genera_i_falla)


def test_desar_el_dia_desfa_alliberats_i_derivats_si_falla_la_reconciliacio(client, centre, monkeypatch):
    _prepara_dia_afectat(client)
    abans = _bolcat(centre)
    _reconciliacio_que_falla(monkeypatch)

    resposta = client.put(f"/api/grups/{DATA}", json={"grups": {"10:00": ["3-ESO-A"]}})

    assert resposta.status_code == 500
    assert "error_ref" in resposta.json()
    assert _bolcat(centre) == abans


def test_desar_el_dia_desfa_tot_si_falla_despres_de_refrescar_cobertures(client, centre, monkeypatch):
    _prepara_dia_afectat(client)
    abans = _bolcat(centre)
    refresca_real = cobertures.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat després de refrescar cobertures")

    monkeypatch.setattr(grups_services, "refresca_cobertures", refresca_i_falla)

    resposta = client.put(f"/api/grups/{DATA}", json={"grups": {"10:00": ["3-ESO-A"]}})

    assert resposta.status_code == 500
    assert "error_ref" in resposta.json()
    assert _bolcat(centre) == abans


def test_afegir_periode_desfa_el_canvi_si_falla_la_reconciliacio(client, centre, monkeypatch):
    _prepara_dia_afectat(client)
    abans = _bolcat(centre)
    _reconciliacio_que_falla(monkeypatch)

    resposta = client.post(
        "/api/grups/periode",
        json={"tipus": "professor", "clau": "Prof 21", "hores": ["10:00"], "data": DATA},
    )

    assert resposta.status_code == 500
    assert "error_ref" in resposta.json()
    assert _bolcat(centre) == abans


def test_afegir_periode_accepta_una_data_sense_zeros(client, centre):
    cos = {"tipus": "professor", "clau": "Prof 21", "hores": ["10:00"]}
    curta = client.post("/api/grups/periode", json={**cos, "data": "2026-3-1"})

    assert curta.status_code == 200, curta.text
    with get_data_db_session(centre) as db:
        assert db.query(AlliberamentPeriode).one().des_de.isoformat() == "2026-03-01"

    normalitzada = client.post("/api/grups/periode", json={**cos, "data": "2026-03-01"})
    assert normalitzada.status_code == 200, normalitzada.text
    assert curta.json() == normalitzada.json()


def test_un_periode_amb_camps_incomplets_retorna_422_abans_de_validar_la_data(client):
    cos = {"tipus": "professor", "clau": "Prof 21", "data": "2026-02-30"}
    resposta = client.post("/api/grups/periode", json=cos)

    assert resposta.status_code == 422, resposta.text
    assert resposta.json() == {
        "detail": [{"type": "missing", "loc": ["body", "hores"], "msg": "Field required", "input": cos}]
    }


def test_franges_de_reforc_sense_data_retorna_el_cos_historic_del_422(client):
    resposta = client.get("/api/grups/reforcos/Reforç")
    error = {"type": "missing", "loc": ["query", "data"], "msg": "Field required", "input": None}

    assert resposta.status_code == 422, resposta.text
    assert resposta.json() == {"detail": [error, error]}


def _desa_absencia(centre, **canvis):
    with get_data_db_session(centre) as db:
        fila = SubstitucioRepository.create(
            db,
            {
                "data": date.fromisoformat(DATA),
                "hora": "09:00",
                "professor_absent": "Prof 1",
                "assignatura": "E.F.",
                "grup": "3-ESO-A",
                "substitut": "Prof 2",
                "tipus_substitut": "disponible (Guàrdia)",
                "tipus_absencia": "SERVEI",
            }
            | canvis,
        )
        db.commit()
        return str(fila.id)


def _desa_grups(client, **marques):
    resposta = client.put(f"/api/grups/{DATA}", json=marques)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@pytest.mark.parametrize("marques", [{"grups": {"09:00": ["3-ESO-A"]}}, {"professors": {"09:00": ["Prof 1"]}}])
def test_alliberar_buida_el_substitut_i_la_quota_i_conserva_l_absencia(client, centre, marques):
    _desa_absencia(centre, grup=" 3-ESO-A ")
    data_quota = date(2026, 4, 27)
    with get_data_db_session(centre) as db:
        assert SubstitucioRepository.historial_quota(db, data_quota) == [("09:00", "Prof 2", "disponible (Guàrdia)")]

    assert _desa_grups(client, **marques)["substituts_trets"] == []

    assert client.get(f"/api/substitucions/{DATA}").json() == []
    with get_data_db_session(centre) as db:
        [fila] = SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA))
        assert (fila.substitut, fila.tipus_substitut) == ("", "")
        assert (fila.professor_absent, fila.hora, fila.tipus_absencia) == ("Prof 1", "09:00", "SERVEI")
        assert SubstitucioRepository.historial_quota(db, data_quota) == []

    _desa_grups(client)
    [visible] = client.get(f"/api/substitucions/{DATA}").json()
    assert (visible["professor_absent"], visible["hora"], visible["substitut"], visible["tipus_absencia"]) == (
        "Prof 1",
        "09:00",
        "",
        "SERVEI",
    )


def test_alliberar_no_avisa_si_el_substitut_tambe_era_invalid(client, centre):
    _desa_absencia(centre, substitut="Professor fora de l'horari")
    assert _desa_grups(client, grups={"09:00": ["3-ESO-A"]})["substituts_trets"] == []


def test_no_substituir_buida_el_substitut_sense_avis_i_preserva_el_vigilant_absent(client, centre):
    no_substituir = _desa_absencia(centre, substitut="Professor fora de l'horari")
    vigilancia = _desa_absencia(centre, grup="1-BAT-A", tipus_absencia="VIGILANCIA_ABSENT", assignatura="VIGILÀNCIA")
    with get_data_db_session(centre) as db:
        NoSubstituirRepository.create(db, "E.F.")
        NoSubstituirRepository.create(db, "VIGILÀNCIA")
        GrupsAlliberatsRepository.afegeix(db, date.fromisoformat(DATA), "09:00", "1-BAT-A")
        VigilanciaRepository.create(
            db,
            date.fromisoformat(DATA),
            {
                "hora": "09:00",
                "tipus": "Examen",
                "grups": "1-BAT-A",
                "aula": "A01",
                "vigilant": "Prof 1",
                "nivell": "3-ESO",
            },
        )
        assert treu_substituts_no_valids(db, date.fromisoformat(DATA)) == []
        db.commit()

    visibles = {str(f["id"]) for f in client.get(f"/api/substitucions/{DATA}").json()}
    assert vigilancia in visibles
    assert no_substituir not in visibles
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA))
        assert {f.id: (f.substitut, f.tipus_substitut) for f in files if f.tipus_absencia != "ENCADENADA"} == {
            no_substituir: ("", ""),
            vigilancia: ("Prof 2", "disponible (Guàrdia)"),
        }


def test_alliberar_la_classe_d_un_vigilant_treu_la_cobertura_i_l_encadenada(client, centre):
    with get_data_db_session(centre) as db:
        VigilanciaRepository.create(
            db,
            date.fromisoformat(DATA),
            {
                "hora": "10:00",
                "tipus": "Examen",
                "grups": "1-BAT-A",
                "aula": "A01",
                "vigilant": "Prof 15",
                "nivell": "1-BAT",
            },
        )
        db.commit()
    _desa_absencia(
        centre,
        hora="10:00",
        professor_absent="Prof 15",
        assignatura="Anglès",
        substitut="Prof 21",
        tipus_absencia="VIGILANCIA",
    )

    _desa_grups(client, grups={"10:00": ["3-ESO-A"]})

    assert client.get(f"/api/substitucions/{DATA}").json() == []
    with get_data_db_session(centre) as db:
        assert SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA)) == []

    _desa_grups(client)

    [fila] = client.get(f"/api/substitucions/{DATA}").json()
    assert (fila["tipus_absencia"], fila["substitut"]) == ("VIGILANCIA", "")


def test_desar_els_grups_conserva_les_cobertures_que_continuen(client, centre):
    """Les cobertures de vigilància es refan per diferències: les que continuen
    conserven id, versió, substitut i comentaris; només desapareixen les que sobren."""
    with get_data_db_session(centre) as db:
        for vigilant, grups in (("Prof 15", "1-BAT-A"), ("Prof 1", "1-BAT-B")):
            VigilanciaRepository.create(
                db,
                date.fromisoformat(DATA),
                {
                    "hora": "10:00",
                    "tipus": "Examen",
                    "grups": grups,
                    "aula": "A01",
                    "vigilant": vigilant,
                    "nivell": "1-BAT",
                },
            )
        db.commit()
    _desa_grups(client)
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA))
        cobertures = {f.professor_absent: f for f in files if f.tipus_absencia == "VIGILANCIA"}
        assert set(cobertures) == {"Prof 15", "Prof 1"}
        SubstitucioRepository.update(db, int(cobertures["Prof 15"].id), {"comentaris": "sense substitut"})
        SubstitucioRepository.update(
            db,
            int(cobertures["Prof 1"].id),
            {"substitut": "Prof 21", "tipus_substitut": "disponible (Guàrdia)", "comentaris": "amb substitut"},
        )
        db.commit()

    def cobertures_desades():
        return {f.professor_absent: f for f in _bolcat(centre)["substitucions"] if f.tipus_absencia == "VIGILANCIA"}

    abans = cobertures_desades()

    _desa_grups(client)

    assert cobertures_desades() == abans

    _desa_grups(client, grups={"10:00": ["3-ESO-A"]})

    assert cobertures_desades() == {"Prof 1": abans["Prof 1"]}
