"""
Lògica principal de substitucions
"""

import logging
import random
from collections import Counter, defaultdict, deque
from fractions import Fraction

from config import constants
from dates import parse_date

# Evitem imports estàtics per no quedar-nos amb valors stale
from grups.disponibilitat import sense_classe
from substitucions.encadenades import activitat_encadenada
from substitucions.files import FilaSubstitucio, PropostaSubstitucio, clau_fila

log = logging.getLogger(__name__)

try:
    from i18n_setup import translate as _
except ImportError:

    def _(text):
        return text


def prioritat_candidat(tipus_activitat: str) -> int:
    """Retorna l'índex de prioritat d'un tipus (0 = prioritat màxima)."""

    for i, categoria in enumerate(constants.ORDRE_PRIORITATS):
        if tipus_activitat in categoria:
            return i
    return len(constants.ORDRE_PRIORITATS)


def absents_a_hora(absents: dict[str, list[str]], hora: str) -> set[str]:
    """Qui és absent a aquella hora (l'absència compta per hores, no tot el dia)."""
    return {professor for professor, hores in absents.items() if hora in hores}


def candidats_per_categoria(
    disponibles: list[tuple[str, str, str]], exclosos: set[str] = frozenset()
) -> dict[int, list[tuple[str, str, str]]]:
    """Regla única de candidats: els disponibles agrupats per categoria de Prioritats.

    Fora els `exclosos` i els tipus que no tenen cap categoria. La fan servir
    el motor, la millora final de «Reassigna» i el vigilant absent.
    """
    per_categoria = defaultdict(list)
    for professor, tipus, detall in disponibles:
        if professor in exclosos:
            continue
        categoria = prioritat_candidat(tipus)
        if categoria < len(constants.ORDRE_PRIORITATS):
            per_categoria[categoria].append((professor, tipus, detall))
    return per_categoria


def pes_de(tipus: str) -> int:
    """Pes de Prioritats per a la quota i el sorteig.

    Sense pes configurat (p. ex. alliberats), nul, zero o negatiu: 1.
    """
    pes = constants.PRIORITATS.get(tipus)
    return pes if pes is not None and pes > 0 else 1


def candidats_de_maxima_prioritat(
    candidats_per_categoria: dict[int, list],
    categories_actives,
    professors_exclosos: set[str] = frozenset(),
) -> list[tuple[str, str, str]]:
    """Calcula els candidats de la primera categoria activa amb disponibles.

    No desempata: conserva l'ordre d'entrada perquè l'atzar el resolgui en un
    pas separat.
    """
    for categoria in sorted(candidats_per_categoria):
        if categoria < len(categories_actives) and not categories_actives[categoria]:
            continue
        candidats = [
            candidat for candidat in candidats_per_categoria[categoria] if candidat[0] not in professors_exclosos
        ]
        if candidats:
            return candidats
    return []


def text_tipus_substitut(tipus: str, detall: str) -> str:
    """El text que es desa a la fila per a un substitut de `tipus` (invers de `tipus_real`).

    Evita la duplicació: si tipus == detall i no és «alliberat», «disponible (tipus)».
    Els alliberats mai tenen tipus == detall (el detall sempre és «tenia X - Y»).
    """
    if tipus == detall and tipus != "alliberat":
        return f"disponible ({tipus})"
    return f"{tipus} ({detall})"


def tipus_real(tipus_substitut: str) -> str:
    """Tipus de Prioritats a partir del text guardat a la substitució."""
    if tipus_substitut.startswith("disponible (") and tipus_substitut.endswith(")"):
        return tipus_substitut[12:-1]
    if tipus_substitut.startswith("alliberat"):
        return "alliberat"
    return tipus_substitut.split(" (", 1)[0]


class QuotaFranja:
    """Últimes deu assignacions per hora i categoria d'un mateix dia setmanal.

    L'historial arriba ordenat per data i ID, amb el dia que es genera exclòs.
    Guarda noms, no torns: tant el pes com la categoria són els actuals.
    Les tries noves s'hi anoten en l'ordre en què s'assignen.
    """

    def __init__(self, historial=()):
        self.finestres = defaultdict(lambda: deque(maxlen=10))
        for hora, professor, tipus_guardat in historial:
            self.anota(hora, professor, tipus_real(tipus_guardat))

    def anota(self, hora: str, professor: str, tipus: str) -> None:
        self.finestres[hora, prioritat_candidat(tipus)].append(professor)

    def torns(self, candidats: list[tuple[str, str, str]], hora: str) -> list[Fraction]:
        categories = {prioritat_candidat(tipus) for _, tipus, _ in candidats}
        comptes = {categoria: Counter(self.finestres.get((hora, categoria), ())) for categoria in categories}
        return [
            Fraction(comptes[prioritat_candidat(tipus)][professor], pes_de(tipus)) for professor, tipus, _ in candidats
        ]


def escull_candidat_amb_quota(
    candidats: list[tuple[str, str, str]], quota: QuotaFranja, hora: str, rng=random
) -> tuple[str, str, str] | None:
    """Mínim de torns dins la categoria guanyadora; empat ponderat pel pes.

    No anota la tria: qui l'aplica l'afegeix a la finestra compartida.
    Sense atzar, el primer mínim en l'ordre d'entrada és estable.
    """
    if not candidats:
        return None
    torns = quota.torns(candidats, hora)
    minim = min(torns)
    empatats = [c for c, torn in zip(candidats, torns, strict=True) if torn == minim]
    if len(empatats) == 1 or rng is None:
        return empatats[0]
    pesos = [pes_de(tipus) for _, tipus, _ in empatats]
    return rng.choices(empatats, weights=pesos, k=1)[0]


class CandidateValidator:
    """Validador centralitzat per candidats a substitucions"""

    def __init__(
        self,
        professors_ocupats_examens: dict = None,
        substitucions_existents: dict = None,
        rng=None,
        quota: QuotaFranja = None,
    ):
        self.professors_ocupats_examens = professors_ocupats_examens or {}
        self.substitucions_existents = substitucions_existents or {}
        self.rng = random if rng is None else rng
        self.quota = quota if quota is not None else QuotaFranja()

    def _escollir_amb_quota(self, candidats: list[tuple[str, str, str]], hora: str = "") -> tuple[str, str, str] | None:
        """Tria i anota el substitut per a la següent assignació de la franja."""
        escollit = escull_candidat_amb_quota(candidats, self.quota, hora, self.rng)
        if escollit:
            self.quota.anota(hora, escollit[0], escollit[1])
        return escollit


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
        self.omplir = True  # False: no es tria cap substitut nou
        self.avisos = []

    def assignar_substitucions(
        self,
        dia: str,
        absents: dict[str, list[str]],
        grups_sense_classe: set[str] | dict[str, set[str]],
        professors_ocupats_examens: dict[str, list[str]] = None,
        substitucions_existents: dict[str, FilaSubstitucio] = None,
        absents_tipus: dict[str, str] = None,
        omplir: bool = True,
        rng=None,
        quota: QuotaFranja = None,
    ) -> list[PropostaSubstitucio]:
        """Assigna substituts automàticament per hores

        Args:
            grups_sense_classe: Set[str] (antic) o Dict[str, Set[str]] (nou) amb grups per hora
            omplir: si és False, només es conserven els substituts que ja hi havia i les
                files noves queden pendents (es fa servir després d'un canvi del dia:
                no s'assigna ningú sense que l'usuari ho demani)
        """
        self.omplir = omplir
        self.avisos = []

        logger = logging.getLogger(__name__)
        logger.debug(
            f"🔵 assignar_substitucions() START: dia='{dia}', absents={len(absents)}, horari={bool(self.horari)}"
        )

        # Converteix dia de format ISO a nom del dia XML si cal
        if isinstance(dia, str) and len(dia) == 10 and "-" in dia:
            weekday_idx = parse_date(dia).weekday()
            dia = self.horari.get_dia_name(weekday_idx)
            logger.info(_("   🔄 Convertit dia ISO a nom XML: '{}'").format(dia))

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
        self.validator = CandidateValidator(professors_ocupats_examens, substitucions_existents, rng, quota)

        substitucions = self.absencies.get_substitucions_necessaries(dia, absents, absents_tipus)
        logger.debug(_("   📋 get_substitucions_necessaries retorna {} substitucions").format(len(substitucions)))

        # ===== FILTRE GRUPS SENSE CLASSE (per hora específica) =====
        substitucions_filtrades = []
        for sub in substitucions:
            if sub.separador:
                continue
            hora = sub.hora
            grup = sub.grup
            assignatura = sub.assignatura
            grups_hora = self.grups_sense_classe_dict.get(hora, set())
            professor = sub.professor_absent or sub.professor

            # Afegir si:
            # 1. Té grup vàlid i no queda sense classe (grup o professor alliberat), O
            # 2. No té grup però l'assignatura necessita substitució (VP, GP, etc.)
            if grup and not sense_classe(professor, grup, grups_hora):
                substitucions_filtrades.append(sub)
            elif not grup:
                # Activitats sense grup que necessiten substitució (VP, GP, etc.)
                if assignatura not in constants.NO_SUBST and not sense_classe(professor, "", grups_hora):
                    substitucions_filtrades.append(sub)

        # Recomponem la llista: separadors + substitucions filtrades
        substitucions = [sub for sub in substitucions if sub.separador or sub in substitucions_filtrades]
        # =====================================

        # Afegeix substitucions per vigilants amb classe
        substitucions_vigilants = self._generar_substitucions_vigilants(dia, absents)

        # Afegeix les noves substitucions a la llista
        substitucions.extend(substitucions_vigilants)

        # Agrupa substitucions per hora
        substitucions_per_hora = defaultdict(list)
        for sub in substitucions:
            if not sub.separador:
                hora = sub.hora
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
                if not sub.separador:
                    clau = clau_fila(sub.professor_absent, sub.hora, sub.assignatura, sub.grup)
                    claus_existents.add(clau)

                    # Registra substituts actius per hora (per validar encadenades)
                    if sub.substitut:
                        hora = sub.hora
                        if hora not in substituts_actius:
                            substituts_actius[hora] = set()
                        substituts_actius[hora].add(sub.substitut)

            # Afegeix encadenades del JSON que no estan a la llista actual
            encadenades_preservades = 0
            encadenades_descartades = 0
            for clau, dades in self.substitucions_existents.items():
                if dades.tipus_absencia == "ENCADENADA" and clau not in claus_existents:
                    # Reconstrueix la substitució encadenada
                    parts = clau.split("|")
                    if len(parts) == 4:
                        professor_absent = parts[0]
                        hora = parts[1]

                        # Només preserva si el professor_absent és un substitut actiu a aquesta hora
                        if hora in substituts_actius and professor_absent in substituts_actius[hora]:
                            encadenada_preservada = PropostaSubstitucio(
                                professor_absent=professor_absent,
                                hora=hora,
                                assignatura=parts[2],
                                grup=parts[3],
                                tipus_absencia="ENCADENADA",
                                substitut=dades.substitut,
                                tipus_substitut=dades.tipus_substitut,
                                comentaris=dades.comentaris,
                                disponibles=[],
                            )
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

    def _generar_substitucions_vigilants(
        self, dia: str, absents: dict[str, list[str]] = None
    ) -> list[PropostaSubstitucio]:
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
                        if (
                            assignatura  # Assignatura no buida = té classe
                            and grup  # Vigilàncies d'exàmens no tenen grup (grup = "")
                            and not sense_classe(vigilant, grup, self.grups_sense_classe_dict.get(hora, ()))
                        ):
                            # Sempre crea substitució de vigilància (és diferent de l'absència)
                            # La vigilància és una classe/activitat addicional, no la mateixa que l'absència
                            substitucions_vigilants.append(
                                PropostaSubstitucio(
                                    professor=vigilant,
                                    professor_absent=vigilant,
                                    hora=hora,
                                    assignatura=assignatura,
                                    grup=grup,
                                    aula=aula,
                                    substitut="",  # S'assignarà després
                                    tipus_substitut="",
                                    comentaris="",  # Comentaris automàtics eliminats
                                    disponibles=[],  # S'afegiran després
                                    tipus_absencia="VIGILANCIA",  # Marca especial per identificar-la
                                )
                            )

                        # CAS 2: Té activitat de PRIORITATS que NO està a NO_SUBST
                        # (si no està alliberat d'aquesta activitat)
                        elif assignatura and not sense_classe(vigilant, "", self.grups_sense_classe_dict.get(hora, ())):
                            if assignatura in constants.PRIORITATS and assignatura not in constants.NO_SUBST:
                                substitucions_vigilants.append(
                                    PropostaSubstitucio(
                                        professor=vigilant,
                                        professor_absent=vigilant,
                                        hora=hora,
                                        assignatura=assignatura,
                                        grup="",  # Activitats de PRIORITATS no tenen grup
                                        aula=aula,
                                        substitut="",  # S'assignarà després
                                        tipus_substitut="",
                                        comentaris="",
                                        disponibles=[],
                                        tipus_absencia="VIGILANCIA",
                                    )
                                )

            return substitucions_vigilants

        except Exception:
            log.warning("No s'han pogut generar les substitucions dels vigilants", exc_info=True)
            self.avisos.append(
                "No s'han pogut generar les cobertures de classe dels vigilants. Revisa les substitucions pendents."
            )
            return []

    def _assignar_substitucions_per_hora(
        self,
        dia: str,
        hora: str,
        substitucions: list[PropostaSubstitucio],
        grups_sense_classe: set[str],
        absents: dict[str, list[str]],
    ) -> list[PropostaSubstitucio]:
        """Assigna substitucions per una hora específica amb estratègia CONSERVADORA

        Returns:
            List[Dict]: Llista de substitucions encadenades generades
        """

        logger = logging.getLogger(__name__)
        logger.debug(
            _("   🟡 _assignar_substitucions_per_hora(): dia='{}', hora='{}', {} subs").format(
                dia, hora, len(substitucions)
            )
        )

        candidats_per_categoria, ocupats_hora = self._seleccio_candidats_per_hora(
            dia, hora, grups_sense_classe, absents
        )

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
            sub.disponibles = candidats

        # SUBSTITUCIONS ENCADENADES: Genera substitucions per disponibles que ara fan substitució
        substitucions_encadenades = []
        for sub in substitucions:
            activitat = activitat_encadenada(sub.tipus_substitut) if sub.substitut else None
            if activitat:
                substitucions_encadenades.append(
                    PropostaSubstitucio(
                        professor_absent=sub.substitut,
                        hora=hora,
                        assignatura=activitat,
                        grup="",
                        tipus_absencia="ENCADENADA",
                    )
                )

        # Processa substitucions encadenades (només 1 nivell de profunditat)
        for sub_encadenada in substitucions_encadenades:
            self._aplica_assignacio(sub_encadenada, hora, candidats_per_categoria, ocupats_hora, absents)
            sub_encadenada.disponibles = candidats

        if substitucions_encadenades:
            log.debug(f"  🔗 Generades {len(substitucions_encadenades)} substitucions encadenades a {hora}")

        return substitucions_encadenades

    def _ordenar_per_conservacio(
        self, substitucions: list[PropostaSubstitucio], hora: str
    ) -> list[PropostaSubstitucio]:
        """Ordena substitucions prioritzant les que poden tenir conservació"""

        def prioritat_conservacio(sub):
            clau = clau_fila(sub.professor_absent, hora, sub.assignatura, sub.grup)

            # Si existeix als existents, prioritat màxima (0)
            if clau in self.substitucions_existents:
                return 0

            # Si no existeix, prioritat baixa (1)
            return 1

        return sorted(substitucions, key=prioritat_conservacio)

    def _seleccio_candidats_per_hora(
        self, dia: str, hora: str, grups_sense_classe: set[str], absents: dict[str, list[str]]
    ) -> tuple[dict[int, list], set[str]]:
        """Prepara i filtra candidats per una hora específica"""
        disponibles = self.alliberats.get_tots_disponibles(dia, hora, grups_sense_classe)
        # Fora els absents (els que tenen una absència coberta ja no són a l'horari del dia)
        return candidats_per_categoria(disponibles, absents_a_hora(absents, hora)), set()

    def _aplica_assignacio(
        self,
        sub: PropostaSubstitucio,
        hora: str,
        candidats_per_categoria: dict[int, list],
        ocupats_hora: set[str],
        absents: dict[str, list[str]],
    ) -> bool:
        """Aplica assignació conservadora per una substitució individual"""
        professor_absent = sub.professor_absent
        # Crea clau semàntica (sense tipus_absencia per preservar substituts en canvis SERVEI ↔ ABSENCIA)
        clau_exacta = clau_fila(professor_absent, hora, sub.assignatura, sub.grup)

        # CAS 1: una fila que ja existia es conserva tal com és, amb substitut o sense.
        # «Genera pendents» no reescriu les files que ja tenen substitut: si aquí se'n
        # triés un altre, no es desaria i en canvi ocuparia aquell professor per a les
        # pendents de la mateixa hora. Si un substitut desat ja no és vàlid, ho detecten
        # les validacions del PDF i «Reassignar problemàtics», que el treu.
        if clau_exacta in self.substitucions_existents:
            sub_anterior = self.substitucions_existents[clau_exacta]
            substitut_actual = sub_anterior.substitut
            sub.substitut = substitut_actual
            sub.tipus_substitut = sub_anterior.tipus_substitut if substitut_actual else ""
            sub.comentaris = sub_anterior.comentaris
            # Respecta el tipus de la proposta nova (absència, servei, vigilància).
            sub.conservat = True
            if substitut_actual:
                ocupats_hora.add(substitut_actual)
            return True

        if not self.omplir:
            return True

        # CAS 2 & 3: Reassigna òptim immediatament / reoptimitza
        substitut = self._escollir_millor_candidat_disponible(candidats_per_categoria, ocupats_hora, hora)
        if substitut:
            prof, tipus, detall = substitut
            sub.substitut = prof
            sub.tipus_substitut = text_tipus_substitut(tipus, detall)
            ocupats_hora.add(prof)

        return True

    def _escollir_millor_candidat_disponible(
        self, candidats_per_categoria: dict[int, list], ocupats_hora: set[str], hora_actual: str
    ) -> tuple[str, str, str] | None:
        """Escull el millor candidat disponible excloent professors amb vigilàncies"""

        # Obté professors ocupats amb vigilàncies
        professors_vigilancies = set()
        if hasattr(self, "professors_ocupats_examens") and self.professors_ocupats_examens:
            professors_vigilancies = set(self.professors_ocupats_examens.get(hora_actual, []))

        # Llegeix categories actives (checkboxes) des del mòdul

        categories_actives = constants.CATEGORIES_ACTIVES

        candidats_prioritaris = candidats_de_maxima_prioritat(
            candidats_per_categoria,
            categories_actives,
            ocupats_hora | professors_vigilancies,
        )
        return self.validator._escollir_amb_quota(candidats_prioritaris, hora_actual)

    def _obtenir_categoria(self, tipus_activitat: str) -> int:
        """Retorna l'índex de categoria (0 = prioritat màxima)"""
        return prioritat_candidat(tipus_activitat)
