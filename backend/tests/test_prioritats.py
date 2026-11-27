"""
Tests per al mòdul prioritats (prioritats/):

- carrega_prioritats: reconstrueix ORDRE_PRIORITATS/PRIORITATS/
  CATEGORIES_ACTIVES i la vigència de «No substituir» a config.constants
  llegint-les de la BD. Alimenta directament la lògica
  d'assignació de substitucions/assignacio.py i vigilancies/context.py — és la
  peça de més risc real d'aquest mòdul, perquè si trenca, l'assignació
  automàtica es trenca en silenci sense que cap altre test ho detecti.

- CRUD de no-substituir i «Desar tot» (categories i
  assignatures):
  es criden les funcions dels endpoints directament (són síncrones).
"""

from datetime import date

import pytest

import config.constants as constants
from errors_domini import NoTrobat, NoValid
from prioritats.memoria import categoria_de_prioritat, no_substituir_a
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

# ===================================================================
# carrega_prioritats
# ===================================================================


def test_recarrega_bd_buida_dona_tot_buit(db_session):
    carrega_prioritats(db_session)

    assert constants.ORDRE_PRIORITATS == []
    assert constants.CATEGORIES_ACTIVES == []
    assert constants.PRIORITATS == {}
    assert no_substituir_a(date(2026, 11, 4)) == frozenset()


def test_el_pdf_i_l_assignacio_de_vigilants_veuen_les_prioritats_recarregades(db_session):
    from pdf.disponibles import linies_de_l_hora
    from vigilancies.context import VigilanciaCore

    guardies = [("Prof 1", "Guàrdia", "")]
    nucli = VigilanciaCore()
    carrega_prioritats(db_session)
    assert "Cat.99:" in linies_de_l_hora(guardies, {})[0]
    assert not nucli.is_activitat_auto_assignable("Guàrdia")

    cat = CategoriaPrioritatRepository.create(db_session, "Guàrdies", ordre=0, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia", cat, pes=4)
    NoSubstituirRepository.create(db_session, "Reunió")

    carrega_prioritats(db_session)

    assert dict(constants.PRIORITATS) == {"Guàrdia": 4}  # ja cap mòdul no la importa en carregar-se
    assert "Cat.0:" in linies_de_l_hora(guardies, {})[0]
    assert nucli.is_activitat_auto_assignable("Guàrdia")
    assert no_substituir_a(date(2026, 11, 4)) == {"Reunió"}


def test_recarrega_construeix_ordre_i_pesos(db_session):
    cat1 = CategoriaPrioritatRepository.create(db_session, "Reforç", ordre=0, activa=True)
    cat2 = CategoriaPrioritatRepository.create(db_session, "Guàrdia", ordre=1, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Reforç-A", cat1, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia", cat2, pes=6)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia-R", cat2, pes=3)

    carrega_prioritats(db_session)

    assert constants.ORDRE_PRIORITATS == [["Reforç-A"], ["Guàrdia", "Guàrdia-R"]]
    assert constants.PRIORITATS == {"Reforç-A": 1, "Guàrdia": 6, "Guàrdia-R": 3}


@pytest.mark.parametrize(
    "categories, ordre",
    [
        # Creades en ordre invers respecte al camp `ordre`
        ([("Segona", 1, ["AssigB"]), ("Primera", 0, ["AssigA"])], [["AssigA"], ["AssigB"]]),
        # Una categoria buida hi és com a llista buida (no s'ha de saltar), perquè
        # l'índex de categoria és significatiu per a CATEGORIES_ACTIVES
        ([("Buida", 0, []), ("Amb assignatures", 1, ["X"])], [[], ["X"]]),
    ],
)
def test_recarrega_segueix_l_ordre_de_les_categories_amb_les_buides(db_session, categories, ordre):
    for nom, posicio, assignatures in categories:
        cat = CategoriaPrioritatRepository.create(db_session, nom, ordre=posicio, activa=True)
        for assignatura in assignatures:
            AssignaturaPrioritatRepository.create(db_session, assignatura, cat, pes=1)

    carrega_prioritats(db_session)

    assert constants.ORDRE_PRIORITATS == ordre
    assert constants.CATEGORIES_ACTIVES == [True, True]


def test_recarrega_categories_actives_en_el_mateix_ordre_que_ordre_prioritats(db_session):
    CategoriaPrioritatRepository.create(db_session, "Activa", ordre=0, activa=True)
    CategoriaPrioritatRepository.create(db_session, "Inactiva", ordre=1, activa=False)

    carrega_prioritats(db_session)

    assert constants.CATEGORIES_ACTIVES == [True, False]


def test_recarrega_no_subst_i_genera_encadenades(db_session):
    from substitucions.encadenades import activitat_encadenada

    cat = CategoriaPrioritatRepository.create(db_session, "Cat", ordre=0, activa=True)
    AssignaturaPrioritatRepository.create(db_session, "Normal", cat, pes=1)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia-P", cat, pes=1)
    NoSubstituirRepository.create(db_session, "Guàrdia-P", vigent_des_de=date(2026, 11, 4))

    carrega_prioritats(db_session)

    # Abans que «Guàrdia-P» entri a «No substituir», també genera encadenada
    for data, esperat in ((date(2026, 11, 3), {"Normal", "Guàrdia-P"}), (date(2026, 11, 4), {"Normal"})):
        llista = no_substituir_a(data)
        assert llista == ({"Guàrdia-P"} if data == date(2026, 11, 4) else frozenset())
        assert {a for a in ("Normal", "Guàrdia-P") if activitat_encadenada(f"disponible ({a})", llista)} == esperat


def test_si_no_es_poden_carregar_les_prioritats_la_peticio_no_continua(monkeypatch):
    """Sense prioritats el motor no troba candidats: l'error arriba (500) en
    lloc de continuar, i la petició següent les torna a llegir."""
    from suport_api import nova_institucio

    from auth import dependencies

    centre = nova_institucio()
    error = RuntimeError("error de prova")

    def falla(_db):
        raise error

    monkeypatch.setattr(dependencies, "carrega_prioritats", falla)
    with pytest.raises(RuntimeError) as capturada:
        dependencies._prepara_institucio(centre)
    assert capturada.value is error
    assert not constants.te_prioritats(centre)


# ===================================================================
# categoria_de_prioritat: la cerca única de categoria
# ===================================================================


@pytest.mark.parametrize(
    "ordre,activitat,esperat",
    [
        ([{"Guàrdia"}, {"CD", ""}], "Guàrdia", 0),
        ([{"Guàrdia"}, {"CD", ""}], "CD", 1),
        ([{"Guàrdia"}, {"CD", ""}], "", 1),  # la cadena buida també es cerca
        ([{"Guàrdia"}, {"CD", ""}], "Desconeguda", 2),
        ([set(), {"X"}], "X", 1),  # una categoria buida compta per a l'índex
        ([], "Guàrdia", 0),
    ],
)
def test_categoria_de_prioritat(monkeypatch, ordre, activitat, esperat):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", ordre)
    assert categoria_de_prioritat(activitat) == esperat


def test_el_selector_de_vigilants_no_busca_categoria_sense_activitat(monkeypatch):
    from vigilancies.services import _disponibles_de

    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{""}, {"Guàrdia"}])
    context = {
        "prioritats": {"Guàrdia"},
        "vigilancies": [],
        "absents_per_professor": {},
        "absents_tipus": {},
        "substituts_ocupats_per_hora": {},
        "grups_sense_classe_per_hora": {},
        "absents_coberts": set(),
        "professors_ordenats": ["Prof 1", "Prof 2"],
        "activitats_per_hora": {"10:00": {"Prof 1": ("", ""), "Prof 2": ("Guàrdia", "")}},
        "config_examens": None,
    }

    categories = {p["value"]: p["categoria"] for p in _disponibles_de(context, "10:00", None, None, None)}

    assert categoria_de_prioritat("") == 0
    assert categories == {"Prof 1": 2, "Prof 2": 1}


# ===================================================================
# Crear, llegir i esborrar a «No substituir»
# ===================================================================


def test_crud_no_substituir_creat_apareix_a_get(db_session):
    create_no_substituir(NoSubstituirRequest(assignatura="Pati"), db_session)
    resposta = get_no_substituir(db_session)
    assert "Pati" in resposta["assignatures"]


def test_crud_no_substituir_string_buit_es_accepta(db_session):
    """El codi accepta explícitament un string buit com a valor vàlid
    (comentari 'Acceptar string buit' a create_no_substituir) — es
    caracteritza tal com és, per estrany que sembli."""
    resultat = create_no_substituir(NoSubstituirRequest(assignatura=""), db_session)
    assert resultat["success"] is True


def test_crud_no_substituir_sense_clau_assignatura_dona_400(db_session):
    """Sense assignatura, un NoValid (400 per l'API, errors_servidor.py);
    abans un except Exception genèric l'atrapava i la convertia en 500."""
    with pytest.raises(NoValid, match="Assignatura requerida"):
        create_no_substituir(NoSubstituirRequest(), db_session)


def test_crud_no_substituir_delete_inexistent_dona_404(db_session):
    with pytest.raises(NoTrobat):
        delete_no_substituir("No existeix enlloc", db_session)


# ===================================================================
# CRUD: professors de baixa
# ===================================================================
# desar_totes_prioritats: reemplaça tot i recarrega les constants
# ===================================================================


@pytest.mark.parametrize(
    "ordre_categories, noms",
    [
        ([["Reforç-A"], ["Guàrdia", "Guàrdia-R"]], ["Reforç-A", "Guàrdia, Guàrdia-R"]),
        ([["Sol"]], ["Sol"]),
        # Caracteritza el comportament real de generació del nom (no necessàriament
        # l'ideal): `", ".join(assignatures_list[:2])`, només les DUES primeres
        ([["Un", "Dos", "Tres"]], ["Un, Dos"]),
        # Una llista d'assignatures buida no crea cap categoria (`if not assignatures_list: continue`)
        ([[], ["Real"]], ["Real"]),
    ],
)
def test_desar_tot_reemplaca_les_categories_i_les_anomena_per_les_assignatures(db_session, ordre_categories, noms):
    # Estat inicial: una categoria que hauria de desaparèixer.
    CategoriaPrioritatRepository.create(db_session, "Vella", ordre=0)

    payload = PrioritatsRequest(
        ordre_categories=ordre_categories,
        pesos=dict.fromkeys(sum(ordre_categories, []), 1),
        categories_actives=[True] * len(ordre_categories),
    )
    assert desar_totes_prioritats(payload, db_session)["success"] is True

    assert [c["nom"] for c in get_categories(db_session)["categories"]] == noms


def test_desar_tot_recarrega_les_constants_globals(db_session):
    payload = PrioritatsRequest(
        ordre_categories=[["Reforç-A"]],
        pesos={"Reforç-A": 1},
        categories_actives=[True],
    )
    desar_totes_prioritats(payload, db_session)

    # carrega_prioritats() s'ha cridat internament: les
    # constants globals han de reflectir el que s'acaba de desar.
    assert constants.ORDRE_PRIORITATS == [["Reforç-A"]]
    assert constants.PRIORITATS == {"Reforç-A": 1}


def test_els_repositoris_de_prioritats_no_fan_commit(db_session):
    """El commit el fa el servei, un cop per operació: sense, no es desa res."""
    cat = CategoriaPrioritatRepository.create(db_session, "Sense commit", ordre=0)
    AssignaturaPrioritatRepository.create(db_session, "Guàrdia", cat, pes=2)
    NoSubstituirRepository.create(db_session, "Reunió")
    db_session.rollback()
    assert CategoriaPrioritatRepository.get_all(db_session) == []
    assert AssignaturaPrioritatRepository.get_all(db_session) == []
    assert NoSubstituirRepository.vigencia(db_session).entrades == ()


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
