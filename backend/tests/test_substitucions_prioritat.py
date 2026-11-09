"""Prioritat de la millora final de «Reassigna problemàtics»."""

from collections import defaultdict

from config import constants
from substitucions.files import FilaSubstitucio
from substitucions.prioritat import MillorsSubstituts


class DiaDeProva:
    nom_del_dia = "Dilluns"
    files = []
    alliberats = defaultdict(set)
    absents_per_hora = defaultdict(set)
    vigilants_per_hora = defaultdict(set)


class MotorDeProva:
    @staticmethod
    def _obtenir_categoria(tipus):
        return next(
            (index for index, categoria in enumerate(constants.ORDRE_PRIORITATS) if tipus in categoria),
            len(constants.ORDRE_PRIORITATS),
        )


class DisponiblesDeProva:
    def get_tots_disponibles(self, _dia, _hora, _grups_alliberats):
        return [
            ("Prof Mateix Nivell", "mateix nivell", "mateix nivell"),
            ("Prof Alliberat", "alliberat", "tenia classe"),
        ]


def test_reassignar_una_guardia_tria_l_alliberat_i_no_el_primer_que_la_millora(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}, {"mateix nivell"}, {"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True, True, True])
    gestors = (MotorDeProva(), None, DisponiblesDeProva(), None)
    millors = MillorsSubstituts(DiaDeProva(), gestors)

    millor = millors.millor(
        FilaSubstitucio(
            **{
                "hora": "09:00",
                "substitut": "Prof Guàrdia",
                "tipus_substitut": "disponible (Guàrdia)",
            }
        )
    )

    assert millor[:3] == ("Prof Alliberat", "alliberat", "tenia classe")
