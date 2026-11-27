"""«No substituir» amb vigència per dates: les entrades i la regla de quines
valen cada dia, en un sol lloc (valors purs, sense BD).

Cada entrada val de `vigent_des_de` a `vigent_fins_a`, tots dos inclosos;
una data buida vol dir sense límit (les entrades d'abans de la migració 0004
valen des de sempre). Les dates es comparen amb els extrems inclosos.

L'única manera d'obtenir una llista és `VigenciaNoSubstituir.a(data)`: no
hi ha cap llista «sense data» (ho vigila tests/test_no_substituir_amb_data.py).
"""

from dataclasses import dataclass
from datetime import date


def _comprova_data(data: date) -> None:
    if type(data) is not date:
        raise ValueError(f"Cal una data ISO (AAAA-MM-DD) per saber què és a «No substituir»: {data!r}")


@dataclass(frozen=True)
class EntradaNoSubstituir:
    id: int
    assignatura: str
    vigent_des_de: date | None = None
    vigent_fins_a: date | None = None

    def vigent_a(self, data: date) -> bool:
        return (self.vigent_des_de is None or self.vigent_des_de <= data) and (
            self.vigent_fins_a is None or data <= self.vigent_fins_a
        )

    def acaba_abans_de(self, data: date) -> bool:
        """Si ja no val a `data` ni després (ha acabat abans)."""
        return self.vigent_fins_a is not None and self.vigent_fins_a < data


@dataclass(frozen=True)
class VigenciaNoSubstituir:
    """Totes les entrades d'un centre. Sense iterar ni `in`: la llista
    depèn sempre d'una data."""

    entrades: tuple[EntradaNoSubstituir, ...] = ()

    def a(self, data: date) -> frozenset[str]:
        """Les activitats que són a «No substituir» a `data`."""
        _comprova_data(data)
        return frozenset(e.assignatura for e in self.entrades if e.vigent_a(data))
