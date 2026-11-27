import gettext
import os
from contextvars import ContextVar

# Un sol catàleg per llengua: locales/<llengua>/LC_MESSAGES/messages.mo
DOMINI = "messages"

# Camí al directori de traduccions
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locales")

# Idioma per defecte (fora d'una petició: arrencada, scripts)
IDIOMA_PER_DEFECTE = "ca"

# Idioma de la petició en curs. Un mateix backend pot servir institucions amb
# idiomes diferents: si l'idioma fos global, dues peticions simultànies el
# trepitjarien (un PDF podria sortir en l'idioma de l'altre centre). Una
# ContextVar té un valor propi per a cada petició.
_idioma_peticio: ContextVar = ContextVar("idioma_peticio", default=None)

# Traduccions ja carregades, per idioma (es carreguen un sol cop)
_traductors: dict = {}


def _carrega(language: str):
    """Funció gettext per a un idioma (sense catàleg, el text original)."""
    if language not in _traductors:
        _traductors[language] = gettext.translation(
            DOMINI, localedir=LOCALE_DIR, languages=[language], fallback=True
        ).gettext
    return _traductors[language]


def carrega_idioma(language: str) -> None:
    """Deixa carregades les traduccions d'un idioma (sense canviar l'actiu)."""
    _carrega(language or IDIOMA_PER_DEFECTE)


def idioma_actual() -> str:
    return _idioma_peticio.get() or IDIOMA_PER_DEFECTE


def setup_translation(language: str = "ca"):
    """Fixa l'idioma de la petició en curs (o del context on es cridi) i en
    carrega les traduccions si cal.

    Args:
        language (str): El codi de l'idioma (p.ex., 'en', 'es', 'ca').
    """
    language = language or IDIOMA_PER_DEFECTE
    _carrega(language)
    _idioma_peticio.set(language)


def translate(text: str) -> str:
    """Tradueix a l'idioma de la petició en curs."""
    return _carrega(idioma_actual())(text)


# Import explícit: la funció tria l'idioma de la petició.
_ = translate
