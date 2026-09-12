"""
Tests de _calcula_impacte_assignacions (routes/config_examens.py): el
càlcul de dry-run que decideix què crearia una importació sense escriure
res, fet servir tant pel resum previ com pel resultat final.
"""
from repositories import MasterConfigRepository
from routes.config_examens import _calcula_impacte_assignacions


def _proposta(nivell="1-ESO", assignatura="Matemàtiques", grup="1-ESO-A", titular="Prof_X", aula="A01"):
    return {"nivell": nivell, "assignatura": assignatura, "grup": grup, "titular": titular, "aula": aula}


def test_tot_nou_quan_no_hi_ha_res_configurat(db_session):
    resum = _calcula_impacte_assignacions(db_session, [_proposta()], overwrite=False)
    assert resum["nivells_creats"] == ["1-ESO"]
    assert resum["grups_creats"] == ["1-ESO-A (1-ESO)"]
    assert resum["assignatures_creades"] == ["Matemàtiques (1-ESO)"]
    assert resum["aules_creades"] == ["A01"]
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A (Prof_X)"]
    assert resum["ja_existien"] == 0
    assert resum["avisos"] == []


def test_no_compta_com_a_nou_el_que_ja_existeix(db_session):
    MasterConfigRepository.add_nivell(db_session, "1-ESO")
    MasterConfigRepository.add_grup(db_session, "1-ESO", "1-ESO-A")
    MasterConfigRepository.add_assignatura(db_session, "1-ESO", "Matemàtiques")
    MasterConfigRepository.add_aula(db_session, "A01")
    db_session.commit()

    resum = _calcula_impacte_assignacions(db_session, [_proposta()], overwrite=False)
    assert resum["nivells_creats"] == []
    assert resum["grups_creats"] == []
    assert resum["assignatures_creades"] == []
    assert resum["aules_creades"] == []
    # L'assignació en si encara no existia
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A (Prof_X)"]
    assert resum["ja_existien"] == 0


def test_assignacio_ja_existent_es_compta_i_no_es_duplica(db_session):
    from repositories import ConfiguracioExamenRepository

    ConfiguracioExamenRepository.create(db_session, "Matemàtiques", "1-ESO-A", "Prof_X", "A01")
    db_session.commit()

    resum = _calcula_impacte_assignacions(db_session, [_proposta()], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert resum["ja_existien"] == 1


def test_overwrite_ignora_configuracio_existent(db_session):
    MasterConfigRepository.add_nivell(db_session, "1-ESO")
    MasterConfigRepository.add_grup(db_session, "1-ESO", "1-ESO-A")
    db_session.commit()

    resum = _calcula_impacte_assignacions(db_session, [_proposta()], overwrite=True)
    # Amb overwrite, es tracta com si tot es creés de zero
    assert resum["nivells_creats"] == ["1-ESO"]
    assert resum["grups_creats"] == ["1-ESO-A (1-ESO)"]


def test_proposta_incompleta_dona_avis_i_no_es_compta(db_session):
    incompleta = _proposta(grup="")
    resum = _calcula_impacte_assignacions(db_session, [incompleta], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert resum["nivells_creats"] == []
    assert len(resum["avisos"]) == 1
    assert "grup" in resum["avisos"][0]


def test_duplicats_al_mateix_lot_es_compten_un_sol_cop(db_session):
    propostes = [_proposta(), _proposta()]  # exactament la mateixa dues vegades
    resum = _calcula_impacte_assignacions(db_session, propostes, overwrite=False)
    assert resum["nivells_creats"] == ["1-ESO"]
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A (Prof_X)"]
    assert resum["ja_existien"] == 1  # la segona ocurrència es compta com "ja existeix"


def test_aula_buida_no_es_proposa(db_session):
    resum = _calcula_impacte_assignacions(db_session, [_proposta(aula="")], overwrite=False)
    assert resum["aules_creades"] == []
