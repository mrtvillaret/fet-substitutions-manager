"""
Si per a un substitut ja assignat hi ha un professor disponible d'una
categoria de més prioritat (p. ex. un alliberat en lloc d'una guàrdia). Ho
fan servir els avisos del PDF i «Reassignar problemàtics».
"""

from collections import defaultdict

from config import constants
from substitucions.assignacio import candidats_de_maxima_prioritat, desempata_candidats
from substitucions.domain import DiaEscolar


def tipus_real(tipus_substitut: str) -> str:
    """El tipus desat a la fila («disponible (Guàrdia)», «alliberat (tenia…)»)
    → el tipus de prioritat («Guàrdia», «alliberat»)."""
    if tipus_substitut.startswith("disponible (") and tipus_substitut.endswith(")"):
        return tipus_substitut[12:-1]
    if tipus_substitut.startswith("alliberat"):
        return "alliberat"
    return tipus_substitut.split(" ")[0] if tipus_substitut else ""


def text_tipus_substitut(tipus: str, detall: str) -> str:
    """El text que es desa a la fila per a un substitut de `tipus`."""
    if not tipus:
        return ""
    if tipus == detall and tipus != "alliberat":
        return f"disponible ({tipus})"
    return f"{tipus} ({detall})"


class MillorsSubstituts:
    def __init__(self, dia: DiaEscolar, gestors, rng=None):
        """`gestors`: el que retorna helpers.get_gestors per a aquell dia."""
        self.dia = dia
        self.motor, _, self.alliberats, _ = gestors
        self.rng = rng
        self.ocupats_per_hora = defaultdict(set)
        for sub in dia.files:
            hora = (sub.get("hora") or "").strip()
            substitut = (sub.get("substitut") or "").strip()
            if hora and substitut:
                self.ocupats_per_hora[hora].add(substitut)

    def millor(self, sub: dict):
        """Millor candidat d'una categoria superior a la de l'actual.

        Retorna (professor, tipus, detall, tipus_actual) o None. No compta qui
        és absent, vigila o ja substitueix a aquella hora.
        """
        hora = (sub.get("hora") or "").strip()
        actual = (sub.get("substitut") or "").strip()
        if not hora or not actual:
            return None
        disponibles = self.alliberats.get_tots_disponibles(self.dia.dia, hora, set(self.dia.alliberats.get(hora, [])))
        tipus_per_professor = {prof: tipus for prof, tipus, _ in disponibles}
        tipus_actual = tipus_per_professor.get(actual, tipus_real((sub.get("tipus_substitut") or "").strip()))
        categoria_actual = self.motor._obtenir_categoria(tipus_actual)

        no_poden = (
            self.dia.absents_per_hora.get(hora, set())
            | self.dia.vigilants_per_hora.get(hora, set())
            | self.ocupats_per_hora.get(hora, set())
        )
        candidats_per_categoria = defaultdict(list)
        for prof, tipus, detall in disponibles:
            categoria = self.motor._obtenir_categoria(tipus)
            if categoria < len(constants.ORDRE_PRIORITATS):
                candidats_per_categoria[categoria].append((prof, tipus, detall))

        candidats = candidats_de_maxima_prioritat(
            candidats_per_categoria,
            constants.CATEGORIES_ACTIVES,
            no_poden,
        )
        # «Reassigna» hi injecta el mateix atzar que la generació. Els avisos
        # del PDF no assignen ningú i conserven un representant estable.
        millor = (
            desempata_candidats(candidats, self.rng) if self.rng is not None else (candidats[0] if candidats else None)
        )
        if millor and self.motor._obtenir_categoria(millor[1]) < categoria_actual:
            return *millor, tipus_actual
        return None

    def canvia(self, hora: str, abans: str, despres: str) -> None:
        """Anota que a `hora` el substitut `abans` ha passat a ser `despres`."""
        self.ocupats_per_hora[hora].discard(abans)
        self.ocupats_per_hora[hora].add(despres)
