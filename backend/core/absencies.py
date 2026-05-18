"""
Gestió d'absències de professors
"""
from typing import Dict, List, Set
from config.constants import NO_SUBST

class GestorAbsencies:
    """Gestiona les absències dels professors"""
    
    def __init__(self, gestor_horari):
        self.horari = gestor_horari
    
    def get_substitucions_necessaries(self, dia: str, absents: Dict[str, List[str]],
                                    absents_tipus: Dict[str, str] = None,
                                    activitats_fallback: Dict = None) -> List[Dict]:
        """
        Calcula quines substitucions calen segons les absències
        Args:
            dia: Dia de la setmana (nom de l'XML) o format ISO (YYYY-MM-DD)
            absents: {professor: [hores]}
            absents_tipus: {professor: tipus_absencia} - 'SERVEI' o 'ABSENCIA'
        Returns: [{professor, hora, assignatura, grup, tipus_absencia}, ...]
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"🟢 get_substitucions_necessaries() START: dia='{dia}', absents={len(absents)}")

        # 🔧 FIX: Assegura que dia està en format nom dia XML, no ISO
        if isinstance(dia, str) and len(dia) == 10 and '-' in dia:
            # Rebut format ISO (2025-08-11), converteix a nom dia XML
            from utils.date_context import DateContext
            try:
                weekday_idx = DateContext.from_iso(dia).weekday_index
                dia = self.horari.get_dia_name(weekday_idx)
                logger.info(_("   🔄 Convertit dia ISO a nom XML: '{}'").format(dia))
            except Exception as e:
                logger.error(_("⚠️ Error en convertir dia ISO: {}").format(e))

        substitucions = []
        absents_tipus = absents_tipus or {}

        activitats_fallback = activitats_fallback or {}

        for professor, hores in absents.items():
            # Obté el tipus d'absència per aquest professor
            tipus_professor = absents_tipus.get(professor, 'ABSENCIA')
            logger.debug(f"      Professor '{professor}' absent a {len(hores)} hores: {hores}")

            for hora in hores:
                activitat = self.horari.get_activitat(dia, hora, professor)
                logger.debug(f"         get_activitat('{dia}', '{hora}', '{professor}') = {activitat}")

                if not activitat:
                    fallback = activitats_fallback.get((professor, hora))
                    if fallback:
                        activitat = {
                            "assignatura": fallback.get("assignatura", ""),
                            "grup": fallback.get("grup", ""),
                            "aula": fallback.get("aula", "")
                        }
                    else:
                        continue
                    continue

                # Comprova si necessita substitució
                if self._necessita_substitucio(activitat):
                    assignatura = activitat.get("assignatura", "")
                    grup = activitat.get("grup", "")
                    aula = activitat.get("aula", "")

                    # Determina tipus_absencia: el tipus del professor té prioritat absoluta
                    tipus_absencia = tipus_professor  # 'SERVEI' o 'ABSENCIA' segons el checkbox

                    sub = {
                        "professor": professor,
                        "professor_absent": professor,
                        "hora": hora,
                        "assignatura": assignatura,
                        "grup": grup,
                        "aula": aula,
                        "substitut": "",
                        "tipus_substitut": "",
                        "tipus_absencia": tipus_absencia
                    }
                    substitucions.append(sub)

        logger.debug(f"🟢 get_substitucions_necessaries() END: retorna {len(substitucions)} substitucions")
        return substitucions
    
    def _necessita_substitucio(self, activitat: Dict) -> bool:
        """Comprova si una activitat necessita substitució"""
        assignatura = activitat.get("assignatura", "")

        # No necessita si l'assignatura està a NO_SUBST
        if assignatura in NO_SUBST:
            return False

        return True
