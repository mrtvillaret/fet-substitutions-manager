"""La finestra s'alimenta de la BD del centre, també des dels camins d'API."""

import pytest
from suport_api import nova_institucio
from test_substitucions_api import ABSENT, DATA, URL, _assigna, _marca_absencia, _sub
from test_vigilancies_api import _admin_de, _crea

from database import get_data_db_session
from prioritats.repositories import NoSubstituirRepository
from rate_limit import limiter
from substitucions import services
from substitucions.repositories import SubstitucioRepository


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()


def _historial(centre, professors=("Prof 3", "Prof 21", "Prof 28"), data="2026-04-13", hora="10:00", tipus="Guàrdia"):
    with get_data_db_session(centre) as db:
        for professor in professors:
            SubstitucioRepository.create(
                db,
                {
                    "data": data,
                    "hora": hora,
                    "professor_absent": "Prof 1",
                    "assignatura": "E.F.",
                    "substitut": professor,
                    "tipus_substitut": f"disponible ({tipus})",
                    "tipus_absencia": "ABSENCIA",
                },
            )
        db.commit()


def _prepara():
    centre = nova_institucio(
        amb_xml=True, prioritats=[("Candidats", [("Guàrdia", 3), ("Pares", 1)]), ("Inferior", ["ED"])]
    )
    client = _admin_de(centre)
    with get_data_db_session(centre) as db:
        for activitat in ["Guàrdia", "Pares", "ED"]:
            NoSubstituirRepository.create(db, activitat)
        db.commit()
    return centre, client


class PrimerEmpat:
    def choices(self, candidats, *, weights, k):
        return [candidats[0]]


@pytest.mark.parametrize("operacio", ["pendents", "regenera", "reassigna", "millora", "vigilant_absent"])
def test_tots_els_camins_apliquen_quota_amb_pesos_i_historial_bd(monkeypatch, operacio):
    centre, client = _prepara()
    _historial(centre)
    carregues = []
    original = SubstitucioRepository.historial_quota

    def carrega(db, data):
        carregues.append(data)
        return original(db, data)

    monkeypatch.setattr(SubstitucioRepository, "historial_quota", carrega)
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    if operacio == "vigilant_absent":
        # Prof 13 fa ED sense grup: no necessita cobertura de classe.
        _crea(client, "Prof 13")
        assert _marca_absencia(client, professor="Prof 13", hores=["10:00"]).status_code == 200
    else:
        assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    if operacio in {"reassigna", "millora"}:
        if operacio == "millora":
            assert _assigna(client, "10:00", "Prof 13").status_code == 200
        resp = client.post(f"{URL}/reassign-problematics")
    else:
        if operacio == "regenera":
            assert _assigna(client, "10:00", "Prof 37").status_code == 200
        resp = client.post(f"{URL}/generar", params={"regenerar_tot": operacio == "regenera"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["avisos"] == []
    assert carregues == [DATA]
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, DATA)
        if operacio == "vigilant_absent":
            fila = next(s for s in files if s.tipus_absencia == "VIGILANCIA_ABSENT")
        else:
            fila = next(s for s in files if s.professor_absent == ABSENT)
        assert fila.substitut == "Prof 37"
        assert fila.tipus_substitut == "disponible (Pares)"


@pytest.mark.parametrize(
    "data,hora,tipus,esperat",
    [
        ("2026-04-27", "10:00", "Guàrdia", "Prof 37"),  # futur ja generat
        ("2026-04-14", "10:00", "Guàrdia", "Prof 3"),  # un altre dia setmanal
        ("2026-04-13", "11:00", "Guàrdia", "Prof 3"),  # una altra hora
        ("2026-04-13", "10:00", "ED", "Prof 3"),  # una altra categoria guardada
    ],
)
def test_franja_i_categoria_de_l_historial_i_dates_futures(monkeypatch, data, hora, tipus, esperat):
    centre, client = _prepara()
    _historial(centre, data=data, hora=hora, tipus=tipus)
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    assert client.post(f"{URL}/generar").status_code == 200
    assert _sub(client, "10:00")["substitut"] == esperat


def test_les_onze_files_amb_la_mateixa_data_tenen_ordre_estable_per_id(monkeypatch):
    centre, client = _prepara()
    _historial(centre, professors=["Prof 37", "Prof 3", "Prof 21", "Prof 28"] + ["Prof 99"] * 7)
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    assert client.post(f"{URL}/generar").status_code == 200
    # Prof 37 és a l'11a fila més antiga i ja no compta; els altres sí.
    assert _sub(client, "10:00")["substitut"] == "Prof 37"


def test_ordre_per_data_abans_de_l_id_i_aillament_del_centre(monkeypatch):
    centre, client = _prepara()
    _historial(centre, professors=["Prof 3", "Prof 21", "Prof 28"] + ["Prof 99"] * 7, data="2026-04-27")
    # ID més alt però data anterior: ha de quedar fora de la finestra.
    _historial(centre, professors=["Prof 37"], data="2026-04-13", tipus="Pares")
    altre, _ = _prepara()
    _historial(altre, professors=["Prof 37"] * 10, tipus="Pares")
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    assert client.post(f"{URL}/generar").status_code == 200
    assert _sub(client, "10:00")["substitut"] == "Prof 37"


def test_una_modificacio_manual_de_l_historial_canvia_la_tria(monkeypatch):
    centre, client = _prepara()
    passat = "/api/substitucions/2026-04-13"
    assert (
        client.put(f"{passat}/absencies/{ABSENT}", json={"hores_absencia": ["10:00"], "updated_at_map": {}}).status_code
        == 200
    )
    assert client.put(f"{passat}/10:00/{ABSENT}", json={"substitut": "Prof 3", "force": True}).status_code == 200
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    assert client.post(f"{URL}/generar").status_code == 200
    assert _sub(client, "10:00")["substitut"] == "Prof 21"
    assert client.put(f"{passat}/10:00/{ABSENT}", json={"substitut": "Prof 21", "force": True}).status_code == 200
    assert client.post(f"{URL}/generar", params={"regenerar_tot": True}).status_code == 200
    assert _sub(client, "10:00")["substitut"] == "Prof 3"
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, "2026-04-13")
        assert files[0].substitut == "Prof 21"
        assert files[0].tipus_substitut == "disponible (Guàrdia)"


def test_simultanies_comparteixen_la_finestra_i_expulsen_la_mes_antiga(monkeypatch):
    centre, client = _prepara()
    _historial(centre, professors=["Prof 3", "Prof 21", "Prof 28"] + ["Prof 99"] * 7)

    class UltimEmpat:
        def choices(self, candidats, *, weights, k):
            return [candidats[-1]]

    monkeypatch.setattr(services, "_atzar", UltimEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    assert _marca_absencia(client, professor="Prof 48", hores=["10:00"]).status_code == 200
    assert client.post(f"{URL}/generar").status_code == 200
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, DATA)
        assert {s.substitut for s in files if s.substitut} == {"Prof 37", "Prof 3"}


def test_generar_i_regenerar_no_es_compten_a_si_mateixos(monkeypatch):
    _, client = _prepara()
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    for _ in range(3):
        assert client.post(f"{URL}/generar", params={"regenerar_tot": True}).status_code == 200
        assert _sub(client, "10:00")["substitut"] == "Prof 3"


def test_una_fila_pendent_no_ocupa_posicio_a_la_finestra(monkeypatch):
    centre, client = _prepara()
    _historial(centre, professors=["Prof 3", "Prof 21", "Prof 28"])
    _historial(centre, professors=[""] * 10)
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    assert client.post(f"{URL}/generar").status_code == 200
    assert _sub(client, "10:00")["substitut"] == "Prof 37"


def test_motor_i_vigilant_absent_comparteixen_la_finestra(monkeypatch):
    centre, client = _prepara()
    _historial(centre, professors=["Prof 3", "Prof 21", "Prof 28"] + ["Prof 99"] * 7)

    class UltimEmpat:
        def choices(self, candidats, *, weights, k):
            return [candidats[-1]]

    monkeypatch.setattr(services, "_atzar", UltimEmpat)
    _crea(client, "Prof 13")
    assert _marca_absencia(client, professor="Prof 13", hores=["10:00"]).status_code == 200
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    assert client.post(f"{URL}/generar").status_code == 200
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, DATA)
        principal = next(s for s in files if s.professor_absent == ABSENT)
        vigilant = next(s for s in files if s.tipus_absencia == "VIGILANCIA_ABSENT")
        assert principal.substitut == "Prof 37"
        assert vigilant.substitut == "Prof 3"
