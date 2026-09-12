"""
Tests de _calcula_impacte_csv (routes/config_examens.py): el càlcul de
dry-run per a la importació CSV, sense escriure res a la BD.
"""
from repositories import MasterConfigRepository
from models import Professor
from routes.config_examens import _calcula_impacte_csv


def _fila(nivell="1-ESO", assignatura="Matemàtiques", grup="1-ESO-A", titular="", aula=""):
    return {"nivell": nivell, "assignatura": assignatura, "grup": grup, "titular": titular, "aula": aula}


def test_fila_completa_es_crea(db_session):
    resum = _calcula_impacte_csv(db_session, [(2, _fila(aula="A01"))], overwrite=False)
    assert resum["nivells_creats"] == ["1-ESO"]
    assert resum["grups_creats"] == ["1-ESO-A (1-ESO)"]
    assert resum["assignatures_creades"] == ["Matemàtiques (1-ESO)"]
    assert resum["aules_creades"] == ["A01"]
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A"]
    assert resum["avisos"] == []


def test_fila_sense_nivell_es_descarta_sencera(db_session):
    fila = _fila(nivell="", aula="A01")
    resum = _calcula_impacte_csv(db_session, [(3, fila)], overwrite=False)
    # Res es crea, ni tan sols l'aula (no es deixen dades soltes a mitges)
    assert resum["nivells_creats"] == []
    assert resum["aules_creades"] == []
    assert resum["assignacions_creades"] == []
    assert len(resum["avisos"]) == 1
    assert "Línia 3" in resum["avisos"][0]
    assert "nivell" in resum["avisos"][0]


def test_fila_sense_grup_es_descarta_sencera(db_session):
    fila = _fila(grup="")
    resum = _calcula_impacte_csv(db_session, [(4, fila)], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert "grup" in resum["avisos"][0]


def test_fila_sense_assignatura_es_descarta_sencera(db_session):
    fila = _fila(assignatura="")
    resum = _calcula_impacte_csv(db_session, [(5, fila)], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert "assignatura" in resum["avisos"][0]


def test_fila_totalment_buida_no_genera_avis(db_session):
    fila = _fila(nivell="", assignatura="", grup="", titular="", aula="")
    resum = _calcula_impacte_csv(db_session, [(6, fila)], overwrite=False)
    assert resum["avisos"] == []


def test_professor_inexistent_descarta_la_fila_sencera(db_session):
    # El titular és opcional, però si se n'especifica un que no existeix, es
    # tracta com una dada incorrecta: es descarta tota la fila (no es crea
    # l'assignació a mitges sense titular).
    fila = _fila(titular="NoExisteix_X")
    resum = _calcula_impacte_csv(db_session, [(7, fila)], overwrite=False)
    assert resum["nivells_creats"] == []
    assert resum["assignacions_creades"] == []
    assert any("NoExisteix_X" in a for a in resum["avisos"])
    assert any("no trobat" in a for a in resum["avisos"])


def test_professor_amb_majus_minus_diferent_es_tracta_com_no_trobat(db_session):
    # Deliberadament sense cap suggeriment: si no coincideix exactament, es
    # tracta igual que un professor inexistent (simplicitat per davant d'una
    # ajuda que l'usuari hauria d'anar a corregir igualment al fitxer).
    db_session.add(Professor(nom="Zapata_M"))
    db_session.commit()

    fila = _fila(titular="zapata_m")
    resum = _calcula_impacte_csv(db_session, [(9, fila)], overwrite=False)
    assert resum["assignacions_creades"] == []
    assert any("zapata_m" in a and "no trobat" in a for a in resum["avisos"])


def test_professor_existent_no_dona_avis(db_session):
    db_session.add(Professor(nom="Prof_Real"))
    db_session.commit()

    fila = _fila(titular="Prof_Real")
    resum = _calcula_impacte_csv(db_session, [(8, fila)], overwrite=False)
    assert resum["assignacions_creades"] == ["Matemàtiques – 1-ESO-A (Prof_Real)"]
    assert resum["avisos"] == []


def test_overwrite_ignora_configuracio_existent(db_session):
    MasterConfigRepository.add_nivell(db_session, "1-ESO")
    db_session.commit()

    resum = _calcula_impacte_csv(db_session, [(2, _fila())], overwrite=True)
    assert resum["nivells_creats"] == ["1-ESO"]
