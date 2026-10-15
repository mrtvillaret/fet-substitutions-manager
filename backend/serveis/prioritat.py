"""
Si per a un substitut ja assignat hi ha un professor disponible d'una
categoria de més prioritat (p. ex. un alliberat en lloc d'una guàrdia). Ho
fan servir els avisos del PDF i «Reassignar problemàtics».
"""
from collections import defaultdict

from serveis.dia_escolar import DiaEscolar


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
    def __init__(self, dia: DiaEscolar, gestors):
        """`gestors`: el que retorna helpers.get_gestors per a aquell dia."""
        self.dia = dia
        self.motor, _, self.alliberats, _ = gestors
        self.ocupats_per_hora = defaultdict(set)
        for sub in dia.files:
            hora = (sub.get("hora") or "").strip()
            substitut = (sub.get("substitut") or "").strip()
            if hora and substitut:
                self.ocupats_per_hora[hora].add(substitut)

    def millor(self, sub: dict):
        """(professor, tipus, detall, tipus_actual) del primer disponible d'una
        categoria de més prioritat que la del substitut de `sub`, o None. No
        compta qui és absent, vigila o ja substitueix a aquella hora."""
        hora = (sub.get("hora") or "").strip()
        actual = (sub.get("substitut") or "").strip()
        if not hora or not actual:
            return None
        disponibles = self.alliberats.get_tots_disponibles(self.dia.dia, hora, set(self.dia.alliberats.get(hora, [])))
        tipus_per_professor = {prof: tipus for prof, tipus, _ in disponibles}
        tipus_actual = tipus_per_professor.get(actual, tipus_real((sub.get("tipus_substitut") or "").strip()))
        categoria_actual = self.motor._obtenir_categoria(tipus_actual)

        no_poden = (self.dia.absents_per_hora.get(hora, set()) | self.dia.vigilants_per_hora.get(hora, set())
                    | self.ocupats_per_hora.get(hora, set()))
        for prof, tipus, detall in disponibles:
            if prof not in no_poden and self.motor._obtenir_categoria(tipus) < categoria_actual:
                return prof, tipus, detall, tipus_actual
        return None

    def canvia(self, hora: str, abans: str, despres: str) -> None:
        """Anota que a `hora` el substitut `abans` ha passat a ser `despres`."""
        self.ocupats_per_hora[hora].discard(abans)
        self.ocupats_per_hora[hora].add(despres)
