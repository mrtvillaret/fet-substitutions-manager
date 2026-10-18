"""
Lògica principal de substitucions
"""
import logging
import random
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

# Evitem imports estàtics per no quedar-nos amb valors stale
from core.alliberats import sense_classe

log = logging.getLogger(__name__)

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

class CandidateValidator:
    """Validador centralitzat per candidats a substitucions"""
    
    def __init__(self, professors_ocupats_examens: Dict = None, substitucions_existents: Dict = None):
        self.professors_ocupats_examens = professors_ocupats_examens or {}
        self.substitucions_existents = substitucions_existents or {}
        
        
    # ELIMINADA: escollir_millor_candidat() - no s'utilitzava (duplicat obsolet)
    # Utilitzar _escollir_millor_candidat_disponible() en lloc d'aquesta

    def _escollir_aleatoriament_amb_pesos(self, candidats: List[Tuple[str, str, str]]) -> Tuple[str, str, str]:
        """Escull aleatòriament segons els pesos dels tipus d'activitat

        NOTA: Els candidats ja estan filtrats per categoria (prioritat).
        Dins de cada categoria, fem selecció aleatòria equiprobable.
        """
        if not candidats:
            return None
        if len(candidats) == 1:
            return candidats[0]

        # Selecció aleatòria equiprobable dins de la mateixa categoria
        # (els candidats ja estan ordenats per categoria abans d'arribar aquí)
        return random.choice(candidats)

class GestorSubstitucions:
    """Gestiona l'assignació de substitucions"""
    
    def __init__(self, gestor_horari, gestor_alliberats, gestor_absencies):
        self.horari = gestor_horari
        self.alliberats = gestor_alliberats
        self.absencies = gestor_absencies
        self.validator = None
        # Estat d'una assignació: el fixa assignar_substitucions (o qui cridi
        # _generar_substitucions_vigilants). Buit fins llavors.
        self.dia_actual = None
        self.professors_ocupats_examens = {}
        self.grups_sense_classe_dict = {}
        self.substitucions_existents = {}
        self.omplir = True   # False: no es tria cap substitut nou
 
 
 
 
    def assignar_substitucions(self, dia: str, absents: Dict[str, List[str]],
                             grups_sense_classe: Union[Set[str], Dict[str, Set[str]]],
                             professors_ocupats_examens: Dict[str, List[str]] = None,
                             substitucions_existents: Dict[str, Dict] = None,
                             absents_tipus: Dict[str, str] = None,
                             activitats_fallback: Dict = None,
                             omplir: bool = True) -> List[Dict]:
        """Assigna substituts automàticament per hores

        Args:
            grups_sense_classe: Set[str] (antic) o Dict[str, Set[str]] (nou) amb grups per hora
            omplir: si és False, només es conserven els substituts que ja hi havia i les
                files noves queden pendents (es fa servir després d'un canvi del dia:
                no s'assigna ningú sense que l'usuari ho demani)
        """
        self.omplir = omplir
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"🔵 assignar_substitucions() START: dia='{dia}', absents={len(absents)}, horari={bool(self.horari)}")

        # Converteix dia de format ISO a nom del dia XML si cal
        if isinstance(dia, str) and len(dia) == 10 and '-' in dia:
            from utils.date_context import DateContext
            try:
                weekday_idx = DateContext.from_iso(dia).weekday_index
                dia = self.horari.get_dia_name(weekday_idx)
                logger.info(_("   🔄 Convertit dia ISO a nom XML: '{}'").format(dia))
            except Exception as e:
                logger.error(_("⚠️ Error en convertir dia ISO: {}").format(e))

        # Guarda info dels professors ocupats i substitucions existents
        self.professors_ocupats_examens = professors_ocupats_examens or {}
        self.substitucions_existents = substitucions_existents or {}
        self.dia_actual = dia


        # Normalitza grups_sense_classe a Dict[str, Set[str]]
        if isinstance(grups_sense_classe, set):
            # Format antic: aplica a totes les hores
            hores = self.horari.hores if self.horari else []
            logger.info(_("   📌 hores carregades de l'XML: {}").format(hores))
            self.grups_sense_classe_dict = {hora: grups_sense_classe for hora in hores if hora != "Pati"}
        else:
            # Format nou: ja és un dict per hora
            self.grups_sense_classe_dict = grups_sense_classe

        
        # Inicialitza validador amb la info actual
        self.validator = CandidateValidator(professors_ocupats_examens, substitucions_existents)
        

        substitucions = self.absencies.get_substitucions_necessaries(
            dia,
            absents,
            absents_tipus,
            activitats_fallback=activitats_fallback
        )
        logger.debug(_("   📋 get_substitucions_necessaries retorna {} substitucions").format(len(substitucions)))

        # ===== FILTRE GRUPS SENSE CLASSE (per hora específica) =====
        substitucions_filtrades = []
        for sub in substitucions:
            if sub.get("separador"):
                continue
            hora = sub.get("hora", "")
            grup = sub.get("grup", "")
            assignatura = sub.get("assignatura", "")
            grups_hora = self.grups_sense_classe_dict.get(hora, set())
            professor = sub.get("professor_absent") or sub.get("professor", "")

            # Afegir si:
            # 1. Té grup vàlid i no queda sense classe (grup o professor alliberat), O
            # 2. No té grup però l'assignatura necessita substitució (VP, GP, etc.)
            if grup and not sense_classe(professor, grup, grups_hora):
                substitucions_filtrades.append(sub)
            elif not grup:
                from config import constants
                # Activitats sense grup que necessiten substitució (VP, GP, etc.)
                if assignatura not in constants.NO_SUBST and not sense_classe(professor, "", grups_hora):
                    substitucions_filtrades.append(sub)

        # Recomponem la llista: separadors + substitucions filtrades
        substitucions = [
            sub for sub in substitucions
            if sub.get("separador") or sub in substitucions_filtrades
        ]
        # =====================================

        # Afegeix substitucions per vigilants amb classe
        substitucions_vigilants = self._generar_substitucions_vigilants(dia, absents)
        
        # Afegeix les noves substitucions a la llista
        substitucions.extend(substitucions_vigilants)
        
        
        # Agrupa substitucions per hora
        substitucions_per_hora = defaultdict(list)
        for sub in substitucions:
            if not sub.get("separador"):
                hora = sub["hora"]
                substitucions_per_hora[hora].append(sub)
        
        # Processa cada hora per separat (amb grups específics per hora)
        totes_substitucions_encadenades = []
        for hora, subs_hora in substitucions_per_hora.items():
            grups_hora = self.grups_sense_classe_dict.get(hora, set())
            subs_encadenades = self._assignar_substitucions_per_hora(dia, hora, subs_hora, grups_hora, absents)
            if subs_encadenades:
                totes_substitucions_encadenades.extend(subs_encadenades)

        # Afegeix totes les substitucions encadenades a la llista principal
        substitucions.extend(totes_substitucions_encadenades)

        # PRESERVA ENCADENADES DEL JSON que no s'han regenerat
        # Això passa quan el substitut original ja no està assignat
        if self.substitucions_existents:
            claus_existents = set()
            substituts_actius = {}  # {hora: {substitut1, substitut2, ...}}

            for sub in substitucions:
                if not sub.get("separador"):
                    clau = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"
                    claus_existents.add(clau)

                    # Registra substituts actius per hora (per validar encadenades)
                    if sub.get("substitut"):
                        hora = sub.get("hora", "")
                        if hora not in substituts_actius:
                            substituts_actius[hora] = set()
                        substituts_actius[hora].add(sub["substitut"])

            # Afegeix encadenades del JSON que no estan a la llista actual
            encadenades_preservades = 0
            encadenades_descartades = 0
            for clau, dades in self.substitucions_existents.items():
                if dades.get("tipus_absencia") == "ENCADENADA" and clau not in claus_existents:
                    # Reconstrueix la substitució encadenada
                    parts = clau.split("|")
                    if len(parts) == 4:
                        professor_absent = parts[0]
                        hora = parts[1]

                        # Només preserva si el professor_absent és un substitut actiu a aquesta hora
                        if hora in substituts_actius and professor_absent in substituts_actius[hora]:
                            encadenada_preservada = {
                                "professor_absent": professor_absent,
                                "hora": hora,
                                "assignatura": parts[2],
                                "grup": parts[3],
                                "tipus_absencia": "ENCADENADA",
                                "substitut": dades.get("substitut", ""),
                                "tipus_substitut": dades.get("tipus_substitut", ""),
                                "comentaris": dades.get("comentaris", ""),
                                "disponibles": []
                            }
                            substitucions.append(encadenada_preservada)
                            encadenades_preservades += 1
                        else:
                            encadenades_descartades += 1

            if encadenades_preservades > 0:
                log.debug(f"  🔗 {encadenades_preservades} encadenades preservades del JSON")
            if encadenades_descartades > 0:
                log.debug(f"  🗑️ {encadenades_descartades} encadenades descartades (substitució mare no existeix)")

        logger.debug(_("🔵 assignar_substitucions() END: retorna {} substitucions").format(len(substitucions)))
        return substitucions

    def _generar_substitucions_vigilants(self, dia: str, absents: Dict[str, List[str]] = None) -> List[Dict]:
        """Genera substitucions per professors que fan vigilància però tenen classe assignada.

        `absents` ({professor: [hores]}): si el vigilant és absent a aquella hora,
        no se'n genera cap: la seva classe ja la cobreix la seva ABSENCIA (i
        l'examen, la VIGILANCIA_ABSENT). Si no, la classe quedaria coberta dues
        vegades."""
        substitucions_vigilants = []
        absents = absents or {}

        try:
            if not self.professors_ocupats_examens:
                return substitucions_vigilants


            for hora, vigilants in self.professors_ocupats_examens.items():
                for vigilant in vigilants:
                    if hora in absents.get(vigilant, ()):
                        continue
                    # Comprova si aquest vigilant té classe assignada a aquesta hora
                    activitat = self.horari.get_activitat(dia, hora, vigilant)

                    if activitat:
                        grup = activitat.get("grup", "")
                        assignatura = activitat.get("assignatura", "")
                        aula = activitat.get("aula", "")

                        # CAS 1: Té classe real amb grup (no està sense classe)
                        if (assignatura and  # Assignatura no buida = té classe
                            grup and  # Vigilàncies d'exàmens no tenen grup (grup = "")
                            not sense_classe(vigilant, grup, self.grups_sense_classe_dict.get(hora, ()))):

                            # Sempre crea substitució de vigilància (és diferent de l'absència)
                            # La vigilància és una classe/activitat addicional, no la mateixa que l'absència
                            substitucions_vigilants.append({
                                "professor": vigilant,
                                "professor_absent": vigilant,
                                "hora": hora,
                                "assignatura": assignatura,
                                "grup": grup,
                                "aula": aula,
                                "substitut": "",  # S'assignarà després
                                "tipus_substitut": "",
                                "comentaris": "",  # Comentaris automàtics eliminats
                                "disponibles": [],  # S'afegiran després
                                "tipus_absencia": "VIGILANCIA"  # Marca especial per identificar-la
                            })

                        # CAS 2: Té activitat de PRIORITATS que NO està a NO_SUBST
                        # (si no està alliberat d'aquesta activitat)
                        elif assignatura and not sense_classe(vigilant, "", self.grups_sense_classe_dict.get(hora, ())):
                            from config import constants
                            if assignatura in constants.PRIORITATS and assignatura not in constants.NO_SUBST:
                                substitucions_vigilants.append({
                                    "professor": vigilant,
                                    "professor_absent": vigilant,
                                    "hora": hora,
                                    "assignatura": assignatura,
                                    "grup": "",  # Activitats de PRIORITATS no tenen grup
                                    "aula": aula,
                                    "substitut": "",  # S'assignarà després
                                    "tipus_substitut": "",
                                    "comentaris": "",
                                    "disponibles": [],
                                    "tipus_absencia": "VIGILANCIA"
                                })
            
            
            return substitucions_vigilants
            
        except Exception:
            log.warning("No s'han pogut generar les substitucions dels vigilants", exc_info=True)
            return []
    
    def _assignar_substitucions_per_hora(self, dia: str, hora: str, substitucions: List[Dict],
                                       grups_sense_classe: Set[str], absents: Dict[str, List[str]]) -> List[Dict]:
        """Assigna substitucions per una hora específica amb estratègia CONSERVADORA

        Returns:
            List[Dict]: Llista de substitucions encadenades generades
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(_("   🟡 _assignar_substitucions_per_hora(): dia='{}', hora='{}', {} subs").format(dia, hora, len(substitucions)))

        candidats_per_categoria, ocupats_hora = self._seleccio_candidats_per_hora(
            dia, hora, grups_sense_classe, absents)

        candidats = []
        for categoria_candidats in candidats_per_categoria.values():
            candidats.extend(categoria_candidats)

        logger.debug(_("      📊 {} candidats trobats per hora {}").format(len(candidats), hora))

        # PRIORITZA CONSERVACIONS: ordena substitucions amb conservació potencial primer
        substitucions_ordenades = self._ordenar_per_conservacio(substitucions, hora)

        for sub in substitucions_ordenades:
            if not self._aplica_assignacio(sub, hora, candidats_per_categoria, ocupats_hora, absents):
                continue
            # Afegeix disponibles per mostrar al desplegable
            sub["disponibles"] = candidats

        # SUBSTITUCIONS ENCADENADES: Genera substitucions per disponibles que ara fan substitució
        substitucions_encadenades = []
        for sub in substitucions:
            if sub.get("substitut") and sub.get("tipus_substitut"):
                tipus_substitut = sub.get("tipus_substitut", "")

                # Extreu el tipus real dels parèntesis: "disponible (Guàrdia-P)" → "Guàrdia-P"
                import re
                match = re.search(r'\(([^)]+)\)', tipus_substitut)
                if match:
                    tipus = match.group(1)
                else:
                    # Fallback per formats antics sense parèntesis
                    tipus = tipus_substitut.split(" (")[0] if " (" in tipus_substitut else tipus_substitut


                # Si el tipus està a PRIORITATS i NO està a NO_SUBST, genera substitució encadenada
                from config import constants
                if tipus in constants.PRIORITATS and tipus not in constants.NO_SUBST:
                    substitucions_encadenades.append({
                        "professor_absent": sub["substitut"],
                        "hora": hora,
                        "assignatura": tipus,
                        "grup": "",
                        "tipus_absencia": "ENCADENADA"
                    })

        # Processa substitucions encadenades (només 1 nivell de profunditat)
        for sub_encadenada in substitucions_encadenades:
            self._aplica_assignacio(sub_encadenada, hora, candidats_per_categoria, ocupats_hora, absents)
            sub_encadenada["disponibles"] = candidats

        if substitucions_encadenades:
            log.debug(f"  🔗 Generades {len(substitucions_encadenades)} substitucions encadenades a {hora}")

        return substitucions_encadenades

    def _ordenar_per_conservacio(self, substitucions: List[Dict], hora: str) -> List[Dict]:
        """Ordena substitucions prioritzant les que poden tenir conservació"""
        def prioritat_conservacio(sub):
            professor_absent = sub.get("professor_absent", "")
            assignatura = sub.get("assignatura", "")
            grup = sub.get("grup", "")

            # Genera clau de conservació
            clau = f"{professor_absent}|{hora}|{assignatura}|{grup}"

            # Si existeix als existents, prioritat màxima (0)
            if clau in self.substitucions_existents:
                return 0

            # Si no existeix, prioritat baixa (1)
            return 1

        return sorted(substitucions, key=prioritat_conservacio)
    
    def _seleccio_candidats_per_hora(self, dia: str, hora: str, grups_sense_classe: Set[str],
                                   absents: Dict[str, List[str]]) -> Tuple[Dict[int, List], Set[str]]:
        """Prepara i filtra candidats per una hora específica"""
        disponibles = self.alliberats.get_tots_disponibles(dia, hora, grups_sense_classe)

        # Filtrar absents i professors de baixa
        from config.constants import PROFESSORS_BAIXA

        # Obtenir llista de professors de baixa per aquesta data (si està configurada)
        professors_baixa_noms = set()
        if hasattr(self, 'data_substitucions'):
            # Si tenim la data de les substitucions, filtrar per rang
            from core.baixes import professors_de_baixa
            professors_baixa_noms = professors_de_baixa(PROFESSORS_BAIXA, self.data_substitucions)

        candidats = [(prof, tipus, detall) for prof, tipus, detall in disponibles
                    if hora not in absents.get(prof, []) and prof not in professors_baixa_noms]

        candidats_per_categoria = defaultdict(list)
        for prof, tipus, detall in candidats:
            categoria = self._obtenir_categoria(tipus)
            from config import constants
            if categoria < len(constants.ORDRE_PRIORITATS):
                candidats_per_categoria[categoria].append((prof, tipus, detall))

        return candidats_per_categoria, set()

    def _aplica_assignacio(self, sub: Dict, hora: str, candidats_per_categoria: Dict[int, List],
                         ocupats_hora: Set[str], absents: Dict[str, List[str]]) -> bool:
        """Aplica assignació conservadora per una substitució individual"""
        professor_absent = sub.get('professor_absent', sub.get('professor', ''))
        # Crea clau semàntica (sense tipus_absencia per preservar substituts en canvis SERVEI ↔ ABSENCIA)
        clau_exacta = f"{professor_absent}|{hora}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"

        # CAS 1: una fila que ja existia es conserva tal com és, amb substitut o sense.
        # «Genera pendents» no reescriu les files que ja tenen substitut: si aquí se'n
        # triés un altre, no es desaria i en canvi ocuparia aquell professor per a les
        # pendents de la mateixa hora. Si un substitut desat ja no és vàlid, ho detecten
        # les validacions del PDF i «Reassignar problemàtics», que el treu.
        if clau_exacta in self.substitucions_existents:
            sub_anterior = self.substitucions_existents[clau_exacta]
            substitut_actual = sub_anterior.get("substitut", "")
            sub.update({
                "substitut": substitut_actual,
                "tipus_substitut": sub_anterior.get("tipus_substitut", "") if substitut_actual else "",
                "comentaris": sub_anterior.get("comentaris", ""),
                # Respecta el tipus de la fila nova (absència, servei, vigilància)
                "tipus_absencia": sub.get("tipus_absencia", sub_anterior.get("tipus_absencia", "ABSENCIA")),
                "_conservat": True
            })
            if substitut_actual:
                ocupats_hora.add(substitut_actual)
            return True

        if not self.omplir:
            return True

        # CAS 2 & 3: Reassigna òptim immediatament / reoptimitza
        substitut = self._escollir_millor_candidat_disponible(candidats_per_categoria, ocupats_hora, hora)
        if substitut:
            prof, tipus, detall = substitut
            # Evita duplicació: si tipus == detall i no és "alliberat", usa "disponible (tipus)"
            # Els alliberats mai tenen tipus == detall (el detall sempre és "tenia X - Y")
            if tipus == detall and tipus != "alliberat":
                tipus_substitut = "disponible ({})".format(tipus)
            else:
                tipus_substitut = "{} ({})".format(tipus, detall)
            sub.update({
                "substitut": prof,
                "tipus_substitut": tipus_substitut,
                "comentaris": sub.get("comentaris", "")
            })
            ocupats_hora.add(prof)
        
        return True

    def _escollir_millor_candidat_disponible(self, candidats_per_categoria: Dict[int, List],
                                           ocupats_hora: Set[str], hora_actual: str) -> Optional[Tuple[str, str, str]]:
        """Escull el millor candidat disponible excloent professors amb vigilàncies"""

        # Obté professors ocupats amb vigilàncies
        professors_vigilancies = set()
        if hasattr(self, 'professors_ocupats_examens') and self.professors_ocupats_examens:
            professors_vigilancies = set(self.professors_ocupats_examens.get(hora_actual, []))

        # Llegeix categories actives (checkboxes) des del mòdul
        import config.constants as constants
        categories_actives = constants.CATEGORIES_ACTIVES

        # Recorre categories per ordre de prioritat
        for categoria in sorted(candidats_per_categoria.keys()):
            # Salta categoria si està desactivada (checkbox desmarcat)
            if categoria < len(categories_actives) and not categories_actives[categoria]:
                continue  # No assigna automàticament d'aquesta categoria

            candidats_categoria = candidats_per_categoria[categoria]
            # Filtra candidats per aquesta categoria
            candidats_disponibles = []
            for prof, tipus, detall in candidats_categoria:
                if prof not in ocupats_hora and prof not in professors_vigilancies:
                    candidats_disponibles.append((prof, tipus, detall))

            if candidats_disponibles:
                # Tria aleatòriament amb pesos dins d'aquesta categoria
                escollit = self.validator._escollir_aleatoriament_amb_pesos(candidats_disponibles)
                return escollit

        return None  # Cap candidat disponible


    def _obtenir_categoria(self, tipus_activitat: str) -> int:
        """Retorna l'índex de categoria (0 = prioritat màxima)"""
        from config import constants
        for i, categoria in enumerate(constants.ORDRE_PRIORITATS):
            if tipus_activitat in categoria:
                return i
        return len(constants.ORDRE_PRIORITATS)  # Categoria mínima per tipus desconeguts
    
    
