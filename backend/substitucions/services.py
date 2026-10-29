"""Casos d'ús de les substitucions d'un dia, sense dependències HTTP."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from absencia_coberta.services import absencia_coberta_de, missatge_absencia_coberta
from core.alliberats import sense_classe
from errors_domini import Conflicte, ErrorDeDomini, NoTrobat, NoValid
from prioritats.repositories import NoSubstituirRepository
from repositories import GrupsAlliberatsRepository
from routes.parametres import data_iso
from serveis.dia import Dia
from substitucions import _consultes
from substitucions.absencies import desa_absencies
from substitucions.domain import DiaEscolar, treu_substituts_no_valids
from substitucions.encadenades import reconcilia_encadenades
from substitucions.generacio import genera_substitucions_dia
from substitucions.prioritat import MillorsSubstituts, text_tipus_substitut
from substitucions.repositories import SubstitucioRepository
from substitucions.vigilancia_absent import es_vigilancia_absent
from vigilancies.repositories import VigilanciaRepository

log = logging.getLogger(__name__)


class ConflicteSubstitucions(Conflicte):
    """Conflicte optimista que inclou la versió actual per a la pantalla."""

    def __init__(self, current_data: dict | list[dict]):
        super().__init__(
            "Aquest registre ha estat modificat per un altre usuari",
            codi="substitucio_modificada",
        )
        self.current_data = current_data


llista_substitucions = _consultes.llista_substitucions
hores_professor = _consultes.hores_professor
disponibles = _consultes.disponibles


def genera_substitucions(
    db: Session,
    dia: Dia,
    data: str,
    *,
    regenerar_tot: bool,
    omplir: bool,
) -> dict:
    data_iso(data)
    resultat = genera_substitucions_dia(db, data, dia.gestors(), regenerar_tot, omplir)
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
            if sub.get("professor_absent") != professor or es_vigilancia_absent(sub):
                continue
            hora_sub = sub.get("hora")
            if hora_sub in update.updated_at_map:
                client_updated_at = update.updated_at_map.get(hora_sub)
                server_updated_at = sub.get("updated_at")
                if client_updated_at and server_updated_at and client_updated_at != server_updated_at:
                    conflictes.append(sub)
        if conflictes:
            raise ConflicteSubstitucions(conflictes)

    if (update.hores_absencia or update.hores_servei) and (baixa := absencia_coberta_de(db, professor, data)):
        raise NoValid(
            missatge_absencia_coberta(professor, baixa),
            codi="professor_amb_absencia_coberta",
        )

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


def actualitza_substitut(db: Session, dia: Dia, data: str, hora: str, professor: str, update) -> dict:
    """Assignació manual amb les mateixes comprovacions i ordre que el router antic."""
    avisos = []
    substitucions_list = SubstitucioRepository.get_by_date(db, data)
    if update.id is not None:
        substitucio_actual = next((sub for sub in substitucions_list if sub.get("id") == update.id), None)
        if substitucio_actual is None:
            raise NoTrobat(
                f"No s'ha trobat la substitució amb identificador {update.id} per al dia {data}",
                codi="substitucio_id_no_trobat",
            )
        if substitucio_actual.get("hora") != hora or substitucio_actual.get("professor_absent") != professor:
            raise NoValid(
                "La substitució indicada no correspon a la data, l'hora i el professor de la URL",
                codi="substitucio_id_no_concorda",
            )
    else:
        substitucio_actual = None
        primera_coincidencia = None
        for sub in substitucions_list:
            if sub.get("hora") == hora and sub.get("professor_absent") == professor:
                if primera_coincidencia is None:
                    primera_coincidencia = sub
                if update.updated_at and sub.get("updated_at") == update.updated_at:
                    substitucio_actual = sub
                    break
        if substitucio_actual is None:
            substitucio_actual = primera_coincidencia

    if not substitucio_actual:
        raise NoTrobat(
            f"Substitució no trobada: {hora} - {professor}",
            codi="substitucio_no_trobada",
        )

    if not update.force:
        if not update.updated_at:
            raise NoValid(
                "Falta el camp updated_at per comprovar conflictes",
                codi="falta_updated_at",
            )
        if substitucio_actual.get("updated_at") and update.updated_at != substitucio_actual.get("updated_at"):
            raise ConflicteSubstitucions(substitucio_actual)

    if update.substitut and update.substitut.strip():
        substitut_normalitzat = update.substitut.strip()
        files_a_alliberar = []
        assignatura_actual = substitucio_actual.get("assignatura", "")
        no_substituir = NoSubstituirRepository.get_all(db)

        if assignatura_actual in no_substituir:
            raise NoValid(
                f"❌ No es pot assignar substitut: '{assignatura_actual}' està a la llista d'activitats que NO es substitueixen",
                codi="activitat_no_substituible",
            )

        vigilants_ocupats = set(VigilanciaRepository.get_vigilants_per_hora(db, data, hora))
        if substitut_normalitzat in vigilants_ocupats:
            raise NoValid(
                f"❌ {substitut_normalitzat} ja està assignat com a VIGILANT a les {hora}",
                codi="substitut_vigilant",
            )

        for sub in substitucions_list:
            if (
                sub.get("hora") == hora
                and sub.get("substitut") == substitut_normalitzat
                and not (sub.get("hora") == hora and sub.get("professor_absent") == professor)
            ):
                if update.moure:
                    files_a_alliberar.append(sub)
                    continue
                raise NoValid(
                    f"❌ {substitut_normalitzat} ja està assignat com a SUBSTITUT per {sub.get('professor_absent')} ({sub.get('assignatura')}, {sub.get('grup')}) a les {hora}",
                    codi="substitut_repetit",
                )

        absents_reals_per_hora = {}
        for sub in substitucions_list:
            h = sub.get("hora", "")
            prof_absent = sub.get("professor_absent", "")
            tipus_abs = sub.get("tipus_absencia", "")
            if h and prof_absent and tipus_abs in ("ABSENCIA", "SERVEI"):
                if h not in absents_reals_per_hora:
                    absents_reals_per_hora[h] = set()
                absents_reals_per_hora[h].add(prof_absent)

        if substitut_normalitzat in absents_reals_per_hora.get(hora, set()):
            raise NoValid(
                f"❌ {substitut_normalitzat} està ABSENT a les {hora}!",
                codi="substitut_absent",
            )

        try:
            horari = dia.horari
            if substitut_normalitzat in horari.absents_coberts:
                raise NoValid(
                    f"❌ {substitut_normalitzat} té una ABSÈNCIA COBERTA aquell dia!",
                    codi="substitut_amb_absencia_coberta",
                )
            dia_name = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
            activitat_sub = horari.get_activitat(dia_name, hora, substitut_normalitzat)
            if activitat_sub:
                assignatura_sub = activitat_sub.get("assignatura", "")
                grup_sub = activitat_sub.get("grup", "")
                if grup_sub and grup_sub.strip():
                    grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data)
                    grups_alliberats_hora = grups_alliberats_data.get(hora, [])
                    if not sense_classe(substitut_normalitzat, grup_sub, grups_alliberats_hora):
                        raise NoValid(
                            f"⚠️ {substitut_normalitzat} té CLASSE a les {hora} ({assignatura_sub}, {grup_sub})",
                            codi="substitut_amb_classe",
                        )
        except ErrorDeDomini:
            raise
        except Exception:
            log.warning("⚠️ No s'ha pogut validar l'horari del substitut", exc_info=True)
            avisos.append("No s'ha pogut validar l'horari del substitut. Revisa que l'assignació sigui correcta.")

    alliberades = []
    for fila in files_a_alliberar if update.substitut and update.substitut.strip() else []:
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": "", "tipus_substitut": ""})
        alliberades.append({k: fila.get(k, "") for k in ("hora", "professor_absent", "assignatura", "grup")})

    updates = {}
    if update.substitut is not None:
        substitut_nou = update.substitut
        tipus_substitut_nou = ""

        if substitut_nou.strip():
            try:
                _, horari, alliberats, _ = dia.gestors()
                dia_name = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
                grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
                grups_hora = set(grups_sense_classe.get(hora, []))
                disponibles_hora = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)
                tipus_map = {prof: (tipus, detall) for prof, tipus, detall in disponibles_hora}
                tipus_substitut_nou = text_tipus_substitut(*tipus_map.get(substitut_nou, ("", "")))
            except Exception as exc:
                log.warning("⚠️ No s'ha pogut calcular tipus_substitut manual: %s", exc)

        updates["substitut"] = substitut_nou
        updates["tipus_substitut"] = tipus_substitut_nou

    if update.comentaris is not None:
        updates["comentaris"] = update.comentaris

    updated_sub = SubstitucioRepository.update(db, int(substitucio_actual["id"]), updates)
    encadenades = reconcilia_encadenades(db, data)
    db.commit()
    return {
        "success": True,
        "message": f"Substitut actualitzat a {update.substitut}",
        "updated_at": updated_sub.updated_at.isoformat() if updated_sub and updated_sub.updated_at else None,
        "alliberades": alliberades,
        "encadenades": encadenades,
        "avisos": avisos,
    }


def reassigna_problematiques(db: Session, dia: Dia, data: str) -> dict:
    substitucions_data = SubstitucioRepository.get_by_date(db, data)
    if not substitucions_data:
        raise NoTrobat(f"No hi ha substitucions per {data}", codi="dia_sense_substitucions")

    substituts_abans = {
        str(sub.get("id")): (sub.get("substitut") or "").strip() for sub in substitucions_data if sub.get("id")
    }
    cleared = len(treu_substituts_no_valids(db, data))
    resultat_generacio = genera_substitucions_dia(db, data, dia.gestors(), regenerar_tot=False)
    avisos = list(resultat_generacio.get("avisos", []))
    substitucions_despres = SubstitucioRepository.get_by_date(db, data)

    try:
        with db.begin_nested():
            millors = MillorsSubstituts(DiaEscolar(db, data), dia.gestors())
            for sub in substitucions_despres:
                millor = millors.millor(sub)
                if millor and sub.get("id"):
                    professor, tipus, detall, _ = millor
                    SubstitucioRepository.update(
                        db,
                        int(sub["id"]),
                        {"substitut": professor, "tipus_substitut": text_tipus_substitut(tipus, detall)},
                    )
                    millors.canvia((sub.get("hora") or "").strip(), (sub.get("substitut") or "").strip(), professor)
            reconcilia_encadenades(db, data)
            substitucions_despres = SubstitucioRepository.get_by_date(db, data)
    except Exception:
        log.warning("No s'ha pogut reassignar per prioritat", exc_info=True)
        avisos.append("No s'ha pogut millorar l'assignació segons les prioritats. Revisa les substitucions.")
        substitucions_despres = SubstitucioRepository.get_by_date(db, data)

    canvis = []
    for sub in substitucions_despres:
        sub_id = str(sub.get("id")) if sub.get("id") else ""
        if not sub_id:
            continue
        abans = substituts_abans.get(sub_id, "")
        despres = (sub.get("substitut") or "").strip()
        if abans != despres and (abans or despres):
            canvis.append(
                {
                    "hora": sub.get("hora", ""),
                    "professor_absent": sub.get("professor_absent", ""),
                    "assignatura": sub.get("assignatura", ""),
                    "grup": sub.get("grup", ""),
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
