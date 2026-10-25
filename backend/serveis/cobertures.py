"""
Les files que cobreixen la classe d'un vigilant (VIGILANCIA) i les de
vigilant absent (VIGILANCIA_ABSENT): es refan per a una hora quan canvien
les vigilàncies, les absències o els alliberats.
"""

from datetime import datetime

from sqlalchemy import and_

from helpers import get_gestors
from models import Substitucio
from repositories import (
    GrupsAlliberatsRepository,
    SubstitucioRepository,
    parse_date,
)
from serveis.vigilancia_absent import crear_vigilancia_absent
from vigilancies.repositories import VigilanciaRepository


def allibera_substitucions_en_conflicte(data: str, db, hores: set | None = None) -> int:
    """
    Política A: vigilàncies tenen prioritat sobre substitucions.
    Si un professor està assignat com a vigilant a una hora, no pot quedar de substitut a la mateixa hora.
    """
    vigilants_per_hora = {}
    for vigs in VigilanciaRepository.get_by_date(db, data).values():
        for vig in vigs:
            hora, vigilant = (vig.get("hora") or "").strip(), (vig.get("vigilant") or "").strip()
            if hora and vigilant:
                vigilants_per_hora.setdefault(hora, set()).add(vigilant)
    if not vigilants_per_hora:
        return 0

    cleared = 0
    for sub in SubstitucioRepository.get_by_date(db, data):
        sub_id = sub.get("id")
        hora = (sub.get("hora") or "").strip()
        substitut = (sub.get("substitut") or "").strip()
        if not sub_id or not hora or not substitut:
            continue
        if hores is not None and hora not in hores:
            continue
        if substitut in vigilants_per_hora.get(hora, set()):
            SubstitucioRepository.update(db, int(sub_id), {"substitut": "", "tipus_substitut": ""})
            cleared += 1
    return cleared


def refresca_cobertures(data: str, hora: str, db) -> None:
    """Refresca substitucions derivades de vigilàncies per una hora concreta."""
    hora = (hora or "").strip()
    if not hora:
        return

    # Carregar ÚNICAMENT Tipus B (VIGILANCIA): la cobertura de classe
    # Els Tipus A (VIGILANCIA_ABSENT: vigilant absent) es preserven sempre
    existing_subs = (
        db.query(Substitucio)
        .filter(
            and_(
                Substitucio.data == parse_date(data),
                Substitucio.hora == hora,
                Substitucio.tipus_absencia == "VIGILANCIA",
            )
        )
        .all()
    )

    # Restaurar substituts ja assignats als Tipus B
    existing_map = {}
    for sub in existing_subs:
        key = f"{sub.professor_absent}|{sub.hora}|{sub.assignatura or ''}|{sub.grup or ''}"
        existing_map[key] = {
            "substitut": sub.substitut or "",
            "tipus_substitut": sub.tipus_substitut or "",
            "comentaris": sub.comentaris or "",
        }

    if existing_subs:
        ids_cobertura = [s.id for s in existing_subs]
        # Sincronitza la sessió: sense això els objectes esborrats hi quedaven
        # i SQLite reaprofitava els seus IDs per a les substitucions noves.
        db.query(Substitucio).filter(Substitucio.id.in_(ids_cobertura)).delete(synchronize_session="fetch")
        db.commit()

    # Professors absents a aquesta hora (ABSENCIA o SERVEI). La classe d'un
    # vigilant absent la cobreix la seva ABSENCIA, no una VIGILANCIA.
    absents_hora = {
        (s.professor_absent or "").strip()
        for s in db.query(Substitucio)
        .filter(
            and_(
                Substitucio.data == parse_date(data),
                Substitucio.hora == hora,
                Substitucio.tipus_absencia.notin_(["VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT"]),
            )
        )
        .all()
        if (s.professor_absent or "").strip()
    }

    vigilants = VigilanciaRepository.get_vigilants_per_hora(db, data, hora)

    # Eliminar Tipus A (VIGILANCIA_ABSENT) per professors que ja no son vigilants
    tipus_a_hora = (
        db.query(Substitucio)
        .filter(
            and_(
                Substitucio.data == parse_date(data),
                Substitucio.hora == hora,
                Substitucio.tipus_absencia == "VIGILANCIA_ABSENT",
            )
        )
        .all()
    )
    for sub_a in tipus_a_hora:
        if (sub_a.professor_absent or "").strip() not in vigilants:
            db.delete(sub_a)
    if tipus_a_hora:
        db.commit()

    if not vigilants:
        return

    substitucions_mgr, horari, _, _ = get_gestors(data_iso=data)
    date_obj = datetime.strptime(data, "%Y-%m-%d")
    dia_name = horari.get_dia_name(date_obj.weekday())

    grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
    grups_hora = grups_sense_classe.get(hora, [])
    grups_hora = set(grups_hora) if isinstance(grups_hora, list) else set(grups_hora or [])

    substitucions_mgr.professors_ocupats_examens = {hora: set(vigilants)}
    substitucions_mgr.grups_sense_classe_dict = {hora: grups_hora}

    noves = substitucions_mgr._generar_substitucions_vigilants(
        dia_name,
        absents={professor: [hora] for professor in absents_hora},
    )

    for sub in noves:
        if (sub.get("hora") or "").strip() != hora:
            continue
        key = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"
        existent = existing_map.get(key)
        if existent and existent.get("substitut"):
            sub["substitut"] = existent.get("substitut", "")
            sub["tipus_substitut"] = existent.get("tipus_substitut", "")
            sub["comentaris"] = existent.get("comentaris", "")

        SubstitucioRepository.create(
            db,
            {
                "data": data,
                "hora": sub.get("hora", ""),
                "professor_absent": sub.get("professor_absent", ""),
                "assignatura": sub.get("assignatura", ""),
                "grup": sub.get("grup", ""),
                "aula": sub.get("aula", ""),
                "substitut": sub.get("substitut", ""),
                "tipus_substitut": sub.get("tipus_substitut", ""),
                "tipus_absencia": sub.get("tipus_absencia", "VIGILANCIA"),
                "comentaris": sub.get("comentaris", ""),
            },
        )

    # Crear Tipus A (VIGILANCIA_ABSENT) si un vigilant ja és absent a aquesta hora
    tipus_a_existents = {
        (s.professor_absent or "").strip()
        for s in db.query(Substitucio)
        .filter(
            and_(
                Substitucio.data == parse_date(data),
                Substitucio.hora == hora,
                Substitucio.tipus_absencia == "VIGILANCIA_ABSENT",
            )
        )
        .all()
    }
    vigilancies_dia = VigilanciaRepository.get_by_date(db, data)
    for nivell_vigs in vigilancies_dia.values():
        for vig in nivell_vigs:
            vigilant = (vig.get("vigilant") or "").strip()
            if (
                vig.get("hora") == hora
                and vigilant in vigilants
                and vigilant in absents_hora
                and vigilant not in tipus_a_existents
            ):
                crear_vigilancia_absent(db, data, vigilant, hora, vig.get("grups", ""), vig.get("aula", ""))
                tipus_a_existents.add(vigilant)

    # Política A: allibera substitucions en conflicte a aquesta mateixa hora.
    allibera_substitucions_en_conflicte(data, db, {hora})
