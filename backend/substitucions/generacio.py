"""
Generació automàtica de les substitucions d'un dia: llegeix l'estat del dia de
la BD, crida el motor (substitucions/assignacio.py) i desa el que en surt.

Dos modes:
- regenerar tot: s'esborren totes les files del dia (menys les de vigilant
  absent, VIGILANCIA_ABSENT) i es desen les que dona el motor;
- pendents: les files que ja tenen substitut es conserven tal com són i les
  pendents es tornen a fer.
"""

import logging

from horari.domain import Dia
from prioritats.repositories import NoSubstituirRepository
from substitucions.assignacio import QuotaFranja
from substitucions.domain import DiaEscolar
from substitucions.files import PropostaSubstitucio, clau_fila
from substitucions.repositories import SubstitucioRepository
from substitucions.vigilancia_absent import (
    assignar_substituts_pendents as assignar_vigilancies_absents_pendents,
)
from substitucions.vigilancia_absent import (
    es_vigilancia_absent,
)

log = logging.getLogger(__name__)

TIPUS_COBERTURA_VIGILANCIA = ("VIGILANCIA", "VIGILANCIA_ABSENT")


def _ocupats(estat: DiaEscolar) -> dict:
    """Qui no pot substituir per hora: els vigilants i els substituts de les
    files de vigilant absent (perquè el motor no els torni a fer servir)."""
    ocupats = {hora: set(vigilants) for hora, vigilants in estat.vigilants.items()}
    for sub in estat.files:
        if es_vigilancia_absent(sub) and sub.substitut.strip():
            ocupats.setdefault(sub.hora, set()).add(sub.substitut)
    return ocupats


def _fila_nova(data: str, sub: PropostaSubstitucio, substitut: str, tipus_substitut: str) -> dict:
    return {
        "data": data,
        "hora": sub.hora,
        "professor_absent": sub.professor_absent,
        "assignatura": sub.assignatura,
        "grup": sub.grup,
        "aula": sub.aula,
        "substitut": substitut,
        "tipus_substitut": tipus_substitut,
        "tipus_absencia": sub.tipus_absencia,
        "comentaris": sub.comentaris,
    }


def _esborra(db, data: str, regenerar_tot: bool) -> None:
    """Regenerar tot: totes les files menys les de vigilant absent. Pendents:
    les que no tenen substitut, menys les cobertures de vigilància (que es
    reaprofiten a _desa_files_motor)."""
    for sub in SubstitucioRepository.get_by_date(db, data):
        if regenerar_tot:
            esborra = not es_vigilancia_absent(sub)
        else:
            esborra = not sub.substitut and sub.tipus_absencia not in TIPUS_COBERTURA_VIGILANCIA
        if esborra:
            SubstitucioRepository.delete(db, int(sub.id))


def _desa_files_motor(db, data: str, files_motor: list[PropostaSubstitucio], desats: dict) -> None:
    no_substituir = NoSubstituirRepository.vigents_a(db, data)

    # Cobertures de vigilància que han quedat a la BD: les que tenen substitut
    # es deixen; a les pendents s'hi posa el substitut del motor, si n'hi ha.
    cobertures = [s for s in SubstitucioRepository.get_by_date(db, data) if s.tipus_absencia == "VIGILANCIA"]
    cobertes = {clau_fila(s.professor_absent, s.hora, s.assignatura, s.grup) for s in cobertures if s.substitut.strip()}
    cobertures_pendents = {
        clau_fila(s.professor_absent, s.hora, s.assignatura, s.grup): int(s.id)
        for s in cobertures
        if not s.substitut.strip()
    }

    for sub in files_motor:
        clau = clau_fila(sub.professor_absent, sub.hora, sub.assignatura, sub.grup)
        substitut = sub.substitut
        tipus_substitut = sub.tipus_substitut

        if sub.tipus_absencia == "VIGILANCIA":
            if clau in cobertes:
                continue
            if clau in cobertures_pendents:
                if substitut and substitut.strip():
                    SubstitucioRepository.update(
                        db,
                        cobertures_pendents[clau],
                        {
                            "substitut": substitut,
                            "tipus_substitut": tipus_substitut,
                        },
                    )
                continue

        if clau in desats:  # ja és a la BD tal com era
            continue

        # El motor pot assignar substituts a activitats que no cal substituir:
        # es desa l'absència sense substitut.
        if substitut and substitut.strip() and sub.assignatura in no_substituir:
            log.warning(
                f"⚠️ IGNORANT substitució de '{sub.assignatura}' (està a no_substituir): "
                f"{sub.professor_absent} a les {sub.hora} → {substitut}"
            )
            substitut, tipus_substitut = "", ""

        SubstitucioRepository.create(db, _fila_nova(data, sub, substitut, tipus_substitut))


def _desa_hores_sense_substitucio(
    db, estat: DiaEscolar, horari, files_motor: list[PropostaSubstitucio], tambe_bd: bool
) -> None:
    """Desa una fila sense substitut per a les hores d'absència que no han
    generat cap substitució (p. ex. una guàrdia): així es continua sabent que
    el professor és absent. Amb `tambe_bd`, no es repeteixen les que ja són a la BD."""
    hores_desades = {}
    for sub in files_motor:
        if sub.professor_absent and sub.hora:
            hores_desades.setdefault(sub.professor_absent, set()).add(sub.hora)
    if tambe_bd:
        for s in SubstitucioRepository.get_by_date(db, estat.data):
            hores_desades.setdefault(s.professor_absent, set()).add(s.hora)

    for professor, hores in estat.absents.items():
        for hora in hores:
            if hora in hores_desades.get(professor, set()):
                continue
            activitat = horari.get_activitat(estat.nom_del_dia, hora, professor) or {}
            SubstitucioRepository.create(
                db,
                {
                    "data": estat.data,
                    "hora": hora,
                    "professor_absent": professor,
                    "assignatura": activitat.get("assignatura", ""),
                    "grup": activitat.get("grup", ""),
                    "aula": activitat.get("aula", ""),
                    "substitut": "",
                    "tipus_substitut": "",
                    "tipus_absencia": estat.absents_tipus.get(professor, "ABSENCIA"),
                    "comentaris": "",
                },
            )


def _resum(
    db, estat: DiaEscolar, files_motor: list[PropostaSubstitucio], regenerar_tot: bool, avisos: list[str]
) -> dict:
    """Assignades i pendents: les absències, segons el motor (sap quines calen);
    les cobertures de vigilància, segons la BD (totes les que tenen assignatura)."""
    assignades = sum(1 for s in files_motor if s.substitut.strip())
    pendents_detall = [
        {
            "professor": s.professor_absent,
            "hora": s.hora,
            "assignatura": s.assignatura,
            "grup": s.grup,
            "tipus": s.tipus_absencia,
        }
        for s in files_motor
        if not s.substitut.strip()
    ]
    for s in SubstitucioRepository.get_by_date(db, estat.data):
        tipus = s.tipus_absencia
        assignatura = s.assignatura or ""
        if tipus not in TIPUS_COBERTURA_VIGILANCIA or not assignatura:
            continue
        if s.substitut.strip():
            assignades += 1
        else:
            pendents_detall.append(
                {
                    "professor": s.professor_absent,
                    "hora": s.hora,
                    "assignatura": assignatura,
                    "grup": s.grup,
                    "tipus": tipus,
                }
            )

    pendents = len(pendents_detall)
    verb = "Regenerades" if regenerar_tot else "Generades"
    return {
        "success": True,
        "message": f"{verb} substitucions per {estat.nom_del_dia}: {assignades} assignades, {pendents} sense cobertura",
        "total": assignades + pendents,
        "assignades": assignades,
        "pendents": pendents,
        "pendents_detall": pendents_detall,
        "regenerar_tot": regenerar_tot,
        "avisos": avisos,
    }


def genera_substitucions_dia(
    db, dia: Dia, regenerar_tot: bool, omplir: bool = True, rng=None, quota: QuotaFranja = None
) -> dict:
    """Genera i desa les substitucions del Dia. Amb `omplir=False` no es tria
    cap substitut nou, ni per al motor (GestorSubstitucions.assignar_substitucions) ni per a les
    vigilàncies d'un vigilant absent."""
    data = dia.iso
    if quota is None:
        quota = QuotaFranja(SubstitucioRepository.historial_quota(db, data) if omplir else ())
    substitucions_mgr, horari, alliberats, _ = dia.gestors()
    estat = DiaEscolar(db, dia)
    # Les files amb substitut es conserven (només en mode pendents)
    desats = (
        {}
        if regenerar_tot
        else {clau_fila(s.professor_absent, s.hora, s.assignatura, s.grup): s for s in estat.files if s.substitut}
    )

    resultat_motor = substitucions_mgr.assignar_substitucions(
        dia=estat.nom_del_dia,
        absents=estat.absents,
        grups_sense_classe=estat.grups,
        professors_ocupats_examens=_ocupats(estat),
        substitucions_existents=desats,
        absents_tipus=estat.absents_tipus,
        omplir=omplir,
        rng=rng,
        quota=quota,
    )
    files_motor = [s for s in resultat_motor if not s.separador]

    _esborra(db, data, regenerar_tot)
    _desa_files_motor(db, data, files_motor, desats)
    _desa_hores_sense_substitucio(db, estat, horari, files_motor, tambe_bd=not regenerar_tot)

    # Vigilàncies d'un vigilant absent pendents: s'hi assigna substitut
    if estat.absents and omplir:
        assignar_vigilancies_absents_pendents(
            db,
            data,
            estat.nom_del_dia,
            alliberats,
            estat.absents,
            estat.vigilants,
            grups_sense_classe=estat.grups,
            rng=rng,
            quota=quota,
        )

    return _resum(db, estat, files_motor, regenerar_tot, list(getattr(substitucions_mgr, "avisos", [])))
