"""Entrada del recàlcul al motor, que encara consumeix dates textuals."""

from dataclasses import dataclass

from pydantic import RootModel

from horari.domain import Dia
from planificador.documents import document_iso
from planificador.motor import recalcul
from planificador.schemas import HorariRecalcularRequest


@dataclass(frozen=True)
class _PeticioMotor:
    horari: RootModel[dict]
    data_referencia: str | None
    selected_dates: list[str] | None
    desa: bool


def recalcula(payload: HorariRecalcularRequest, institucio: str, planificacio: Dia) -> dict:
    peticio = _PeticioMotor(
        horari=RootModel[dict](payload.horari.model_dump(mode="json", exclude_unset=True, by_alias=True)),
        data_referencia=document_iso(payload.data_referencia),
        selected_dates=document_iso(payload.selected_dates),
        desa=payload.desa,
    )
    return recalcul.recalcula(peticio, institucio, planificacio)
