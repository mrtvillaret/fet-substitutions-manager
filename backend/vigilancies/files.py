"""La fila de vigilància llegida de persistència, independent de l'ORM."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FilaVigilancia:
    """Instantània immutable; l'ordre i les assignacions es desen a l'ORM.

    L’id és el de BD en text, també per conservar els empats del motor.
    La lectura diària normalitza vigilant i comentaris. La projecció dels
    recomptes conserva el vigilant NULL i afegeix la data com a text ISO.
    """

    id: str | None = None
    hora: str = ""
    tipus: str = ""
    grups: str = ""
    aula: str = ""
    vigilant: str | None = ""
    comentaris: str = ""
    nivell: str = ""
    ordre: int | None = None
    updated_at: str | None = None
    data: str = ""
