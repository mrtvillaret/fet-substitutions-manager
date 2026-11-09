"""Quota amb finestra de deu: fraccions exactes i atzar reproduïble."""

import random
from collections import Counter
from fractions import Fraction

import pytest

from config import constants
from substitucions import assignacio


@pytest.fixture(autouse=True)
def prioritats(monkeypatch):
    monkeypatch.setattr(constants, "PRIORITATS", {"A": 3, "B": 1, "C": 9})
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"A", "B", "C"}, {"alliberat"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True, True])


def _candidats(pesos):
    tipus = {1: "B", 3: "A", 9: "C"}
    return [(f"Prof {i}", tipus[pes], tipus[pes]) for i, pes in enumerate(pesos)]


def _tria(quota, candidats, rng=None, hora="10:00"):
    escollit = assignacio.escull_candidat_amb_quota(candidats, quota, hora, rng)
    if escollit:
        quota.anota(hora, escollit[0], escollit[1])
    return escollit


def test_set_tries_des_de_buit_tenen_quota_exacta():
    candidats = _candidats([3, 3, 1])
    for llavor in range(100):
        selector = assignacio.CandidateValidator(rng=random.Random(llavor))
        recomptes = Counter(selector._escollir_amb_quota(candidats)[0] for _ in range(7))
        assert recomptes == {"Prof 0": 3, "Prof 1": 3, "Prof 2": 1}, llavor


@pytest.mark.parametrize(
    "pesos,tries,limits",
    [([3, 3, 1], 17, [(6, 8), (6, 8), (3, 3)]), ([9, 3, 3, 1], 35, [(18, 19), (6, 7), (6, 7), (3, 4)])],
)
def test_desviacio_acotada_en_els_horitzons_de_referencia(pesos, tries, limits):
    candidats = _candidats(pesos)
    for llavor in range(200):
        rng = random.Random(llavor)
        quota = assignacio.QuotaFranja()
        recomptes = Counter(_tria(quota, candidats, rng)[0] for _ in range(tries))
        for candidat, (minim, maxim) in zip(candidats, limits, strict=True):
            assert minim <= recomptes[candidat[0]] <= maxim, (llavor, recomptes)


@pytest.mark.parametrize("retorn", [False, True])
def test_entrada_o_retorn_del_candidat_de_pes_un_no_fa_allau(retorn):
    candidats = _candidats([3, 3, 1])
    for llavor in range(100):
        rng = random.Random(llavor)
        quota = assignacio.QuotaFranja()
        if retorn:
            for _ in range(35):
                _tria(quota, candidats, rng)
        for _ in range(60):
            _tria(quota, candidats[:2], rng)
        consecutives = 0
        for _ in range(60):
            triat = _tria(quota, candidats, rng)
            consecutives = consecutives + 1 if triat == candidats[2] else 0
            assert consecutives <= 2, llavor


def test_la_onzena_mes_antiga_no_compta_i_les_categories_i_hores_son_independents():
    historial = [("10:00", "Prof 0", "disponible (A)")]
    historial += [("10:00", "Prof 1", "disponible (A)")] * 10
    historial += [("10:00", "Prof 0", "alliberat (tenia classe)")] * 10
    historial += [("11:00", "Prof 0", "disponible (A)")] * 10
    quota = assignacio.QuotaFranja(historial)
    assert quota.torns(_candidats([3, 3, 1]), "10:00") == [0, Fraction(10, 3), 0]
    assert quota.torns(_candidats([3, 3, 1]), "11:00") == [Fraction(10, 3), 0, 0]
    assert quota.torns([("Prof 0", "alliberat", "")], "10:00") == [10]


def test_empats_amb_fraccions_i_pesos_actuals(monkeypatch):
    candidats = _candidats([3, 3, 1])
    quota = assignacio.QuotaFranja(
        [("10:00", "Prof 0", "disponible (A)")] * 3
        + [("10:00", "Prof 1", "disponible (A)")] * 3
        + [("10:00", "Prof 2", "disponible (B)")]
    )

    class Atzar:
        def choices(self, poblacio, *, weights, k):
            assert poblacio == candidats
            assert weights == [3, 3, 1]
            assert k == 1
            return [poblacio[-1]]

    assert _tria(quota, candidats, Atzar()) == candidats[-1]
    assert quota.torns(candidats, "10:00") == [1, 1, 2]
    monkeypatch.setattr(constants, "PRIORITATS", {"A": 6, "B": 2})
    assert quota.torns(candidats, "10:00") == [Fraction(1, 2), Fraction(1, 2), 1]


def test_una_tria_unica_tambe_entra_a_la_finestra_i_empat_sense_rng_es_estable():
    quota = assignacio.QuotaFranja()
    candidats = _candidats([3, 3, 1])
    assert _tria(quota, []) is None
    assert _tria(quota, candidats[:1]) == candidats[0]
    assert _tria(quota, candidats) == candidats[1]
    assert quota.torns(candidats, "10:00") == [Fraction(1, 3), Fraction(1, 3), 0]


def test_el_pes_actual_del_candidat_s_aplica_a_totes_les_seves_aparicions():
    quota = assignacio.QuotaFranja([("10:00", "Prof 0", "disponible (B)")] * 3)
    assert quota.torns(_candidats([3]), "10:00") == [1]


def test_una_categoria_prioritaria_amb_mes_torns_continua_guanyant(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"A"}, {"B"}])
    quota = assignacio.QuotaFranja([("10:00", "Prof 0", "disponible (A)")] * 10)
    gestor = assignacio.GestorSubstitucions(None, None, None)
    gestor.validator = assignacio.CandidateValidator(quota=quota)
    alta = ("Prof 0", "A", "A")
    baixa = ("Prof 1", "B", "B")
    assert gestor._escollir_millor_candidat_disponible({0: [alta], 1: [baixa]}, set(), "10:00") == alta


def test_l_activitat_guardada_amb_espais_identifica_la_categoria(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Activitat amb espais"}, {"A"}])
    quota = assignacio.QuotaFranja([("10:00", "Prof 0", "Activitat amb espais (detall)")] * 10)
    # La mateixa persona en una altra categoria continua tenint zero torns.
    assert quota.torns([("Prof 0", "A", "")], "10:00") == [0]
    assert quota.torns([("Prof 0", "Activitat amb espais", "")], "10:00") == [10]


def test_millores_finals_successives_anoten_nomes_les_tries_aplicables(monkeypatch):
    from types import SimpleNamespace

    from substitucions.files import FilaSubstitucio
    from substitucions.prioritat import MillorsSubstituts

    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"A", "B"}, {"C"}])
    quota = assignacio.QuotaFranja(
        [("10:00", "Prof 0", "disponible (A)"), ("10:00", "Prof 1", "disponible (A)")]
        + [("10:00", "Prof 99", "disponible (A)")] * 8
    )
    candidats = _candidats([3, 3, 1])
    disponibles = SimpleNamespace(get_tots_disponibles=lambda *args: candidats)
    dia = SimpleNamespace(files=[], nom_del_dia="Dilluns", alliberats={}, absents_per_hora={}, vigilants_per_hora={})

    class UltimEmpat:
        def choices(self, poblacio, *, weights, k):
            return [poblacio[-1]]

    motor = assignacio.GestorSubstitucions(None, None, None)
    millors = MillorsSubstituts(dia, (motor, None, disponibles, None), rng=UltimEmpat(), quota=quota)
    primera = FilaSubstitucio(hora="10:00", substitut="Prof 90", tipus_substitut="disponible (C)")
    segona = FilaSubstitucio(hora="10:00", substitut="Prof 91", tipus_substitut="disponible (C)")
    millor = millors.millor(primera)
    assert millor[:3] == candidats[2]
    millors.canvia("10:00", primera.substitut, millor[0])
    assert millors.millor(segona)[:3] == candidats[0]
    abans = quota.torns(candidats, "10:00")
    # Cap categoria superior a A: aquesta consulta no ha d'alterar la finestra.
    assert millors.millor(FilaSubstitucio(hora="10:00", substitut="Prof 0", tipus_substitut="disponible (A)")) is None
    assert quota.torns(candidats, "10:00") == abans
