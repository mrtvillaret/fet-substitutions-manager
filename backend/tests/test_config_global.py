"""La configuració mutable viu fora del codi, amb lectura antiga compatible."""

import json

import pytest

from config.settings import Config


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "dades"))
    monkeypatch.delenv("APP_CONFIG_PATH", raising=False)
    monkeypatch.delenv("APP_INSTITUCIO", raising=False)
    return tmp_path / "antic" / "config.json", tmp_path / "dades" / "config.json"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_new_installation_writes_only_to_data(paths):
    legacy, target = paths
    config = Config(legacy_config_file=legacy)
    assert config.global_config_file == target
    assert json.loads(target.read_text()) == config.global_defaults
    assert not legacy.parent.exists()


def test_legacy_fallback_is_readonly_and_saves_to_new_location(paths):
    legacy, target = paths
    write_json(legacy, {"idioma": "it", "institucio": "centre_inventat"})
    before = legacy.read_bytes()
    config = Config(legacy_config_file=legacy)
    assert config.idioma == "it"
    assert config.institucio == "centre_inventat"
    assert not target.exists()
    config.idioma = "ca"
    config.save_global()
    assert legacy.read_bytes() == before
    assert json.loads(target.read_text())["idioma"] == "ca"
    assert Config(legacy_config_file=legacy).idioma == "ca"


def test_new_file_precedes_legacy(paths):
    legacy, target = paths
    write_json(legacy, {"idioma": "it"})
    write_json(target, {"idioma": "en"})
    assert Config(legacy_config_file=legacy).idioma == "en"


def test_explicit_path_and_environment_override(paths, tmp_path, monkeypatch):
    legacy, default_target = paths
    target = tmp_path / "extern" / "config.json"
    monkeypatch.setenv("APP_CONFIG_PATH", str(target))
    monkeypatch.setenv("APP_INSTITUCIO", "centre_entorn")
    write_json(legacy, {"institucio": "centre_antic", "idioma": "it"})
    before = legacy.read_bytes()
    config = Config(legacy_config_file=legacy)
    assert config.global_config_file == target
    assert config.institucio == "centre_entorn"
    assert config.idioma == "it"
    config.save_global()
    assert target.is_file()
    assert not default_target.exists()
    assert legacy.read_bytes() == before
    assert json.loads(target.read_text())["institucio"] == "centre_entorn"


def test_carrega_diferida_conserva_el_fitxer_inicial_i_l_override(paths, monkeypatch):
    legacy, target = paths
    monkeypatch.setenv("APP_INSTITUCIO", "centre_entorn")
    config = Config(legacy_config_file=legacy, desa_si_falta=False)
    assert not target.exists()
    assert config.institucio == "centre_entorn"
    config.inicialitza_fitxer()
    assert json.loads(target.read_text()) == config.global_defaults
    abans = target.read_bytes()
    config.inicialitza_fitxer()
    assert target.read_bytes() == abans
