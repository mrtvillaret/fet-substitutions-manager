"""
Gestió d'absències de professors
"""

import logging

from dates import parse_date
from i18n_setup import _
from substitucions.files import PropostaSubstitucio


class GestorAbsencies:
    """Gestiona les absències dels professors. `no_substituir`: la llista
    vigent el dia dels gestors (substitucions.context.get_gestors)."""

    def __init__(self, gestor_horari, *, no_substituir: frozenset[str]):
        self.horari = gestor_horari
        self.no_substituir = no_substituir

    def get_substitucions_necessaries(
        self,
        dia: str,
        absents: dict[str, list[str]],
        absents_tipus: dict[str, str] = None,
    ) -> list[PropostaSubstitucio]:
        """
        Calcula quines substitucions calen segons les absències
        Args:
            dia: Dia de la setmana (nom de l'XML) o format ISO (YYYY-MM-DD)
            absents: {professor: [hores]}
            absents_tipus: {professor: tipus_absencia} - 'SERVEI' o 'ABSENCIA'
        Returns: [{professor, hora, assignatura, grup, tipus_absencia}, ...]
        """

        logger = logging.getLogger(__name__)
        logger.debug(f"🟢 get_substitucions_necessaries() START: dia='{dia}', absents={len(absents)}")

        # Assegura que dia està en format nom dia XML, no ISO
        if isinstance(dia, str) and len(dia) == 10 and "-" in dia:
            # Rebut format ISO (2025-08-11), converteix a nom dia XML

            weekday_idx = parse_date(dia).weekday()
            dia = self.horari.get_dia_name(weekday_idx)
            logger.info(_("   🔄 Convertit dia ISO a nom XML: '{}'").format(dia))

        substitucions = []
        absents_tipus = absents_tipus or {}

        for professor, hores in absents.items():
            # Obté el tipus d'absència per aquest professor
            tipus_professor = absents_tipus.get(professor, "ABSENCIA")
            logger.debug(f"      Professor '{professor}' absent a {len(hores)} hores: {hores}")

            for hora in hores:
                activitat = self.horari.get_activitat(dia, hora, professor)
                logger.debug(f"         get_activitat('{dia}', '{hora}', '{professor}') = {activitat}")

                if not activitat:
                    continue

                # Comprova si necessita substitució
                if self._necessita_substitucio(activitat):
                    assignatura = activitat.get("assignatura", "")
                    grup = activitat.get("grup", "")
                    aula = activitat.get("aula", "")

                    # Determina tipus_absencia: el tipus del professor té prioritat absoluta
                    tipus_absencia = tipus_professor  # 'SERVEI' o 'ABSENCIA' segons el checkbox

                    sub = PropostaSubstitucio(
                        professor=professor,
                        professor_absent=professor,
                        hora=hora,
                        assignatura=assignatura,
                        grup=grup,
                        aula=aula,
                        substitut="",
                        tipus_substitut="",
                        tipus_absencia=tipus_absencia,
                    )
                    substitucions.append(sub)

        logger.debug(f"🟢 get_substitucions_necessaries() END: retorna {len(substitucions)} substitucions")
        return substitucions

    def _necessita_substitucio(self, activitat: dict) -> bool:
        """Comprova si una activitat necessita substitució"""
        assignatura = activitat.get("assignatura", "")

        # No necessita si l'assignatura és a «No substituir» aquell dia
        if assignatura in self.no_substituir:
            return False

        return True
