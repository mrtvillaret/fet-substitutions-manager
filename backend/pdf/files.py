"""Files del domini amb les metadades de presentació de l'interval PDF."""

from dataclasses import dataclass

from substitucions.files import FilaSubstitucio
from vigilancies.files import FilaVigilancia


@dataclass(frozen=True, slots=True)
class SubstitucioPdf(FilaSubstitucio):
    dia_interval: str = ""
    data_iso: str = ""


@dataclass(frozen=True, slots=True)
class VigilanciaPdf(FilaVigilancia):
    dia_interval: str = "Dia desconegut"
    data_iso: str = ""
    dia_buit: bool = False
