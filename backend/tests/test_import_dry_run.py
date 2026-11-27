"""
Tests de impacte_propostes i impacte_csv (configuracio_examens/importacio.py):
el càlcul de dry-run que decideix què crearia una importació (de l'horari o
d'un CSV) sense escriure res, fet servir tant pel resum previ com pel resultat final.
"""

import pytest

from configuracio_examens.importacio import impacte_csv, impacte_propostes
from configuracio_examens.repositories import MasterConfigRepository
from models import Professor


def _proposta(nivell="1-ESO", assignatura="Matemàtiques", grup="1-ESO-A", titular="Prof_X", aula="A01"):
    return {"nivell": nivell, "assignatura": assignatura, "grup": grup, "titular": titular, "aula": aula}


def test_tot_nou_quan_no_hi_ha_res_configurat(db_session):
    resum = impacte_propostes(db_session, [_proposta()], overwrite=False)
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

    resum = impacte_propostes(db_session, [_proposta()], overwrite=False)
    assert resum["nivells_creats"] == []
    assert resum["grups_creats"] == []
    assert resum["assignatures_creades"] == []
    assert resum["aules_creades"] == []
    # L'assignació en si encara no existia
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A (Prof_X)"]
    assert resum["ja_existien"] == 0


def test_assignacio_ja_existent_es_compta_i_no_es_duplica(db_session):
    from configuracio_examens.repositories import ConfiguracioExamenRepository

    ConfiguracioExamenRepository.create(db_session, "Matemàtiques", "1-ESO-A", "Prof_X", "A01")
    db_session.commit()

    resum = impacte_propostes(db_session, [_proposta()], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert resum["ja_existien"] == 1


def test_overwrite_ignora_configuracio_existent(db_session):
    MasterConfigRepository.add_nivell(db_session, "1-ESO")
    MasterConfigRepository.add_grup(db_session, "1-ESO", "1-ESO-A")
    db_session.commit()

    resum = impacte_propostes(db_session, [_proposta()], overwrite=True)
    # Amb overwrite, es tracta com si tot es creés de zero
    assert resum["nivells_creats"] == ["1-ESO"]
    assert resum["grups_creats"] == ["1-ESO-A (1-ESO)"]


def test_proposta_incompleta_dona_avis_i_no_es_compta(db_session):
    incompleta = _proposta(grup="")
    resum = impacte_propostes(db_session, [incompleta], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert resum["nivells_creats"] == []
    assert len(resum["avisos"]) == 1
    assert "grup" in resum["avisos"][0]


def test_duplicats_al_mateix_lot_es_compten_un_sol_cop(db_session):
    propostes = [_proposta(), _proposta()]  # exactament la mateixa dues vegades
    resum = impacte_propostes(db_session, propostes, overwrite=False)
    assert resum["nivells_creats"] == ["1-ESO"]
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A (Prof_X)"]
    assert resum["ja_existien"] == 1  # la segona ocurrència es compta com "ja existeix"


def test_aula_buida_no_es_proposa(db_session):
    resum = impacte_propostes(db_session, [_proposta(aula="")], overwrite=False)
    assert resum["aules_creades"] == []


# -------------------------------------------- impacte_csv: la importació CSV


def _fila(nivell="1-ESO", assignatura="Matemàtiques", grup="1-ESO-A", titular="", aula=""):
    return {"nivell": nivell, "assignatura": assignatura, "grup": grup, "titular": titular, "aula": aula}


def test_fila_completa_es_crea(db_session):
    resum = impacte_csv(db_session, [(2, _fila(aula="A01"))], overwrite=False)
    assert resum["nivells_creats"] == ["1-ESO"]
    assert resum["grups_creats"] == ["1-ESO-A (1-ESO)"]
    assert resum["assignatures_creades"] == ["Matemàtiques (1-ESO)"]
    assert resum["aules_creades"] == ["A01"]
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A"]
    assert resum["avisos"] == []


@pytest.mark.parametrize("camp", ["nivell", "grup", "assignatura"])
def test_una_fila_sense_un_camp_obligatori_es_descarta_sencera(db_session, camp):
    fila = _fila(**{camp: ""}, aula="A01")
    resum = impacte_csv(db_session, [(3, fila)], overwrite=False)
    # Res es crea, ni tan sols l'aula (no es deixen dades soltes a mitges)
    assert resum["nivells_creats"] == []
    assert resum["aules_creades"] == []
    assert resum["assignacions_creades"] == []
    assert len(resum["avisos"]) == 1
    assert "Línia 3" in resum["avisos"][0]
    assert camp in resum["avisos"][0]


def test_fila_totalment_buida_no_genera_avis(db_session):
    fila = _fila(nivell="", assignatura="", grup="", titular="", aula="")
    resum = impacte_csv(db_session, [(6, fila)], overwrite=False)
    assert resum["avisos"] == []


def test_professor_inexistent_descarta_la_fila_sencera(db_session):
    # El titular és opcional, però si se n'especifica un que no existeix, es
    # tracta com una dada incorrecta: es descarta tota la fila (no es crea
    # l'assignació a mitges sense titular).
    fila = _fila(titular="NoExisteix_X")
    resum = impacte_csv(db_session, [(7, fila)], overwrite=False)
    assert resum["nivells_creats"] == []
    assert resum["assignacions_creades"] == []
    assert any("NoExisteix_X" in a for a in resum["avisos"])
    assert any("no trobat" in a for a in resum["avisos"])


def test_professor_amb_majus_minus_diferent_es_tracta_com_no_trobat(db_session):
    # Deliberadament sense cap suggeriment: si no coincideix exactament, es
    # tracta igual que un professor inexistent (simplicitat per davant d'una
    # ajuda que l'usuari hauria d'anar a corregir igualment al fitxer).
    db_session.add(Professor(nom="Prof_Titular"))
    db_session.commit()

    fila = _fila(titular="prof_titular")
    resum = impacte_csv(db_session, [(9, fila)], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert any("prof_titular" in a and "no trobat" in a for a in resum["avisos"])


def test_professor_existent_no_dona_avis(db_session):
    db_session.add(Professor(nom="Prof_Real"))
    db_session.commit()

    fila = _fila(titular="Prof_Real")
    resum = impacte_csv(db_session, [(8, fila)], overwrite=False)
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A (Prof_Real)"]
    assert resum["avisos"] == []


def test_overwrite_ignora_configuracio_existent(db_session):
    MasterConfigRepository.add_nivell(db_session, "1-ESO")
    db_session.commit()

    resum = impacte_csv(db_session, [(2, _fila())], overwrite=True)
    assert resum["nivells_creats"] == ["1-ESO"]
