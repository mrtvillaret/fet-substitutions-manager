"""
Tests de core/vigilancia_core.py (VigilanciaCore). No toca cap base de
dades ni sistema de fitxers real.

Són "characterization tests": capturen el comportament REAL del codi
actual (incloent-hi branques secundàries i casos "lletjos", com
excepcions silencioses) perquè serveixin de xarxa de seguretat davant
de qualsevol canvi futur, encara que algun comportament no sigui ideal.
"""

from config import constants
from core.vigilancia_core import VigilanciaCore


def _nucli(**overrides):
    """Crea un VigilanciaCore amb configuració per defecte, sobreescrivible."""
    nucli = VigilanciaCore()
    cfg = dict(
        assignatures_config=None,
        professors=[],
        absents_actuals={},
        horari_gestor=None,
        alliberats_gestor=None,
        grups_sense_classe=set(),
        dia_actual="Dilluns",
    )
    cfg.update(overrides)
    nucli.set_config(**cfg)
    return nucli


# ===== get_categoria_prioritat / is_activitat_auto_assignable =====


def test_categoria_prioritat_retorna_index_de_la_categoria(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    nucli = _nucli()
    assert nucli.get_categoria_prioritat("Guàrdia") == 0
    assert nucli.get_categoria_prioritat("CD") == 1


def test_categoria_prioritat_no_trobada_retorna_longitud_total(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    nucli = _nucli()
    assert nucli.get_categoria_prioritat("Inexistent") == 2


def test_activitat_auto_assignable_si_categoria_activa(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True, True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Guàrdia") is True


def test_activitat_no_auto_assignable_si_categoria_inactiva(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [False, True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Guàrdia") is False


def test_activitat_no_trobada_a_cap_categoria_no_es_assignable(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Desconeguda") is False


def test_activitat_buida_mai_es_assignable(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("") is False


def test_fallback_defensiu_quan_ordre_prioritats_encara_buit(monkeypatch):
    # Characterization: si encara no s'han carregat categories des de BD
    # (ORDRE_PRIORITATS buit), es fa servir un fallback basat en PRIORITATS.
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [])
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Guàrdia") is True
    assert nucli.is_activitat_auto_assignable("alliberat") is True
    assert nucli.is_activitat_auto_assignable("QualsevolAltra") is False
