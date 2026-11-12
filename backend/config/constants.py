"""
Constants globals del sistema
"""

import logging
from collections.abc import Mapping as _Mapping
from collections.abc import Sequence as _Sequence
from collections.abc import Set as _Set
from pathlib import Path

from config.context import institucio_peticio

BASE_DIR = Path(__file__).resolve().parents[1]

try:
    from i18n_setup import translate as _
except ImportError:

    def _(text):
        return text

# ── Prioritats i activitats que no se substitueixen, per institució ──
#
# Cada institució té les seves (es carreguen de la seva BD amb
# prioritats.memoria.carrega_prioritats). Els noms públics de sota
# (PRIORITATS, ORDRE_PRIORITATS, ...) són vistes: objectes fixos que, cada cop que es
# consulten, mostren les dades de la institució de la petició en curs
# (config.context). Així:
#   - dues peticions simultànies de centres diferents no es trepitgen;
#   - un mòdul que les importa en carregar-se ("from config.constants import
#     PRIORITATS") sempre veu les actuals, perquè l'objecte no canvia mai.
# Fora d'una petició (arrencada, tests unitaris) la institució és None.

log = logging.getLogger(__name__)

_PRIORITATS_PER_INSTITUCIO: dict = {}


def _dades_actuals() -> dict:

    return _PRIORITATS_PER_INSTITUCIO.get(institucio_peticio(), {})


def desa_prioritats(institucio, **valors) -> None:
    """Desa les prioritats d'una institució (claus: PRIORITATS,
    ORDRE_PRIORITATS, CATEGORIES_ACTIVES i NO_SUBSTITUIR, la vigència de
    «No substituir», que només es llegeix per data: prioritats.memoria)."""
    _PRIORITATS_PER_INSTITUCIO[institucio] = valors


def dada_actual(nom, buit):
    """Una dada desada de la institució de la petició en curs."""
    return _dades_actuals().get(nom, buit)


def te_prioritats(institucio) -> bool:
    return institucio in _PRIORITATS_PER_INSTITUCIO


class _Vista:
    def __init__(self, nom, buit):
        self._nom, self._buit = nom, buit

    def _valor(self):
        return _dades_actuals().get(self._nom, self._buit)

    def __repr__(self):
        return repr(self._valor())

    __hash__ = None


class _VistaDict(_Vista, _Mapping):
    def __getitem__(self, clau):
        return self._valor()[clau]

    def __iter__(self):
        return iter(self._valor())

    def __len__(self):
        return len(self._valor())


class _VistaSet(_Vista, _Set):
    def __contains__(self, element):
        return element in self._valor()

    def __iter__(self):
        return iter(self._valor())

    def __len__(self):
        return len(self._valor())


class _VistaLlista(_Vista, _Sequence):
    def __getitem__(self, index):
        return self._valor()[index]

    def __len__(self):
        return len(self._valor())

    def __eq__(self, altre):
        if isinstance(altre, (list, tuple, _Sequence)) and not isinstance(altre, str):
            return list(self._valor()) == list(altre)
        return NotImplemented


PRIORITATS = _VistaDict("PRIORITATS", {})
ORDRE_PRIORITATS = _VistaLlista("ORDRE_PRIORITATS", ())
CATEGORIES_ACTIVES = _VistaLlista("CATEGORIES_ACTIVES", ())

# EMOJI MAPPING FOR PROFESSOR TYPES
PROFESSOR_TYPE_EMOJIS = {
    # Categoria 0 - Prioritat màxima
    "reforç": "⭐",
    "alliberat": "✅",
    # Categoria 1 - Guàrdies
    "guàrdia": "🛡️",
    # Categoria 2 - Activitats específiques
    "web": "💻",
    "informàtica": "🖥️",
    "correcció": "✏️",
    "bat dual": "🎓",
    # Categoria 4
    "cd": "👨‍💼",  # Cap de departament
    # Categoria 5
    "alumnes": "👥",
    # Categoria 6
    "orientació": "🧭",
    # Categoria 7
    "gp": "🌳",  # Guàrdia pati
    # Altres possibles
    "disponible": "🟢",
    "lliure": "⚪",
}


def get_professor_emoji(tipus: str) -> str:
    """Retorna emoji per tipus de professor (consolidated helper)"""
    tipus_lower = tipus.lower()
    for key, emoji in PROFESSOR_TYPE_EMOJIS.items():
        if key in tipus_lower:
            return emoji
    return "🟢"  # Emoji per defecte per disponibles genèrics
