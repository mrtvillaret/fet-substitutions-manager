"""
Les files que cobreixen la classe d'un vigilant (VIGILANCIA) i les de
vigilant absent (VIGILANCIA_ABSENT): es refan per a una hora quan canvien
les vigilàncies, les absències o els alliberats.
"""

from datetime import date

from grups.lectures import AlliberatsDelDia
from horari.domain import Dia
from substitucions.context import get_gestors
from substitucions.domain import DiaEscolar
from substitucions.encadenades import reconcilia_encadenades
from substitucions.files import clau_fila, fila_de_proposta
from substitucions.repositories import SubstitucioRepository
from substitucions.vigilancia_absent import crear_vigilancia_absent
from vigilancies.repositories import VigilanciaRepository


def _treu_vigilants_substituts(data: date, hora: str, db) -> None:
    """Un vigilant no substitueix a la mateixa hora (DiaEscolar.motius_substitut):
    se li treu la substitució i les encadenades es tornen a reconciliar."""
    dia = DiaEscolar(db, Dia.del_centre(data, db.info.get("institucio")))
    for fila in dia.files:
        substitut = fila.substitut
        if (
            (fila.hora or "").strip() == hora
            and substitut
            and dia.motius_substitut(substitut, hora, nomes={"vigilancia"})
        ):
            SubstitucioRepository.update(db, int(fila.id), {"substitut": "", "tipus_substitut": ""})
    reconcilia_encadenades(db, data)


def refresca_cobertures(data: date, hora: str, db, gestors=None) -> None:
    """Refresca substitucions derivades de vigilàncies per una hora concreta.

    Les cobertures de classe (VIGILANCIA) es refan per diferències amb la clau
    de fila: les que continuen conserven id, versió, substitut i comentaris (si
    l'aula de l'horari ha canviat, només s'hi actualitza l'aula); les que sobren
    s'esborren i les que falten es creen. Si el càlcul falla, l'error arriba a
    qui ha cridat abans d'haver tocat cap fila."""
    hora = (hora or "").strip()
    if not hora:
        return

    existents, repetides = {}, []
    for sub in SubstitucioRepository.get_by_date_hour_and_type(db, data, hora, "VIGILANCIA"):
        clau = clau_fila(sub.professor_absent, sub.hora, sub.assignatura or "", sub.grup or "")
        if existents.setdefault(clau, sub) is not sub:
            repetides.append(sub.id)

    # Professors absents a aquesta hora (ABSENCIA o SERVEI). La classe d'un
    # vigilant absent la cobreix la seva ABSENCIA, no una VIGILANCIA.
    absents_hora = {
        s.professor_absent
        for s in SubstitucioRepository.get_absences_by_date_and_hour(db, data, hora)
        if s.professor_absent
    }

    vigilants = VigilanciaRepository.get_vigilants_per_hora(db, data, hora)
    noves = _cobertures_noves(data, hora, db, gestors, vigilants, absents_hora) if vigilants else {}

    sobrants = repetides + [sub.id for clau, sub in existents.items() if clau not in noves]
    if sobrants:
        SubstitucioRepository.delete_by_ids(db, sobrants)
        db.flush()
    for clau, sub in noves.items():
        existent = existents.get(clau)
        if existent is None:
            SubstitucioRepository.create(db, fila_de_proposta(data, sub))
        elif (existent.aula or "") != (sub.aula or ""):
            SubstitucioRepository.update(db, existent.id, {"aula": sub.aula})

    # Eliminar Tipus A (VIGILANCIA_ABSENT) per professors que ja no son vigilants
    tipus_a_hora = SubstitucioRepository.get_by_date_hour_and_type(db, data, hora, "VIGILANCIA_ABSENT")
    sense_vigilancia = [s.id for s in tipus_a_hora if s.professor_absent not in vigilants]
    if sense_vigilancia:
        SubstitucioRepository.delete_by_ids(db, sense_vigilancia)
    if tipus_a_hora:
        db.flush()

    if not vigilants:
        return

    # Tipus A (VIGILANCIA_ABSENT) d'un vigilant absent a aquesta hora: es crea
    # amb la seva primera vigilància de l'hora i, si ja no coincideix amb cap
    # de les seves vigilàncies (s'ha canviat l'aula o el grup), en pren el grup
    # i l'aula. El substitut es conserva.
    tipus_a_existents = {}
    for s in SubstitucioRepository.get_by_date_hour_and_type(db, data, hora, "VIGILANCIA_ABSENT"):
        tipus_a_existents.setdefault(s.professor_absent, s)
    vigilancies_absents: dict[str, list] = {}
    for nivell_vigs in VigilanciaRepository.get_by_date(db, data).values():
        for vig in nivell_vigs:
            vigilant = vig.vigilant
            if vig.hora == hora and vigilant in vigilants and vigilant in absents_hora:
                vigilancies_absents.setdefault(vigilant, []).append(vig)
    for vigilant, vigs in vigilancies_absents.items():
        primera = vigs[0]
        existent = tipus_a_existents.get(vigilant)
        if existent is None:
            crear_vigilancia_absent(db, data, vigilant, hora, primera.grups, primera.aula)
        elif (existent.grup, existent.aula) not in {(v.grups, v.aula) for v in vigs}:
            SubstitucioRepository.update(db, existent.id, {"grup": primera.grups, "aula": primera.aula})

    # Política A: les vigilàncies tenen prioritat sobre les substitucions.
    _treu_vigilants_substituts(data, hora, db)


def _cobertures_noves(data: date, hora: str, db, gestors, vigilants: list, absents_hora: set) -> dict:
    """Les cobertures de classe que demana l'horari a l'hora, per clau de fila."""
    substitucions_mgr, horari, _, _ = gestors or get_gestors(db.info.get("institucio"), data_iso=data)
    grups_hora = AlliberatsDelDia.get_by_date(db, data).get(hora, [])
    substitucions_mgr.professors_ocupats_examens = {hora: set(vigilants)}
    substitucions_mgr.grups_sense_classe_dict = {hora: set(grups_hora or [])}
    noves = substitucions_mgr.cobertures_de_vigilants(
        horari.get_dia_name(data.weekday()),
        absents={professor: [hora] for professor in absents_hora},
    )
    return {
        clau_fila(sub.professor_absent, sub.hora, sub.assignatura, sub.grup): sub
        for sub in noves
        if (sub.hora or "").strip() == hora
    }
