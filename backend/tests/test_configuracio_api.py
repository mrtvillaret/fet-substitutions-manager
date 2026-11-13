"""
Configuració del centre (/api/settings): què es desa, qui ho pot desar i què
en surt.
"""

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from config.settings import config
from configuracio import router as configuracio
from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session
from horari import context as horari_context
from rate_limit import limiter

APP = crea_app(configuracio.router)
URL = "/api/settings"
DILLUNS = "2026-04-20"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def config_global(tmp_path, monkeypatch):
    """La configuració global, en un fitxer temporal: desar-la no toca el
    config.json del codi, i en acabar torna a ser la d'abans."""
    monkeypatch.setattr(config, "global_config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "global_data", dict(config.global_data))
    return config


def _client(centre, rol="admin"):
    nom = f"{rol}_{unic()}"
    crea_usuari(nom, centre, rol)
    return entra(client_per(APP), nom)


def test_desar_la_configuracio_no_canvia_el_centre_per_defecte(config_global):
    # La pantalla envia sempre el camp institucio (el centre de qui desa): el
    # superadmin que desava des d'un altre centre canviava el per defecte del servidor
    centre = nova_institucio()
    per_defecte = config_global.global_data.get("institucio")

    resposta = _client(centre, "super_admin").put(URL, json={"institucio": centre, "idioma": "es"})

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["changed"] == ["Idioma → es"]
    assert config_global.global_data.get("institucio") == per_defecte
    assert not config_global.global_config_file.exists()


def test_desar_la_configuracio_no_escriu_a_la_bd_del_centre_per_defecte(config_global):
    # Abans, en desar l'idioma, les dates o l'últim professor, es tornava a llegir
    # la configuració del centre per defecte del servidor i s'hi escrivien les
    # claus que hi faltaven
    centre, per_defecte = nova_institucio(), nova_institucio()
    config_global.global_data["institucio"] = per_defecte
    with get_data_db_session(per_defecte) as db:
        abans = ConfiguracioRepository.get_all_as_dict(db)

    cos = {"idioma": "es", "data_inici_estadistiques": "2026-09-01", "ultim_professor_subs": "Prof 9"}
    resposta = _client(centre).put(URL, json=cos)

    assert resposta.status_code == 200, resposta.text
    with get_data_db_session(per_defecte) as db:
        assert ConfiguracioRepository.get_all_as_dict(db) == abans
    with get_data_db_session(centre) as db:
        assert ConfiguracioRepository.get(db, "idioma") == "es"


def test_canviar_l_ultim_professor_nomes_buida_l_horari_del_centre():
    # Abans es buidava la memòria cau de l'horari de tots els centres
    centre, altre = nova_institucio(amb_xml=True), nova_institucio(amb_xml=True)
    del_centre, de_l_altre = (
        horari_context.get_horari(centre, data_iso=DILLUNS),
        horari_context.get_horari(altre, data_iso=DILLUNS),
    )

    resposta = _client(centre).put(URL, json={"ultim_professor_subs": "Prof 12"})

    assert resposta.status_code == 200, resposta.text
    assert horari_context.get_horari(altre, data_iso=DILLUNS) is de_l_altre
    nou = horari_context.get_horari(centre, data_iso=DILLUNS)
    assert nou is not del_centre and "Prof 13" not in nou.professors


def _config_del_centre(centre, clau):
    with get_data_db_session(centre) as db:
        return ConfiguracioRepository.get(db, clau)


def test_desar_la_configuracio_es_tot_o_res():
    # L'admin no pot canviar el nom visible: abans, l'idioma (enviat al
    # mateix temps) ja s'havia desat quan arribava el 403
    centre = nova_institucio()

    resposta = _client(centre).put(URL, json={"idioma": "en", "institucio_display_name": "Nom nou"})

    assert resposta.status_code == 403
    assert _config_del_centre(centre, "idioma") is None
    assert _config_del_centre(centre, "institucio_display_name") is None


@pytest.mark.parametrize(
    "cos",
    [
        {"idioma": "xx"},
        {"data_inici_estadistiques": "no és una data"},
        {"data_final_estadistiques": "2027-02-30"},
        {"idioma": "es", "data_inici_estadistiques": "1/9/2026"},
    ],
)
def test_un_idioma_desconegut_o_una_data_mal_escrita_donen_400_i_no_es_desa_res(cos):
    centre = nova_institucio()

    resposta = _client(centre).put(URL, json=cos)

    assert resposta.status_code == 400, resposta.text
    for clau in ("idioma", "data_inici_estadistiques", "data_final_estadistiques"):
        assert _config_del_centre(centre, clau) is None


def test_els_idiomes_i_les_dates_valids_es_desen():
    centre = nova_institucio()
    cos = {"idioma": "it", "data_inici_estadistiques": "2026-09-01", "data_final_estadistiques": "2027-06-30"}

    assert _client(centre).put(URL, json=cos).status_code == 200
    assert [_config_del_centre(centre, clau) for clau in cos] == list(cos.values())


def test_la_configuracio_no_diu_la_carpeta_del_servidor_ni_no_substituir():
    # La pantalla no feia servir cap dels dos camps, i data_dir era un camí del servidor
    cos = _client(nova_institucio()).get(URL).json()

    assert "data_dir" not in cos and "no_substituir" not in cos
    assert {"institucio", "idioma", "te_logo", "xml_missing", "ultim_professor_subs"} <= set(cos)
