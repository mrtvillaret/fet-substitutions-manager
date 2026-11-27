"""Tipus i errors propis del domini dels PDF."""

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from errors_domini import NoTrobat, NoValid
from recomptes.domain import IntervalNoValid  # noqa: F401  (també és dels PDF)


@dataclass(frozen=True)
class OpcionsPdf:
    format: str = "hores"
    mida_lletra: float | None = None
    compressio: bool = False
    mostra_comentaris: bool = True
    mostra_hores: bool = False


@contextmanager
def directori_temporal() -> Iterator[Path]:
    """Un directori nou per generar-hi un PDF (no es desa al servidor). Si la
    generació falla, s'esborra aquí mateix; si no, qui envia el PDF l'esborra
    un cop enviat (esborra_directori)."""
    directori = Path(tempfile.mkdtemp(prefix="gestor-pdf-"))
    try:
        yield directori
    except BaseException:
        esborra_directori(directori)
        raise


def esborra_directori(directori) -> None:
    shutil.rmtree(directori, ignore_errors=True)


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


class SenseVigilancies(NoTrobat):
    pass


class SenseProfessors(NoTrobat):
    pass
