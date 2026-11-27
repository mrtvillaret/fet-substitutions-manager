"""La fila de substitució llegida de persistència, independent de l'ORM."""

from dataclasses import dataclass, field
from datetime import date

from ordre_curs import clau_curs, natural


def clau_fila(professor_absent: str, hora: str, assignatura: str, grup: str) -> str:
    """Clau d'una fila per conservar-la entre generacions (sense el tipus d'absència)."""
    return f"{professor_absent}|{hora}|{assignatura}|{grup}"


@dataclass(frozen=True, slots=True)
class FilaSubstitucio:
    """Instantània immutable: els canvis es desen pel repositori i es rellegeixen.

    La lectura diària normalitza els buits; la dels recomptes conserva els
    NULL, els identificadors enters i els timestamps SQL històrics.
    """

    id: str | int = ""
    data: date | None = None
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


def fila_de_proposta(data: date, proposta: PropostaSubstitucio) -> dict:
    """Les dades per desar una proposta tal com és."""
    return {
        "data": data,
        "hora": proposta.hora,
        "professor_absent": proposta.professor_absent,
        "assignatura": proposta.assignatura,
        "grup": proposta.grup,
        "aula": proposta.aula,
        "substitut": proposta.substitut,
        "tipus_substitut": proposta.tipus_substitut,
        "tipus_absencia": proposta.tipus_absencia,
        "comentaris": proposta.comentaris,
    }


def fila_sense_substitut(data: date, hora: str, professor: str, activitat: dict | None, tipus_absencia: str) -> dict:
    """Les dades per desar una hora d'absència sense substitut, amb la classe
    de l'horari (`activitat`, o res si no n'hi ha)."""
    activitat = activitat or {}
    return {
        "data": data,
        "hora": hora,
        "professor_absent": professor,
        "assignatura": activitat.get("assignatura", ""),
        "grup": activitat.get("grup", ""),
        "aula": activitat.get("aula", ""),
        "substitut": "",
        "tipus_substitut": "",
        "tipus_absencia": tipus_absencia,
        "comentaris": "",
    }


# L'ordre per mostrar-les (la pantalla i el PDF): per hores i, dins de cada
# hora, segons el criteri triat a la pantalla (ORDRES): per curs
# (ordre_curs.clau_curs: etapa, número, grup) i professor absent, o al
# revés. Les files d'un mateix professor i grup, juntes (absència,
# cobertura de vigilància...). Cada encadenada, just a sota de la
# substitució que la provoca (la del seu professor com a substitut), s'ordeni
# com s'ordeni: s'entén millor. No s'aplica a SubstitucioRepository.get_by_date:
# el motor reparteix els substituts en l'ordre en què li arriben.
_ORDRE_TIPUS = {"VIGILANCIA_ABSENT": 1, "VIGILANCIA": 2}
ORDRES = ("curs", "professor")


def ordena_per_mostrar(files: list, hores: list, ordre: str = "curs") -> list:
    """Les files en l'ordre per mostrar-les. `hores`: l'ordre de l'horari
    (una hora que no hi és, al final). `ordre`: un d'ORDRES."""
    if ordre not in ORDRES:
        raise ValueError(f"Ordre desconegut: {ordre}")

    def tipus(fila):
        return (fila.tipus_absencia or "").upper()

    def clau(fila):
        curs = clau_curs(fila.grup)
        professor = natural(fila.professor_absent)
        primer, segon = (curs, professor) if ordre == "curs" else (professor, curs)
        return (
            primer,
            segon,
            _ORDRE_TIPUS.get(tipus(fila), 0),
            natural(fila.assignatura),
        )

    posicio = {hora: i for i, hora in enumerate(hores)}
    per_hora: dict[str, list] = {}
    for fila in files:
        per_hora.setdefault(fila.hora, []).append(fila)

    ordenades = []
    for hora in sorted(per_hora, key=lambda h: (posicio.get(h, len(posicio)), h or "")):
        files_hora = per_hora[hora]
        encadenades = sorted(
            (f for f in files_hora if tipus(f) == "ENCADENADA"),
            key=lambda f: natural(f.professor_absent),
        )
        pendents = list(encadenades)
        for fila in sorted((f for f in files_hora if tipus(f) != "ENCADENADA"), key=clau):
            ordenades.append(fila)
            substitut = (fila.substitut or "").strip()
            for encadenada in [e for e in pendents if substitut and e.professor_absent == substitut]:
                ordenades.append(encadenada)
                pendents.remove(encadenada)
        # Sense la substitució que la provoca (no hauria de passar): al final de l'hora
        ordenades.extend(pendents)
    return ordenades
