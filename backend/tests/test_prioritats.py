"""
Tests per al mòdul prioritats (prioritats/):

- carrega_prioritats: reconstrueix ORDRE_PRIORITATS/PRIORITATS/
  CATEGORIES_ACTIVES/NO_SUBST/GENERA_ENCADENADES a
  config.constants llegint-les de la BD. Alimenta directament la lògica
  d'assignació de core/substitucions.py i core/vigilancia_core.py — és la
  peça de més risc real d'aquest mòdul, perquè si trenca, l'assignació
  automàtica es trenca en silenci sense que cap altre test ho detecti.

- CRUD de no-substituir i «Desar tot» (categories i
  assignatures):
  es criden les funcions dels endpoints directament amb asyncio.run (el
  projecte no fa servir pytest-asyncio i cap d'aquestes funcions té `await`
  real dins seu, només crides síncrones a SQLAlchemy).
"""

import asyncio

import pytest

import config.constants as constants
from errors_domini import NoTrobat, NoValid
from prioritats.repositories import AssignaturaPrioritatRepository, CategoriaPrioritatRepository, NoSubstituirRepository
from prioritats.router import (
    create_no_substituir,
    delete_no_substituir,
    desar_totes_prioritats,
    get_categories,
    get_no_substituir,
)
from prioritats.schemas import NoSubstituirRequest, PrioritatsRequest
from prioritats.services import carrega_prioritats


def run(coro):
    return asyncio.run(coro)


# ===================================================================
# carrega_prioritats
# ===================================================================


def test_recarrega_bd_buida_dona_tot_buit(db_session):
    carrega_prioritats(db_session)

    assert constants.ORDRE_PRIORITATS == []
    assert constants.CATEGORIES_ACTIVES == []
    assert constants.PRIORITATS == {}
    assert constants.NO_SUBST == set()
    assert constants.GENERA_ENCADENADES == []


def test_els_moduls_que_importen_les_prioritats_veuen_les_actuals(db_session):
    # Aquests mòduls fan "from config.constants import ..." en carregar-se:
    # la recàrrega ha d'omplir els mateixos objectes, no crear-ne de nous.
    import core.absencies
    import core.vigilancia_assignacio
    import helpers
    import routes.disponibles
    import routes.settings

    cat = CategoriaPrioritatRepository.create(db_session, "Guàrdies", ordre=0, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia", cat, pes=4)
    NoSubstituirRepository.create(db_session, "Reunió")

    carrega_prioritats(db_session)

    for modul in (helpers, core.vigilancia_assignacio):
        assert modul.PRIORITATS == {"Guàrdia": 4}, modul.__name__
    for modul in (core.vigilancia_assignacio, routes.disponibles):
        assert modul.ORDRE_PRIORITATS == [["Guàrdia"]], modul.__name__
    for modul in (core.absencies, routes.settings):
        assert modul.NO_SUBST == {"Reunió"}, modul.__name__


def test_recarrega_construeix_ordre_i_pesos(db_session):
    cat1 = CategoriaPrioritatRepository.create(db_session, "Reforç", ordre=0, activa=True)
    cat2 = CategoriaPrioritatRepository.create(db_session, "Guàrdia", ordre=1, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Reforç-A", cat1, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia", cat2, pes=6)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia-R", cat2, pes=3)

    carrega_prioritats(db_session)

    assert constants.ORDRE_PRIORITATS == [["Reforç-A"], ["Guàrdia", "Guàrdia-R"]]
    assert constants.PRIORITATS == {"Reforç-A": 1, "Guàrdia": 6, "Guàrdia-R": 3}


def test_recarrega_respecta_ordre_de_categoria_no_ordre_de_creacio(db_session):
    # Creades en ordre invers respecte al camp `ordre`.
    cat_b = CategoriaPrioritatRepository.create(db_session, "Segona", ordre=1, activa=True)
    cat_a = CategoriaPrioritatRepository.create(db_session, "Primera", ordre=0, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "AssigB", cat_b, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "AssigA", cat_a, pes=1)

    carrega_prioritats(db_session)

    assert constants.ORDRE_PRIORITATS == [["AssigA"], ["AssigB"]]


def test_recarrega_categories_actives_en_el_mateix_ordre_que_ordre_prioritats(db_session):
    CategoriaPrioritatRepository.create(db_session, "Activa", ordre=0, activa=True)
    CategoriaPrioritatRepository.create(db_session, "Inactiva", ordre=1, activa=False)

    carrega_prioritats(db_session)

    assert constants.CATEGORIES_ACTIVES == [True, False]


def test_recarrega_no_subst_i_genera_encadenades(db_session):
    cat = CategoriaPrioritatRepository.create(db_session, "Cat", ordre=0, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Normal", cat, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia-P", cat, pes=1)
    NoSubstituirRepository.create(db_session, "Guàrdia-P")

    carrega_prioritats(db_session)

    assert constants.NO_SUBST == {"Guàrdia-P"}
    assert set(constants.GENERA_ENCADENADES) == {"Normal"}
    assert "Guàrdia-P" not in constants.GENERA_ENCADENADES


def test_recarrega_categoria_sense_assignatures_dona_llista_buida_en_ordre(db_session):
    """Una categoria buida ha d'aparèixer com a llista buida a
    ORDRE_PRIORITATS (no s'ha de saltar), perquè l'índex de categoria és
    significatiu per a CATEGORIES_ACTIVES."""
    CategoriaPrioritatRepository.create(db_session, "Buida", ordre=0, activa=True)
    cat2 = CategoriaPrioritatRepository.create(db_session, "Amb assignatures", ordre=1, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "X", cat2, pes=1)

    carrega_prioritats(db_session)

    assert constants.ORDRE_PRIORITATS == [[], ["X"]]
    assert constants.CATEGORIES_ACTIVES == [True, True]


# ===================================================================
# CRUD: no-substituir
# ===================================================================


def test_crud_no_substituir_creat_apareix_a_get(db_session):
    run(create_no_substituir(NoSubstituirRequest(assignatura="Pati"), db_session))
    resposta = run(get_no_substituir(db_session))
    assert "Pati" in resposta["assignatures"]


def test_crud_no_substituir_string_buit_es_accepta(db_session):
    """El codi accepta explícitament un string buit com a valor vàlid
    (comentari 'Acceptar string buit' a create_no_substituir) — es
    caracteritza tal com és, per estrany que sembli."""
    resultat = run(create_no_substituir(NoSubstituirRequest(assignatura=""), db_session))
    assert resultat["success"] is True


def test_crud_no_substituir_sense_clau_assignatura_dona_400(db_session):
    """Sense assignatura, un NoValid (400 per l'API, errors_servidor.py);
    abans un except Exception genèric l'atrapava i la convertia en 500."""
    with pytest.raises(NoValid, match="Assignatura requerida"):
        run(create_no_substituir(NoSubstituirRequest(), db_session))


def test_crud_no_substituir_delete_inexistent_dona_404(db_session):
    with pytest.raises(NoTrobat):
        run(delete_no_substituir("No existeix enlloc", db_session))


# ===================================================================
# CRUD: professors de baixa
# ===================================================================
# desar_totes_prioritats: reemplaça tot i recarrega les constants
# ===================================================================


def test_desar_tot_reemplaca_categories_existents(db_session):
    # Estat inicial: una categoria que hauria de desaparèixer.
    CategoriaPrioritatRepository.create(db_session, "Vella", ordre=0)

    payload = PrioritatsRequest(
        ordre_categories=[["Reforç-A"], ["Guàrdia", "Guàrdia-R"]],
        pesos={"Reforç-A": 1, "Guàrdia": 6, "Guàrdia-R": 3},
        categories_actives=[True, False],
    )
    resultat = run(desar_totes_prioritats(payload, db_session))
    assert resultat["success"] is True

    categories = run(get_categories(db_session))["categories"]
    noms = [c["nom"] for c in categories]
    assert "Vella" not in noms
    assert len(categories) == 2


def test_desar_tot_recarrega_les_constants_globals(db_session):
    payload = PrioritatsRequest(
        ordre_categories=[["Reforç-A"]],
        pesos={"Reforç-A": 1},
        categories_actives=[True],
    )
    run(desar_totes_prioritats(payload, db_session))

    # carrega_prioritats() s'ha cridat internament: les
    # constants globals han de reflectir el que s'acaba de desar.
    assert constants.ORDRE_PRIORITATS == [["Reforç-A"]]
    assert constants.PRIORITATS == {"Reforç-A": 1}


def test_desar_tot_categoria_amb_una_sola_assignatura_pren_el_seu_nom(db_session):
    payload = PrioritatsRequest(
        ordre_categories=[["Sol"]],
        pesos={"Sol": 1},
        categories_actives=[True],
    )
    run(desar_totes_prioritats(payload, db_session))

    categories = run(get_categories(db_session))["categories"]
    assert categories[0]["nom"] == "Sol"


def test_desar_tot_categoria_amb_diverses_assignatures_concatena_les_dues_primeres(db_session):
    """Caracteritza el comportament real de generació del nom (no
    necessàriament l'ideal): `", ".join(assignatures_list[:2])` — només
    les DUES primeres, encara que la categoria en tingui més."""
    payload = PrioritatsRequest(
        ordre_categories=[["Un", "Dos", "Tres"]],
        pesos={"Un": 1, "Dos": 1, "Tres": 1},
        categories_actives=[True],
    )
    run(desar_totes_prioritats(payload, db_session))

    categories = run(get_categories(db_session))["categories"]
    assert categories[0]["nom"] == "Un, Dos"


def test_desar_tot_categoria_buida_a_ordre_categories_es_salta(db_session):
    """Una llista d'assignatures buida dins ordre_categories no crea cap
    categoria (`if not assignatures_list: continue`)."""
    payload = PrioritatsRequest(
        ordre_categories=[[], ["Real"]],
        pesos={"Real": 1},
        categories_actives=[True, True],
    )
    run(desar_totes_prioritats(payload, db_session))

    categories = run(get_categories(db_session))["categories"]
    assert len(categories) == 1
    assert categories[0]["nom"] == "Real"


def test_els_repositoris_de_prioritats_no_fan_commit(db_session):
    """El commit el fa el servei, un cop per operació: sense, no es desa res."""
    cat = CategoriaPrioritatRepository.create(db_session, "Sense commit", ordre=0)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia", cat, pes=2)
    NoSubstituirRepository.create(db_session, "Reunió")
    db_session.rollback()
    assert CategoriaPrioritatRepository.get_all(db_session) == []
    assert AssignaturaPrioritatRepository.get_all(db_session) == []
    assert NoSubstituirRepository.get_all(db_session) == []


def test_una_categoria_sense_ordre_va_al_final_sense_xocar(db_session):
    # Ordres que no comencen per 0 (com les de suport_api): comptar-les donava
    # l'ordre d'una que ja existeix, i la restricció UNIQUE petava
    CategoriaPrioritatRepository.create(db_session, "Primera", ordre=1)
    CategoriaPrioritatRepository.create(db_session, "Segona", ordre=2)
    CategoriaPrioritatRepository.create(db_session, "Nova")
    db_session.commit()
    assert [(c["nom"], c["ordre"]) for c in CategoriaPrioritatRepository.get_all(db_session)] == [
        ("Primera", 1),
        ("Segona", 2),
        ("Nova", 3),
    ]


def test_una_assignatura_sense_ordre_va_al_final_de_la_seva_categoria(db_session):
    cat = CategoriaPrioritatRepository.create(db_session, "Cat", ordre=0)
    AssignaturaPrioritatRepository.create(db_session, "A", cat, ordre=0)
    AssignaturaPrioritatRepository.create(db_session, "B", cat, ordre=5)
    AssignaturaPrioritatRepository.create(db_session, "C", cat)
    altra = CategoriaPrioritatRepository.create(db_session, "Altra", ordre=1)
    AssignaturaPrioritatRepository.create(db_session, "D", altra)
    db_session.commit()
    ordres = {a["assignatura"]: a["ordre"] for a in AssignaturaPrioritatRepository.get_all(db_session)}
    assert ordres == {"A": 0, "B": 5, "C": 6, "D": 0}
