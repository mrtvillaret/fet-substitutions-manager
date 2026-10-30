"""Tipus i errors propis del domini dels PDF."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from errors_domini import NoTrobat, NoValid

FormatPdf = Literal["hores", "dia"]
MidesLletra = Literal[1.0, 1.2, 1.35]


@dataclass(frozen=True)
class OpcionsPdf:
    format: FormatPdf = "hores"
    mida_lletra: float | None = None
    compressio: bool = False
    mostra_comentaris: bool = True
    mostra_hores: bool = False


@dataclass(frozen=True)
class PdfGenerat:
    """Un PDF acabat de generar en un directori temporal per petició (no es
    desa al servidor): qui l'envia l'ha d'esborrar."""

    directori: Path
    nom: str | None  # None si el renderitzador no n'ha generat cap


# Errors esperats mentre es prepara un PDF o un informe (el status, a
# errors_servidor.py segons la categoria)


class FormatPdfNoValid(NoValid):
    pass


class MidaPdfNoValida(NoValid):
    pass


class IntervalNoValid(NoValid):
    pass


class SenseVigilancies(NoTrobat):
    pass


class SenseProfessors(NoTrobat):
    pass
