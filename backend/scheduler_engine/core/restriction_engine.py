"""
Motor únic de validació de restriccions dures.

Façana sobre les funcions primitives de constraints.py.
Tots els motors de generació (v2-greedy, v2-backtrack, v3-SA) han d'usar
aquesta classe per garantir comportament consistent i detectar violacions
dures de manera uniforme.

NO reimplementa lògica: delega sempre a constraints.py.
"""

import re as _re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from scheduler_engine.core.constraints import (
    viola_restriccio_dia_hora_fixos,
    viola_restriccio_dura,
    viola_combinacions_permeses,
    viola_limit_dies_professor_obligatori,
    viola_preferencia_dia_obligatoria,
)
from scheduler_engine.defaults import ETIQUETES_RESTRICCIONS

_ISO_RE = _re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _is_iso(s: str) -> bool:
    return bool(_ISO_RE.match(s)) if s else False


@dataclass
class ViolationResult:
    restriction: str   # Clau interna: "no_mateix_dia", "dia_hora_fix", etc.
    label: str         # Etiqueta llegible: "Dies distints", "Dia/hora fixat", etc.
    is_hard: bool = True
    detail: str = ""   # Descripció específica de la violació


class RestrictionEngine:
    """
    Motor únic de restriccions dures per al generador d'horaris.

    Ús als motors:
        engine = RestrictionEngine(restriccions, nivells_actius)
        violation = engine.check_hard(sessio, dia, hora, prefix,
                                      sessions_dia, sessions_slot,
                                      dia_sessions=dia_sessions)
        if violation:
            # bloquejar el slot
    """

    def __init__(self, restriccions: dict, nivells_actius: list):
        self.restriccions = restriccions
        self.nivells_actius = list(nivells_actius or [])

        # Pre-carregar professors amb horari estricte
        dures = restriccions.get('restriccions_dures', {})
        pe = dures.get('professors_horari_estricte', [])
        if isinstance(pe, dict):
            self.professors_estrictes: List[str] = [
                k for k in pe.keys() if not k.startswith('_')
            ]
        else:
            self.professors_estrictes = list(pe or [])

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def check_hard(
        self,
        sessio: Dict,
        dia: str,
        hora: str,
        prefix: str,
        sessions_dia: List[Dict],
        sessions_slot: List[Dict],
        dia_sessions: Optional[Dict] = None,
        analisi: Optional[Dict] = None,
    ) -> Optional[ViolationResult]:
        """
        Retorna la primera restricció dura violada, o None si el slot és vàlid.

        Paràmetres:
          sessio        — sessió a col·locar (dict amb 'nom', 'curs', 'examens', ...)
          dia           — nom del dia, p.ex. "Dilluns"
          hora          — hora d'inici, p.ex. "09:00"
          prefix        — prefix del slot: data ISO "2026-05-06" o dia_nom si no n'hi ha
          sessions_dia  — sessions ja col·locades al mateix dia ISO (per no_mateix_dia)
          sessions_slot — sessions ja al slot (per combinacions_permeses)
          dia_sessions  — dict {dia_nom: [sessions]} de totes les assignades
                          (per viola_limit_dies i viola_preferencia; pot ser None)
          analisi       — resultat de analitzar_disponibilitat_sessio
                          (per professors_estrictes; pot ser None)
        """
        data_iso = prefix if _is_iso(prefix) else ""

        # 1. Dia/hora fix, slots prohibits, alliberaments
        if viola_restriccio_dia_hora_fixos(
            sessio, dia, hora, self.restriccions, self.nivells_actius, data_iso
        ):
            return ViolationResult(
                restriction="dia_hora_fix",
                label=ETIQUETES_RESTRICCIONS.get("dia_hora_fix", "Dia/hora fixat"),
                detail=f"{sessio.get('nom', '')} — slot {dia} {hora} no permès",
            )

        # 2. no_mateix_dia (pes >= 100)
        if viola_restriccio_dura(sessio, sessions_dia, self.restriccions):
            return ViolationResult(
                restriction="no_mateix_dia",
                label=ETIQUETES_RESTRICCIONS.get("no_mateix_dia", "Dies distints"),
                detail=f"{sessio.get('nom', '')} — conflicte amb sessió al dia {prefix or dia}",
            )

        # 3. combinacions_permeses
        if sessions_slot and viola_combinacions_permeses(
            sessio, sessions_slot, self.restriccions
        ):
            return ViolationResult(
                restriction="combinacions_permeses",
                label=ETIQUETES_RESTRICCIONS.get("combinacions_permeses", "Combinació no permesa"),
                detail=f"{sessio.get('nom', '')} — combinació no permesa al slot {dia} {hora}",
            )

        # 4. Límit dies professor (pes >= 100)
        if dia_sessions is not None and viola_limit_dies_professor_obligatori(
            sessio, dia, dia_sessions, self.restriccions
        ):
            return ViolationResult(
                restriction="limit_dies_professor",
                label=ETIQUETES_RESTRICCIONS.get("limit_dies_professor", "Límit exàmens professor"),
                detail=f"{sessio.get('nom', '')} — professor supera límit el {dia}",
            )

        # 5. Preferència de dia obligatòria (pes >= 100)
        if dia_sessions is not None and viola_preferencia_dia_obligatoria(
            sessio, dia, dia_sessions, self.restriccions
        ):
            return ViolationResult(
                restriction="preferencia_dia",
                label=ETIQUETES_RESTRICCIONS.get("preferencia_dia", "Preferència de dia"),
                detail=f"{sessio.get('nom', '')} — viola preferència de dia obligatòria el {dia}",
            )

        # 6. Professors estrictes (requereix analisi pre-computada)
        if analisi and self.professors_estrictes:
            estrictes_afectats: Set[str] = (
                {i['professor'] for i in analisi.get('abans_jornada', [])} |
                {i['professor'] for i in analisi.get('despres_jornada', [])} |
                {i['professor'] for i in analisi.get('no_treballa_dia', [])}
            ) & set(self.professors_estrictes)
            if estrictes_afectats:
                return ViolationResult(
                    restriction="professors_estrictes",
                    label=ETIQUETES_RESTRICCIONS.get("professors_estrictes", "Horari estricte professor"),
                    detail=f"Professors {', '.join(sorted(estrictes_afectats))} amb horari estricte",
                )

        return None

    def check_all(
        self,
        sessio: Dict,
        dia: str,
        hora: str,
        prefix: str,
        sessions_dia: List[Dict],
        sessions_slot: List[Dict],
        dia_sessions: Optional[Dict] = None,
        analisi: Optional[Dict] = None,
    ) -> List[ViolationResult]:
        """
        Retorna totes les restriccions violades (per diagnòstic).
        A diferència de check_hard(), no s'atura al primer conflicte.
        """
        data_iso = prefix if _is_iso(prefix) else ""
        violations: List[ViolationResult] = []

        if viola_restriccio_dia_hora_fixos(
            sessio, dia, hora, self.restriccions, self.nivells_actius, data_iso
        ):
            violations.append(ViolationResult(
                restriction="dia_hora_fix",
                label=ETIQUETES_RESTRICCIONS.get("dia_hora_fix", "Dia/hora fixat"),
                detail=f"{sessio.get('nom', '')} — slot {dia} {hora} no permès",
            ))

        if viola_restriccio_dura(sessio, sessions_dia, self.restriccions):
            violations.append(ViolationResult(
                restriction="no_mateix_dia",
                label=ETIQUETES_RESTRICCIONS.get("no_mateix_dia", "Dies distints"),
                detail=f"{sessio.get('nom', '')} — conflicte amb sessió al dia {prefix or dia}",
            ))

        if sessions_slot and viola_combinacions_permeses(
            sessio, sessions_slot, self.restriccions
        ):
            violations.append(ViolationResult(
                restriction="combinacions_permeses",
                label=ETIQUETES_RESTRICCIONS.get("combinacions_permeses", "Combinació no permesa"),
                detail=f"{sessio.get('nom', '')} — combinació no permesa al slot {dia} {hora}",
            ))

        if dia_sessions is not None and viola_limit_dies_professor_obligatori(
            sessio, dia, dia_sessions, self.restriccions
        ):
            violations.append(ViolationResult(
                restriction="limit_dies_professor",
                label=ETIQUETES_RESTRICCIONS.get("limit_dies_professor", "Límit exàmens professor"),
                detail=f"{sessio.get('nom', '')} — professor supera límit el {dia}",
            ))

        if dia_sessions is not None and viola_preferencia_dia_obligatoria(
            sessio, dia, dia_sessions, self.restriccions
        ):
            violations.append(ViolationResult(
                restriction="preferencia_dia",
                label=ETIQUETES_RESTRICCIONS.get("preferencia_dia", "Preferència de dia"),
                detail=f"{sessio.get('nom', '')} — viola preferència de dia obligatòria el {dia}",
            ))

        if analisi and self.professors_estrictes:
            estrictes_afectats: Set[str] = (
                {i['professor'] for i in analisi.get('abans_jornada', [])} |
                {i['professor'] for i in analisi.get('despres_jornada', [])} |
                {i['professor'] for i in analisi.get('no_treballa_dia', [])}
            ) & set(self.professors_estrictes)
            if estrictes_afectats:
                violations.append(ViolationResult(
                    restriction="professors_estrictes",
                    label=ETIQUETES_RESTRICCIONS.get("professors_estrictes", "Horari estricte professor"),
                    detail=f"Professors {', '.join(sorted(estrictes_afectats))} amb horari estricte",
                ))

        return violations
