"""
Les files que cobreixen la classe d'un vigilant (VIGILANCIA) i les de
vigilant absent (VIGILANCIA_ABSENT): es refan per a una hora quan canvien
les vigilàncies, les absències o els alliberats.
"""

from datetime import datetime

from grups.lectures import AlliberatsDelDia
from substitucions.context import get_gestors
from substitucions.files import FilaSubstitucio
from substitucions.repositories import SubstitucioRepository
from substitucions.vigilancia_absent import crear_vigilancia_absent
from vigilancies.repositories import VigilanciaRepository


def allibera_substitucions_en_conflicte(data: str, db, hores: set | None = None) -> int:
    """
    Política A: vigilàncies tenen prioritat sobre substitucions.
    Si un professor està assignat com a vigilant a una hora, no pot quedar de substitut a la mateixa hora.
    """
    vigilants_per_hora = {}
    for vigs in VigilanciaRepository.get_by_date(db, data).values():
        for vig in vigs:
            hora, vigilant = (vig.hora or "").strip(), (vig.vigilant or "").strip()
            if hora and vigilant:
                vigilants_per_hora.setdefault(hora, set()).add(vigilant)
    if not vigilants_per_hora:
        return 0

    cleared = 0
    for sub in SubstitucioRepository.get_by_date(db, data):
        sub_id = sub.id
        hora = (sub.hora or "").strip()
        substitut = (sub.substitut or "").strip()
        if not sub_id or not hora or not substitut:
            continue
        if hores is not None and hora not in hores:
            continue
        if substitut in vigilants_per_hora.get(hora, set()):
            SubstitucioRepository.update(db, int(sub_id), {"substitut": "", "tipus_substitut": ""})
            cleared += 1
    return cleared


def refresca_cobertures(data: str, hora: str, db, gestors=None) -> None:
    """Refresca substitucions derivades de vigilàncies per una hora concreta."""
    hora = (hora or "").strip()
    if not hora:
        return

    # Carregar ÚNICAMENT Tipus B (VIGILANCIA): la cobertura de classe
    # Els Tipus A (VIGILANCIA_ABSENT: vigilant absent) es preserven sempre
    existing_subs = SubstitucioRepository.get_by_date_hour_and_type(db, data, hora, "VIGILANCIA")

    # Restaurar substituts ja assignats als Tipus B
    existing_map = {}
    for sub in existing_subs:
        key = f"{sub.professor_absent}|{sub.hora}|{sub.assignatura or ''}|{sub.grup or ''}"
        existing_map[key] = FilaSubstitucio(
            substitut=sub.substitut or "",
            tipus_substitut=sub.tipus_substitut or "",
            comentaris=sub.comentaris or "",
        )

    if existing_subs:
        ids_cobertura = [s.id for s in existing_subs]
        # Sincronitza la sessió: sense això els objectes esborrats hi quedaven
        # i SQLite reaprofitava els seus IDs per a les substitucions noves.
        SubstitucioRepository.delete_by_ids(db, ids_cobertura)
        db.flush()

    # Professors absents a aquesta hora (ABSENCIA o SERVEI). La classe d'un
    # vigilant absent la cobreix la seva ABSENCIA, no una VIGILANCIA.
    absents_hora = {
        (s.professor_absent or "").strip()
        for s in SubstitucioRepository.get_absences_by_date_and_hour(db, data, hora)
        if (s.professor_absent or "").strip()
    }

    vigilants = VigilanciaRepository.get_vigilants_per_hora(db, data, hora)

    # Eliminar Tipus A (VIGILANCIA_ABSENT) per professors que ja no son vigilants
    tipus_a_hora = SubstitucioRepository.get_by_date_hour_and_type(db, data, hora, "VIGILANCIA_ABSENT")
    for sub_a in tipus_a_hora:
        if (sub_a.professor_absent or "").strip() not in vigilants:
            db.delete(sub_a)
    if tipus_a_hora:
        db.flush()

    if not vigilants:
        return

    substitucions_mgr, horari, _, _ = gestors or get_gestors(db.info.get("institucio"), data_iso=data)
    date_obj = datetime.strptime(data, "%Y-%m-%d")
    dia_name = horari.get_dia_name(date_obj.weekday())

    grups_sense_classe = AlliberatsDelDia.get_by_date(db, data)
    grups_hora = grups_sense_classe.get(hora, [])
    grups_hora = set(grups_hora) if isinstance(grups_hora, list) else set(grups_hora or [])

    substitucions_mgr.professors_ocupats_examens = {hora: set(vigilants)}
    substitucions_mgr.grups_sense_classe_dict = {hora: grups_hora}

    noves = substitucions_mgr._generar_substitucions_vigilants(
        dia_name,
        absents={professor: [hora] for professor in absents_hora},
    )

    for sub in noves:
        if (sub.hora or "").strip() != hora:
            continue
        key = f"{sub.professor_absent}|{sub.hora}|{sub.assignatura}|{sub.grup}"
        existent = existing_map.get(key)
        if existent and existent.substitut:
            sub.substitut = existent.substitut
            sub.tipus_substitut = existent.tipus_substitut
            sub.comentaris = existent.comentaris

        SubstitucioRepository.create(
            db,
            {
                "data": data,
                "hora": sub.hora,
                "professor_absent": sub.professor_absent,
                "assignatura": sub.assignatura,
                "grup": sub.grup,
                "aula": sub.aula,
                "substitut": sub.substitut,
                "tipus_substitut": sub.tipus_substitut,
                "tipus_absencia": sub.tipus_absencia,
                "comentaris": sub.comentaris,
            },
        )

    # Crear Tipus A (VIGILANCIA_ABSENT) si un vigilant ja és absent a aquesta hora
    tipus_a_existents = {
        (s.professor_absent or "").strip()
        for s in SubstitucioRepository.get_by_date_hour_and_type(db, data, hora, "VIGILANCIA_ABSENT")
    }
    vigilancies_dia = VigilanciaRepository.get_by_date(db, data)
    for nivell_vigs in vigilancies_dia.values():
        for vig in nivell_vigs:
            vigilant = (vig.vigilant or "").strip()
            if (
                vig.hora == hora
                and vigilant in vigilants
                and vigilant in absents_hora
                and vigilant not in tipus_a_existents
            ):
                crear_vigilancia_absent(db, data, vigilant, hora, vig.grups, vig.aula)
                tipus_a_existents.add(vigilant)

    # Política A: allibera substitucions en conflicte a aquesta mateixa hora.
    allibera_substitucions_en_conflicte(data, db, {hora})
