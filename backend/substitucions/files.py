"""La fila de substitució llegida de persistència, independent de l'ORM."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FilaSubstitucio:
    """Instantània immutable: els canvis es desen pel repositori i es rellegeixen.

    La lectura diària normalitza els buits; la dels recomptes conserva els
    NULL, els identificadors enters i els timestamps SQL històrics.
    """

    id: str | int = ""
    data: str = ""
    hora: str = ""
    professor_absent: str = ""
    assignatura: str | None = ""
    grup: str | None = ""
    aula: str | None = ""
    substitut: str | None = ""
    tipus_substitut: str | None = ""
    tipus_absencia: str | None = ""
    comentaris: str | None = ""
    updated_at: str | None = None
    created_at: str | None = None


@dataclass(slots=True)
class PropostaSubstitucio:
    """Fila encara en preparació; el motor hi assigna i conserva candidats.

    És mutable perquè l'assignació s'aplica a la mateixa proposta dins de la
    llista. No està vinculada a l'ORM; la fila desada es rellegeix immutable.
    """

    professor_absent: str = ""
    hora: str = ""
    assignatura: str = ""
    grup: str = ""
    aula: str = ""
    substitut: str = ""
    tipus_substitut: str = ""
    tipus_absencia: str = ""
    comentaris: str = ""
    professor: str = ""
    separador: bool = False
    disponibles: list[tuple[str, str, str]] = field(default_factory=list)
    conservat: bool = False
