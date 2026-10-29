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
from dataclasses import dataclass
from datetime import datetime

from prioritats.repositories import NoSubstituirRepository
from repositories import GrupsAlliberatsRepository
from substitucions.repositories import SubstitucioRepository
from substitucions.vigilancia_absent import (
    assignar_substituts_pendents as assignar_vigilancies_absents_pendents,
)
from substitucions.vigilancia_absent import (
    es_vigilancia_absent,
)
from vigilancies.repositories import VigilanciaRepository

log = logging.getLogger(__name__)

# Files que no són absències d'un professor (es gestionen a part)
TIPUS_NO_ABSENCIA = ("VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT")
TIPUS_COBERTURA_VIGILANCIA = ("VIGILANCIA", "VIGILANCIA_ABSENT")


def clau_fila(sub: dict) -> str:
    return f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"


@dataclass
class EstatDia:
    """El que el motor necessita saber d'un dia, tal com és a la BD."""

    data: str
    dia: str  # nom del dia a l'XML
    files: list  # files de substitució desades
    absents: dict  # {professor: [hores]}: absències i serveis
    absents_tipus: dict  # {professor: "ABSENCIA" | "SERVEI"}
    activitats_fallback: dict  # {(professor, hora): activitat desada}
    grups: dict  # {hora: set()}: alliberats efectius
    vigilants: dict  # {hora: set()}: qui vigila un examen


def llegeix_estat(db, data: str, horari) -> EstatDia:
    files = SubstitucioRepository.get_by_date(db, data)

    absents, absents_tipus, activitats_fallback = {}, {}, {}
    for sub in files:
        professor = sub.get("professor_absent", "")
        hora = sub.get("hora", "")
        tipus = sub.get("tipus_absencia", "") or "ABSENCIA"
        if tipus in TIPUS_NO_ABSENCIA or not professor or not hora:
            continue
        if professor not in absents:
            absents[professor] = []
            absents_tipus[professor] = tipus
        if hora not in absents[professor]:
            absents[professor].append(hora)
        activitats_fallback.setdefault(
            (professor, hora),
            {
                "assignatura": sub.get("assignatura", ""),
                "grup": sub.get("grup", ""),
                "aula": sub.get("aula", ""),
            },
        )

    grups = {
        hora: set(valors) if isinstance(valors, list) else valors
        for hora, valors in GrupsAlliberatsRepository.get_by_date(db, data).items()
    }

    vigilants = {}
    for vigs in VigilanciaRepository.get_by_date(db, data).values():
        for vig in vigs:
            if vig.get("hora") and vig.get("vigilant"):
                vigilants.setdefault(vig["hora"], set()).add(vig["vigilant"])

    dia = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
    return EstatDia(data, dia, files, absents, absents_tipus, activitats_fallback, grups, vigilants)


def _ocupats(estat: EstatDia) -> dict:
    """Qui no pot substituir per hora: els vigilants i els substituts de les
    files de vigilant absent (perquè el motor no els torni a fer servir)."""
    ocupats = {hora: set(vigilants) for hora, vigilants in estat.vigilants.items()}
    for sub in estat.files:
        if es_vigilancia_absent(sub) and sub.get("substitut", "").strip():
            ocupats.setdefault(sub.get("hora", ""), set()).add(sub["substitut"])
    return ocupats


def _fila_nova(data: str, sub: dict, substitut: str, tipus_substitut: str) -> dict:
    return {
        "data": data,
        "hora": sub.get("hora", ""),
        "professor_absent": sub.get("professor_absent", ""),
        "assignatura": sub.get("assignatura", ""),
        "grup": sub.get("grup", ""),
        "aula": sub.get("aula", ""),
        "substitut": substitut,
        "tipus_substitut": tipus_substitut,
        "tipus_absencia": sub.get("tipus_absencia", ""),
        "comentaris": sub.get("comentaris", ""),
    }


def _esborra(db, data: str, regenerar_tot: bool) -> None:
    """Regenerar tot: totes les files menys les de vigilant absent. Pendents:
    les que no tenen substitut, menys les cobertures de vigilància (que es
    reaprofiten a _desa_files_motor)."""
    for sub in SubstitucioRepository.get_by_date(db, data):
        if regenerar_tot:
            esborra = not es_vigilancia_absent(sub)
        else:
            esborra = not sub.get("substitut") and sub.get("tipus_absencia") not in TIPUS_COBERTURA_VIGILANCIA
        if esborra:
            SubstitucioRepository.delete(db, int(sub["id"]))


def _desa_files_motor(db, data: str, files_motor: list, desats: dict) -> None:
    no_substituir = NoSubstituirRepository.get_all(db)

    # Cobertures de vigilància que han quedat a la BD: les que tenen substitut
    # es deixen; a les pendents s'hi posa el substitut del motor, si n'hi ha.
    cobertures = [s for s in SubstitucioRepository.get_by_date(db, data) if s.get("tipus_absencia") == "VIGILANCIA"]
    cobertes = {clau_fila(s) for s in cobertures if s.get("substitut", "").strip()}
    cobertures_pendents = {clau_fila(s): int(s["id"]) for s in cobertures if not s.get("substitut", "").strip()}

    for sub in files_motor:
        clau = clau_fila(sub)
        substitut = sub.get("substitut", "")
        tipus_substitut = sub.get("tipus_substitut", "")

        if sub.get("tipus_absencia") == "VIGILANCIA":
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
        if substitut and substitut.strip() and sub.get("assignatura", "") in no_substituir:
            log.warning(
                f"⚠️ IGNORANT substitució de '{sub.get('assignatura', '')}' (està a no_substituir): "
                f"{sub.get('professor_absent')} a les {sub.get('hora')} → {substitut}"
            )
            substitut, tipus_substitut = "", ""

        SubstitucioRepository.create(db, _fila_nova(data, sub, substitut, tipus_substitut))


def _desa_hores_sense_substitucio(db, estat: EstatDia, horari, files_motor: list, tambe_bd: bool) -> None:
    """Desa una fila sense substitut per a les hores d'absència que no han
    generat cap substitució (p. ex. una guàrdia): així es continua sabent que
    el professor és absent. Amb `tambe_bd`, no es repeteixen les que ja són a la BD."""
    hores_desades = {}
    for sub in files_motor:
        if sub.get("professor_absent", "") and sub.get("hora", ""):
            hores_desades.setdefault(sub["professor_absent"], set()).add(sub["hora"])
    if tambe_bd:
        for s in SubstitucioRepository.get_by_date(db, estat.data):
            hores_desades.setdefault(s.get("professor_absent", ""), set()).add(s.get("hora", ""))

    for professor, hores in estat.absents.items():
        for hora in hores:
            if hora in hores_desades.get(professor, set()):
                continue
            activitat = horari.get_activitat(estat.dia, hora, professor) or {}
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


def _resum(db, estat: EstatDia, files_motor: list, regenerar_tot: bool, avisos: list[str]) -> dict:
    """Assignades i pendents: les absències, segons el motor (sap quines calen);
    les cobertures de vigilància, segons la BD (totes les que tenen assignatura)."""
    assignades = sum(1 for s in files_motor if s.get("substitut", "").strip())
    pendents_detall = [
        {
            "professor": s.get("professor_absent", ""),
            "hora": s.get("hora", ""),
            "assignatura": s.get("assignatura", ""),
            "grup": s.get("grup", ""),
            "tipus": s.get("tipus_absencia", ""),
        }
        for s in files_motor
        if not s.get("substitut", "").strip()
    ]
    for s in SubstitucioRepository.get_by_date(db, estat.data):
        tipus = s.get("tipus_absencia", "")
        assignatura = s.get("assignatura", "") or ""
        if tipus not in TIPUS_COBERTURA_VIGILANCIA or not assignatura:
            continue
        if s.get("substitut", "").strip():
            assignades += 1
        else:
            pendents_detall.append(
                {
                    "professor": s.get("professor_absent", ""),
                    "hora": s.get("hora", ""),
                    "assignatura": assignatura,
                    "grup": s.get("grup", ""),
                    "tipus": tipus,
                }
            )

    pendents = len(pendents_detall)
    verb = "Regenerades" if regenerar_tot else "Generades"
    return {
        "success": True,
        "message": f"{verb} substitucions per {estat.dia}: {assignades} assignades, {pendents} sense cobertura",
        "total": assignades + pendents,
        "assignades": assignades,
        "pendents": pendents,
        "pendents_detall": pendents_detall,
        "regenerar_tot": regenerar_tot,
        "avisos": avisos,
    }


def genera_substitucions_dia(db, data: str, gestors, regenerar_tot: bool, omplir: bool = True) -> dict:
    """Genera i desa les substitucions d'un dia. `gestors`: el que retorna
    helpers.get_gestors. Amb `omplir=False` no es tria cap substitut nou, ni
    per al motor (GestorSubstitucions.assignar_substitucions) ni per a les
    vigilàncies d'un vigilant absent."""
    substitucions_mgr, horari, alliberats, _ = gestors
    estat = llegeix_estat(db, data, horari)
    # Les files amb substitut es conserven (només en mode pendents)
    desats = {} if regenerar_tot else {clau_fila(s): s for s in estat.files if s.get("substitut")}

    resultat_motor = substitucions_mgr.assignar_substitucions(
        dia=estat.dia,
        absents=estat.absents,
        grups_sense_classe=estat.grups,
        professors_ocupats_examens=_ocupats(estat),
        substitucions_existents=desats,
        absents_tipus=estat.absents_tipus,
        activitats_fallback=estat.activitats_fallback,
        omplir=omplir,
    )
    files_motor = [s for s in resultat_motor if not s.get("separador")]

    _esborra(db, data, regenerar_tot)
    _desa_files_motor(db, data, files_motor, desats)
    _desa_hores_sense_substitucio(db, estat, horari, files_motor, tambe_bd=not regenerar_tot)

    # Vigilàncies d'un vigilant absent pendents: s'hi assigna substitut
    if estat.absents and omplir:
        assignar_vigilancies_absents_pendents(
            db,
            data,
            estat.dia,
            alliberats,
            estat.absents,
            estat.vigilants,
            grups_sense_classe=estat.grups,
        )

    return _resum(db, estat, files_motor, regenerar_tot, list(getattr(substitucions_mgr, "avisos", [])))
