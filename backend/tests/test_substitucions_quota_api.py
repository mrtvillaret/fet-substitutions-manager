"""La finestra s'alimenta de la BD del centre, també des dels camins d'API."""

from datetime import date

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
                    "data": date.fromisoformat(data),
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
        carregues.append(data.isoformat())
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
        files = SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA))
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
        ("2026-04-14", "10:00", "Guàrdia", "Prof 3"),  # dimarts
        ("2026-04-19", "10:00", "Guàrdia", "Prof 3"),  # diumenge
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


# Historials (del centre o d'un altre) on Prof 37 queda fora de la finestra o no hi és
FINESTRES = {
    # Prof 37 és a l'11a fila més antiga i ja no compta; els altres sí
    "onze files amb la mateixa data: ordre estable per id": [
        {"professors": ["Prof 37", "Prof 3", "Prof 21", "Prof 28"] + ["Prof 99"] * 7}
    ],
    "ordre per data abans de l'id i aïllament del centre": [
        {"professors": ["Prof 3", "Prof 21", "Prof 28"] + ["Prof 99"] * 7, "data": "2026-04-27"},
        # ID més alt però data anterior: ha de quedar fora de la finestra
        {"professors": ["Prof 37"], "data": "2026-04-13", "tipus": "Pares"},
        {"altre_centre": True, "professors": ["Prof 37"] * 10, "tipus": "Pares"},
    ],
    "una fila pendent no ocupa posició a la finestra": [
        {"professors": ["Prof 3", "Prof 21", "Prof 28"]},
        {"professors": [""] * 10},
    ],
}


@pytest.mark.parametrize("historials", FINESTRES.values(), ids=FINESTRES)
def test_la_finestra_son_les_deu_ultimes_files_amb_substitut_del_centre(monkeypatch, historials):
    centre, client = _prepara()
    altre, _ = _prepara()
    for historial in historials:
        historial = dict(historial)
        _historial(altre if historial.pop("altre_centre", False) else centre, **historial)
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
        files = SubstitucioRepository.get_by_date(db, date.fromisoformat("2026-04-13"))
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
        files = SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA))
        assert {s.substitut for s in files if s.substitut} == {"Prof 37", "Prof 3"}


def test_generar_i_regenerar_no_es_compten_a_si_mateixos(monkeypatch):
    _, client = _prepara()
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)
    assert _marca_absencia(client, hores=["10:00"]).status_code == 200
    for _ in range(3):
        assert client.post(f"{URL}/generar", params={"regenerar_tot": True}).status_code == 200
        assert _sub(client, "10:00")["substitut"] == "Prof 3"


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
        files = SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA))
        principal = next(s for s in files if s.professor_absent == ABSENT)
        vigilant = next(s for s in files if s.tipus_absencia == "VIGILANCIA_ABSENT")
        assert principal.substitut == "Prof 37"
        assert vigilant.substitut == "Prof 3"


def test_la_quota_de_diumenge_compta_nomes_els_diumenges(monkeypatch):
    import xml.etree.ElementTree as ET
    from copy import deepcopy

    from database import get_data_dir_for_institucio

    centre, client = _prepara()
    cami = get_data_dir_for_institucio(centre) / "teachers.xml"
    arbre = ET.parse(cami)
    # Horari de prova de set dies, amb les mateixes classes i guàrdies dilluns i diumenge.
    for professor in arbre.getroot().findall("Teacher"):
        dilluns = professor.find("Day[@name='Dilluns']")
        if dilluns is not None:
            ET.SubElement(professor, "Day", name="Dissabte")
            diumenge = deepcopy(dilluns)
            diumenge.set("name", "Diumenge")
            professor.append(diumenge)
    arbre.write(cami, encoding="utf-8")
    monkeypatch.setattr(services, "_atzar", PrimerEmpat)

    ruta = "/api/substitucions/2026-04-19"
    absencia = client.put(f"{ruta}/absencies/{ABSENT}", json={"hores_absencia": ["10:00"], "updated_at_map": {}})
    assert absencia.status_code == 200, absencia.text

    for data, esperat in (("2026-04-13", "Prof 3"), ("2026-04-12", "Prof 37")):
        _historial(centre, data=data)
        generat = client.post(f"{ruta}/generar", params={"regenerar_tot": True})
        assert generat.status_code == 200, generat.text
        resposta = client.get(ruta)
        assert resposta.status_code == 200, resposta.text
        [fila] = resposta.json()
        assert fila["substitut"] == esperat
