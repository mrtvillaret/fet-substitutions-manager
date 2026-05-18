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
from repositories import SubstitucioRepository, VigilanciaRepository
from config import constants


def es_vigilancia_absent(sub: dict) -> bool:
    """Retorna True si el registre és una vigilancia absent (Tipus A)."""
    return (sub.get('tipus_absencia') or '').upper() == 'VIGILANCIA_ABSENT'


def crear_vigilancia_absent(db, data: str, professor: str,
                             hora: str, grup: str, aula: str) -> None:
    """Crea un registre de vigilancia absent (Tipus A) a la BD."""
    SubstitucioRepository.create(db, {
        'data': data,
        'hora': hora,
        'professor_absent': professor,
        'assignatura': 'VIGILÀNCIA',
        'grup': grup,
        'aula': aula,
        'substitut': '',
        'tipus_substitut': '',
        'tipus_absencia': 'VIGILANCIA_ABSENT',
        'comentaris': '',
    })


def sincronitzar_vigilancies_absents(db, data: str, professor: str,
                                      substitucions_list: list,
                                      hores_actives: set) -> int:
    """
    Sincronitza els registres Tipus A per a un professor i data:
    - Crea els que falten (professor és vigilant a hora activa i no existia Tipus A)
    - Elimina els obsolets (hora ja no és activa)

    Returns: nombre de registres Tipus A nous creats
    """
    # Detectar Tipus A existents per aquest professor
    tipus_a_existents = {
        s.get('hora')
        for s in substitucions_list
        if s.get('professor_absent') == professor and es_vigilancia_absent(s)
    }

    # Crear els que falten
    vigilancies_dia = VigilanciaRepository.get_by_date(db, data)
    creats = 0
    for nivell_vigs in vigilancies_dia.values():
        for vig in nivell_vigs:
            if (vig.get('vigilant') == professor
                    and vig.get('hora') in hores_actives
                    and vig.get('hora') not in tipus_a_existents):
                crear_vigilancia_absent(
                    db, data, professor,
                    vig.get('hora'), vig.get('grups', ''), vig.get('aula', '')
                )
                tipus_a_existents.add(vig.get('hora'))
                creats += 1
                print(f"   Vigilancia absent creada: {professor} a les {vig.get('hora')}")

    # Eliminar els obsolets
    for sub in substitucions_list:
        if (sub.get('professor_absent') == professor
                and es_vigilancia_absent(sub)
                and sub.get('hora') not in hores_actives):
            SubstitucioRepository.delete(db, int(sub['id']))

    return creats


def assignar_substituts_pendents(db, data: str, dia_name: str, alliberats,
                                  absents: dict, professors_ocupats: dict,
                                  grups_sense_classe: dict = None) -> int:
    """
    Assigna substituts als registres Tipus A pendents (vigilant absent → cobrir slot).
    Usa la mateixa lògica de prioritats (ORDRE_PRIORITATS) que les substitucions normals.

    Returns: nombre d'assignacions fetes
    """
    all_subs = SubstitucioRepository.get_by_date(db, data)
    absents_set = set(absents.keys())

    pendents = [s for s in all_subs
                if es_vigilancia_absent(s)
                and not s.get('substitut', '').strip()]
    if not pendents:
        return 0

    # Mapejar substituts ja assignats per hora
    assignats_hora = defaultdict(set)
    for s in all_subs:
        sub_nom = s.get('substitut', '')
        if sub_nom:
            assignats_hora[s.get('hora', '')].add(sub_nom)

    assignades = 0
    for pendent in pendents:
        hora = pendent.get('hora', '')
        prof_absent = pendent.get('professor_absent', '')
        vigilants_hora = professors_ocupats.get(hora, set())

        grups_hora = set(grups_sense_classe.get(hora, [])) if grups_sense_classe else set()
        disponibles = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)

        def categoria_idx(tipus: str) -> int:
            for i, cat in enumerate(constants.ORDRE_PRIORITATS):
                if tipus in cat:
                    return i
            return len(constants.ORDRE_PRIORITATS)

        # Agrupar candidats per categoria (igual que _escollir_millor_candidat_disponible)
        from collections import defaultdict as _dd
        candidats_per_cat = _dd(list)
        for p, tipus, detall in disponibles:
            if (p != prof_absent
                    and p not in absents_set
                    and p not in assignats_hora[hora]
                    and p not in vigilants_hora):
                candidats_per_cat[categoria_idx(tipus)].append((p, tipus, detall))

        # Escollir primer candidat de la categoria activa amb prioritat més alta
        best = None
        for cat_i in sorted(candidats_per_cat.keys()):
            if cat_i < len(constants.CATEGORIES_ACTIVES) and not constants.CATEGORIES_ACTIVES[cat_i]:
                continue  # Categoria inactiva → saltar
            disponibles_cat = candidats_per_cat[cat_i]
            if disponibles_cat:
                best, best_tipus, best_detall = disponibles_cat[0]
                break

        if not best:
            continue
        tipus_sub = (f"disponible ({best_tipus})" if best_tipus == best_detall and best_tipus != "alliberat"
                     else f"{best_tipus} ({best_detall})")
        SubstitucioRepository.update(db, int(pendent['id']), {
            'substitut': best,
            'tipus_substitut': tipus_sub,
        })
        assignats_hora[hora].add(best)
        assignades += 1
        print(f"   Vigilancia absent assignada: {prof_absent} a les {hora} → {best} [{tipus_sub}]")

    return assignades
