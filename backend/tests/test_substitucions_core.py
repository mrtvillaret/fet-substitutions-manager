"""
Tests de substitucions/assignacio.py: la lògica d'assignació automàtica de
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
from collections import Counter

import pytest

from config import constants
from substitucions.assignacio import CandidateValidator, GestorSubstitucions, QuotaFranja, escull_candidat_amb_quota
from substitucions.files import FilaSubstitucio, PropostaSubstitucio


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

    def get_substitucions_necessaries(self, dia, absents, absents_tipus):
        return [
            PropostaSubstitucio(**{"professor_absent": sub.get("professor", ""), **sub}) for sub in self._substitucions
        ]


# ===== GestorSubstitucions: assignació bàsica =====


def test_assignacio_basica_amb_candidat_disponible(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe={})

    assert len(resultat) == 1
    assert resultat[0].substitut == "Prof_B"


def test_sense_candidats_disponibles_queda_pendent():
    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": []})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=frozenset())
    resultat = gestor.assignar_substitucions(dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe={})

    assert len(resultat) == 1
    assert resultat[0].substitut == ""


def test_no_assigna_el_mateix_substitut_dues_vegades_a_la_mateixa_hora(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choices", lambda seq, *, weights, k: [seq[0]])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat"), ("Prof_C", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [
            {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
            {"professor_absent": "Prof_X", "hora": "09:00", "assignatura": "Física", "grup": "1-ESO-B"},
        ]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"], "Prof_X": ["09:00"]},
        grups_sense_classe={},
    )

    substituts = [sub.substitut for sub in resultat]
    assert len(substituts) == 2
    assert len(set(substituts)) == 2  # cap substitut repetit a la mateixa hora


# ===== Selecció per categoria/prioritat =====


@pytest.mark.parametrize("ordre_invers", [False, True])
def test_quota_inicial_proporcional_independent_de_l_ordre(monkeypatch, ordre_invers):
    monkeypatch.setattr(constants, "PRIORITATS", {"Activitat A": 3, "Activitat B": 1})
    candidats = [("Prof 1", "Activitat A", ""), ("Prof 2", "Activitat A", ""), ("Prof 3", "Activitat B", "")]
    if ordre_invers:
        candidats.reverse()
    selector = CandidateValidator(rng=random.Random(20261108))

    recomptes = Counter(selector._escollir_amb_quota(candidats)[0] for _ in range(7))

    for professor, probabilitat in zip(["Prof 1", "Prof 2", "Prof 3"], [3 / 7, 3 / 7, 1 / 7], strict=True):
        assert recomptes[professor] == round(probabilitat * 7)


def test_pesos_absents_zero_i_negatius_equivalen_a_un(monkeypatch):
    monkeypatch.setattr(constants, "PRIORITATS", {"Zero": 0, "Negatiu": -3, "Positiu": 3})
    candidats = [
        ("Prof 1", "alliberat", "tenia classe"),
        ("Prof 2", "Zero", ""),
        ("Prof 3", "Negatiu", ""),
        ("Prof 4", "Positiu", ""),
    ]

    class AtzarControlat:
        def choices(self, poblacio, *, weights, k):
            assert poblacio == candidats
            assert weights == [1, 1, 1, 3]
            assert k == 1
            return [poblacio[-1]]

    assert escull_candidat_amb_quota(candidats, QuotaFranja(), "09:00", AtzarControlat()) == candidats[-1]
    assert escull_candidat_amb_quota([], QuotaFranja(), "09:00", AtzarControlat()) is None
    assert escull_candidat_amb_quota(candidats[:1], QuotaFranja(), "09:00", AtzarControlat()) == candidats[0]


def test_prioritza_la_categoria_mes_alta_encara_que_tingui_menys_candidats():
    gestor = GestorSubstitucions(FakeHorari([]), FakeAlliberats({}), FakeAbsencies([]), no_substituir=frozenset())
    gestor.validator = CandidateValidator()

    candidats_per_categoria = {
        0: [("Prof_AltaPrioritat", "alliberat", "alliberat")],
        1: [("Prof_BaixaPrioritat_1", "Guàrdia", "Guàrdia"), ("Prof_BaixaPrioritat_2", "Guàrdia", "Guàrdia")],
    }

    escollit = gestor._escollir_millor_candidat_disponible(candidats_per_categoria, set(), "09:00")

    assert escollit[0] == "Prof_AltaPrioritat"


def test_un_alliberat_guanya_dos_de_guardia_sense_consultar_l_atzar(monkeypatch):
    class AtzarProhibit:
        def choice(self, candidats):
            raise AssertionError(f"No calia desempatar entre {candidats}")

    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True, True])
    gestor = GestorSubstitucions(FakeHorari([]), FakeAlliberats({}), FakeAbsencies([]), no_substituir=frozenset())
    gestor.validator = CandidateValidator(rng=AtzarProhibit())

    escollit = gestor._escollir_millor_candidat_disponible(
        {
            0: [("Prof_Alliberat", "alliberat", "tenia classe")],
            1: [
                ("Prof_Guardia_1", "Guàrdia", "Guàrdia"),
                ("Prof_Guardia_2", "Guàrdia", "Guàrdia"),
            ],
        },
        set(),
        "09:00",
    )

    assert escollit == ("Prof_Alliberat", "alliberat", "tenia classe")


def test_categoria_desactivada_no_assigna_automaticament(monkeypatch):
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [False, True])

    gestor = GestorSubstitucions(FakeHorari([]), FakeAlliberats({}), FakeAbsencies([]), no_substituir=frozenset())
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
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    monkeypatch.setattr(random, "choices", lambda seq, *, weights, k: [seq[0]])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "Guàrdia", "Guàrdia"), ("Prof_C", "Guàrdia", "Guàrdia")]})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe={})

    # L'absència original de Prof_A la cobreix Prof_B (tenia Guàrdia, categoria
    # que genera encadenada); com que Prof_B ara fa una substitució, cal
    # generar-ne una altra per cobrir la seva pròpia Guàrdia.
    assert len(resultat) == 2

    original = next(sub for sub in resultat if sub.professor_absent == "Prof_A")
    assert original.substitut == "Prof_B"

    encadenada = next(sub for sub in resultat if sub.tipus_absencia == "ENCADENADA")
    assert encadenada.professor_absent == "Prof_B"
    assert encadenada.substitut == "Prof_C"


def test_no_genera_encadenada_si_lassignatura_esta_a_no_subst(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset({"Guàrdia"})
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    monkeypatch.setattr(random, "choices", lambda seq, *, weights, k: [seq[0]])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "Guàrdia", "Guàrdia"), ("Prof_C", "Guàrdia", "Guàrdia")]})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(dia="Dilluns", absents={"Prof_A": ["09:00"]}, grups_sense_classe={})

    # "Guàrdia" és a «No substituir»: no s'ha de generar cap substitució encadenada.
    assert len(resultat) == 1
    assert resultat[0].substitut == "Prof_B"


def test_substitucions_amb_llavor_conserven_l_ordre_i_el_consum_d_atzar(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia", "Suport", "Tutoria"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1, "Suport": 3, "Tutoria": 1})

    horari = FakeHorari(hores=["09:00", "11:30"])
    alliberats = FakeAlliberats(
        {
            "11:30": [
                ("Prof_B", "Guàrdia", "Guàrdia"),
                ("Prof_C", "Suport", "Suport"),
                ("Prof_D", "Tutoria", "Tutoria"),
                ("Prof_P", "Guàrdia", "Guàrdia"),
            ],
            "09:00": [("Prof_E", "Suport", "Suport"), ("Prof_F", "Tutoria", "Tutoria")],
        }
    )
    absencies = FakeAbsencies(
        [
            {"professor_absent": "Prof_A", "hora": "11:30", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
            {"professor_absent": "Prof_X", "hora": "09:00", "assignatura": "Anglès", "grup": "2-ESO-A"},
            {"professor_absent": "Prof_Y", "hora": "11:30", "assignatura": "Física", "grup": "1-ESO-B"},
        ]
    )
    substitucions_existents = {
        "Prof_Y|11:30|Física|1-ESO-B": FilaSubstitucio(substitut="Prof_P", tipus_substitut="disponible (Guàrdia)")
    }
    # Prof_D té un torn previ: la primera encadenada té un mínim únic, Prof_C.
    quota = QuotaFranja([("11:30", "Prof_D", "disponible (Tutoria)")])
    # Si s'intercanvien els dos sortejos, guanyen Prof_C a les 11:30 i Prof_E a les 09:00.
    rng = random.Random(1)
    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=frozenset({"Suport", "Tutoria"}))
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["11:30"], "Prof_X": ["09:00"], "Prof_Y": ["11:30"]},
        grups_sense_classe={},
        substitucions_existents=substitucions_existents,
        rng=rng,
        quota=quota,
    )

    assert [(s.professor_absent, s.hora, s.assignatura, s.grup, s.substitut) for s in resultat] == [
        ("Prof_A", "11:30", "Matemàtiques", "1-ESO-A", "Prof_B"),
        ("Prof_X", "09:00", "Anglès", "2-ESO-A", "Prof_F"),
        ("Prof_Y", "11:30", "Física", "1-ESO-B", "Prof_P"),
        ("Prof_B", "11:30", "Guàrdia", "", "Prof_C"),
        ("Prof_P", "11:30", "Guàrdia", "", "Prof_D"),
    ]
    assert rng.random() == 0.763774618976614


# =====================================================================
# CHARACTERIZATION TESTS: branques i paràmetres no coberts pels tests
# anteriors — capturen el comportament real actual, no una idealització.
# =====================================================================

# ----- Paràmetres que es reenvien tal qual al gestor d'absències -----


def test_absents_tipus_es_reenvia_al_gestor_dabsencies(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})

    crides = {}

    class FakeAbsenciesEspia(FakeAbsencies):
        def get_substitucions_necessaries(self, dia, absents, absents_tipus):
            crides["absents_tipus"] = absents_tipus
            return super().get_substitucions_necessaries(dia, absents, absents_tipus)

    absents_tipus = {"Prof_A": "SERVEI"}

    gestor = GestorSubstitucions(
        FakeHorari(hores=["09:00"]), FakeAlliberats({}), FakeAbsenciesEspia([]), no_substituir=no_substituir
    )
    gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe={},
        absents_tipus=absents_tipus,
    )

    assert crides["absents_tipus"] == absents_tipus


# ----- Conservació d'assignacions anteriors (substitucions_existents) -----


@pytest.mark.parametrize("omplir", [True, False])
@pytest.mark.parametrize("substitut_desat", ["Prof_B", ""])
def test_substitucio_desada_te_preferencia_sobre_una_nova(monkeypatch, omplir, substitut_desat):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "tenia classe")]})
    absencies = FakeAbsencies(
        [
            {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
            {
                "professor_absent": "Prof_X",
                "hora": "09:00",
                "assignatura": "Física",
                "grup": "1-ESO-B",
                "tipus_absencia": "SERVEI",
            },
        ]
    )
    desada = FilaSubstitucio(
        substitut=substitut_desat, tipus_substitut="manual", tipus_absencia="ABSENCIA", comentaris="Comentari desat"
    )
    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=frozenset())
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"], "Prof_X": ["09:00"]},
        grups_sense_classe={},
        substitucions_existents={"Prof_X|09:00|Física|1-ESO-B": desada},
        omplir=omplir,
    )

    assert [s.professor_absent for s in resultat] == ["Prof_A", "Prof_X"]
    nova, conservada = resultat
    assert nova.substitut == ("Prof_B" if omplir and not substitut_desat else "")
    assert conservada.substitut == substitut_desat
    assert conservada.tipus_substitut == ("manual" if substitut_desat else "")
    assert conservada.comentaris == "Comentari desat"
    assert conservada.tipus_absencia == "SERVEI"


def test_conserva_el_substitut_anterior_si_encara_esta_disponible(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choices", lambda seq, *, weights, k: [seq[0]])

    horari = FakeHorari(hores=["09:00"])
    # Dos candidats disponibles: si no hi hagués conservació, l'ordre/atzar
    # en podria triar un altre.
    alliberats = FakeAlliberats(
        {"09:00": [("Prof_Nou", "alliberat", "alliberat"), ("Prof_Antic", "alliberat", "alliberat")]}
    )
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )
    substitucions_existents = {
        "Prof_A|09:00|Matemàtiques|1-ESO-A": FilaSubstitucio(
            **{
                "substitut": "Prof_Antic",
                "tipus_substitut": "alliberat (alliberat)",
                "comentaris": "",
                "tipus_absencia": "ABSENCIA",
            }
        )
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe={},
        substitucions_existents=substitucions_existents,
    )

    assert resultat[0].substitut == "Prof_Antic"


def test_conserva_el_substitut_desat_encara_que_ja_no_surti_disponible(monkeypatch):
    """«Genera pendents» no reescriu les files que ja tenen substitut: el motor
    les conserva tal com són i no hi gasta cap altre candidat. Prof_Antic ja no
    surt com a disponible, però la seva fila no es toca, i l'únic candidat lliure
    (Prof_Nou) va a la fila pendent de la mateixa hora."""
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choices", lambda seq, *, weights, k: [seq[0]])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_Nou", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [
            {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
            {"professor_absent": "Prof_B", "hora": "09:00", "assignatura": "Anglès", "grup": "2-ESO-A"},
        ]
    )
    substitucions_existents = {
        "Prof_A|09:00|Matemàtiques|1-ESO-A": FilaSubstitucio(
            **{
                "substitut": "Prof_Antic",
                "tipus_substitut": "",
                "comentaris": "",
                "tipus_absencia": "ABSENCIA",
            }
        )
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"], "Prof_B": ["09:00"]},
        grups_sense_classe={},
        substitucions_existents=substitucions_existents,
    )

    per_absent = {s.professor_absent: s for s in resultat if not s.separador}
    assert per_absent["Prof_A"].substitut == "Prof_Antic"
    assert per_absent["Prof_B"].substitut == "Prof_Nou"


def test_conserva_seleccio_buida_anterior_encara_que_hi_hagi_candidat(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )
    substitucions_existents = {
        "Prof_A|09:00|Matemàtiques|1-ESO-A": FilaSubstitucio(
            **{
                "substitut": "",
                "tipus_substitut": "",
                "comentaris": "pendent de decidir",
                "tipus_absencia": "ABSENCIA",
            }
        )
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe={},
        substitucions_existents=substitucions_existents,
    )

    # Comportament actual (una mica sorprenent, però és el que fa el codi):
    # tot i haver-hi Prof_B disponible, com que la selecció desada era
    # explícitament buida ("-- selecciona substitut --"), es conserva
    # buida en lloc de reassignar-se automàticament.
    assert resultat[0].substitut == ""
    assert resultat[0].comentaris == "pendent de decidir"


# ----- Preservació d'encadenades desades a substitucions_existents -----


def test_recupera_encadenades_desades_dels_substituts_actius_a_la_mateixa_hora(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True, True])
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})

    horari = FakeHorari(hores=["09:00", "11:30"])
    candidats = [("Prof_B", "Guàrdia", "Guàrdia"), ("Prof_C", "alliberat", "tenia classe")]
    alliberats = FakeAlliberats({"09:00": candidats})
    absencies = FakeAbsencies(
        [
            {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
            {"professor_absent": "Prof_X", "hora": "09:00", "assignatura": "Física", "grup": "1-ESO-B"},
        ]
    )
    regenerada = FilaSubstitucio(
        tipus_absencia="ENCADENADA", substitut="Prof_D", tipus_substitut="manual", comentaris="Comentari regenerat"
    )
    recuperable = FilaSubstitucio(
        tipus_absencia="ENCADENADA",
        substitut="Prof_C",
        tipus_substitut="alliberat (tenia classe)",
        comentaris="Comentari recuperat",
    )
    substitucions_existents = {
        "Prof_D|09:00|Tutoria|1-ESO-C": recuperable,
        "Prof_D|11:30|Tutoria|1-ESO-C": recuperable,
        "Prof_D|09:00|Tutoria": recuperable,
        "Prof_B|09:00|Guàrdia|": regenerada,
    }
    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=frozenset())
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"], "Prof_X": ["09:00"]},
        grups_sense_classe={},
        substitucions_existents=substitucions_existents,
    )

    # Comportament actual (sospitós, pendent de decidir): es recupera l'encadenada de Prof_D
    # encara que l'activitat no sigui a Prioritats i Prof_C ja cobreixi una fila de la mateixa hora.
    assert [(s.professor_absent, s.hora, s.substitut) for s in resultat] == [
        ("Prof_A", "09:00", "Prof_B"),
        ("Prof_X", "09:00", "Prof_C"),
        ("Prof_B", "09:00", "Prof_D"),
        ("Prof_D", "09:00", "Prof_C"),
    ]
    assert resultat[2:] == [
        PropostaSubstitucio(
            professor_absent="Prof_B",
            hora="09:00",
            assignatura="Guàrdia",
            tipus_absencia="ENCADENADA",
            substitut="Prof_D",
            tipus_substitut="manual",
            comentaris="Comentari regenerat",
            disponibles=candidats,
        ),
        PropostaSubstitucio(
            professor_absent="Prof_D",
            hora="09:00",
            assignatura="Tutoria",
            grup="1-ESO-C",
            tipus_absencia="ENCADENADA",
            substitut="Prof_C",
            tipus_substitut="alliberat (tenia classe)",
            comentaris="Comentari recuperat",
        ),
    ]


def test_preserva_encadenada_del_json_quan_el_pare_torna_a_tenir_el_mateix_substitut(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})  # buit: no es regenera en viu

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )
    # Encadenada desada d'una execució anterior: Prof_B, quan feia de
    # substitut, tenia una Guàrdia que la cobria Prof_C.
    substitucions_existents = {
        "Prof_B|09:00|Guàrdia|": FilaSubstitucio(
            **{
                "tipus_absencia": "ENCADENADA",
                "substitut": "Prof_C",
                "tipus_substitut": "",
                "comentaris": "",
            }
        )
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe={},
        substitucions_existents=substitucions_existents,
    )

    # Prof_B torna a ser assignat com a substitut de Prof_A (mateixa clau
    # que abans), i per tant l'encadenada desada es reafegeix.
    assert len(resultat) == 2
    original = next(sub for sub in resultat if sub.professor_absent == "Prof_A")
    assert original.substitut == "Prof_B"
    encadenada = next(sub for sub in resultat if sub.tipus_absencia == "ENCADENADA")
    assert encadenada.professor_absent == "Prof_B"
    assert encadenada.substitut == "Prof_C"


def test_encadenada_del_json_es_descarta_si_el_pare_ja_no_es_actiu(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )
    # L'encadenada desada fa referència a Prof_Z, que en aquesta execució
    # NO ha estat assignat com a substitut de ningú a les 09:00.
    substitucions_existents = {
        "Prof_Z|09:00|Guàrdia|": FilaSubstitucio(
            **{
                "tipus_absencia": "ENCADENADA",
                "substitut": "Prof_C",
                "tipus_substitut": "",
                "comentaris": "",
            }
        )
    }

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe={},
        substitucions_existents=substitucions_existents,
    )

    assert len(resultat) == 1
    assert all(sub.tipus_absencia != "ENCADENADA" for sub in resultat)


# ----- grups_sense_classe: {hora: grups} -----


def test_grups_sense_classe_com_a_dict_filtra_nomes_lhora_indicada(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_B", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [{"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"}]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"]},
        grups_sense_classe={"09:00": {"1-ESO-A"}},
    )

    # El grup 1-ESO-A ja no té classe a les 09:00: no cal cap substitut.
    assert resultat == []


# ----- Més absents que candidats / mateix professor a diverses hores -----


def test_mes_absents_que_candidats_alguns_queden_pendents(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choices", lambda seq, *, weights, k: [seq[0]])

    horari = FakeHorari(hores=["09:00"])
    alliberats = FakeAlliberats({"09:00": [("Prof_Unic", "alliberat", "alliberat")]})
    absencies = FakeAbsencies(
        [
            {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
            {"professor_absent": "Prof_X", "hora": "09:00", "assignatura": "Física", "grup": "1-ESO-B"},
            {"professor_absent": "Prof_Y", "hora": "09:00", "assignatura": "Química", "grup": "1-ESO-C"},
        ]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns",
        absents={"Prof_A": ["09:00"], "Prof_X": ["09:00"], "Prof_Y": ["09:00"]},
        grups_sense_classe={},
    )

    assignats = [sub for sub in resultat if sub.substitut]
    pendents = [sub for sub in resultat if not sub.substitut]
    assert len(resultat) == 3
    assert len(assignats) == 1
    assert len(pendents) == 2


def test_mateix_professor_absent_a_diverses_hores_es_resol_independentment(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    no_substituir = frozenset()
    monkeypatch.setattr(constants, "PRIORITATS", {})
    monkeypatch.setattr(random, "choices", lambda seq, *, weights, k: [seq[0]])

    horari = FakeHorari(hores=["09:00", "10:00"])
    alliberats = FakeAlliberats(
        {
            "09:00": [("Prof_Mati", "alliberat", "alliberat")],
            "10:00": [],  # a les 10:00 no hi ha ningú disponible
        }
    )
    absencies = FakeAbsencies(
        [
            {"professor_absent": "Prof_A", "hora": "09:00", "assignatura": "Matemàtiques", "grup": "1-ESO-A"},
            {"professor_absent": "Prof_A", "hora": "10:00", "assignatura": "Física", "grup": "1-ESO-A"},
        ]
    )

    gestor = GestorSubstitucions(horari, alliberats, absencies, no_substituir=no_substituir)
    resultat = gestor.assignar_substitucions(
        dia="Dilluns", absents={"Prof_A": ["09:00", "10:00"]}, grups_sense_classe={}
    )

    per_hora = {sub.hora: sub for sub in resultat}
    assert per_hora["09:00"].substitut == "Prof_Mati"
    assert per_hora["10:00"].substitut == ""


# ----- _generar_substitucions_vigilants (inclòs l'avís d'excepcions) -----


def test_vigilant_amb_classe_real_genera_substitucio_de_vigilancia():
    horari = FakeHorari(hores=["09:00"])
    horari._activitats[("Dilluns", "09:00", "Prof_V")] = {
        "grup": "1-ESO-A",
        "assignatura": "Matemàtiques",
        "aula": "A1",
    }
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]), no_substituir=frozenset())
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns")

    assert len(resultat) == 1
    assert resultat[0].tipus_absencia == "VIGILANCIA"
    assert resultat[0].professor_absent == "Prof_V"
    assert resultat[0].grup == "1-ESO-A"


def test_vigilant_sense_activitat_no_genera_substitucio():
    horari = FakeHorari(hores=["09:00"])  # get_activitat retorna None per defecte
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]), no_substituir=frozenset())
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns")

    assert resultat == []


def test_vigilant_amb_activitat_de_prioritats_sense_grup_genera_substitucio(monkeypatch):
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    no_substituir = frozenset()

    horari = FakeHorari(hores=["09:00"])
    horari._activitats[("Dilluns", "09:00", "Prof_V")] = {"grup": "", "assignatura": "Guàrdia", "aula": ""}
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]), no_substituir=no_substituir)
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns")

    assert len(resultat) == 1
    assert resultat[0].grup == ""
    assert resultat[0].assignatura == "Guàrdia"


def test_vigilant_amb_assignatura_a_no_subst_no_genera_substitucio(monkeypatch):
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    no_substituir = frozenset({"Guàrdia"})

    horari = FakeHorari(hores=["09:00"])
    horari._activitats[("Dilluns", "09:00", "Prof_V")] = {"grup": "", "assignatura": "Guàrdia", "aula": ""}
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]), no_substituir=no_substituir)
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns")

    assert resultat == []


class _HorariQueTrenca(FakeHorari):
    def get_activitat(self, dia, hora, professor):
        raise RuntimeError("error simulat d'horari")


def test_generar_substitucions_vigilants_avisa_d_excepcions_internes(caplog):
    """Si `horari.get_activitat` peta, `_generar_substitucions_vigilants`
    ho registra amb traça, retorna una llista buida i deixa un avís: la
    generació de la resta de substitucions no s'atura."""
    horari = _HorariQueTrenca(hores=["09:00"])
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]), no_substituir=frozenset())
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}

    resultat = gestor._generar_substitucions_vigilants("Dilluns")

    assert resultat == []
    assert gestor.avisos == [
        "No s'han pogut generar les cobertures de classe dels vigilants. Revisa les substitucions pendents."
    ]
    assert any(
        "No s'han pogut generar les substitucions dels vigilants" in record.getMessage() and record.exc_info
        for record in caplog.records
    )


def test_cobertura_de_vigilant_nomes_mira_els_grups_sense_classe_de_la_seva_hora():
    """El grup del vigilant està sense classe a les 12:30, no a les 09:00:
    a les 09:00 té classe i cal cobrir-la."""
    horari = FakeHorari(hores=["09:00", "12:30"])
    horari._activitats[("Dilluns", "09:00", "Prof_V")] = {
        "grup": "1-ESO-A",
        "assignatura": "Matemàtiques",
        "aula": "A1",
    }
    gestor = GestorSubstitucions(horari, FakeAlliberats({}), FakeAbsencies([]), no_substituir=frozenset())
    gestor.professors_ocupats_examens = {"09:00": ["Prof_V"]}
    gestor.grups_sense_classe_dict = {"12:30": ["1-ESO-A"]}

    assert len(gestor._generar_substitucions_vigilants("Dilluns")) == 1

    gestor.grups_sense_classe_dict = {"09:00": ["1-ESO-A"]}
    assert gestor._generar_substitucions_vigilants("Dilluns") == []
