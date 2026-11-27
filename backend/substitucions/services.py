"""Casos d'ús de les substitucions d'un dia, sense dependències HTTP."""

import logging
import random
from datetime import datetime

from sqlalchemy.orm import Session

from absencia_coberta.domain import absencia_coberta_de, missatge_absencia_coberta
from database import inicia_escriptura
from errors_domini import Conflicte, NoTrobat, NoValid
from grups.lectures import AlliberatsDelDia
from horari.domain import Dia
from i18n_setup import translate as _
from parametres import data_iso
from prioritats.repositories import NoSubstituirRepository
from substitucions import _consultes
from substitucions.absencies import desa_absencies
from substitucions.assignacio import QuotaFranja, text_tipus_substitut
from substitucions.domain import DiaEscolar
from substitucions.encadenades import reconcilia_encadenades
from substitucions.files import FilaSubstitucio
from substitucions.generacio import genera_substitucions_dia
from substitucions.prioritat import MillorsSubstituts
from substitucions.reconciliacio import treu_substituts_no_valids
from substitucions.repositories import SubstitucioRepository
from substitucions.vigilancia_absent import es_vigilancia_absent

log = logging.getLogger(__name__)


class ConflicteSubstitucions(Conflicte):
    """Conflicte optimista que inclou la versió actual per a la pantalla."""

    def __init__(self, current_data: FilaSubstitucio | list[FilaSubstitucio]):
        super().__init__(
            "Aquest registre ha estat modificat per un altre usuari",
            codi="substitucio_modificada",
        )
        self.current_data = current_data


llista_substitucions = _consultes.llista_substitucions
hores_professor = _consultes.hores_professor
disponibles = _consultes.disponibles
disponibles_en_bloc = _consultes.disponibles_en_bloc


def _atzar():
    """Atzar dels empats de quota; els tests poden injectar-hi un generador."""
    return random


def genera_substitucions(
    db: Session,
    dia: Dia,
    data: str,
    *,
    regenerar_tot: bool,
    omplir: bool,
) -> dict:
    data_iso(data)
    resultat = genera_substitucions_dia(db, dia, regenerar_tot, omplir, rng=_atzar())
    db.commit()
    return resultat


def actualitza_absencies(db: Session, dia: Dia, data: str, professor: str, update) -> dict:
    data_iso(data)
    _, horari, _, absencies = dia.gestors()
    dia_name = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
    substitucions_list = SubstitucioRepository.get_by_date(db, data)

    if not update.force and update.updated_at_map is None:
        raise NoValid(
            "Falta el camp updated_at_map per comprovar conflictes",
            codi="falta_updated_at_map",
        )

    if not update.force and update.updated_at_map:
        conflictes = []
        for sub in substitucions_list:
            if sub.professor_absent != professor or es_vigilancia_absent(sub):
                continue
            hora_sub = sub.hora
            if hora_sub in update.updated_at_map:
                client_updated_at = update.updated_at_map.get(hora_sub)
                server_updated_at = sub.updated_at
                if client_updated_at and server_updated_at and client_updated_at != server_updated_at:
                    conflictes.append(sub)
        if conflictes:
            raise ConflicteSubstitucions(conflictes)

    if (update.hores_absencia or update.hores_servei) and (baixa := absencia_coberta_de(db, professor, data)):
        raise NoValid(
            missatge_absencia_coberta(professor, baixa),
            codi="professor_amb_absencia_coberta",
        )

    if not update.force and update.updated_at_map:
        # Els UPDATE sense canvi comproven les versions i retenen el bloqueig
        # d'escriptura fins al commit de tota l'operació d'absències.
        for sub in substitucions_list:
            if sub.professor_absent != professor or es_vigilancia_absent(sub):
                continue
            esperat = update.updated_at_map.get(sub.hora)
            if esperat and SubstitucioRepository.update(db, int(sub.id), {}, updated_at_esperat=esperat) is None:
                db.rollback()
                actuals = [s for s in SubstitucioRepository.get_by_date(db, data) if s.professor_absent == professor]
                raise ConflicteSubstitucions(actuals)

    resultat = desa_absencies(
        db,
        data,
        professor,
        update.hores_absencia,
        update.hores_servei,
        gestors=(horari, absencies),
        dia_name=dia_name,
    )
    db.commit()
    return {
        "success": True,
        "message": f"Absències de {professor} actualitzades (multi-tipus)",
        **resultat,
    }


def _rebutja_motius_manual(motius: list, substitut: str, hora: str) -> None:
    """Tradueix els motius comuns als codis i textos històrics de la tria manual."""
    for motiu in motius:
        match motiu["motiu"]:
            case "fora_horari":
                raise NoValid(
                    _("❌ {substitut} no és un professor de l’horari d’aquell dia").format(substitut=substitut),
                    codi="substitut_fora_horari",
                    params={"substitut": substitut},
                )
            case "vigilancia":
                raise NoValid(
                    f"❌ {substitut} ja està assignat com a VIGILANT a les {hora}",
                    codi="substitut_vigilant",
                    params={"substitut": substitut, "hora": hora},
                )
            case "absent":
                raise NoValid(
                    f"❌ {substitut} està ABSENT a les {hora}!",
                    codi="substitut_absent",
                    params={"substitut": substitut, "hora": hora},
                )
            case "baixa":
                raise NoValid(
                    f"❌ {substitut} té una ABSÈNCIA COBERTA aquell dia!",
                    codi="substitut_amb_absencia_coberta",
                    params={"substitut": substitut},
                )
            case "classe":
                raise NoValid(
                    f"⚠️ {substitut} té CLASSE a les {hora} ({motiu['classe_assignatura']}, {motiu['classe_grup']})",
                    codi="substitut_amb_classe",
                    params={
                        "substitut": substitut,
                        "hora": hora,
                        "assignatura": motiu["classe_assignatura"],
                        "grup": motiu["classe_grup"],
                    },
                )


def actualitza_substitut(db: Session, dia: Dia, data: str, hora: str, professor: str, update) -> dict:
    """Assigna un substitut a mà en una sola transacció (regles 1–26)."""
    inicia_escriptura(db)
    files = SubstitucioRepository.get_by_date(db, data)
    fila = _troba_fila(files, update, data, hora, professor)
    _comprova_versio(fila, update)
    files_a_alliberar = _valida_substitut(db, dia, data, fila, update, files)
    fila_desada, alliberades = _aplica(db, dia, data, fila, update, files_a_alliberar)
    encadenades = reconcilia_encadenades(db, data)  # regles 24–25
    db.commit()
    return {
        "success": True,
        "message": "Observacions desades"
        if update.substitut is None
        else f"Substitut actualitzat a {update.substitut}",
        "updated_at": fila_desada.updated_at.isoformat() if fila_desada and fila_desada.updated_at else None,
        "alliberades": alliberades,
        "encadenades": encadenades,
    }


def _troba_fila(files: list[FilaSubstitucio], update, data: str, hora: str, professor: str) -> FilaSubstitucio:
    """Tria la fila per identificador o per hora, professor i versió (regles 1–5)."""
    if update.id is not None:
        fila = next((sub for sub in files if sub.id == update.id), None)
        if fila is None:
            raise NoTrobat(
                f"No s'ha trobat la substitució amb identificador {update.id} per al dia {data}",
                codi="substitucio_id_no_trobat",
                params={"id": update.id, "data": data},
            )
        if fila.hora != hora or fila.professor_absent != professor:
            raise NoValid(
                "La substitució indicada no correspon a la data, l'hora i el professor de la URL",
                codi="substitucio_id_no_concorda",
            )
        return fila

    coincidencies = [fila for fila in files if fila.hora == hora and fila.professor_absent == professor]
    if coincidencies:
        versio = update.updated_at
        return next((fila for fila in coincidencies if versio and fila.updated_at == versio), coincidencies[0])
    raise NoTrobat(
        f"Substitució no trobada: {hora} - {professor}",
        codi="substitucio_no_trobada",
        params={"hora": hora, "professor": professor},
    )


def _comprova_versio(fila: FilaSubstitucio, update) -> None:
    """Comprova la versió llegida, llevat que es forci el canvi (regles 6–8)."""
    if not update.force:
        if not update.updated_at:
            raise NoValid("Falta el camp updated_at per comprovar conflictes", codi="falta_updated_at")
        if fila.updated_at and update.updated_at != fila.updated_at:
            raise ConflicteSubstitucions(fila)


def _valida_substitut(
    db: Session, dia: Dia, data: str, fila: FilaSubstitucio, update, files: list[FilaSubstitucio]
) -> list[FilaSubstitucio]:
    """Valida la tria en ordre i recull les files a alliberar (regles 10–18 i 20)."""
    substitut_normalitzat = (update.substitut or "").strip()
    if not substitut_normalitzat:
        return []
    hora = fila.hora
    assignatura_actual = fila.assignatura
    if assignatura_actual in NoSubstituirRepository.vigents_a(db, data):
        raise NoValid(
            f"❌ No es pot assignar substitut: '{assignatura_actual}' està a la llista d'activitats que NO es substitueixen",
            codi="activitat_no_substituible",
            params={"assignatura": assignatura_actual},
        )

    estat = DiaEscolar(db, dia, estricte=True)
    motius = estat.motius_substitut(substitut_normalitzat, hora, nomes={"vigilancia"})
    _rebutja_motius_manual(motius, substitut_normalitzat, hora)

    files_a_alliberar = []
    for sub in files:
        if sub.hora != hora or sub.substitut != substitut_normalitzat or sub.professor_absent == fila.professor_absent:
            continue
        if not update.moure:
            raise NoValid(
                f"❌ {substitut_normalitzat} ja està assignat com a SUBSTITUT per {sub.professor_absent} ({sub.assignatura}, {sub.grup}) a les {hora}",
                codi="substitut_repetit",
                params={
                    "substitut": substitut_normalitzat,
                    "absent": sub.professor_absent,
                    "assignatura": sub.assignatura,
                    "grup": sub.grup,
                    "hora": hora,
                },
            )
        files_a_alliberar.append(sub)

    motius = estat.motius_substitut(substitut_normalitzat, hora, nomes={"absent"})
    _rebutja_motius_manual(motius, substitut_normalitzat, hora)

    _rebutja_motius_manual(
        estat.motius_substitut(substitut_normalitzat, hora, nomes={"baixa"}), substitut_normalitzat, hora
    )
    _rebutja_motius_manual(
        estat.motius_substitut(substitut_normalitzat, hora, nomes={"fora_horari"}), substitut_normalitzat, hora
    )
    _rebutja_motius_manual(
        estat.motius_substitut(substitut_normalitzat, hora, nomes={"classe"}, classe_sense_assignatura=True),
        substitut_normalitzat,
        hora,
    )
    return files_a_alliberar


def _aplica(db: Session, dia: Dia, data: str, fila: FilaSubstitucio, update, files_a_alliberar: list[FilaSubstitucio]):
    """Aplica els canvis i desfà l'operació si la versió ha canviat (regles 8–9 i 19–23)."""
    hora = fila.hora
    alliberades = []
    for altra in files_a_alliberar:
        SubstitucioRepository.update(db, int(altra.id), {"substitut": "", "tipus_substitut": ""})
        alliberades.append({k: getattr(altra, k) for k in ("hora", "professor_absent", "assignatura", "grup")})

    canvis = {}
    if update.substitut is not None:
        tipus = _tipus_manual(db, dia, data, hora, update.substitut) if update.substitut.strip() else ""
        canvis.update(substitut=update.substitut, tipus_substitut=tipus)

    if update.comentaris is not None:
        canvis["comentaris"] = update.comentaris

    versio_esperada = None if update.force else update.updated_at
    fila_desada = SubstitucioRepository.update(db, int(fila.id), canvis, updated_at_esperat=versio_esperada)
    if fila_desada is None and not update.force:
        db.rollback()
        actual = next((sub for sub in SubstitucioRepository.get_by_date(db, data) if sub.id == fila.id), fila)
        raise ConflicteSubstitucions(actual)
    return fila_desada, alliberades


def _tipus_manual(db: Session, dia: Dia, data: str, hora: str, substitut: str) -> str:
    """El tipus del substitut triat a mà segons els disponibles de l'hora; buit si no hi és (regla 21)."""
    _, horari, alliberats, _ = dia.gestors()
    dia_name = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
    grups_hora = set(AlliberatsDelDia.get_by_date(db, data).get(hora, []))
    tipus_map = {
        prof: (tipus, detall) for prof, tipus, detall in alliberats.get_tots_disponibles(dia_name, hora, grups_hora)
    }
    tipus, detall = tipus_map.get(substitut, ("", ""))
    return text_tipus_substitut(tipus, detall) if tipus else ""


def reassigna_problematiques(db: Session, dia: Dia, data: str) -> dict:
    substitucions_data = SubstitucioRepository.get_by_date(db, data)
    if not substitucions_data:
        raise NoTrobat(f"No hi ha substitucions per {data}", codi="dia_sense_substitucions", params={"data": data})

    substituts_abans = {str(sub.id): (sub.substitut or "").strip() for sub in substitucions_data if sub.id}
    cleared = len(treu_substituts_no_valids(db, data))
    rng = _atzar()
    quota = QuotaFranja(SubstitucioRepository.historial_quota(db, data))
    resultat_generacio = genera_substitucions_dia(
        db,
        dia,
        regenerar_tot=False,
        rng=rng,
        quota=quota,
    )
    avisos = list(resultat_generacio.get("avisos", []))
    substitucions_despres = SubstitucioRepository.get_by_date(db, data)

    try:
        with db.begin_nested():
            millors = MillorsSubstituts(DiaEscolar(db, dia), dia.gestors(), rng=rng, quota=quota)
            for sub in substitucions_despres:
                millor = millors.millor(sub)
                if millor and sub.id:
                    professor, tipus, detall, _ = millor
                    SubstitucioRepository.update(
                        db,
                        int(sub.id),
                        {
                            "substitut": professor,
                            "tipus_substitut": text_tipus_substitut(tipus, detall) if tipus else "",
                        },
                    )
                    millors.canvia((sub.hora or "").strip(), (sub.substitut or "").strip(), professor)
            reconcilia_encadenades(db, data)
            substitucions_despres = SubstitucioRepository.get_by_date(db, data)
    except Exception:
        log.warning("No s'ha pogut reassignar per prioritat", exc_info=True)
        avisos.append("No s'ha pogut millorar l'assignació segons les prioritats. Revisa les substitucions.")
        substitucions_despres = SubstitucioRepository.get_by_date(db, data)

    canvis = []
    for sub in substitucions_despres:
        sub_id = str(sub.id) if sub.id else ""
        if not sub_id:
            continue
        abans = substituts_abans.get(sub_id, "")
        despres = (sub.substitut or "").strip()
        if abans != despres and (abans or despres):
            canvis.append(
                {
                    "hora": sub.hora,
                    "professor_absent": sub.professor_absent,
                    "assignatura": sub.assignatura,
                    "grup": sub.grup,
                    "abans": abans,
                    "despres": despres,
                }
            )

    db.commit()
    return {
        "success": True,
        "cleared": cleared,
        "changes": canvis,
        "message": "Reassignació de substitucions completada",
        "avisos": avisos,
    }
