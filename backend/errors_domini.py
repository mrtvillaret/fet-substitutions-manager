"""
Errors del domini: el que llancen els serveis quan una regla no es compleix.

Els serveis no saben res d'HTTP: diuen de quina mena és l'error (no
autenticat, no trobat, no permès, no vàlid, conflicte). Quin status li
correspon i com es respon ho decideix errors_servidor.py.

Cada error porta el missatge per a l'usuari i un codi estable (p. ex.
"contrasenya_curta"), amb uns paràmetres opcionals ({"minim": 8}): el
frontend tradueix el missatge a partir del codi (`errors.<codi>`). Un codi
diu sempre el mateix text, i els paràmetres porten els valors que el text
interpola (ho vigila tests/test_codis_errors.py).
"""


class ErrorDeDomini(Exception):
    """Base comuna. No es llança directament: cal triar-ne la categoria."""

    # Si la resposta HTTP porta el codi i els paràmetres a més del missatge
    amb_codi_a_la_resposta = True

    def __init__(self, missatge: str, *, codi: str, params: dict | None = None):
        if type(self) is ErrorDeDomini:
            raise TypeError("Cal llançar una categoria: NoAutenticat, NoTrobat, NoPermes, NoValid o Conflicte")
        super().__init__(missatge)
        self.missatge = missatge
        self.codi = codi
        self.params = params or {}


class NoAutenticat(ErrorDeDomini):
    """Qui ho demana no ha entrat, o la seva sessió ja no val."""

    # La resposta només porta el `detail`: la web no el tradueix (diu per què
    # cal tornar a entrar amb els seus textos, app.login.*).
    amb_codi_a_la_resposta = False


class NoTrobat(ErrorDeDomini):
    """El que es demana no existeix."""


class NoPermes(ErrorDeDomini):
    """Existeix, però qui ho demana no hi té dret."""


class NoValid(ErrorDeDomini):
    """Les dades no compleixen una regla."""


class Conflicte(ErrorDeDomini):
    """Xoca amb el que ja hi ha (un nom repetit...)."""


class MissingXmlError(NoValid):
    """No hi ha cap XML d'horari disponible per al centre."""

    def __init__(self, institucio: str, xml_path: str | None):
        super().__init__(
            f"Cal pujar un fitxer XML d'horari per a la institució {institucio}.",
            codi="xml_missing",
            params={"institucio": institucio},
        )
        self.institucio = institucio
        self.xml_path = xml_path
