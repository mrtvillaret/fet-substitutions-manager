"""
Tests per a routes/prioritats.py:

- _recarregar_prioritats_desde_bd: reconstrueix ORDRE_PRIORITATS/PRIORITATS/
  CATEGORIES_ACTIVES/NO_SUBST/GENERA_ENCADENADES/PROFESSORS_BAIXA a
  config.constants llegint-les de la BD. Alimenta directament la lògica
  d'assignació de core/substitucions.py i core/vigilancia_core.py — és la
  peça de més risc real d'aquest mòdul, perquè si trenca, l'assignació
  automàtica es trenca en silenci sense que cap altre test ho detecti.

- CRUD de categories, assignatures, no-substituir i professors de baixa:
  es criden les funcions dels endpoints directament amb asyncio.run (el
  projecte no fa servir pytest-asyncio i cap d'aquestes funcions té `await`
  real dins seu, només crides síncrones a SQLAlchemy).
"""
import asyncio

import pytest
from fastapi import HTTPException

import config.constants as constants
from repositories import (
    CategoriaPrioritatRepository,
    AssignaturaPrioritatRepository,
    NoSubstituirRepository,
    ProfessorBaixaRepository,
)
from routes.prioritats import (
    _recarregar_prioritats_desde_bd,
    get_categories,
    create_categoria,
    update_categoria,
    update_categories_ordre,
    delete_categoria,
    get_assignatures_prioritat,
    get_assignatures_by_categoria,
    create_assignatura_prioritat,
    update_assignatura_prioritat,
    delete_assignatura_prioritat,
    get_no_substituir,
    create_no_substituir,
    delete_no_substituir,
    get_professors_baixa,
    create_professor_baixa,
    update_professor_baixa,
    delete_professor_baixa,
    desar_totes_prioritats,
    CategoriaPrioritatCreate,
    AssignaturaPrioritatCreate,
    ProfessorBaixaCreate,
    PrioritatsCompletesUpdate,
)


def run(coro):
    return asyncio.run(coro)


# ===================================================================
# _recarregar_prioritats_desde_bd
# ===================================================================

def test_recarrega_bd_buida_dona_tot_buit(db_session):
    _recarregar_prioritats_desde_bd(db_session)

    assert constants.ORDRE_PRIORITATS == []
    assert constants.CATEGORIES_ACTIVES == []
    assert constants.PRIORITATS == {}
    assert constants.NO_SUBST == set()
    assert constants.GENERA_ENCADENADES == []
    assert constants.PROFESSORS_BAIXA == []


def test_recarrega_construeix_ordre_i_pesos(db_session):
    cat1 = CategoriaPrioritatRepository.create(db_session, "Reforç", ordre=0, activa=True)
    cat2 = CategoriaPrioritatRepository.create(db_session, "Guàrdia", ordre=1, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Reforç-A", cat1, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia", cat2, pes=6)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia-R", cat2, pes=3)

    _recarregar_prioritats_desde_bd(db_session)

    assert constants.ORDRE_PRIORITATS == [["Reforç-A"], ["Guàrdia", "Guàrdia-R"]]
    assert constants.PRIORITATS == {"Reforç-A": 1, "Guàrdia": 6, "Guàrdia-R": 3}


def test_recarrega_respecta_ordre_de_categoria_no_ordre_de_creacio(db_session):
    # Creades en ordre invers respecte al camp `ordre`.
    cat_b = CategoriaPrioritatRepository.create(db_session, "Segona", ordre=1, activa=True)
    cat_a = CategoriaPrioritatRepository.create(db_session, "Primera", ordre=0, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "AssigB", cat_b, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "AssigA", cat_a, pes=1)

    _recarregar_prioritats_desde_bd(db_session)

    assert constants.ORDRE_PRIORITATS == [["AssigA"], ["AssigB"]]


def test_recarrega_categories_actives_en_el_mateix_ordre_que_ordre_prioritats(db_session):
    CategoriaPrioritatRepository.create(db_session, "Activa", ordre=0, activa=True)
    CategoriaPrioritatRepository.create(db_session, "Inactiva", ordre=1, activa=False)

    _recarregar_prioritats_desde_bd(db_session)

    assert constants.CATEGORIES_ACTIVES == [True, False]


def test_recarrega_no_subst_i_genera_encadenades(db_session):
    cat = CategoriaPrioritatRepository.create(db_session, "Cat", ordre=0, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Normal", cat, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia-P", cat, pes=1)
    NoSubstituirRepository.create(db_session, "Guàrdia-P")

    _recarregar_prioritats_desde_bd(db_session)

    assert constants.NO_SUBST == {"Guàrdia-P"}
    assert set(constants.GENERA_ENCADENADES) == {"Normal"}
    assert "Guàrdia-P" not in constants.GENERA_ENCADENADES


def test_recarrega_professors_baixa(db_session):
    ProfessorBaixaRepository.create(
        db_session, "Prof Test", "2026-01-10", "2026-01-20", motiu="Malaltia"
    )

    _recarregar_prioritats_desde_bd(db_session)

    assert len(constants.PROFESSORS_BAIXA) == 1
    baixa = constants.PROFESSORS_BAIXA[0]
    assert baixa["professor"] == "Prof Test"
    assert baixa["data_inici"] == "2026-01-10"
    assert baixa["data_final"] == "2026-01-20"
    assert baixa["motiu"] == "Malaltia"


def test_recarrega_professor_baixa_sense_motiu_dona_string_buit(db_session):
    ProfessorBaixaRepository.create(db_session, "Prof Sense Motiu", "2026-02-01", "2026-02-05")

    _recarregar_prioritats_desde_bd(db_session)

    assert constants.PROFESSORS_BAIXA[0]["motiu"] == ""


def test_recarrega_categoria_sense_assignatures_dona_llista_buida_en_ordre(db_session):
    """Una categoria buida ha d'aparèixer com a llista buida a
    ORDRE_PRIORITATS (no s'ha de saltar), perquè l'índex de categoria és
    significatiu per a CATEGORIES_ACTIVES."""
    CategoriaPrioritatRepository.create(db_session, "Buida", ordre=0, activa=True)
    cat2 = CategoriaPrioritatRepository.create(db_session, "Amb assignatures", ordre=1, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "X", cat2, pes=1)

    _recarregar_prioritats_desde_bd(db_session)

    assert constants.ORDRE_PRIORITATS == [[], ["X"]]
    assert constants.CATEGORIES_ACTIVES == [True, True]


# ===================================================================
# CRUD: categories
# ===================================================================

def test_crud_categoria_creada_apareix_a_get(db_session):
    payload = CategoriaPrioritatCreate(nom="Nova categoria", ordre=0, activa=True)
    resultat = run(create_categoria(payload, db_session))
    assert resultat["success"] is True

    resposta = run(get_categories(db_session))
    noms = [c["nom"] for c in resposta["categories"]]
    assert "Nova categoria" in noms


def test_crud_categoria_update_inexistent_dona_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        run(update_categoria(999999, {"nom": "X"}, db_session))
    assert exc_info.value.status_code == 404


def test_crud_categoria_delete_inexistent_dona_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        run(delete_categoria(999999, db_session))
    assert exc_info.value.status_code == 404


def test_crud_categoria_delete_fa_cascada_sobre_assignatures(db_session):
    """El comentari del codi diu 'per CASCADE' — es comprova que realment
    ho fa a nivell de BD (PRAGMA foreign_keys=ON + ondelete='CASCADE')."""
    payload = CategoriaPrioritatCreate(nom="Amb fills", ordre=0, activa=True)
    creada = run(create_categoria(payload, db_session))
    cat_id = creada["id"]
    AssignaturaPrioritatRepository.create(db_session, "Filla", cat_id, pes=1)

    run(delete_categoria(cat_id, db_session))

    assig_restants = run(get_assignatures_by_categoria(cat_id, db_session))
    assert assig_restants["assignatures"] == []


def test_crud_categories_ordre_swap_funciona(db_session):
    """Bug corregit: `update_ordre` passava els valors finals fila a fila,
    cosa que amb la restricció UNIQUE de `ordre` petava en intercanviar dues
    categories (l'operació normal de "puja"/"baixa" a la UI). Ara passa
    per un pas intermedi amb valors negatius que no col·lisionen."""
    c1 = run(create_categoria(CategoriaPrioritatCreate(nom="A", ordre=0), db_session))
    c2 = run(create_categoria(CategoriaPrioritatCreate(nom="B", ordre=1), db_session))

    run(update_categories_ordre([c2["id"], c1["id"]], db_session))

    categories = run(get_categories(db_session))["categories"]
    per_id = {c["id"]: c["ordre"] for c in categories}
    assert per_id[c2["id"]] == 0
    assert per_id[c1["id"]] == 1


# ===================================================================
# CRUD: assignatures de prioritat
# ===================================================================

def test_crud_assignatura_creada_apareix_a_la_seva_categoria(db_session):
    cat = run(create_categoria(CategoriaPrioritatCreate(nom="Cat"), db_session))
    payload = AssignaturaPrioritatCreate(assignatura="Guàrdia", categoria_id=cat["id"], pes=2)
    creada = run(create_assignatura_prioritat(payload, db_session))
    assert creada["success"] is True

    resposta = run(get_assignatures_by_categoria(cat["id"], db_session))
    assert any(a["assignatura"] == "Guàrdia" and a["pes"] == 2 for a in resposta["assignatures"])


def test_crud_assignatura_update_inexistent_dona_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        run(update_assignatura_prioritat(999999, {"pes": 5}, db_session))
    assert exc_info.value.status_code == 404


def test_crud_assignatura_delete_inexistent_dona_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        run(delete_assignatura_prioritat(999999, db_session))
    assert exc_info.value.status_code == 404


def test_crud_assignatura_creacio_amb_categoria_inexistent_falla(db_session):
    """No hi ha validació prèvia a nivell d'aplicació — depèn únicament de
    la restricció de clau forana de la BD (FK enforcement ON). Es
    caracteritza el comportament real: no dona un 400 net, deixa pujar
    l'excepció de SQLAlchemy/SQLite tal qual."""
    payload = AssignaturaPrioritatCreate(assignatura="Orfe", categoria_id=999999, pes=1)
    with pytest.raises(Exception):
        run(create_assignatura_prioritat(payload, db_session))


# ===================================================================
# CRUD: no-substituir
# ===================================================================

def test_crud_no_substituir_creat_apareix_a_get(db_session):
    run(create_no_substituir({"assignatura": "Pati"}, db_session))
    resposta = run(get_no_substituir(db_session))
    assert "Pati" in resposta["assignatures"]


def test_crud_no_substituir_string_buit_es_accepta(db_session):
    """El codi accepta explícitament un string buit com a valor vàlid
    (comentari 'Acceptar string buit' a create_no_substituir) — es
    caracteritza tal com és, per estrany que sembli."""
    resultat = run(create_no_substituir({"assignatura": ""}, db_session))
    assert resultat["success"] is True


def test_crud_no_substituir_sense_clau_assignatura_dona_500_per_bug(db_session):
    """BUG DE PRODUCCIÓ CONFIRMAT: create_no_substituir() aixeca
    deliberadament un HTTPException(400, "Assignatura requerida"), però a
    diferència d'altres endpoints d'aquest mateix fitxer (update_categoria,
    delete_categoria, etc.) li falta el `except HTTPException: raise`
    previ al `except Exception` genèric. Com que HTTPException també és
    Exception, el bloc genèric l'atrapa i el reempaqueta com a 500 — la
    validació existeix però mai arriba al client com a 400.
    Reportat a l'usuari — no s'ha corregit aquí, fora d'abast d'aquesta
    tasca (només test dedicat)."""
    with pytest.raises(HTTPException) as exc_info:
        run(create_no_substituir({}, db_session))
    assert exc_info.value.status_code == 500
    assert "Assignatura requerida" in exc_info.value.detail


def test_crud_no_substituir_delete_inexistent_dona_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        run(delete_no_substituir("No existeix enlloc", db_session))
    assert exc_info.value.status_code == 404


# ===================================================================
# CRUD: professors de baixa
# ===================================================================

def test_crud_professor_baixa_creat_apareix_a_get(db_session):
    payload = ProfessorBaixaCreate(
        professor="Prof X", data_inici="2026-03-01", data_final="2026-03-10", motiu="Formació"
    )
    run(create_professor_baixa(payload, db_session))

    resposta = run(get_professors_baixa(db_session))
    professors = [p["professor"] for p in resposta["professors_baixa"]]
    assert "Prof X" in professors


def test_crud_professor_baixa_update_inexistent_dona_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        run(update_professor_baixa(999999, {"professor": "X"}, db_session))
    assert exc_info.value.status_code == 404


def test_crud_professor_baixa_delete_inexistent_dona_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        run(delete_professor_baixa(999999, db_session))
    assert exc_info.value.status_code == 404


# ===================================================================
# desar_totes_prioritats: reemplaça tot i recarrega les constants
# ===================================================================

def test_desar_tot_reemplaca_categories_existents(db_session):
    # Estat inicial: una categoria que hauria de desaparèixer.
    run(create_categoria(CategoriaPrioritatCreate(nom="Vella"), db_session))

    payload = PrioritatsCompletesUpdate(
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
    payload = PrioritatsCompletesUpdate(
        ordre_categories=[["Reforç-A"]],
        pesos={"Reforç-A": 1},
        categories_actives=[True],
    )
    run(desar_totes_prioritats(payload, db_session))

    # _recarregar_prioritats_desde_bd() s'ha cridat internament: les
    # constants globals han de reflectir el que s'acaba de desar.
    assert constants.ORDRE_PRIORITATS == [["Reforç-A"]]
    assert constants.PRIORITATS == {"Reforç-A": 1}


def test_desar_tot_categoria_amb_una_sola_assignatura_pren_el_seu_nom(db_session):
    payload = PrioritatsCompletesUpdate(
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
    payload = PrioritatsCompletesUpdate(
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
    payload = PrioritatsCompletesUpdate(
        ordre_categories=[[], ["Real"]],
        pesos={"Real": 1},
        categories_actives=[True, True],
    )
    run(desar_totes_prioritats(payload, db_session))

    categories = run(get_categories(db_session))["categories"]
    assert len(categories) == 1
    assert categories[0]["nom"] == "Real"
