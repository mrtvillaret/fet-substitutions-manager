"""Files del domini amb les metadades de presentació de l'interval PDF."""

from dataclasses import dataclass

from substitucions.files import FilaSubstitucio
from vigilancies.files import FilaVigilancia


@dataclass(frozen=True, slots=True)
class SubstitucioPdf(FilaSubstitucio):
    dia_interval: str = ""


@dataclass(frozen=True, slots=True)
class VigilanciaPdf(FilaVigilancia):
    dia_interval: str = "Dia desconegut"
    dia_buit: bool = False
