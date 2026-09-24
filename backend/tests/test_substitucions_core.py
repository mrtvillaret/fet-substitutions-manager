"""
Tests de core/substitucions.py: la lògica d'assignació automàtica de
substituts (GestorSubstitucions i CandidateValidator). No toca cap base
de dades ni sistema real — els tres col·laboradors (horari, alliberats,
absencies) es simulen amb fakes lleugers perquè els tests siguin ràpids
i deterministes.

La segona meitat del fitxer són "characterization tests": no verifiquen
només el que hauria de passar segons la documentació, sinó que capturen
sistemàticament el comportament REAL del codi actual (branques
secundàries, casos d'entrada menys habituals, camins d'error) perquè
serveixin de xarxa de seguretat davant de qualsevol canvi futur, encara
que algun d'aquests comportaments no sigui ideal.
"""
import random

from config import constants
from core.substitucions import CandidateValidator, GestorSubstitucions


class FakeHorari:
    """Simula el gestor d'horari: només `hores` i `get_activitat` calen
    per als camins que cobrim aquí."""

    def __init__(self, hores):
        self.hores = hores
        self._activitats = {}

    def get_dia_name(self, weekday_idx):
        return "Dilluns"

    def get_activitat(self, dia, hora, professor):
        return self._activitats.get((dia, hora, professor))


class FakeAlliberats:
    """Simula el gestor de disponibilitats: `disponibles_per_hora` és un
    dict {hora: [(professor, tipus, detall), ...]}."""

    def __init__(self, disponibles_per_hora):
        self._disponibles = disponibles_per_hora

    def get_tots_disponibles(self, dia, hora, grups_sense_classe):
        return list(self._disponibles.get(hora, []))


class FakeAbsencies:
    """Simula el gestor d'absències: retorna sempre la mateixa llista de
    substitucions necessàries que se li passi al constructor."""

    def __init__(self, substitucions):
        self._substitucions = substitucions

    def get_substitucions_necessaries(self, dia, absents, absents_tipus, activitats_fallback=None):
        return [dict(sub) for sub in self._substitucions]


# ===== CandidateValidator: validació de candidats =====

def test_candidat_absent_a_aquella_hora_es_invalid():
    validator = CandidateValidator()
    absents = {"Prof_Absent": ["09:00"]}
    assert validator.es_valid("Prof_Absent", "09:00", absents) is False


def test_candidat_ocupat_amb_vigilancia_es_invalid():
    validator = CandidateValidator(professors_ocupats_examens={"09:00": ["Prof_Vigilant"]})
    assert validator.es_valid("Prof_Vigilant", "09:00", {}) is False


def test_candidat_lliure_es_valid():
    validator = CandidateValidator()
    assert validator.es_valid("Prof_Lliure", "09:00", {}) is True


# ===== GestorSubstitucions: assignació bàsica =====

def test_assignacio_basica_amb_candidat_disponible(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe=set()
    )

    assert len(resultat) == 1
    assert resultat[0]["substitut"] == "Prof_B"


def test_sense_candidats_disponibles_queda_pendent():
    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": []})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe=set()
    )

    assert len(resultat) == 1
    assert resultat[0].get("substitut", "") == ""


def test_no_assigna_el_mateix_substitut_dues_vegades_a_la_mateixa_hora(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({
        "09:00": [("Prof_B", "alliberat", "alliberat"), ("Prof_C", "alliberat", "alliberat")]
    })
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
        {"professor_absent": "Prof_X", "hora": "09:00", "assignatura": "Física", "grup": "1-ESO-B"},
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"], "Prof_X": ["09:00"]},
        grups_sense_classe=set(),
    )

    substituts = [sub["substitut"] for sub in resultat]
    assert len(substituts) == 2
    assert len(set(substituts)) == 2  # cap substitut repetit a la mateixa hora


# ===== Selecció per categoria/prioritat =====

def test_prioritza_la_categoria_mes_alta_encara_que_tingui_menys_candidats():
    gestor = GestorSubstitucions(FakeHorari([]), FakeAlliberats({}), FakeAbsencies([]))
    gestor.validator = CandidateValidator()

    candidats_per_categoria = {
        0: [("Prof_AltaPrioritat", "alliberat", "alliberat")],
        1: [("Prof_BaixaPrioritat_1", "Guàrdia", "Guàrdia"),
            ("Prof_BaixaPrioritat_2", "Guàrdia", "Guàrdia")],
    }

    escollit = gestor._escollir_millor_candidat_disponible(candidats_per_categoria, set(), "09:00")

    assert escollit[0] == "Prof_AltaPrioritat"


def test_categoria_desactivada_no_assigna_automaticament(monkeypatch):
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [False, True])

    gestor = GestorSubstitucions(FakeHorari([]), FakeAlliberats({}), FakeAbsencies([]))
    gestor.validator = CandidateValidator()

    candidats_per_categoria = {
        0: [("Prof_CategoriaInactiva", "alliberat", "alliberat")],
        1: [("Prof_CategoriaActiva", "Guàrdia", "Guàrdia")],
    }

    escollit = gestor._escollir_millor_candidat_disponible(candidats_per_categoria, set(), "09:00")

    assert escollit[0] == "Prof_CategoriaActiva"


# ===== Substitucions encadenades (generades en viu) =====

def test_substitucio_encadenada_cobreix_el_professor_substitut(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({
        "09:00": [("Prof_B", "Guàrdia", "Guàrdia"), ("Prof_C", "Guàrdia", "Guàrdia")]
    })
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe=set()
    )

    # L'absència original de Prof_A la cobreix Prof_B (tenia Guàrdia, categoria
    # que genera encadenada); com que Prof_B ara fa una substitució, cal
    # generar-ne una altra per cobrir la seva pròpia Guàrdia.
    assert len(resultat) == 2

    original = next(sub for sub in resultat if sub.get("professor_absent") == "Prof_A")
    assert original["substitut"] == "Prof_B"

    encadenada = next(sub for sub in resultat if sub.get("tipus_absencia") == "ENCADENADA")
    assert encadenada["professor_absent"] == "Prof_B"
    assert encadenada["substitut"] == "Prof_C"


def test_no_genera_encadenada_si_lassignatura_esta_a_no_subst(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", {"Guàrdia"})
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({
        "09:00": [("Prof_B", "Guàrdia", "Guàrdia"), ("Prof_C", "Guàrdia", "Guàrdia")]
    })
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe=set()
    )

    # "Guàrdia" és a NO_SUBST: no s'ha de generar cap substitució encadenada.
    assert len(resultat) == 1
    assert resultat[0]["substitut"] == "Prof_B"


# =====================================================================
# CHARACTERIZATION TESTS: branques i paràmetres no coberts pels tests
# anteriors — capturen el comportament real actual, no una idealització.
# =====================================================================

# ----- Paràmetres que es reenvien tal qual al gestor d'absències -----

def test_absents_tipus_i_activitats_fallback_es_reenvien_al_gestor_dabsencies(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})

    crides = {}

    class FakeAbsenciesEspia(FakeAbsencies):
        def get_substitucions_necessaries(self, dia, absents, absents_tipus, activitats_fallback=None):
            crides["absents_tipus"] = absents_tipus
            crides["activitats_fallback"] = activitats_fallback
            return super().get_substitucions_necessaries(dia, absents, absents_tipus, activitats_fallback)

    absents_tipus = {"Prof_A": "SERVEI"}
    activitats_fallback = {"Prof_A": {"09:00": {"assignatura": "Guàrdia"}}}

    gestor = GestorSubstitucions(FakeHorari(hores=["09:00"]), FakeAlliberats({}), FakeAbsenciesEspia([]))
    gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe=set(),
        absents_tipus=absents_tipus,
        activitats_fallback=activitats_fallback,
    )

    assert crides["absents_tipus"] == absents_tipus
    assert crides["activitats_fallback"] == activitats_fallback


# ----- Conservació d'assignacions anteriors (substitucions_existents) -----

def test_conserva_el_substitut_anterior_si_encara_esta_disponible(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    horari = FakeHorari(hores=["09:00"])
    # Dos candidats disponibles: si no hi hagués conservació, l'ordre/atzar
    # en podria triar un altre.
    alliberats = FakeAlliberats({
        "09:00": [("Prof_Nou", "alliberat", "alliberat"), ("Prof_Antic", "alliberat", "alliberat")]
    })
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])
    substitucions_existents = {
        "Prof_A|09:00|Matemàtiques|1-ESO-A": {
            "substitut": "Prof_Antic",
            "tipus_substitut": "alliberat (alliberat)",
            "comentaris": "",
            "tipus_absencia": "ABSENCIA",
        }
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe=set(),
        substitucions_existents=substitucions_existents,
    )

    assert resultat[0]["substitut"] == "Prof_Antic"
    assert resultat[0].get("_conservat") is True


def test_reassigna_si_el_substitut_anterior_ja_no_esta_disponible(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    horari = FakeHorari(hores=["09:00"])
    # Prof_Antic ja no surt a la llista de disponibles d'aquesta execució.
    alliberats = FakeAlliberats({"09:00": [("Prof_Nou", "alliberat", "alliberat")]})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])
    substitucions_existents = {
        "Prof_A|09:00|Matemàtiques|1-ESO-A": {
            "substitut": "Prof_Antic", "tipus_substitut": "", "comentaris": "", "tipus_absencia": "ABSENCIA"
        }
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe=set(),
        substitucions_existents=substitucions_existents,
    )

    assert resultat[0]["substitut"] == "Prof_Nou"
    assert "_conservat" not in resultat[0]


def test_conserva_seleccio_buida_anterior_encara_que_hi_hagi_candidat(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])
    substitucions_existents = {
        "Prof_A|09:00|Matemàtiques|1-ESO-A": {
            "substitut": "", "tipus_substitut": "", "comentaris": "pendent de decidir", "tipus_absencia": "ABSENCIA"
        }
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe=set(),
        substitucions_existents=substitucions_existents,
    )

    # Comportament actual (una mica sorprenent, però és el que fa el codi):
    # tot i haver-hi Prof_B disponible, com que la selecció desada era
    # explícitament buida ("-- selecciona substitut --"), es conserva
    # buida en lloc de reassignar-se automàticament.
    assert resultat[0]["substitut"] == ""
    assert resultat[0]["comentaris"] == "pendent de decidir"


# ----- Preservació d'encadenades desades a substitucions_existents -----

def test_preserva_encadenada_del_json_quan_el_pare_torna_a_tenir_el_mateix_substitut(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})  # buit: no es regenera en viu

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])
    # Encadenada desada d'una execució anterior: Prof_B, quan feia de
    # substitut, tenia una Guàrdia que la cobria Prof_C.
    substitucions_existents = {
        "Prof_B|09:00|Guàrdia|": {
            "tipus_absencia": "ENCADENADA", "substitut": "Prof_C", "tipus_substitut": "", "comentaris": ""
        }
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe=set(),
        substitucions_existents=substitucions_existents,
    )

    # Prof_B torna a ser assignat com a substitut de Prof_A (mateixa clau
    # que abans), i per tant l'encadenada desada es reafegeix.
    assert len(resultat) == 2
    original = next(sub for sub in resultat if sub.get("professor_absent") == "Prof_A")
    assert original["substitut"] == "Prof_B"
    encadenada = next(sub for sub in resultat if sub.get("tipus_absencia") == "ENCADENADA")
    assert encadenada["professor_absent"] == "Prof_B"
    assert encadenada["substitut"] == "Prof_C"


def test_encadenada_del_json_es_descarta_si_el_pare_ja_no_es_actiu(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])
    # L'encadenada desada fa referència a Prof_Z, que en aquesta execució
    # NO ha estat assignat com a substitut de ningú a les 09:00.
    substitucions_existents = {
        "Prof_Z|09:00|Guàrdia|": {
            "tipus_absencia": "ENCADENADA", "substitut": "Prof_C", "tipus_substitut": "", "comentaris": ""
        }
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe=set(),
        substitucions_existents=substitucions_existents,
    )

    assert len(resultat) == 1
    assert all(sub.get("tipus_absencia") != "ENCADENADA" for sub in resultat)


# ----- grups_sense_classe: Dict[str, Set[str]] (nou) vs Set[str] (antic) -----

def test_grups_sense_classe_com_a_dict_filtra_nomes_lhora_indicada(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe={"09:00": {"1-ESO-A"}},
    )

    # El grup 1-ESO-A ja no té classe a les 09:00: no cal cap substitut.
    assert resultat == []


def test_grups_sense_classe_com_a_set_antic_saplica_a_totes_les_hores(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00", "10:00"])
    alliberats = FakeAlliberats({
        "09:00": [("Prof_B", "alliberat", "alliberat")],
        "10:00": [("Prof_B", "alliberat", "alliberat")],
    })
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
        {"professor_absent": "Prof_A", "hora": "10:00", "assignatura": "Física", "grup": "1-ESO-A"},
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00", "10:00"]},
        grups_sense_classe={"1-ESO-A"},  # format antic: Set[str], s'aplica a totes les hores
    )

    assert resultat == []


# ----- Més absents que candidats / mateix professor a diverses hores -----

def test_mes_absents_que_candidats_alguns_queden_pendents(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_Unic", "alliberat", "alliberat")]})
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
        {"professor_absent": "Prof_X", "hora": "09:00", "assignatura": "Física", "grup": "1-ESO-B"},
        {"professor_absent": "Prof_Y", "hora": "09:00", "assignatura": "Química", "grup": "1-ESO-C"},
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"], "Prof_X": ["09:00"], "Prof_Y": ["09:00"]},
        grups_sense_classe=set(),
    )

    assignats = [sub for sub in resultat if sub.get("substitut")]
    pendents = [sub for sub in resultat if not sub.get("substitut")]
    assert len(resultat) == 3
    assert len(assignats) == 1
    assert len(pendents) == 2


def test_mateix_professor_absent_a_diverses_hores_es_resol_independentment(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "NO_SUBST", set())
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    horari = FakeHorari(hores=["09:00", "10:00"])
    alliberats = FakeAlliberats({
        "09:00": [("Prof_Mati", "alliberat", "alliberat")],
        "10:00": [],  # a les 10:00 no hi ha ningú disponible
    })
    absencies = FakeAbsencies([
        {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
        {"professor_absent": "Prof_A", "hora": "10:00", "assignatura": "Física", "grup": "1-ESO-A"},
    ])

    gestor = GestorSubstitucions(horari, alliberats, absencies)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns", absents={"Prof_A": ["09:00", "10:00"]}, grups_sense_classe=set()
    )

    per_hora = {sub["hora"]: sub for sub in resultat}
    assert per_hora["09:00"]["substitut"] == "Prof_Mati"
    assert per_hora["10:00"].get("substitut", "") == ""


# ----- _generar_substitucions_vigilants (inclòs el silenci d'excepcions) -----

def test_vigilant_amb_classe_real_genera_substitucio_de_vigilancia():
    horari = FakeHorari(hores=["09:00"])
    horari._activitats[("Dilluns", "09:00", "Prof_V")] = {
        "grup": "1-ESO-A", "assignatura": "Matemàtiques", "aula": "A1"
    }
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]))
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns", grups_sense_classe=set())

    assert len(resultat) == 1
    assert resultat[0]["tipus_absencia"] == "VIGILANCIA"
    assert resultat[0]["professor_absent"] == "Prof_V"
    assert resultat[0]["grup"] == "1-ESO-A"


def test_vigilant_sense_activitat_no_genera_substitucio():
    horari = FakeHorari(hores=["09:00"])  # get_activitat retorna None per defecte
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]))
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns", grups_sense_classe=set())

    assert resultat == []


def test_vigilant_amb_activitat_de_prioritats_sense_grup_genera_substitucio(monkeypatch):
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    monkeypatch.setattr(constants, "NO_SUBST", set())

    horari = FakeHorari(hores=["09:00"])
    horari._activitats[("Dilluns", "09:00", "Prof_V")] = {"grup": "", "assignatura": "Guàrdia", "aula": ""}
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]))
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns", grups_sense_classe=set())

    assert len(resultat) == 1
    assert resultat[0]["grup"] == ""
    assert resultat[0]["assignatura"] == "Guàrdia"


def test_vigilant_amb_assignatura_a_no_subst_no_genera_substitucio(monkeypatch):
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    monkeypatch.setattr(constants, "NO_SUBST", {"Guàrdia"})

    horari = FakeHorari(hores=["09:00"])
    horari._activitats[("Dilluns", "09:00", "Prof_V")] = {"grup": "", "assignatura": "Guàrdia", "aula": ""}
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]))
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns", grups_sense_classe=set())

    assert resultat == []


class _HorariQueTrenca(FakeHorari):
    def get_activitat(self, dia, hora, professor):
        raise RuntimeError("error simulat d'horari")


def test_generar_substitucions_vigilants_silencia_excepcions_internes():
    """Characterization test d'un comportament real però lleig del codi
    actual: si `horari.get_activitat` peta, `_generar_substitucions_vigilants`
    atrapa l'excepció amb un `except Exception: pass` sense cap log ni
    rastre de l'error, i simplement retorna una llista buida (ja
    identificat com a punt de millora en una auditoria de qualitat
    d'aquesta mateixa sessió). Aquest test no en jutja la bondat, només
    en documenta el comportament actual perquè un canvi futur que
    l'"arregli" (per exemple afegint un log) no el trenqui sense
    adonar-se'n."""
    horari = _HorariQueTrenca(hores=["09:00"])
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]))
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns", grups_sense_classe=set())

    assert resultat == []
