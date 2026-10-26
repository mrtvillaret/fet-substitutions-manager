"""
Routes per gestió de substitucions:
- Obtenir substitucions per data
- Generar substitucions automàticament
- Actualitzar absències de professor
- Actualitzar substitut específic
- Eliminar substitució
- Afegir nova substitució
- Obtenir professors disponibles per hora
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from absencia_coberta.services import absencia_coberta_de, missatge_absencia_coberta
from core.alliberats import sense_classe
from dependencies import dia_de_la_peticio, get_db
from helpers import MissingXmlError
from models import Substitucio
from noms import NomNet
from repositories import (
    CursRepository,
    GrupsAlliberatsRepository,
    SubstitucioRepository,
)
from routes.parametres import DataISO, data_iso
from schemas import (
    ActualitzarAbsenciesRequest,
    NovaSubstitucioRequest,
    SubstitucioResponse,
    SubstitucioUpdate,
)
from serveis.absencies import canvia_tipus_cobertures, desa_absencies
from serveis.dia import Dia
from serveis.dia_escolar import DiaEscolar, treu_substituts_no_valids
from serveis.encadenades import reconcilia_encadenades
from serveis.generacio import genera_substitucions_dia
from serveis.prioritat import MillorsSubstituts, text_tipus_substitut
from serveis.vigilancia_absent import (
    es_vigilancia_absent,
    sincronitzar_vigilancies_absents,
)
from vigilancies.repositories import VigilanciaRepository

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/substitucions", tags=["Substitucions"])


def _raise_missing_xml(exc: MissingXmlError):
    raise HTTPException(status_code=400, detail={"xml_missing": True, "message": str(exc)})


def _calcular_estadistiques_substitucions(db: Session, horari, data: str = None) -> dict:
    """Calcula estadístiques de substitucions (dia/hora i total).

    Es compten NOMÉS les substitucions del curs al qual pertany `data`: el comptador
    que es mostra al selector de substitut ha de reflectir la càrrega d'aquest curs,
    no l'històric acumulat de tots els anys. Si encara no hi ha cursos definits (o la
    data és anterior al primer), es compta tot, com abans.
    """
    estadistiques = {}

    query = db.query(Substitucio).filter(
        Substitucio.substitut.isnot(None),
        Substitucio.substitut != "",
        Substitucio.professor_absent.isnot(None),
        Substitucio.professor_absent != "",
    )

    curs = CursRepository.get_for_date(db, data) if data else None
    if curs:
        query = query.filter(Substitucio.data >= curs.data_inici)
        if curs.data_fi:
            query = query.filter(Substitucio.data <= curs.data_fi)

    subs = query.all()

    for sub in subs:
        substitut = (sub.substitut or "").strip()
        hora = (sub.hora or "").strip()
        professor_absent = (sub.professor_absent or "").strip()
        if not substitut or not hora or not professor_absent or not sub.data:
            continue

        try:
            weekday_idx = sub.data.weekday()
        except AttributeError:
            continue

        if horari:
            try:
                dia_name = horari.get_dia_name(weekday_idx)
            except Exception:
                dia_name = f"Dia_{weekday_idx}"
        else:
            dia_name = f"Dia_{weekday_idx}"

        key_substitut_dia = f"{substitut}|{dia_name}|{hora}"
        estadistiques[key_substitut_dia] = estadistiques.get(key_substitut_dia, 0) + 1

        key_substitut_total = f"{substitut}|TOTAL"
        estadistiques[key_substitut_total] = estadistiques.get(key_substitut_total, 0) + 1

    return estadistiques


@router.get("/{data}", response_model=List[SubstitucioResponse])
async def get_substitucions(
    data: DataISO, include_all: bool = False, db: Session = Depends(get_db), dia: Dia = Depends(dia_de_la_peticio)
):
    """
    Retorna totes les substitucions per una data específica (SQLite)

    IMPORTANT: Per defecte només retorna les que generen substitució (tenen grup I no alliberat).
    Les absències sense grup (Guàrdia, Reforç, etc.) i amb grup alliberat es desen per estadístiques
    però NO es mostren a la taula per defecte.

    Args:
        data: Format ISO (YYYY-MM-DD), ex: 2025-12-23
        include_all: Si True, retorna TOTES les absències (amb i sense grup, alliberat o no)
                     Útil per editar absències i veure totes les hores marcades
    """
    data_iso(data)

    try:
        # Obtenir horari per ordre correcte d'hores
        horari = dia.horari

        # Carregar substitucions de SQLite
        substitucions_list = SubstitucioRepository.get_by_date(db, data)

        # Convertir a format API
        result = []

        if include_all:
            # Mode edició: retornar TOTES les absències (amb i sense grup)
            # PERÒ NO les encadenades (són automàtiques i no s'editen)
            for sub in substitucions_list:
                # Filtrar substitucions encadenades
                if sub.get("tipus_absencia") == "ENCADENADA":
                    continue

                result.append(
                    SubstitucioResponse(
                        hora=sub.get("hora", ""),
                        professor_absent=sub.get("professor_absent", ""),
                        assignatura=sub.get("assignatura", ""),
                        grup=sub.get("grup", ""),
                        aula=sub.get("aula", ""),
                        substitut=sub.get("substitut", None),
                        comentaris=sub.get("comentaris", ""),
                        estat="assignada" if sub.get("substitut") else "pendent",
                        tipus_absencia=sub.get("tipus_absencia", ""),
                        updated_at=sub.get("updated_at"),
                    )
                )
        else:
            # Mode visualització: només les que generen substitució real
            # Carregar grups sense classe per filtrar-los
            grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)

            # Carregar llista de no_substituir
            from prioritats.repositories import NoSubstituirRepository

            no_substituir = NoSubstituirRepository.get_all(db)

            for sub in substitucions_list:
                # Filtrar:
                # 1. Té grup I el grup NO està alliberat, O
                # 2. NO té grup però l'assignatura NO està a no_substituir
                grup = sub.get("grup", "")
                hora = sub.get("hora", "")
                assignatura = sub.get("assignatura", "")

                mostrar = False

                if es_vigilancia_absent(sub):
                    # Tipus A (VIGILANCIA_ABSENT): vigilant absent → slot descobert, sempre cal cobrir-lo
                    mostrar = True
                elif grup and grup.strip():
                    # CAS 1: Té grup → comprovar si està alliberat
                    grups_hora = grups_sense_classe.get(hora, [])
                    professor = sub.get("professor_absent") or sub.get("professor", "")
                    if not sense_classe(professor, grup, grups_hora):
                        mostrar = True
                else:
                    # CAS 2: NO té grup → comprovar si l'assignatura necessita substitució
                    # (i que el professor no estigui alliberat, p.ex. un reforç alliberat)
                    professor = sub.get("professor_absent") or sub.get("professor", "")
                    if assignatura not in no_substituir and not sense_classe(
                        professor, "", grups_sense_classe.get(hora, [])
                    ):
                        mostrar = True

                if mostrar:
                    result.append(
                        SubstitucioResponse(
                            hora=hora,
                            professor_absent=sub.get("professor_absent", ""),
                            assignatura=assignatura,
                            grup=grup,
                            aula=sub.get("aula", ""),
                            substitut=sub.get("substitut", None),
                            comentaris=sub.get("comentaris", ""),
                            estat="assignada" if sub.get("substitut") else "pendent",
                            tipus_absencia=sub.get("tipus_absencia", ""),
                            updated_at=sub.get("updated_at"),
                        )
                    )

        # L'ordre per mostrar-les, el mateix que el PDF (SubstitucioRepository.ordena):
        # fix, regenerar no ha de canviar les files de lloc
        return SubstitucioRepository.ordena(result, horari.hores, valor=getattr)

    except MissingXmlError as e:
        _raise_missing_xml(e)


@router.post("/{data}/generar")
async def generar_substitucions(
    data: DataISO,
    regenerar_tot: bool = False,
    db: Session = Depends(get_db),
    omplir: bool = True,
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Genera automàticament les substitucions d'un dia (veure
    serveis/generacio.py). `regenerar_tot`: des de zero;
    si no, es conserven les files que ja tenen substitut.
    """
    data_iso(data)

    try:
        return genera_substitucions_dia(db, data, dia.gestors(), regenerar_tot, omplir)
    except MissingXmlError as e:
        _raise_missing_xml(e)


@router.put("/{data}/absencies/{professor}")
async def actualitzar_absencies_professor(
    data: DataISO,
    professor: NomNet,
    update: ActualitzarAbsenciesRequest,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Actualitza les absències d'un professor (SQLite):
    - Elimina substitucions de les hores que s'han tret
    - Manté les hores seleccionades
    - Actualitza el tipus d'absència per totes les hores
    """
    data_iso(data)

    try:
        # Obtenir gestors
        substitucions_mgr, horari, alliberats, absencies = dia.gestors()

        # Convertir data ISO a nom del dia de l'XML
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        weekday_idx = date_obj.weekday()
        dia_name = horari.get_dia_name(weekday_idx)

        # Carregar substitucions de SQLite
        substitucions_list = SubstitucioRepository.get_by_date(db, data)

        # Comprovació de conflictes (optimistic locking)
        if not update.force:
            if update.updated_at_map is None:
                raise HTTPException(status_code=400, detail="Falta el camp updated_at_map per comprovar conflictes")
        if not update.force and update.updated_at_map:
            conflictes = []
            for sub in substitucions_list:
                if sub.get("professor_absent") != professor:
                    continue
                # Saltar Tipus A VIGILANCIA_ABSENT (gestionats internament, l'usuari no els controla)
                if es_vigilancia_absent(sub):
                    continue
                hora_sub = sub.get("hora")
                if hora_sub in update.updated_at_map:
                    client_updated_at = update.updated_at_map.get(hora_sub)
                    server_updated_at = sub.get("updated_at")
                    if client_updated_at and server_updated_at and client_updated_at != server_updated_at:
                        conflictes.append(sub)

            if conflictes:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "conflict",
                        "message": "Aquest registre ha estat modificat per un altre usuari",
                        "current_data": conflictes,
                    },
                )

        # Un professor de baixa no és substituït: no se li posen absències (sí que se li poden treure)
        if (update.hores_absencia or update.hores_servei) and (baixa := absencia_coberta_de(db, professor, data)):
            raise HTTPException(status_code=400, detail=missatge_absencia_coberta(professor, baixa))

        resultat = desa_absencies(
            db,
            data,
            professor,
            update.hores_absencia,
            update.hores_servei,
            gestors=(horari, absencies),
            dia_name=dia_name,
        )
        return {
            "success": True,
            "message": f"Absències de {professor} actualitzades (multi-tipus)",
            **resultat,
        }
    except MissingXmlError as e:
        _raise_missing_xml(e)


@router.put("/{data}/{hora}/{professor}")
async def update_substitucio(
    data: DataISO,
    hora: str,
    professor: NomNet,
    update: SubstitucioUpdate,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Actualitza el substitut d'una substitució específica (SQLite)
    Valida que el substitut NO estigui ocupat, absent o amb classe
    """
    # Carregar substitucions de SQLite
    substitucions_list = SubstitucioRepository.get_by_date(db, data)

    # Buscar la substitució: quan un vigilant absent té múltiples registres (ABSENCIA +
    # VIGILANCIA_ABSENT) per la mateixa (hora, professor), cal trobar el correcte.
    # Prioritzem el que té updated_at coincident per evitar fals 409 entre els dos registres.
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
        raise HTTPException(status_code=404, detail=f"Substitució no trobada: {hora} - {professor}")

    # Comprovació de conflictes (optimistic locking)
    if not update.force:
        if not update.updated_at:
            raise HTTPException(status_code=400, detail="Falta el camp updated_at per comprovar conflictes")
        if substitucio_actual.get("updated_at") and update.updated_at != substitucio_actual.get("updated_at"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "conflict",
                    "message": "Aquest registre ha estat modificat per un altre usuari",
                    "current_data": substitucio_actual,
                },
            )

    # Si s'està assignant un substitut (no buidant), validar-lo
    if update.substitut and update.substitut.strip():
        substitut_normalitzat = update.substitut.strip()

        files_a_alliberar = []
        # 0. Validar que l'assignatura no estigui a la llista no_substituir (SQLite)
        assignatura_actual = substitucio_actual.get("assignatura", "")
        from prioritats.repositories import NoSubstituirRepository

        no_substituir = NoSubstituirRepository.get_all(db)

        if assignatura_actual in no_substituir:
            raise HTTPException(
                status_code=400,
                detail=f"❌ No es pot assignar substitut: '{assignatura_actual}' està a la llista d'activitats que NO es substitueixen",
            )

        # 1. Validar que NO estigui ocupat com a vigilant
        vigilants_ocupats = set(VigilanciaRepository.get_vigilants_per_hora(db, data, hora))
        if substitut_normalitzat in vigilants_ocupats:
            raise HTTPException(
                status_code=400, detail=f"❌ {substitut_normalitzat} ja està assignat com a VIGILANT a les {hora}"
            )

        # 2. Validar que NO estigui ja assignat com a substitut a una altra substitució
        # (amb `moure`, se'l treu d'aquella després de les altres comprovacions)
        for sub in substitucions_list:
            # Comprovar si el substitut ja està assignat a ALTRA substitució
            # (no comprovar la substitució actual que estem actualitzant)
            if (
                sub.get("hora") == hora
                and sub.get("substitut") == substitut_normalitzat
                and not (sub.get("hora") == hora and sub.get("professor_absent") == professor)
            ):
                if update.moure:
                    files_a_alliberar.append(sub)
                    continue
                raise HTTPException(
                    status_code=400,
                    detail=f"❌ {substitut_normalitzat} ja està assignat com a SUBSTITUT per {sub.get('professor_absent')} ({sub.get('assignatura')}, {sub.get('grup')}) a les {hora}",
                )

        # 3. Validar que NO estigui REALMENT absent (ABSENCIA o SERVEI, NO ENCADENADA)
        absents_reals_per_hora = {}
        for sub in substitucions_list:
            h = sub.get("hora", "")
            prof_absent = sub.get("professor_absent", "")
            tipus_abs = sub.get("tipus_absencia", "")

            # Només comptar ABSENCIA i SERVEI com absències reals
            # ENCADENADA NO impedeix fer altres substitucions
            if h and prof_absent and tipus_abs in ("ABSENCIA", "SERVEI"):
                if h not in absents_reals_per_hora:
                    absents_reals_per_hora[h] = set()
                absents_reals_per_hora[h].add(prof_absent)

        if substitut_normalitzat in absents_reals_per_hora.get(hora, set()):
            raise HTTPException(status_code=400, detail=f"❌ {substitut_normalitzat} està ABSENT a les {hora}!")

        # 4. Validar que NO tingui classe (o que el seu grup estigui alliberat)
        try:
            horari = dia.horari

            # Convertir data ISO a dia de la setmana
            date_obj = datetime.strptime(data, "%Y-%m-%d")
            weekday_idx = date_obj.weekday()
            dia_name = horari.get_dia_name(weekday_idx)

            # Comprovar si té classe a l'horari
            activitat_sub = horari.get_activitat(dia_name, hora, substitut_normalitzat)
            if activitat_sub:
                assignatura_sub = activitat_sub.get("assignatura", "")
                grup_sub = activitat_sub.get("grup", "")

                # Si té grup específic, comprovar si està alliberat
                if grup_sub and grup_sub.strip():
                    # Només l'allibera que el seu grup estigui marcat sense
                    # classe: un examen (vigilància) no n'hi ha prou, pot
                    # ser un examen extra i el grup continua tenint classe.
                    grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data)
                    grups_alliberats_hora = grups_alliberats_data.get(hora, [])

                    if not sense_classe(substitut_normalitzat, grup_sub, grups_alliberats_hora):
                        raise HTTPException(
                            status_code=400,
                            detail=f"⚠️ {substitut_normalitzat} té CLASSE a les {hora} ({assignatura_sub}, {grup_sub})",
                        )
        except HTTPException:
            raise
        except Exception as e:
            # Si no es pot validar l'horari, continuar (no bloquejar)
            log.warning(f"⚠️ No s'ha pogut validar l'horari del substitut: {e}")
            pass

    # Moure: l'altra substitució que feia queda pendent
    alliberades = []
    for fila in files_a_alliberar if update.substitut and update.substitut.strip() else []:
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": "", "tipus_substitut": ""})
        alliberades.append({k: fila.get(k, "") for k in ("hora", "professor_absent", "assignatura", "grup")})

    # Actualitzar a SQLite (substitucio_actual ja trobada a l'inici)
    updates = {}
    if update.substitut is not None:
        substitut_nou = update.substitut
        tipus_substitut_nou = ""

        if substitut_nou.strip():
            try:
                substitucions_mgr, horari, alliberats, _ = dia.gestors()
                date_obj = datetime.strptime(data, "%Y-%m-%d")
                dia_name = horari.get_dia_name(date_obj.weekday())

                grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
                grups_hora = set(grups_sense_classe.get(hora, []))

                disponibles = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)
                tipus_map = {prof: (tipus, detall) for prof, tipus, detall in disponibles}

                tipus_substitut_nou = text_tipus_substitut(*tipus_map.get(substitut_nou, ("", "")))
            except Exception as e:
                log.warning(f"⚠️ No s'ha pogut calcular tipus_substitut manual: {e}")

        updates["substitut"] = substitut_nou
        updates["tipus_substitut"] = tipus_substitut_nou

    # Actualitzar comentaris si s'han especificat
    if update.comentaris is not None:
        updates["comentaris"] = update.comentaris

    updated_sub = SubstitucioRepository.update(db, int(substitucio_actual["id"]), updates)
    # L'encadenada del substitut nou (pendent) i fora la de l'anterior
    encadenades = reconcilia_encadenades(db, data)

    return {
        "success": True,
        "message": f"Substitut actualitzat a {update.substitut}",
        "updated_at": updated_sub.updated_at.isoformat() if updated_sub and updated_sub.updated_at else None,
        "alliberades": alliberades,
        "encadenades": encadenades,  # {creades, esborrades}: si n'hi ha, la llista ha canviat
    }


@router.post("/{data}/nova")
async def afegir_nova_substitucio(
    data: DataISO, nova: NovaSubstitucioRequest, db: Session = Depends(get_db), dia: Dia = Depends(dia_de_la_peticio)
):
    """
    Afegeix una nova substitució per un professor absent (SQLite)
    L'assignatura i grup es carreguen automàticament de l'horari del professor

    Args:
        data: Format ISO (YYYY-MM-DD)
        nova: Dades de la nova substitució (professor, hores, tipus_absencia)
    """
    data_iso(data)

    try:
        # Validar que hi hagi almenys una hora
        if not nova.hores or len(nova.hores) == 0:
            raise HTTPException(status_code=400, detail="Has de seleccionar almenys una hora")
        if baixa := absencia_coberta_de(db, nova.professor, data):
            raise HTTPException(status_code=400, detail=missatge_absencia_coberta(nova.professor, baixa))

        # Obtenir gestors
        substitucions_mgr, horari, alliberats, absencies = dia.gestors()

        # Convertir data ISO a nom del dia de l'XML
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        weekday_idx = date_obj.weekday()
        dia_name = horari.get_dia_name(weekday_idx)

        # Crear substitucions NOMÉS per al nou professor amb absencies.get_substitucions_necessaries()
        # (això carrega automàticament assignatura i grup de l'horari)
        absents_nous = {nova.professor: nova.hores}
        absents_nous_tipus = {nova.professor: nova.tipus_absencia}
        noves_subs_generades = absencies.get_substitucions_necessaries(dia_name, absents_nous, absents_nous_tipus)

        # Si vigila un examen a alguna d'aquestes hores, la fila VIGILANCIA de la
        # seva classe (amb el seu substitut) passa a ser l'absència.
        canvia_tipus_cobertures(db, data, nova.professor, set(nova.hores), "VIGILANCIA", nova.tipus_absencia)

        # Carregar substitucions existents de SQLite
        substitucions_existents = SubstitucioRepository.get_by_date(db, data)

        # Filtrar només les substitucions que NO existeixen ja
        noves_substitucions = []
        for nova_sub in noves_subs_generades:
            hora = nova_sub.get("hora", "")
            assignatura = nova_sub.get("assignatura", "")
            grup = nova_sub.get("grup", "")

            # Comprovar si ja existeix a SQLite
            existeix = False
            for sub in substitucions_existents:
                if (
                    sub.get("hora") == hora
                    and sub.get("professor_absent") == nova.professor
                    and sub.get("assignatura") == assignatura
                    and sub.get("grup") == grup
                ):
                    existeix = True
                    break

            if not existeix:
                # Afegir a SQLite
                sub_data = {
                    "data": data,
                    "hora": nova_sub.get("hora", ""),
                    "professor_absent": nova_sub.get("professor_absent", ""),
                    "assignatura": nova_sub.get("assignatura", ""),
                    "grup": nova_sub.get("grup", ""),
                    "aula": nova_sub.get("aula", ""),
                    "substitut": nova_sub.get("substitut", ""),
                    "tipus_substitut": nova_sub.get("tipus_substitut", ""),
                    "tipus_absencia": nova_sub.get("tipus_absencia", ""),
                    "comentaris": nova_sub.get("comentaris", ""),
                }
                SubstitucioRepository.create(db, sub_data)
                noves_substitucions.append(nova_sub)

        # Desar TOTES les hores d'absència, fins i tot si no generen substitució
        # (per exemple, Guàrdia-R, Reforç, etc. no generen substitució però cal saber que el professor està absent)
        hores_amb_substitucio = {sub.get("hora") for sub in noves_subs_generades}

        for hora in nova.hores:
            if hora not in hores_amb_substitucio:
                # Aquesta hora NO ha generat substitució (Guàrdia, Reforç, etc.)
                # Comprovar si ja existeix aquesta absència a SQLite
                existeix = False
                for sub in substitucions_existents:
                    if sub.get("hora") == hora and sub.get("professor_absent") == nova.professor:
                        existeix = True
                        break

                if not existeix:
                    # Obtenir activitat que tenia el professor
                    activitat = horari.get_activitat(dia_name, hora, nova.professor)
                    assignatura_absent = activitat.get("assignatura", "") if activitat else ""
                    grup_absent = activitat.get("grup", "") if activitat else ""
                    aula_absent = activitat.get("aula", "") if activitat else ""

                    # Crear entrada d'absència sense substitut
                    sub_data = {
                        "data": data,
                        "hora": hora,
                        "professor_absent": nova.professor,
                        "assignatura": assignatura_absent,
                        "grup": grup_absent,
                        "aula": aula_absent,
                        "substitut": "",  # Buit perquè no necessita substitut
                        "tipus_substitut": "",
                        "tipus_absencia": nova.tipus_absencia,
                        "comentaris": "",
                    }
                    SubstitucioRepository.create(db, sub_data)

        # Si és vigilant d'un examen a alguna hora en què és absent, cal cobrir
        # l'examen. Es passen TOTES les seves hores d'absència del dia: la
        # funció també esborra les VIGILANCIA_ABSENT de les hores que no rep.
        subs_dia = SubstitucioRepository.get_by_date(db, data)
        hores_absent = {
            s.get("hora")
            for s in subs_dia
            if s.get("professor_absent") == nova.professor
            and s.get("tipus_absencia") not in ("VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT")
        }
        sincronitzar_vigilancies_absents(db, data, nova.professor, subs_dia, hores_absent)

        return {
            "success": True,
            "message": f"Afegides {len(noves_substitucions)} substitucions per {nova.professor}",
            "count": len(noves_substitucions),
        }

    except MissingXmlError as e:
        _raise_missing_xml(e)


@router.post("/{data}/reassign-problematics")
async def reassignar_problematics(data: DataISO, db: Session = Depends(get_db), dia: Dia = Depends(dia_de_la_peticio)):
    """
    Reassigna substitucions problemàtiques (vigilant, absent, de baixa o amb classe).
    """
    try:
        substitucions_data = SubstitucioRepository.get_by_date(db, data)
        if not substitucions_data:
            raise HTTPException(status_code=404, detail=f"No hi ha substitucions per {data}")

        substituts_abans = {
            str(sub.get("id")): (sub.get("substitut") or "").strip() for sub in substitucions_data if sub.get("id")
        }

        trets = treu_substituts_no_valids(db, data)
        cleared = len(trets)

        genera_substitucions_dia(db, data, dia.gestors(), regenerar_tot=False)

        substitucions_despres = SubstitucioRepository.get_by_date(db, data)

        # Substituts que es poden canviar per un disponible de més prioritat
        try:
            millors = MillorsSubstituts(DiaEscolar(db, data), dia.gestors())
            for sub in substitucions_despres:
                millor = millors.millor(sub)
                if millor and sub.get("id"):
                    prof, tipus, detall, _ = millor
                    SubstitucioRepository.update(
                        db, int(sub["id"]), {"substitut": prof, "tipus_substitut": text_tipus_substitut(tipus, detall)}
                    )
                    millors.canvia((sub.get("hora") or "").strip(), (sub.get("substitut") or "").strip(), prof)
            reconcilia_encadenades(db, data)
            substitucions_despres = SubstitucioRepository.get_by_date(db, data)
        except Exception:
            log.warning("No s'ha pogut reassignar per prioritat", exc_info=True)

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

        return {
            "success": True,
            "cleared": cleared,
            "changes": canvis,
            "message": "Reassignació de substitucions completada",
        }

    except MissingXmlError as e:
        _raise_missing_xml(e)


@router.get("/{data}/hores-professor/{professor}")
async def get_hores_professor(
    data: DataISO, professor: NomNet, db: Session = Depends(get_db), dia: Dia = Depends(dia_de_la_peticio)
):
    """Retorna les hores on el professor té classe, i les hores que és al centre sense classe."""
    try:
        from prioritats.repositories import NoSubstituirRepository

        horari = dia.horari
        weekday_idx = datetime.strptime(data, "%Y-%m-%d").weekday()
        dia_name = horari.get_dia_name(weekday_idx)
        no_substituir = NoSubstituirRepository.get_all(db)

        hores_amb_classe = []
        hores_al_centre = []
        for hora in horari.hores:
            activitat = horari.get_activitat(dia_name, hora, professor)
            if not activitat:
                continue  # fora d'horari → no afegim a cap llista
            assignatura = activitat.get("assignatura", "")
            if not assignatura:
                continue  # activitat buida → fora d'horari
            if assignatura in no_substituir:
                hores_al_centre.append(hora)
            else:
                hores_amb_classe.append(hora)

        return {"hores_amb_classe": hores_amb_classe, "hores_al_centre": hores_al_centre}
    except MissingXmlError as e:
        _raise_missing_xml(e)


@router.get("/{data}/{hora}/disponibles")
async def get_disponibles(
    data: DataISO, hora: str, db: Session = Depends(get_db), dia: Dia = Depends(dia_de_la_peticio)
):
    """
    Retorna professors disponibles per una hora específica,
    ordenats per prioritat amb informació del que estan fent.
    """
    data_iso(data)

    try:
        from config.constants import ORDRE_PRIORITATS, get_professor_emoji

        # Carregar vigilants ocupats a aquesta hora (SQLite)
        vigilants_ocupats = set(VigilanciaRepository.get_vigilants_per_hora(db, data, hora))

        # Carregar professors ja assignats com a substituts a aquesta hora (SQLite)
        substitucions_hora = SubstitucioRepository.get_by_date(db, data)
        substituts_ocupats = set()
        professors_absents = set()
        for sub in substitucions_hora:
            if sub.get("hora") == hora:
                # Afegir absents
                prof_absent = sub.get("professor_absent")
                if prof_absent:
                    professors_absents.add(prof_absent)
                # Afegir substituts ocupats
                if sub.get("substitut"):
                    substituts_ocupats.add(sub["substitut"])

        # Obtenir gestors
        substitucions_mgr, horari, alliberats, absencies = dia.gestors()
        absents_coberts = horari.absents_coberts  # ja no hi són: no sortiran com a disponibles

        # Convertir data ISO a nom del dia de l'XML
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        weekday_idx = date_obj.weekday()
        dia_name = horari.get_dia_name(weekday_idx)

        # Carregar grups sense classe des de SQLite
        grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
        grups_hora = set(grups_sense_classe.get(hora, []))

        # Obtenir disponibles
        disponibles = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)

        # Estadístiques de substitucions (dia/hora i total) per mostrar al combo
        estadistiques_subs = _calcular_estadistiques_substitucions(db, horari, data)

        # Funció per obtenir categoria de prioritat
        def get_categoria_prioritat(tipus_activitat: str) -> int:
            """Retorna l'índex de categoria segons ORDRE_PRIORITATS (0 = prioritat màxima)"""
            for i, categoria in enumerate(ORDRE_PRIORITATS):
                if tipus_activitat in categoria:
                    return i
            return len(ORDRE_PRIORITATS)

        # Funció per obtenir color segons estat
        def get_color_for_status(professor: str, tipus: str) -> tuple[str, str]:
            """
            Retorna (color_hex, status) segons l'estat del professor.

            Prioritat:
            1. ABSENT (groc) - prioritat màxima
            2. DE BAIXA (salmó) - professors de baixa
            3. OCUPAT VIGILÀNCIA (violeta)
            4. JA ASSIGNAT (vermell)
            5. alliberat (blau)
            6. disponible (verd) - default
            """
            if professor in professors_absents:
                return "rgba(255, 255, 0, 0.4)", "ABSENT"

            if professor in absents_coberts:
                return "rgba(255, 160, 122, 0.5)", "DE BAIXA"

            if professor in vigilants_ocupats:
                return "rgba(138, 43, 226, 0.4)", "OCUPAT VIGILÀNCIA"

            if professor in substituts_ocupats:
                return "rgba(255, 0, 0, 0.4)", "JA ASSIGNAT"

            if tipus.lower() == "alliberat":
                return "rgba(0, 0, 255, 0.4)", "alliberat"

            # Disponible (default)
            return "rgba(0, 255, 0, 0.4)", "disponible"

        # Convertir a format API amb text_display
        result = []
        for disp in disponibles:
            professor, tipus, detall = disp
            categoria = get_categoria_prioritat(tipus)
            color, status = get_color_for_status(professor, tipus)

            # Obtenir emoji
            emoji = get_professor_emoji(tipus)

            # Estadístiques de guàrdies (num_guardies_dia/num_guardies_total)
            stats_key_dia_hora = f"{professor}|{dia_name}|{hora}"
            stats_key_total = f"{professor}|TOTAL"
            num_guardies_dia_hora = estadistiques_subs.get(stats_key_dia_hora, 0)
            num_guardies_total = estadistiques_subs.get(stats_key_total, 0)
            stats_text = f" ({num_guardies_dia_hora}/{num_guardies_total})"

            # Flags d'ocupació
            es_absent = professor in professors_absents
            es_de_baixa = professor in absents_coberts
            es_vigilant = professor in vigilants_ocupats
            es_ja_assignat = professor in substituts_ocupats
            es_ocupat = es_absent or es_de_baixa or es_vigilant or es_ja_assignat

            # Indicadors
            indicador_alliberat = " [alliberat]" if tipus.lower() == "alliberat" else ""
            indicador_baixa = " 🏥 [DE BAIXA]" if es_de_baixa else ""
            indicador_vigilancia = " [VIGILÀNCIA]" if es_vigilant else ""

            # Format text: emoji nom (detall) (stats) [alliberat] [DE BAIXA] [VIGILÀNCIA]
            text_display = f"{emoji} {professor} ({detall}){stats_text}{indicador_alliberat}{indicador_baixa}{indicador_vigilancia}"

            result.append(
                {
                    "professor": professor,
                    "tipus": tipus,
                    "detall": detall,
                    "emoji": emoji,
                    "text_display": text_display,
                    "categoria": categoria,
                    "color": color,
                    "status": status,
                    "ocupat": es_ocupat,
                    "absent": es_absent,
                    "de_baixa": es_de_baixa,
                    "ocupat_vigilancia": es_vigilant,
                    "ja_assignat": es_ja_assignat,
                }
            )

        # Ordenar: primer disponibles, després ocupats, i professors de baixa al final
        # Prioritat d'ordenació:
        # 1. Disponibles (ocupat=False, de_baixa=False)
        # 2. Ocupats normals (ocupat=True, de_baixa=False) - ABSENT, VIGILÀNCIA, JA ASSIGNAT
        # 3. De baixa (de_baixa=True) - al final de tot
        # Dins de cada grup: per categoria i nom
        result.sort(key=lambda x: (x["de_baixa"], x["ocupat"], x["categoria"], x["professor"]))

        return {"disponibles": result}

    except MissingXmlError as e:
        _raise_missing_xml(e)
