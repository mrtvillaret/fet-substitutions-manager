"""
Gestió de vigilàncies amb vigilant absent (Tipus A).

Quan un professor absent tenia una vigilància assignada, cal crear una
substitució de tipus VIGILANCIA_ABSENT perquè algú la cobreixi.

Distingim:
  VIGILANCIA_ABSENT (Tipus A): el vigilant és absent → cal cobrir la vigilància
  VIGILANCIA       (Tipus B): cobertura de classe derivada de vigilàncies d'examen

Nota: Anteriorment s'usava assignatura='VIGILÀNCIÀ' com a sentinel (error de
teclat inclòs). Ara s'usa el camp tipus_absencia='VIGILANCIA_ABSENT' directament.
"""

from collections import defaultdict
from collections import defaultdict as _dd

from config import constants
from substitucions.assignacio import CandidateValidator, QuotaFranja, candidats_de_maxima_prioritat
from substitucions.files import FilaSubstitucio
from substitucions.repositories import SubstitucioRepository
from vigilancies.repositories import VigilanciaRepository


def es_vigilancia_absent(sub: FilaSubstitucio) -> bool:
    """Retorna True si el registre és una vigilancia absent (Tipus A)."""
    return (sub.tipus_absencia or "").upper() == "VIGILANCIA_ABSENT"


def crear_vigilancia_absent(db, data: str, professor: str, hora: str, grup: str, aula: str) -> None:
    """Crea un registre de vigilancia absent (Tipus A) a la BD."""
    SubstitucioRepository.create(
        db,
        {
            "data": data,
            "hora": hora,
            "professor_absent": professor,
            "assignatura": "VIGILÀNCIA",
            "grup": grup,
            "aula": aula,
            "substitut": "",
            "tipus_substitut": "",
            "tipus_absencia": "VIGILANCIA_ABSENT",
            "comentaris": "",
        },
    )


def sincronitzar_vigilancies_absents(
    db, data: str, professor: str, substitucions_list: list, hores_actives: set
) -> int:
    """
    Sincronitza els registres Tipus A per a un professor i data:
    - Crea els que falten (professor és vigilant a hora activa i no existia Tipus A)
    - Elimina els obsolets (hora ja no és activa)

    Returns: nombre de registres Tipus A nous creats
    """
    # Detectar Tipus A existents per aquest professor
    tipus_a_existents = {
        s.hora for s in substitucions_list if s.professor_absent == professor and es_vigilancia_absent(s)
    }

    # Crear els que falten
    vigilancies_dia = VigilanciaRepository.get_by_date(db, data)
    creats = 0
    for nivell_vigs in vigilancies_dia.values():
        for vig in nivell_vigs:
            if vig.vigilant == professor and vig.hora in hores_actives and vig.hora not in tipus_a_existents:
                crear_vigilancia_absent(db, data, professor, vig.hora, vig.grups, vig.aula)
                tipus_a_existents.add(vig.hora)
                creats += 1

    # Eliminar els obsolets
    for sub in substitucions_list:
        if sub.professor_absent == professor and es_vigilancia_absent(sub) and sub.hora not in hores_actives:
            SubstitucioRepository.delete(db, int(sub.id))

    return creats


def assignar_substituts_pendents(
    db,
    data: str,
    dia_name: str,
    alliberats,
    absents: dict,
    professors_ocupats: dict,
    grups_sense_classe: dict = None,
    rng=None,
    quota: QuotaFranja = None,
) -> int:
    """
    Assigna substituts als registres Tipus A pendents (vigilant absent → cobrir slot).
    Usa les mateixes categories i la mateixa quota per franja que les substitucions normals.

    Returns: nombre d'assignacions fetes
    """
    all_subs = SubstitucioRepository.get_by_date(db, data)
    absents_set = set(absents.keys())

    pendents = [s for s in all_subs if es_vigilancia_absent(s) and not s.substitut.strip()]
    if not pendents:
        return 0

    # Mapejar substituts ja assignats per hora
    assignats_hora = defaultdict(set)
    for s in all_subs:
        sub_nom = s.substitut
        if sub_nom:
            assignats_hora[s.hora].add(sub_nom)

    assignades = 0
    if quota is None:
        quota = QuotaFranja(SubstitucioRepository.historial_quota(db, data))
    selector = CandidateValidator(rng=rng, quota=quota)
    for pendent in pendents:
        hora = pendent.hora
        prof_absent = pendent.professor_absent
        vigilants_hora = professors_ocupats.get(hora, set())

        grups_hora = set(grups_sense_classe.get(hora, [])) if grups_sense_classe else set()
        disponibles = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)

        def categoria_idx(tipus: str) -> int:
            for i, cat in enumerate(constants.ORDRE_PRIORITATS):
                if tipus in cat:
                    return i
            return len(constants.ORDRE_PRIORITATS)

        # Agrupar candidats per categoria (igual que _escollir_millor_candidat_disponible)

        candidats_per_cat = _dd(list)
        for p, tipus, detall in disponibles:
            if p != prof_absent and p not in absents_set and p not in assignats_hora[hora] and p not in vigilants_hora:
                candidats_per_cat[categoria_idx(tipus)].append((p, tipus, detall))

        # La prioritat i el desempat són dos passos separats, igual que al
        # motor normal de substitucions.
        prioritaris = candidats_de_maxima_prioritat(candidats_per_cat, constants.CATEGORIES_ACTIVES)
        escollit = selector._escollir_amb_quota(prioritaris, hora)
        best = None
        if escollit:
            best, best_tipus, best_detall = escollit

        if not best:
            continue
        tipus_sub = (
            f"disponible ({best_tipus})"
            if best_tipus == best_detall and best_tipus != "alliberat"
            else f"{best_tipus} ({best_detall})"
        )
        SubstitucioRepository.update(
            db,
            int(pendent.id),
            {
                "substitut": best,
                "tipus_substitut": tipus_sub,
            },
        )
        assignats_hora[hora].add(best)
        assignades += 1

    return assignades
