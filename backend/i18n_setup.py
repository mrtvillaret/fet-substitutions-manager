import builtins
import gettext
import os
import logging
from contextvars import ContextVar

# Dominis de traducció modular
DOMAINS = ["messages", "gui", "core", "export", "utils", "manual"]

# Camí al directori de traduccions
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locales")

# Idioma per defecte (fora d'una petició: arrencada, scripts)
IDIOMA_PER_DEFECTE = 'ca'

# Idioma de la petició en curs. Un mateix backend pot servir institucions amb
# idiomes diferents: si l'idioma fos global, dues peticions simultànies el
# trepitjarien (un PDF podria sortir en l'idioma de l'altre centre). Una
# ContextVar té un valor propi per a cada petició.
_idioma_peticio: ContextVar = ContextVar("idioma_peticio", default=None)

# Traduccions ja carregades, per idioma (es carreguen un sol cop)
_traductors: dict = {}


def _carrega(language: str):
    """Funció gettext per a un idioma, combinant tots els dominis."""
    if language in _traductors:
        return _traductors[language]
    traductor = gettext.gettext
    try:
        translations = []
        for domain in DOMAINS:
            try:
                translations.append(gettext.translation(
                    domain, localedir=LOCALE_DIR, languages=[language], fallback=True
                ))
            except FileNotFoundError:
                logging.warning(f"No s'ha trobat el domini '{domain}' per a l'idioma '{language}'")
        if translations:
            combined_translation = translations[0]
            for trans in translations[1:]:
                combined_translation.add_fallback(trans)
            traductor = combined_translation.gettext
            logging.info(f"Traduccions per a l'idioma '{language}' carregades des de {LOCALE_DIR}.")
        else:
            logging.warning(f"No s'ha pogut carregar cap traducció per a '{language}'. S'utilitzarà el text original.")
    except Exception as e:
        logging.error(f"S'ha produït un error en carregar les traduccions: {e}")
    _traductors[language] = traductor
    return traductor


def carrega_idioma(language: str) -> None:
    """Deixa carregades les traduccions d'un idioma (sense canviar l'actiu)."""
    _carrega(language or IDIOMA_PER_DEFECTE)


def idioma_actual() -> str:
    return _idioma_peticio.get() or IDIOMA_PER_DEFECTE


def setup_translation(language: str = 'ca'):
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


# Alguns mòduls fan servir `_` directament (sense importar-la): abans
# gettext.install() la desava a builtins en cada canvi d'idioma. Ara és
# sempre `translate`, que tria l'idioma de la petició.
_ = translate
builtins._ = translate


def __getattr__(nom):
    # Compatibilitat: i18n_setup.CURRENT_LANGUAGE és l'idioma de la petició.
    if nom == "CURRENT_LANGUAGE":
        return idioma_actual()
    raise AttributeError(nom)
