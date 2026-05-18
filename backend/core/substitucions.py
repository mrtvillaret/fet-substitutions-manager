"""
Lògica principal de substitucions
"""
import random
from typing import List, Dict, Set, Tuple, Optional, Union
from collections import defaultdict
# Evitem imports estàtics per no quedar-nos amb valors stale
from utils.exception_chain import safe_core_operation

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
        
    def es_valid(self, nom_substitut: str, hora: str, absents: Dict[str, List[str]]) -> bool:
        """Comprova si un substitut és vàlid per preservar"""
        # 1. No pot estar absent
        if nom_substitut in absents and hora in absents[nom_substitut]:
            return False
            
        # 2. No pot estar ocupat amb vigilàncies
        professors_vigilancies = set(self.professors_ocupats_examens.get(hora, []))
        if nom_substitut in professors_vigilancies:
            return False
                
        return True
        
    def esta_disponible(self, nom_substitut: str, candidats: List) -> bool:
        """Comprova si el substitut està dins la llista de candidats disponibles"""
        for candidat in candidats:
            if candidat[0] == nom_substitut:
                return True
        return False
        
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
 
 
 
 
    def assignar_substitucions(self, dia: str, absents: Dict[str, List[str]],
                             grups_sense_classe: Union[Set[str], Dict[str, Set[str]]],
                             professors_ocupats_examens: Dict[str, List[str]] = None,
                             substitucions_existents: Dict[str, Dict] = None,
                             absents_tipus: Dict[str, str] = None,
                             activitats_fallback: Dict = None) -> List[Dict]:
        """Assigna substituts automàticament per hores

        Args:
            grups_sense_classe: Set[str] (antic) o Dict[str, Set[str]] (nou) amb grups per hora
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"🔵 assignar_substitucions() START: dia='{dia}', absents={len(absents)}, horari={bool(self.horari)}")

        # 🔧 FIX: Converteix dia de format ISO a nom del dia XML si cal
        if isinstance(dia, str) and len(dia) == 10 and '-' in dia:
            from utils.date_context import DateContext
            try:
                weekday_idx = DateContext.from_iso(dia).weekday_index
                dia = self.horari.get_dia_name(weekday_idx)
                logger.info(_("   🔄 Convertit dia ISO a nom XML: '{}'").format(dia))
            except Exception as e:
                logger.error(_("⚠️ Error en convertir dia ISO: {}").format(e))

        # 🚀 GUARDA INFO DELS PROFESSORS OCUPATS I SUBSTITUCIONS EXISTENTS
        self.professors_ocupats_examens = professors_ocupats_examens or {}
        self.substitucions_existents = substitucions_existents or {}
        self.dia_actual = dia

        print(f"\n🔍 DEBUG Vigilants carregats:")
        if self.professors_ocupats_examens:
            for hora, vigilants in self.professors_ocupats_examens.items():
                print(f"  {hora}: {vigilants}")
        else:
            print(f"  ❌ Cap vigilant carregat (dict buit)")

        # Normalitza grups_sense_classe a Dict[str, Set[str]]
        if isinstance(grups_sense_classe, set):
            # Format antic: aplica a totes les hores
            hores = self.horari.hores if self.horari else []
            logger.info(_("   📌 hores carregades de l'XML: {}").format(hores))
            self.grups_sense_classe_dict = {hora: grups_sense_classe for hora in hores if hora != "Pati"}
        else:
            # Format nou: ja és un dict per hora
            self.grups_sense_classe_dict = grups_sense_classe

        # Mantenir compatibilitat amb self.grups_sense_classe_actual (tots els grups)
        tots_grups = set()
        for grups in self.grups_sense_classe_dict.values():
            tots_grups.update(grups)
        self.grups_sense_classe_actual = tots_grups
        
        # Inicialitza validador amb la info actual
        self.validator = CandidateValidator(professors_ocupats_examens, substitucions_existents)
        
        # Les substitucions existents ja es passen com a paràmetre

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

            # Afegir si:
            # 1. Té grup vàlid i el grup no està sense classe, O
            # 2. No té grup però l'assignatura necessita substitució (VP, GP, etc.)
            if grup and grup not in grups_hora:
                substitucions_filtrades.append(sub)
            elif not grup:
                from config import constants
                if assignatura not in constants.NO_SUBST:
                # Activitats sense grup que necessiten substitució (VP, GP, etc.)
                    substitucions_filtrades.append(sub)

        # Recomponem la llista: separadors + substitucions filtrades
        substitucions = [
            sub for sub in substitucions
            if sub.get("separador") or sub in substitucions_filtrades
        ]
        # =====================================

        # 🚀 NOVA FUNCIÓ: AFEGEIX SUBSTITUCIONS PER VIGILANTS AMB CLASSE
        # Passa tots els grups per compatibilitat (la funció filtrarà internament)
        substitucions_vigilants = self._generar_substitucions_vigilants(dia, self.grups_sense_classe_actual)
        
        # Afegeix les noves substitucions a la llista
        substitucions.extend(substitucions_vigilants)
        
        # Total substitucions generades
        
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

        # 🔗 PRESERVA ENCADENADES DEL JSON que no s'han regenerat
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

                        # ✅ VALIDACIÓ: Només preserva si el professor_absent és un substitut actiu a aquesta hora
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
                print(f"  🔗 {encadenades_preservades} encadenades preservades del JSON")
            if encadenades_descartades > 0:
                print(f"  🗑️ {encadenades_descartades} encadenades descartades (substitució mare no existeix)")

        logger.debug(_("🔵 assignar_substitucions() END: retorna {} substitucions").format(len(substitucions)))
        return substitucions

    def _generar_substitucions_vigilants(self, dia: str, grups_sense_classe: Set[str]) -> List[Dict]:
        """Genera substitucions per professors que fan vigilància però tenen classe assignada"""
        substitucions_vigilants = []

        try:
            if not self.professors_ocupats_examens:
                return substitucions_vigilants

            # Removed excessive debug output

            for hora, vigilants in self.professors_ocupats_examens.items():
                for vigilant in vigilants:
                    # Comprova si aquest vigilant té classe assignada a aquesta hora
                    activitat = self.horari.get_activitat(dia, hora, vigilant)

                    if activitat:
                        grup = activitat.get("grup", "")
                        assignatura = activitat.get("assignatura", "")
                        aula = activitat.get("aula", "")

                        # CAS 1: Té classe real amb grup (no està sense classe)
                        if (assignatura and  # Assignatura no buida = té classe
                            grup and  # Vigilàncies d'exàmens no tenen grup (grup = "")
                            grup not in grups_sense_classe):

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
                        elif assignatura:
                            from config import constants
                            if assignatura in constants.PRIORITATS and assignatura not in constants.NO_SUBST:
                                print(f"  🔍 Vigilant {vigilant} té activitat '{assignatura}' (PRIORITATS, NO a NO_SUBST) → genera substitució")
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
            
            # Return generated vigilant substitutions
            
            return substitucions_vigilants
            
        except Exception as e:
            # Error generat substitucions per vigilants
            pass
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

        # 🔧 PRIORITZA CONSERVACIONS: ordena substitucions amb conservació potencial primer
        substitucions_ordenades = self._ordenar_per_conservacio(substitucions, hora)

        for sub in substitucions_ordenades:
            if not self._aplica_assignacio(sub, hora, candidats_per_categoria, ocupats_hora, absents):
                continue
            # Afegeix disponibles per mostrar al desplegable
            sub["disponibles"] = candidats

        # 🔄 SUBSTITUCIONS ENCADENADES: Genera substitucions per disponibles que ara fan substitució
        substitucions_encadenades = []
        print(f"🔍 Comprovant encadenades per {len(substitucions)} substitucions a {hora}...")
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

                print(f"  🔹 {sub['substitut']} → tipus_substitut='{tipus_substitut}', tipus='{tipus}'")

                # Si el tipus està a PRIORITATS i NO està a NO_SUBST, genera substitució encadenada
                from config import constants
                if tipus in constants.PRIORITATS and tipus not in constants.NO_SUBST:
                    print(f"    ✅ Genera encadenada!")
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
            print(f"  🔗 Generades {len(substitucions_encadenades)} substitucions encadenades a {hora}")

        return substitucions_encadenades

    def _ordenar_per_conservacio(self, substitucions: List[Dict], hora: str) -> List[Dict]:
        """Ordena substitucions prioritzant les que poden tenir conservació"""
        def prioritat_conservacio(sub):
            professor_absent = sub.get("professor_absent", "")
            assignatura = sub.get("assignatura", "")
            grup = sub.get("grup", "")
            tipus_absencia = sub.get("tipus_absencia", "ABSENCIA")

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
        from datetime import datetime, date

        # Obtenir llista de professors de baixa per aquesta data (si està configurada)
        professors_baixa_noms = set()
        if hasattr(self, 'data_substitucions'):
            # Si tenim la data de les substitucions, filtrar per rang
            try:
                data_obj = datetime.strptime(self.data_substitucions, '%Y-%m-%d').date()
                for baixa in PROFESSORS_BAIXA:
                    data_inici = datetime.strptime(baixa['data_inici'], '%Y-%m-%d').date()
                    data_final = datetime.strptime(baixa['data_final'], '%Y-%m-%d').date()
                    if data_inici <= data_obj <= data_final:
                        professors_baixa_noms.add(baixa['professor'])
            except:
                pass

        candidats = [(prof, tipus, detall) for prof, tipus, detall in disponibles
                    if hora not in absents.get(prof, []) and prof not in professors_baixa_noms]

        candidats_per_categoria = defaultdict(list)
        for prof, tipus, detall in candidats:
            categoria = self._obtenir_categoria(tipus)
            from config import constants
            if categoria < len(constants.ORDRE_PRIORITATS):
                candidats_per_categoria[categoria].append((prof, tipus, detall))

        # 🔧 DEBUG: Mostrar candidats per categoria
        if candidats_per_categoria:
            print(f"\n  📊 Hora {hora}: {len(candidats)} candidats disponibles")
            for cat in sorted(candidats_per_categoria.keys()):
                cands = candidats_per_categoria[cat]
                print(f"    Categoria {cat}: {len(cands)} candidats")
                for i, (p, t, d) in enumerate(cands[:3]):  # Només mostrar primers 3
                    print(f"      {i+1}. {p} ({t})")
                if len(cands) > 3:
                    print(f"      ... i {len(cands)-3} més")

        return candidats_per_categoria, set()

    def _valida_indisponibilitat(self, substitut: str, hora: str, ocupats_hora: Set[str], 
                               absents: Dict[str, List[str]]) -> bool:
        """Valida si un substitut està disponible (no absent, no ocupat, no vigilància)"""
        if hora in absents.get(substitut, []):
            return False
        if substitut in ocupats_hora:
            return False  
        if self._professor_te_vigilancia(substitut, hora):
            return False
        return True

    def _aplica_assignacio(self, sub: Dict, hora: str, candidats_per_categoria: Dict[int, List],
                         ocupats_hora: Set[str], absents: Dict[str, List[str]]) -> bool:
        """Aplica assignació conservadora per una substitució individual"""
        professor_absent = sub.get('professor_absent', sub.get('professor', ''))
        # Crea clau semàntica (sense tipus_absencia per preservar substituts en canvis SERVEI ↔ ABSENCIA)
        tipus_absencia = sub.get('tipus_absencia', 'ABSENCIA')
        clau_exacta = f"{professor_absent}|{hora}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"

        print(f"🔍 _aplica_assignacio: clau_exacta='{clau_exacta}'")
        print(f"   Està a substitucions_existents? {clau_exacta in self.substitucions_existents}")
        if clau_exacta in self.substitucions_existents:
            print(f"   Substitut existent: {self.substitucions_existents[clau_exacta].get('substitut')}")

        # ✅ CAS 1: Conserva QUALSEVOL selecció anterior (inclús buides o categoria baixa)
        if clau_exacta in self.substitucions_existents:
            sub_anterior = self.substitucions_existents[clau_exacta]
            substitut_actual = sub_anterior.get("substitut", "")
            tipus_absencia_original = sub_anterior.get("tipus_absencia", "ABSENCIA")

            # CANVI CLAU: Conserva SEMPRE la selecció anterior, fins i tot si és buida
            if substitut_actual:
                # MILLORA: Valida contra TOTS els disponibles (automàtics + manuals)
                tots_disponibles = self.alliberats.get_tots_disponibles(self.dia_actual, hora, self.grups_sense_classe_actual)

                if (self._valida_indisponibilitat(substitut_actual, hora, ocupats_hora, absents) and
                    self._substitut_esta_disponible(substitut_actual, tots_disponibles)):
                    # Respecta el tipus de substitució que s'està creant (absència vs vigilància)
                    tipus_absencia_nova = sub.get("tipus_absencia", tipus_absencia_original)
                    sub.update({
                        "substitut": substitut_actual,
                        "tipus_substitut": sub_anterior.get("tipus_substitut", ""),
                        "comentaris": sub_anterior.get("comentaris", ""),
                        "tipus_absencia": tipus_absencia_nova,  # Usa el valor de la substitució nova
                        "_conservat": True
                    })
                    ocupats_hora.add(substitut_actual)
                    return True
                # Si no està disponible a la llista completa, continua amb reassignació automàtica
            else:
                # MILLORA: Conserva seleccions buides ("-- selecciona substitut --")
                tipus_absencia_nova = sub.get("tipus_absencia", tipus_absencia_original)
                sub.update({
                    "substitut": "",  # Conserva selecció buida
                    "tipus_substitut": "",
                    "comentaris": sub_anterior.get("comentaris", ""),
                    "tipus_absencia": tipus_absencia_nova,
                    "_conservat": True
                })
                return True
        
        # ✅ CAS 2 & 3: Reassigna òptim immediatament / reoptimitza
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
                # 🔧 DEBUG
                if escollit:
                    print(f"    ✅ Triat de categoria {categoria}: {escollit[0]} ({escollit[1]})")
                return escollit

        return None  # Cap candidat disponible

    def _filtrar_substitucions_per_hora(self, substitucions_dict: Dict[str, Dict], hora: str) -> Dict[str, Dict]:
        """Helper: filtra substitucions per hora de la clau semàntica"""
        resultat = {}
        for clau, dades in substitucions_dict.items():
            parts = clau.split("|")
            if len(parts) >= 2 and parts[1] == hora:
                resultat[clau] = dades
        return resultat

    def _carregar_substitucions_publicades(self, dia: str) -> Dict[str, Dict]:
        """Carrega substitucions publicades des de substitucions.json (unificat)"""
        try:
            from data.storage import storage
            from utils.date_context import DateContext

            # Normalitza data
            data_iso = dia if isinstance(dia, str) and len(dia) == 10 else DateContext(dia).iso_format
            
            # Carrega directament de substitucions.json
            substitucions_llista = storage.carregar_substitucions(data_iso)
            
            if not substitucions_llista:
                return {}
            
            # Converteix al format de preservació (clau: dades)
            # Inclou TOTES les substitucions (inclús buides) per conservar seleccions
            substitucions_dict = {}
            encadenades_count = 0
            for sub in substitucions_llista:
                assignatura = sub.get("assignatura", "")
                grup = sub.get("grup", "")
                substitut = sub.get("substitut", "")
                tipus_absencia = sub.get("tipus_absencia", "ABSENCIA")

                # CANVI: Carrega TOTES les substitucions que tenen assignatura i grup,
                # o que són encadenades (grup="" però tipus_absencia="ENCADENADA")
                # (inclús si no tenen substitut per conservar seleccions buides)
                if sub.get("assignatura") and (sub.get("grup") or tipus_absencia == "ENCADENADA"):
                    # Clau sense tipus_absencia per preservar substituts quan només canvia SERVEI ↔ ABSENCIA
                    clau = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{assignatura}|{grup}"
                    substitucions_dict[clau] = {
                        "substitut": substitut,  # Pot ser buit per conservar seleccions "-- selecciona substitut --"
                        "tipus_substitut": sub.get("tipus_substitut", ""),
                        "comentaris": sub.get("comentaris", ""),
                        "tipus_absencia": tipus_absencia
                    }
                    if tipus_absencia == "ENCADENADA":
                        encadenades_count += 1

            if encadenades_count > 0:
                print(f"  🔗 {encadenades_count} encadenades carregades del JSON")

            return substitucions_dict

        except Exception as e:
            print(_("ℹ️ No hi ha substitucions publicades per {}: {}").format(dia, e))
        
        return {}

    def _substitut_esta_disponible(self, nom_substitut: str, candidats: List) -> bool:
        """Comprova si un substitut està dins dels candidats disponibles"""
        return self.validator.esta_disponible(nom_substitut, candidats)
    
    def _professor_te_vigilancia(self, nom_professor: str, hora: str) -> bool:
        """Comprova si un professor té vigilància assignada a una hora específica"""
        if not hasattr(self, 'professors_ocupats_examens') or not self.professors_ocupats_examens:
            return False

        # Comprova si el professor està a la llista d'ocupats amb vigilàncies per aquesta hora
        professors_ocupats_hora = self.professors_ocupats_examens.get(hora, [])
        te_vigilancia = nom_professor in professors_ocupats_hora

        if te_vigilancia:
            print(f"  🔍 _professor_te_vigilancia({nom_professor}, {hora}) = True (està a {professors_ocupats_hora})")

        return te_vigilancia
        
    def _obtenir_categoria(self, tipus_activitat: str) -> int:
        """Retorna l'índex de categoria (0 = prioritat màxima)"""
        from config import constants
        for i, categoria in enumerate(constants.ORDRE_PRIORITATS):
            if tipus_activitat in categoria:
                return i
        return len(constants.ORDRE_PRIORITATS)  # Categoria mínima per tipus desconeguts
    
    
    def reordenar_per_hora(self, substitucions: List[Dict]) -> List[Dict]:
        """Reordena substitucions per hora amb separadors"""
        hores = self.horari.hores if self.horari else []

        result = []
        hores_amb_subs = {}
        
        # Agrupa per hora (ignora separadors existents)
        for sub in substitucions:
            if sub.get("separador"):
                continue
            hora = sub["hora"]
            if hora not in hores_amb_subs:
                hores_amb_subs[hora] = []
            hores_amb_subs[hora].append(sub)
        
        # Construeix resultat amb separadors ordenats per hores del XML
        for hora in hores:
            if hora in hores_amb_subs:
                # Afegeix separador per aquesta hora
                result.append({"separador": True, "hora": hora})
                
                # Ordena les substitucions dins de cada hora per tipus
                # (primer absents normals, després vigilants)
                subs_hora = hores_amb_subs[hora]
                def ordre_tipus(s):
                    tipus = s.get("tipus_absencia", "ABSENCIA")
                    ordre = {"ABSENCIA": 0, "SERVEI": 1, "VIGILANCIA": 2}
                    return (ordre.get(tipus, 0), s.get("professor_absent", ""))
                subs_hora.sort(key=ordre_tipus)
                
                result.extend(subs_hora)
        
        return result
