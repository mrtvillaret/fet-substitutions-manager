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

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from collections import defaultdict

from dependencies import get_db
from repositories import SubstitucioRepository, VigilanciaRepository, GrupsAlliberatsRepository
from helpers import get_horari, get_gestors, MissingXmlError
from routes.vigilancia_absent import (
    es_vigilancia_absent,
    sincronitzar_vigilancies_absents,
    assignar_substituts_pendents as assignar_vigilancies_absents_pendents,
)
from schemas import (
    SubstitucioResponse,
    SubstitucioUpdate,
    NovaSubstitucioRequest,
    ActualitzarAbsenciesRequest
)
from models import Substitucio

router = APIRouter(prefix="/api/substitucions", tags=["Substitucions"])




def _raise_missing_xml(exc: MissingXmlError):
    raise HTTPException(
        status_code=400,
        detail={"xml_missing": True, "message": str(exc)}
    )


def _calcular_estadistiques_substitucions(db: Session, horari) -> dict:
    """Calcula estadístiques de substitucions com el desktop (dia/hora i total)."""
    estadistiques = {}

    subs = db.query(Substitucio).filter(
        Substitucio.substitut.isnot(None),
        Substitucio.substitut != '',
        Substitucio.professor_absent.isnot(None),
        Substitucio.professor_absent != ''
    ).all()

    for sub in subs:
        substitut = (sub.substitut or '').strip()
        hora = (sub.hora or '').strip()
        professor_absent = (sub.professor_absent or '').strip()
        if not substitut or not hora or not professor_absent or not sub.data:
            continue

        try:
            weekday_idx = sub.data.weekday()
        except Exception:
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
async def get_substitucions(data: str, include_all: bool = False, db: Session = Depends(get_db)):
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
    try:
        # Validar format data
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")

    try:
        # Obtenir horari per ordre correcte d'hores
        horari = get_horari(data_iso=data)

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

                result.append(SubstitucioResponse(
                    hora=sub.get("hora", ""),
                    professor_absent=sub.get("professor_absent", ""),
                    assignatura=sub.get("assignatura", ""),
                    grup=sub.get("grup", ""),
                    aula=sub.get("aula", ""),
                    substitut=sub.get("substitut", None),
                    comentaris=sub.get("comentaris", ""),
                    estat="assignada" if sub.get("substitut") else "pendent",
                    tipus_absencia=sub.get("tipus_absencia", ""),
                    updated_at=sub.get("updated_at")
                ))
        else:
            # Mode visualització: només les que generen substitució real
            # Carregar grups sense classe per filtrar-los
            grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)

            # Carregar llista de no_substituir
            from repositories import NoSubstituirRepository
            no_substituir = NoSubstituirRepository.get_all(db)

            for sub in substitucions_list:
                # Filtrar segons lògica del desktop:
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
                    if grup not in grups_hora:
                        mostrar = True
                else:
                    # CAS 2: NO té grup → comprovar si l'assignatura necessita substitució
                    if assignatura not in no_substituir:
                        mostrar = True

                if mostrar:
                    result.append(SubstitucioResponse(
                        hora=hora,
                        professor_absent=sub.get("professor_absent", ""),
                        assignatura=assignatura,
                        grup=grup,
                        aula=sub.get("aula", ""),
                        substitut=sub.get("substitut", None),
                        comentaris=sub.get("comentaris", ""),
                        estat="assignada" if sub.get("substitut") else "pendent",
                        tipus_absencia=sub.get("tipus_absencia", ""),
                        updated_at=sub.get("updated_at")
                    ))

        # Ordenar per ordre de l'horari (no alfabètic)
        ordre_hores = {hora: idx for idx, hora in enumerate(horari.hores)}
        result.sort(key=lambda x: ordre_hores.get(x.hora, 999))

        return result

    except MissingXmlError as e:
        _raise_missing_xml(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en carregar substitucions: {str(e)}")


@router.post("/{data}/generar")
async def generar_substitucions(data: str, regenerar_tot: bool = False, db: Session = Depends(get_db)):
    """
    Genera automàticament substitucions per una data (SQLite)
    (reutilitza la lògica de core/substitucions.py)
    """
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid")

    try:
        # Obtenir gestors
        substitucions_mgr, horari, alliberats, absencies = get_gestors(data_iso=data)

        # Convertir data ISO a nom del dia de l'XML
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        weekday_idx = date_obj.weekday()
        dia_name = horari.get_dia_name(weekday_idx)

        # Carregar absents i tipus des de SQLite
        substitucions_existents_list = SubstitucioRepository.get_by_date(db, data)
        absents = {}
        absents_tipus = {}
        activitats_fallback = {}

        for sub in substitucions_existents_list:
            professor = sub.get("professor_absent", "")
            hora = sub.get("hora", "")
            tipus = sub.get("tipus_absencia", "") or "ABSENCIA"

            # Skip vigilancies, encadenades i Tipus A (gestionats per separat)
            if tipus in ["VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT"]:
                continue

            if professor and hora:
                if professor not in absents:
                    absents[professor] = []
                    absents_tipus[professor] = tipus
                if hora not in absents[professor]:
                    absents[professor].append(hora)
                if (professor, hora) not in activitats_fallback:
                    activitats_fallback[(professor, hora)] = {
                        "assignatura": sub.get("assignatura", ""),
                        "grup": sub.get("grup", ""),
                        "aula": ""
                    }

        # Carregar grups sense classe des de SQLite
        grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)

        # Convertir a Sets per compatibilitat amb el codi existent
        grups_dict = {hora: set(grups) if isinstance(grups, list) else grups
                     for hora, grups in grups_sense_classe.items()}

        # Carregar vigilàncies (professors ocupats amb exàmens) de SQLite
        professors_ocupats_vigilancies = {}
        vigilancies_list = VigilanciaRepository.get_by_date(db, data)

        # Agrupar vigilants per hora
        for nivell, vigilancies in vigilancies_list.items():
            for vig in vigilancies:
                hora = vig.get('hora')
                vigilant = vig.get('vigilant')

                if hora and vigilant:
                    if hora not in professors_ocupats_vigilancies:
                        professors_ocupats_vigilancies[hora] = set()
                    professors_ocupats_vigilancies[hora].add(vigilant)

        # Carregar substitucions existents de SQLite (només si NO regenerar_tot)
        # Format: {professor}|{hora}|{assignatura}|{grup} -> {substitut, tipus_substitut, ...}
        # IMPORTANT: Només preservar les que JA tenen substitut assignat, no les pendents
        substitucions_existents = {}
        if not regenerar_tot:
            substitucions_list = SubstitucioRepository.get_by_date(db, data)
            for sub in substitucions_list:
                # Només preservar si TÉ substitut assignat
                if sub.get("substitut"):
                    clau = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"
                    substitucions_existents[clau] = sub

        # Passar la data al gestor per filtrar professors de baixa
        substitucions_mgr.data_substitucions = data

        # Comptar professors de baixa per aquesta data
        from config.constants import PROFESSORS_BAIXA
        professors_baixa_avui = []
        for baixa in PROFESSORS_BAIXA:
            try:
                from datetime import datetime as dt
                data_inici = dt.strptime(baixa['data_inici'], '%Y-%m-%d').date()
                data_final = dt.strptime(baixa['data_final'], '%Y-%m-%d').date()
                if data_inici <= date_obj.date() <= data_final:
                    professors_baixa_avui.append(baixa['professor'])
            except:
                pass

        # Debug: Mostrar configuració abans d'assignar
        print(f"\n{'='*60}")
        print(f"🔧 DEBUG PRIORITATS - Generant substitucions per {dia_name}")
        print(f"{'='*60}")
        print(f"  Regenerar tot: {regenerar_tot}")
        print(f"  Absents: {len(absents)} professors")
        print(f"  Professors de baixa: {len(professors_baixa_avui)} ({', '.join(professors_baixa_avui) if professors_baixa_avui else 'cap'})")
        print(f"  Grups sense classe: {len(grups_dict)} hores configurades")
        print(f"  Substitucions existents: {len(substitucions_existents)} (preservant: {not regenerar_tot})")

        # Afegir substituts de Tipus A (VIGILANCIA_ABSENT) a professors_ocupats,
        # per evitar que el motor els reassigni a substitucions normals.
        professors_ocupats_amb_tipus_a = {h: set(s) for h, s in professors_ocupats_vigilancies.items()}
        for sub in substitucions_existents_list:
            if es_vigilancia_absent(sub) and sub.get('substitut', '').strip():
                hora_ta = sub.get('hora', '')
                if hora_ta not in professors_ocupats_amb_tipus_a:
                    professors_ocupats_amb_tipus_a[hora_ta] = set()
                professors_ocupats_amb_tipus_a[hora_ta].add(sub['substitut'])

        # Assignar substitucions automàticament
        substitucions = substitucions_mgr.assignar_substitucions(
            dia=dia_name,
            absents=absents,
            grups_sense_classe=grups_dict,
            professors_ocupats_examens=professors_ocupats_amb_tipus_a,
            substitucions_existents=substitucions_existents,
            absents_tipus=absents_tipus,
            activitats_fallback=activitats_fallback
        )

        print(f"\n{'='*60}")
        print(f"✅ Substitucions generades: {len([s for s in substitucions if not s.get('separador')])}")
        print(f"{'='*60}\n")

        # Guardar substitucions a SQLite
        if regenerar_tot:
            # Eliminar totes les substitucions de la data EXCEPTE Tipus A (VIGILANCIA_ABSENT)
            # (sub-absents de vigilant absent: es preserven i se'ls assigna substitut al final)
            existing = SubstitucioRepository.get_by_date(db, data)
            for sub in existing:
                if es_vigilancia_absent(sub):
                    continue  # Preservar Tipus A
                SubstitucioRepository.delete(db, int(sub['id']))

            # 🔧 IMPORTANT: Carregar llista d'activitats que NO es substitueixen des de SQLite
            from repositories import NoSubstituirRepository
            no_substituir = NoSubstituirRepository.get_all(db)

            # Claus de Tipus B VIGILANCIA ja existents (per evitar duplicats si _refresh ja les va crear)
            existing_vigil_b_keys = {
                f"{s['professor_absent']}|{s['hora']}|{s['assignatura']}|{s['grup']}"
                for s in SubstitucioRepository.get_by_date(db, data)
                if s.get('tipus_absencia') == 'VIGILANCIA'
            }

            # Desar noves substitucions (ignorant separadors)
            for sub in substitucions:
                if not sub.get("separador"):
                    assignatura = sub.get('assignatura', '')
                    substitut = sub.get('substitut', '')

                    # Saltar Tipus B VIGILANCIA si ja existeix (creada per _refresh_vigilancia_substitucions)
                    if sub.get('tipus_absencia') == 'VIGILANCIA':
                        clau_b = f"{sub.get('professor_absent','')}|{sub.get('hora','')}|{assignatura}|{sub.get('grup','')}"
                        if clau_b in existing_vigil_b_keys:
                            continue

                    # 🔧 IMPORTANT: Si té substitut assignat però l'assignatura està a no_substituir, NO desar amb substitut
                    # (el motor desktop assigna substituts a activitats que no cal substituir com "Coord. Inform.")
                    if substitut and substitut.strip() and assignatura in no_substituir:
                        print(f"⚠️ IGNORANT substitució de '{assignatura}' (està a no_substituir): {sub.get('professor_absent')} a les {sub.get('hora')} → {substitut}")
                        # Desar l'absència SENSE substitut
                        sub_data = {
                            'data': data,
                            'hora': sub.get('hora', ''),
                            'professor_absent': sub.get('professor_absent', ''),
                            'assignatura': assignatura,
                            'grup': sub.get('grup', ''),
                            'aula': sub.get('aula', ''),
                            'substitut': '',  # Buidem el substitut
                            'tipus_substitut': '',
                            'tipus_absencia': sub.get('tipus_absencia', ''),
                            'comentaris': sub.get('comentaris', '')
                        }
                        SubstitucioRepository.create(db, sub_data)
                        continue

                    sub_data = {
                        'data': data,
                        'hora': sub.get('hora', ''),
                        'professor_absent': sub.get('professor_absent', ''),
                        'assignatura': assignatura,
                        'grup': sub.get('grup', ''),
                        'aula': sub.get('aula', ''),
                        'substitut': substitut,
                        'tipus_substitut': sub.get('tipus_substitut', ''),
                        'tipus_absencia': sub.get('tipus_absencia', ''),
                        'comentaris': sub.get('comentaris', '')
                    }
                    SubstitucioRepository.create(db, sub_data)

            # 🔧 IMPORTANT: Desar TOTES les hores d'absència, fins i tot si no generen substitució
            # (per exemple, Guàrdia-R, Reforç, etc. no generen substitució però cal saber que el professor està absent)
            hores_amb_substitucio = {}  # {professor: set(hores)}
            for sub in substitucions:
                if not sub.get("separador"):
                    prof = sub.get('professor_absent', '')
                    hora = sub.get('hora', '')
                    if prof and hora:
                        if prof not in hores_amb_substitucio:
                            hores_amb_substitucio[prof] = set()
                        hores_amb_substitucio[prof].add(hora)

            # Per cada professor absent, comprovar si totes les seves hores estan desades
            for professor, hores in absents.items():
                tipus_abs = absents_tipus.get(professor, 'ABSENCIA')
                for hora in hores:
                    # Comprovar si aquesta hora JA s'ha desat
                    if professor not in hores_amb_substitucio or hora not in hores_amb_substitucio[professor]:
                        # Aquesta hora NO ha generat substitució (Guàrdia, Reforç, etc.)
                        # Obtenir activitat que tenia el professor
                        activitat = horari.get_activitat(dia_name, hora, professor)
                        assignatura_absent = activitat.get("assignatura", "") if activitat else ""
                        grup_absent = activitat.get("grup", "") if activitat else ""
                        aula_absent = activitat.get("aula", "") if activitat else ""

                        # Crear entrada d'absència sense substitut
                        sub_data = {
                            'data': data,
                            'hora': hora,
                            'professor_absent': professor,
                            'assignatura': assignatura_absent,
                            'grup': grup_absent,
                            'aula': aula_absent,
                            'substitut': '',  # Buit perquè no necessita substitut
                            'tipus_substitut': '',
                            'tipus_absencia': tipus_abs,
                            'comentaris': ''
                        }
                        SubstitucioRepository.create(db, sub_data)

        else:
            # Mode "generar pendents": eliminar pendents sense substitut (excepte VIGILANCIA i VIGILANCIA_ABSENT)
            existing = SubstitucioRepository.get_by_date(db, data)
            for sub in existing:
                if not sub.get('substitut') and sub.get('tipus_absencia') not in ('VIGILANCIA', 'VIGILANCIA_ABSENT'):
                    SubstitucioRepository.delete(db, int(sub['id']))

            # 🔧 IMPORTANT: Carregar llista d'activitats que NO es substitueixen des de SQLite
            from repositories import NoSubstituirRepository
            no_substituir = NoSubstituirRepository.get_all(db)

            subs_vigil_b = [s for s in SubstitucioRepository.get_by_date(db, data)
                            if s.get('tipus_absencia') == 'VIGILANCIA']
            # Claus amb substitut: saltar (ja cobertes)
            existing_vigil_b_keys = {
                f"{s['professor_absent']}|{s['hora']}|{s['assignatura']}|{s['grup']}"
                for s in subs_vigil_b if s.get('substitut', '').strip()
            }
            # IDs sense substitut: actualitzar en lloc de crear duplicat
            vigil_b_pending_ids = {
                f"{s['professor_absent']}|{s['hora']}|{s['assignatura']}|{s['grup']}": int(s['id'])
                for s in subs_vigil_b if not s.get('substitut', '').strip()
            }

            # Crear noves substitucions (només les que no existeixen amb substitut)
            for sub in substitucions:
                if not sub.get("separador"):
                    assignatura = sub.get('assignatura', '')
                    substitut = sub.get('substitut', '')
                    grup = sub.get('grup', '')

                    # Tipus B VIGILANCIA: saltar si ja té substitut; actualitzar si és pendent
                    if sub.get('tipus_absencia') == 'VIGILANCIA':
                        clau_b = f"{sub.get('professor_absent','')}|{sub.get('hora','')}|{assignatura}|{grup}"
                        if clau_b in existing_vigil_b_keys:
                            continue
                        if clau_b in vigil_b_pending_ids and substitut and substitut.strip():
                            SubstitucioRepository.update(db, vigil_b_pending_ids[clau_b], {
                                'substitut': substitut,
                                'tipus_substitut': sub.get('tipus_substitut', ''),
                            })
                            continue

                    # 🔧 IMPORTANT: Si té substitut assignat però l'assignatura està a no_substituir, NO desar amb substitut
                    # (el motor desktop assigna substituts a activitats que no cal substituir com "Coord. Inform.")
                    if substitut and substitut.strip() and assignatura in no_substituir:
                        print(f"⚠️ IGNORANT substitució de '{assignatura}' (està a no_substituir): {sub.get('professor_absent')} a les {sub.get('hora')} → {substitut}")
                        # Comprovar si ja existeix
                        clau = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{assignatura}|{grup}"
                        if clau not in substitucions_existents:
                            # Desar l'absència SENSE substitut
                            sub_data = {
                                'data': data,
                                'hora': sub.get('hora', ''),
                                'professor_absent': sub.get('professor_absent', ''),
                                'assignatura': assignatura,
                                'grup': grup,
                                'aula': sub.get('aula', ''),
                                'substitut': '',  # Buidem el substitut
                                'tipus_substitut': '',
                                'tipus_absencia': sub.get('tipus_absencia', ''),
                                'comentaris': sub.get('comentaris', '')
                            }
                            SubstitucioRepository.create(db, sub_data)
                        continue

                    # Comprovar si ja existeix amb substitut assignat
                    clau = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{assignatura}|{grup}"

                    # Si està a substitucions_existents, ja l'hem preservat, no cal crear-la
                    if clau not in substitucions_existents:
                        sub_data = {
                            'data': data,
                            'hora': sub.get('hora', ''),
                            'professor_absent': sub.get('professor_absent', ''),
                            'assignatura': assignatura,
                            'grup': grup,
                            'aula': sub.get('aula', ''),
                            'substitut': substitut,
                            'tipus_substitut': sub.get('tipus_substitut', ''),
                            'tipus_absencia': sub.get('tipus_absencia', ''),
                            'comentaris': sub.get('comentaris', '')
                        }
                        SubstitucioRepository.create(db, sub_data)

            # 🔧 IMPORTANT: Desar TOTES les hores d'absència, fins i tot si no generen substitució
            # (per exemple, Guàrdia-R, Reforç, etc. no generen substitució però cal saber que el professor està absent)
            hores_amb_substitucio = {}  # {professor: set(hores)}
            for sub in substitucions:
                if not sub.get("separador"):
                    prof = sub.get('professor_absent', '')
                    hora = sub.get('hora', '')
                    if prof and hora:
                        if prof not in hores_amb_substitucio:
                            hores_amb_substitucio[prof] = set()
                        hores_amb_substitucio[prof].add(hora)

            # Consultar estat actual de la BD per evitar duplicats (incloent registres sense substitut)
            from collections import defaultdict as _defaultdict
            subs_bd_actuals = SubstitucioRepository.get_by_date(db, data)
            hores_existents_bd = _defaultdict(set)
            for s in subs_bd_actuals:
                hores_existents_bd[s.get('professor_absent', '')].add(s.get('hora', ''))

            # Per cada professor absent, comprovar si totes les seves hores estan desades
            for professor, hores in absents.items():
                tipus_abs = absents_tipus.get(professor, 'ABSENCIA')
                for hora in hores:
                    # Comprovar si aquesta hora JA s'ha desat (noves substitucions, BD actual o substitut preservat)
                    ja_existeix = (
                        hora in hores_amb_substitucio.get(professor, set())
                        or hora in hores_existents_bd.get(professor, set())
                    )

                    if not ja_existeix:
                        # Aquesta hora NO ha generat substitució i no existeix (Guàrdia, Reforç, etc.)
                        # Obtenir activitat que tenia el professor
                        activitat = horari.get_activitat(dia_name, hora, professor)
                        assignatura_absent = activitat.get("assignatura", "") if activitat else ""
                        grup_absent = activitat.get("grup", "") if activitat else ""
                        aula_absent = activitat.get("aula", "") if activitat else ""

                        # Crear entrada d'absència sense substitut
                        sub_data = {
                            'data': data,
                            'hora': hora,
                            'professor_absent': professor,
                            'assignatura': assignatura_absent,
                            'grup': grup_absent,
                            'aula': aula_absent,
                            'substitut': '',  # Buit perquè no necessita substitut
                            'tipus_substitut': '',
                            'tipus_absencia': tipus_abs,
                            'comentaris': ''
                        }
                        SubstitucioRepository.create(db, sub_data)

        # Assignar substituts a Tipus A VIGILANCIA pendents (vigilant absent → cobrir slot)
        if absents:
            assignar_vigilancies_absents_pendents(
                db, data, dia_name, alliberats, absents, professors_ocupats_vigilancies,
                grups_sense_classe=grups_dict
            )

        # Comptar estadístiques:
        # - ABSENCIA: des de la llista del motor (sap quines realment necessiten substitut)
        # - VIGILANCIA/VIGILANCIA_ABSENT: des de la BD (totes amb assignatura necessiten substitut)
        assignades = sum(1 for s in substitucions if not s.get("separador") and s.get("substitut", "").strip())
        pendents_detall = []

        # Pendents ABSENCIA: slots on el motor va intentar assignar i no va trobar ningú
        for s in substitucions:
            if not s.get("separador") and not s.get("substitut", "").strip():
                pendents_detall.append({
                    'professor': s.get('professor_absent', ''),
                    'hora': s.get('hora', ''),
                    'assignatura': s.get('assignatura', ''),
                    'grup': s.get('grup', ''),
                    'tipus': s.get('tipus_absencia', ''),
                })

        # Pendents VIGILANCIA i VIGILANCIA_ABSENT: des de la BD
        subs_finals = SubstitucioRepository.get_by_date(db, data)
        for s in subs_finals:
            ta = s.get('tipus_absencia', '')
            if ta not in ('VIGILANCIA', 'VIGILANCIA_ABSENT'):
                continue
            assignatura = s.get('assignatura', '') or ''
            if not assignatura:
                continue
            if s.get('substitut', '').strip():
                assignades += 1
            else:
                pendents_detall.append({
                    'professor': s.get('professor_absent', ''),
                    'hora': s.get('hora', ''),
                    'assignatura': assignatura,
                    'grup': s.get('grup', ''),
                    'tipus': ta,
                })

        pendents = len(pendents_detall)
        verb = "Regenerades" if regenerar_tot else "Generades"
        missatge = f"{verb} substitucions per {dia_name}: {assignades} assignades, {pendents} sense cobertura"

        return {
            "success": True,
            "message": missatge,
            "total": assignades + pendents,
            "assignades": assignades,
            "pendents": pendents,
            "pendents_detall": pendents_detall,
            "regenerar_tot": regenerar_tot
        }

    except MissingXmlError as e:
        _raise_missing_xml(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en generar substitucions: {str(e)}")


@router.put("/{data}/absencies/{professor}")
async def actualitzar_absencies_professor(data: str, professor: str, update: ActualitzarAbsenciesRequest, db: Session = Depends(get_db)):
    """
    Actualitza les absències d'un professor (SQLite):
    - Elimina substitucions de les hores que s'han tret
    - Manté les hores seleccionades
    - Actualitza el tipus d'absència per totes les hores
    """
    try:
        # Validar format data
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")

    try:
        # Obtenir gestors
        substitucions_mgr, horari, alliberats, absencies = get_gestors(data_iso=data)

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
                        "current_data": conflictes
                    }
                )

        types_a_processar = []
        if update.hores_absencia is not None:
            types_a_processar.append(('ABSENCIA', set(update.hores_absencia)))
        if update.hores_servei is not None:
            types_a_processar.append(('SERVEI', set(update.hores_servei)))

        total_afegides = 0
        total_eliminades = 0
        total_tipus_a_creades = 0

        for tipus, hores_noves_tipus in types_a_processar:
            # Hores antigues FILTRADES per aquest tipus concret (evita interferències entre tipus)
            hores_antigues_tipus = set(
                sub.get("hora") for sub in substitucions_list
                if sub.get("professor_absent") == professor
                and sub.get("tipus_absencia") == tipus
            )

            hores_a_eliminar_tipus = hores_antigues_tipus - hores_noves_tipus
            hores_a_afegir_tipus = hores_noves_tipus - hores_antigues_tipus

            print(f"\n🔍 DEBUG multi-tipus [{tipus}] professor={professor}")
            print(f"   Antigues: {sorted(hores_antigues_tipus)}")
            print(f"   Noves: {sorted(hores_noves_tipus)}")
            print(f"   A eliminar: {sorted(hores_a_eliminar_tipus)}")
            print(f"   A afegir: {sorted(hores_a_afegir_tipus)}")

            # Eliminar hores d'aquest tipus que s'han tret
            for sub in substitucions_list:
                if (sub.get("professor_absent") == professor
                        and sub.get("tipus_absencia") == tipus
                        and sub.get("hora") in hores_a_eliminar_tipus):
                    SubstitucioRepository.delete(db, int(sub['id']))


            # Afegir hores noves d'aquest tipus
            if hores_a_afegir_tipus:
                # Hores on el professor ja té Tipus B VIGILANCIA (classe coberta per vigilància)
                # → no cal crear ABSENCIA per aquella hora (evita triple substitució)
                hores_vigil_b = {
                    s.get('hora') for s in substitucions_list
                    if s.get('professor_absent') == professor
                    and s.get('tipus_absencia') == 'VIGILANCIA'
                }

                absents_nous = {professor: list(hores_a_afegir_tipus)}
                absents_nous_tipus = {professor: tipus}
                subs_generades = absencies.get_substitucions_necessaries(dia_name, absents_nous, absents_nous_tipus)

                for sub in subs_generades:
                    if sub.get('hora') in hores_vigil_b:
                        continue  # Classe ja coberta pel Tipus B VIGILANCIA
                    sub_data = {
                        'data': data,
                        'hora': sub.get('hora', ''),
                        'professor_absent': sub.get('professor_absent', ''),
                        'assignatura': sub.get('assignatura', ''),
                        'grup': sub.get('grup', ''),
                        'aula': sub.get('aula', ''),
                        'substitut': sub.get('substitut', ''),
                        'tipus_substitut': sub.get('tipus_substitut', ''),
                        'tipus_absencia': sub.get('tipus_absencia', ''),
                        'comentaris': sub.get('comentaris', '')
                    }
                    SubstitucioRepository.create(db, sub_data)

                hores_amb_substitucio = {sub.get("hora") for sub in subs_generades}
                for hora in hores_a_afegir_tipus:
                    if hora in hores_vigil_b:
                        continue  # Classe ja coberta pel Tipus B VIGILANCIA
                    if hora not in hores_amb_substitucio:
                        activitat = horari.get_activitat(dia_name, hora, professor)
                        assignatura_absent = activitat.get("assignatura", "") if activitat else ""
                        grup_absent = activitat.get("grup", "") if activitat else ""
                        aula_absent = activitat.get("aula", "") if activitat else ""
                        sub_data = {
                            'data': data,
                            'hora': hora,
                            'professor_absent': professor,
                            'assignatura': assignatura_absent,
                            'grup': grup_absent,
                            'aula': aula_absent,
                            'substitut': '',
                            'tipus_substitut': '',
                            'tipus_absencia': tipus,
                            'comentaris': ''
                        }
                        SubstitucioRepository.create(db, sub_data)

                # Sincronitzar Tipus A VIGILANCIA_ABSENT per les hores noves
                subs_actuals = SubstitucioRepository.get_by_date(db, data)
                total_tipus_a_creades += sincronitzar_vigilancies_absents(
                    db, data, professor, subs_actuals, hores_a_afegir_tipus
                )

            total_afegides += len(hores_a_afegir_tipus)
            total_eliminades += len(hores_a_eliminar_tipus)
            print(f"✅ [{tipus}] afegides={len(hores_a_afegir_tipus)} eliminades={len(hores_a_eliminar_tipus)}\n")

        # Sincronitzar Tipus A VIGILANCIA_ABSENT: eliminar obsolets i crear nous si cal
        totes_hores_noves = set()
        for _, hores_noves in types_a_processar:
            totes_hores_noves |= hores_noves
        subs_finals = SubstitucioRepository.get_by_date(db, data)
        sincronitzar_vigilancies_absents(db, data, professor, subs_finals, totes_hores_noves)

        return {
            "success": True,
            "message": f"Absències de {professor} actualitzades (multi-tipus)",
            "hores_afegides": total_afegides,
            "hores_eliminades": total_eliminades,
            "hores_totals": sum(len(h) for _, h in types_a_processar),
            "vigilancies_desassignades": total_tipus_a_creades,
        }
    except MissingXmlError as e:
        _raise_missing_xml(e)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar absències: {str(e)}")


@router.put("/{data}/{hora}/{professor}")
async def update_substitucio(
    data: str,
    hora: str,
    professor: str,
    update: SubstitucioUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualitza el substitut d'una substitució específica (SQLite)
    Valida que el substitut NO estigui ocupat, absent o amb classe
    """
    try:
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
                        "current_data": substitucio_actual
                    }
                )

        # Si s'està assignant un substitut (no buidant), validar-lo
        if update.substitut and update.substitut.strip():
            substitut_normalitzat = update.substitut.strip()

            # 0. Validar que l'assignatura no estigui a la llista no_substituir (SQLite)
            assignatura_actual = substitucio_actual.get('assignatura', '')
            from repositories import NoSubstituirRepository
            no_substituir = NoSubstituirRepository.get_all(db)

            if assignatura_actual in no_substituir:
                raise HTTPException(
                    status_code=400,
                    detail=f"❌ No es pot assignar substitut: '{assignatura_actual}' està a la llista d'activitats que NO es substitueixen"
                )

            # 1. Validar que NO estigui ocupat com a vigilant
            vigilants_ocupats = set(VigilanciaRepository.get_vigilants_per_hora(db, data, hora))
            if substitut_normalitzat in vigilants_ocupats:
                raise HTTPException(
                    status_code=400,
                    detail=f"❌ {substitut_normalitzat} ja està assignat com a VIGILANT a les {hora}"
                )

            # 2. Validar que NO estigui ja assignat com a substitut a una altra substitució
            for sub in substitucions_list:
                # Comprovar si el substitut ja està assignat a ALTRA substitució
                # (no comprovar la substitució actual que estem actualitzant)
                if (sub.get("hora") == hora and
                    sub.get("substitut") == substitut_normalitzat and
                    not (sub.get("hora") == hora and sub.get("professor_absent") == professor)):
                    raise HTTPException(
                        status_code=400,
                        detail=f"❌ {substitut_normalitzat} ja està assignat com a SUBSTITUT per {sub.get('professor_absent')} ({sub.get('assignatura')}, {sub.get('grup')}) a les {hora}"
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
                raise HTTPException(
                    status_code=400,
                    detail=f"❌ {substitut_normalitzat} està ABSENT a les {hora}!"
                )

            # 4. Validar que NO tingui classe (o que el seu grup estigui alliberat)
            try:
                from helpers import get_horari
                horari = get_horari(data_iso=data)

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
                        # Carregar grups alliberats (grups sense classe)
                        grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data)
                        grups_alliberats_hora = set(grups_alliberats_data.get(hora, []))

                        # Carregar grups que fan examen (de vigilàncies)
                        vigilancies_data = VigilanciaRepository.get_by_date(db, data)
                        for nivell_vigs in vigilancies_data.values():
                            for vig in nivell_vigs:
                                if vig.get("hora") == hora:
                                    grups_vig = vig.get("grups", "")
                                    if grups_vig:
                                        grups_alliberats_hora.add(grups_vig)

                        # Comprovar si el grup del substitut està alliberat
                        grup_alliberat = False
                        for grup_exam in grups_alliberats_hora:
                            # Funció simple de compatibilitat de grups
                            if grup_sub == grup_exam or grup_exam in grup_sub or grup_sub in grup_exam:
                                grup_alliberat = True
                                break

                        # Només avisar si NO està alliberat
                        if not grup_alliberat:
                            raise HTTPException(
                                status_code=400,
                                detail=f"⚠️ {substitut_normalitzat} té CLASSE a les {hora} ({assignatura_sub}, {grup_sub})"
                            )
            except HTTPException:
                raise
            except Exception as e:
                # Si no es pot validar l'horari, continuar (no bloquejar)
                print(f"⚠️ No s'ha pogut validar l'horari del substitut: {e}")
                pass

        # Actualitzar a SQLite (substitucio_actual ja trobada a l'inici)
        updates = {}
        if update.substitut is not None:
            substitut_nou = update.substitut
            tipus_substitut_nou = ""

            if substitut_nou.strip():
                try:
                    substitucions_mgr, horari, alliberats, _ = get_gestors(data_iso=data)
                    date_obj = datetime.strptime(data, "%Y-%m-%d")
                    dia_name = horari.get_dia_name(date_obj.weekday())

                    grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
                    grups_hora = set(grups_sense_classe.get(hora, []))

                    disponibles = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)
                    tipus_map = {prof: (tipus, detall) for prof, tipus, detall in disponibles}

                    tipus, detall = tipus_map.get(substitut_nou, ("", ""))
                    if tipus:
                        if tipus == detall and tipus != "alliberat":
                            tipus_substitut_nou = f"disponible ({tipus})"
                        else:
                            tipus_substitut_nou = f"{tipus} ({detall})"
                except Exception as e:
                    print(f"⚠️ No s'ha pogut calcular tipus_substitut manual: {e}")

            updates["substitut"] = substitut_nou
            updates["tipus_substitut"] = tipus_substitut_nou

        # Actualitzar comentaris si s'han especificat
        if update.comentaris is not None:
            updates["comentaris"] = update.comentaris

        updated_sub = SubstitucioRepository.update(db, int(substitucio_actual['id']), updates)

        return {
            "success": True,
            "message": f"Substitut actualitzat a {update.substitut}",
            "updated_at": updated_sub.updated_at.isoformat() if updated_sub and updated_sub.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar: {str(e)}")


@router.delete("/{data}/{hora}/{professor}/{assignatura}/{grup}")
async def eliminar_substitucio(
    data: str,
    hora: str,
    professor: str,
    assignatura: str,
    grup: str,
    updated_at: Optional[str] = None,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Elimina una substitució específica i actualitza absents si cal (SQLite)
    """
    try:
        # Carregar substitucions de SQLite
        substitucions_list = SubstitucioRepository.get_by_date(db, data)

        if not substitucions_list:
            raise HTTPException(status_code=404, detail="No hi ha substitucions per aquesta data")

        # Buscar i eliminar substitució
        trobada = False
        for sub in substitucions_list:
            # Eliminar si coincideix
            if (sub.get("hora") == hora and
                sub.get("professor_absent") == professor and
                sub.get("assignatura") == assignatura and
                sub.get("grup") == grup):
                if not force:
                    if not updated_at:
                        raise HTTPException(status_code=400, detail="Falta el paràmetre updated_at per comprovar conflictes")
                if not force and updated_at and sub.get("updated_at") and updated_at != sub.get("updated_at"):
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "error": "conflict",
                            "message": "Aquest registre ha estat modificat per un altre usuari",
                            "current_data": sub
                        }
                    )
                # Eliminar de SQLite
                SubstitucioRepository.delete(db, int(sub['id']))
                trobada = True
                break

        if not trobada:
            raise HTTPException(status_code=404, detail=f"Substitució no trobada: {hora} - {professor}")

        # ✅ Substitució eliminada només de SQLite (no cal JSON)

        return {
            "success": True,
            "message": f"Substitució de {professor} eliminada correctament"
        }

    except MissingXmlError as e:
        _raise_missing_xml(e)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar: {str(e)}")


@router.post("/{data}/nova")
async def afegir_nova_substitucio(data: str, nova: NovaSubstitucioRequest, db: Session = Depends(get_db)):
    """
    Afegeix una nova substitució per un professor absent (SQLite)
    L'assignatura i grup es carreguen automàticament de l'horari del professor

    Args:
        data: Format ISO (YYYY-MM-DD)
        nova: Dades de la nova substitució (professor, hores, tipus_absencia)
    """
    try:
        # Validar format data
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")

    try:
        # Validar que hi hagi almenys una hora
        if not nova.hores or len(nova.hores) == 0:
            raise HTTPException(status_code=400, detail="Has de seleccionar almenys una hora")

        # Obtenir gestors
        substitucions_mgr, horari, alliberats, absencies = get_gestors(data_iso=data)

        # Convertir data ISO a nom del dia de l'XML
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        weekday_idx = date_obj.weekday()
        dia_name = horari.get_dia_name(weekday_idx)

        # Crear substitucions NOMÉS per al nou professor amb absencies.get_substitucions_necessaries()
        # (això carrega automàticament assignatura i grup de l'horari)
        absents_nous = {nova.professor: nova.hores}
        absents_nous_tipus = {nova.professor: nova.tipus_absencia}
        noves_subs_generades = absencies.get_substitucions_necessaries(dia_name, absents_nous, absents_nous_tipus)

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
                if (sub.get("hora") == hora and
                    sub.get("professor_absent") == nova.professor and
                    sub.get("assignatura") == assignatura and
                    sub.get("grup") == grup):
                    existeix = True
                    break

            if not existeix:
                # Afegir a SQLite
                sub_data = {
                    'data': data,
                    'hora': nova_sub.get('hora', ''),
                    'professor_absent': nova_sub.get('professor_absent', ''),
                    'assignatura': nova_sub.get('assignatura', ''),
                    'grup': nova_sub.get('grup', ''),
                    'aula': nova_sub.get('aula', ''),
                    'substitut': nova_sub.get('substitut', ''),
                    'tipus_substitut': nova_sub.get('tipus_substitut', ''),
                    'tipus_absencia': nova_sub.get('tipus_absencia', ''),
                    'comentaris': nova_sub.get('comentaris', '')
                }
                SubstitucioRepository.create(db, sub_data)
                noves_substitucions.append(nova_sub)

        # 🔧 IMPORTANT: Desar TOTES les hores d'absència, fins i tot si no generen substitució
        # (per exemple, Guàrdia-R, Reforç, etc. no generen substitució però cal saber que el professor està absent)
        hores_amb_substitucio = {sub.get("hora") for sub in noves_subs_generades}

        for hora in nova.hores:
            if hora not in hores_amb_substitucio:
                # Aquesta hora NO ha generat substitució (Guàrdia, Reforç, etc.)
                # Comprovar si ja existeix aquesta absència a SQLite
                existeix = False
                for sub in substitucions_existents:
                    if (sub.get("hora") == hora and
                        sub.get("professor_absent") == nova.professor):
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
                        'data': data,
                        'hora': hora,
                        'professor_absent': nova.professor,
                        'assignatura': assignatura_absent,
                        'grup': grup_absent,
                        'aula': aula_absent,
                        'substitut': '',  # Buit perquè no necessita substitut
                        'tipus_substitut': '',
                        'tipus_absencia': nova.tipus_absencia,
                        'comentaris': ''
                    }
                    SubstitucioRepository.create(db, sub_data)

        # ✅ Dades desades només a SQLite (no cal JSON)

        return {
            "success": True,
            "message": f"Afegides {len(noves_substitucions)} substitucions per {nova.professor}",
            "count": len(noves_substitucions)
        }

    except MissingXmlError as e:
        _raise_missing_xml(e)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
    raise HTTPException(status_code=500, detail=f"Error en afegir substitució: {str(e)}")


@router.post("/{data}/reassign-problematics")
async def reassignar_problematics(data: str, db: Session = Depends(get_db)):
    """
    Reassigna substitucions problemàtiques (vigilant, absent, de baixa o amb classe).
    """
    try:
        substitucions_data = SubstitucioRepository.get_by_date(db, data)
        if not substitucions_data:
            raise HTTPException(status_code=404, detail=f"No hi ha substitucions per {data}")

        substituts_abans = {
            str(sub.get("id")): (sub.get("substitut") or "").strip()
            for sub in substitucions_data
            if sub.get("id")
        }

        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
        vigilants_per_hora = defaultdict(set)
        for nivell, vigs in vigilancies_dict.items():
            for vig in vigs:
                hora = (vig.get("hora") or "").strip()
                vigilant = (vig.get("vigilant") or "").strip()
                if hora and vigilant:
                    vigilants_per_hora[hora].add(vigilant)

        from config.constants import PROFESSORS_BAIXA
        professors_baixa = set()
        try:
            data_obj_date = datetime.strptime(data, "%Y-%m-%d").date()
            for baixa in PROFESSORS_BAIXA:
                data_inici = datetime.strptime(baixa['data_inici'], '%Y-%m-%d').date()
                data_final = datetime.strptime(baixa['data_final'], '%Y-%m-%d').date()
                if data_inici <= data_obj_date <= data_final:
                    professors_baixa.add(baixa['professor'])
        except:
            pass

        absents_reals_per_hora = defaultdict(set)
        for sub in substitucions_data:
            hora = (sub.get("hora") or "").strip()
            prof_absent = (sub.get("professor_absent") or "").strip()
            tipus = (sub.get("tipus_absencia") or "").strip()
            if hora and prof_absent and tipus in ("ABSENCIA", "SERVEI"):
                absents_reals_per_hora[hora].add(prof_absent)

        horari_mgr = get_horari(data_iso=data)
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        dia_name = horari_mgr.get_dia_name(date_obj.weekday())
        grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data)

        grups_examen_per_hora = defaultdict(set)
        for hora, vigs in vigilancies_dict.items():
            for vig in vigs:
                grups_vig = (vig.get("grups") or "").strip()
                if grups_vig:
                    grups_examen_per_hora[hora].add(grups_vig)
        for hora, grups in grups_alliberats_data.items():
            for grup in grups:
                grups_examen_per_hora[hora].add(grup)

        def grups_compatible(grup_classe: str, grup_examen: str) -> bool:
            if not grup_classe or not grup_examen:
                return False
            gc = grup_classe.strip().upper()
            ge = grup_examen.strip().upper()
            if gc == ge:
                return True
            if ge in gc or gc in ge:
                return True
            parts_classe = gc.split('-')
            parts_examen = ge.split('-')
            if len(parts_classe) >= 2 and len(parts_examen) >= 2:
                nivell_classe = '-'.join(parts_classe[:-1])
                nivell_examen = '-'.join(parts_examen[:-1])
                if nivell_classe == nivell_examen:
                    lletra_classe = parts_classe[-1]
                    lletra_examen = parts_examen[-1]
                    if lletra_examen in lletra_classe or lletra_classe in lletra_examen:
                        return True
            return False

        problemes = []

        for sub in substitucions_data:
            sub_id = sub.get("id")
            hora = (sub.get("hora") or "").strip()
            substitut = (sub.get("substitut") or "").strip()
            if not substitut or not hora:
                continue

            if substitut in vigilants_per_hora.get(hora, set()):
                problemes.append(sub_id)
                continue

            if substitut in professors_baixa:
                problemes.append(sub_id)
                continue

            if substitut in absents_reals_per_hora.get(hora, set()):
                problemes.append(sub_id)
                continue

            try:
                activitat_sub = horari_mgr.get_activitat(dia_name, hora, substitut)
                if activitat_sub:
                    assignatura_sub = activitat_sub.get("assignatura", "")
                    grup_sub = activitat_sub.get("grup", "")
                    if grup_sub and assignatura_sub:
                        grup_alliberat = False
                        for grup_exam in grups_examen_per_hora.get(hora, set()):
                            if grups_compatible(grup_sub, grup_exam):
                                grup_alliberat = True
                                break
                        if not grup_alliberat:
                            problemes.append(sub_id)
            except:
                pass

        cleared = 0
        for sub_id in problemes:
            if not sub_id:
                continue
            SubstitucioRepository.update(db, int(sub_id), {"substitut": "", "tipus_substitut": ""})
            cleared += 1

        await generar_substitucions(data, regenerar_tot=False, db=db)

        substitucions_despres = SubstitucioRepository.get_by_date(db, data)

        def _extract_real_type(tipus_actual: str) -> str:
            if tipus_actual.startswith("disponible (") and tipus_actual.endswith(")"):
                return tipus_actual[12:-1]
            if tipus_actual.startswith("alliberat"):
                return "alliberat"
            return tipus_actual.split(" ")[0] if tipus_actual else ""

        def _build_tipus_substitut(tipus: str, detall: str) -> str:
            if not tipus:
                return ""
            if tipus == detall and tipus != "alliberat":
                return f"disponible ({tipus})"
            return f"{tipus} ({detall})"

        try:
            substitucions_mgr, horari_mgr_full, alliberats, _ = get_gestors(data_iso=data)
            date_obj = datetime.strptime(data, "%Y-%m-%d")
            dia_name = horari_mgr_full.get_dia_name(date_obj.weekday())

            grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)

            substituts_per_hora = defaultdict(set)
            absents_actuals = defaultdict(set)
            for sub in substitucions_despres:
                hora = (sub.get("hora") or "").strip()
                substitut = (sub.get("substitut") or "").strip()
                prof_absent = (sub.get("professor_absent") or "").strip()
                tipus_absencia = (sub.get("tipus_absencia") or "").strip()
                if hora and substitut:
                    substituts_per_hora[hora].add(substitut)
                if hora and prof_absent and tipus_absencia in ("ABSENCIA", "SERVEI"):
                    absents_actuals[hora].add(prof_absent)

            for sub in substitucions_despres:
                sub_id = sub.get("id")
                hora = (sub.get("hora") or "").strip()
                substitut_actual = (sub.get("substitut") or "").strip()
                tipus_actual = (sub.get("tipus_substitut") or "").strip()
                if not sub_id or not hora or not substitut_actual:
                    continue

                grups_hora = set(grups_sense_classe.get(hora, []))
                disponibles_hora = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)

                ocupats = set(substituts_per_hora.get(hora, set()))
                ocupats.discard(substitut_actual)

                disponibles_filtrats = []
                for prof, tipus, detall in disponibles_hora:
                    if prof in absents_actuals.get(hora, set()):
                        continue
                    if prof in vigilants_per_hora.get(hora, set()):
                        continue
                    if prof in ocupats:
                        continue
                    disponibles_filtrats.append((prof, tipus, detall))

                tipus_real = _extract_real_type(tipus_actual)
                categoria_actual = substitucions_mgr._obtenir_categoria(tipus_real)

                millor = None
                for prof_disp, tipus_disp, detall_disp in disponibles_filtrats:
                    categoria_disp = substitucions_mgr._obtenir_categoria(tipus_disp)
                    if categoria_disp < categoria_actual:
                        millor = (prof_disp, tipus_disp, detall_disp)
                        break

                if millor:
                    prof_disp, tipus_disp, detall_disp = millor
                    SubstitucioRepository.update(
                        db,
                        int(sub_id),
                        {
                            "substitut": prof_disp,
                            "tipus_substitut": _build_tipus_substitut(tipus_disp, detall_disp)
                        }
                    )
                    substituts_per_hora[hora].discard(substitut_actual)
                    substituts_per_hora[hora].add(prof_disp)

            substitucions_despres = SubstitucioRepository.get_by_date(db, data)
        except Exception as e:
            print(f"⚠️ No s'ha pogut reassignar per prioritat: {e}")

        canvis = []
        for sub in substitucions_despres:
            sub_id = str(sub.get("id")) if sub.get("id") else ""
            if not sub_id:
                continue
            abans = substituts_abans.get(sub_id, "")
            despres = (sub.get("substitut") or "").strip()
            if abans != despres and (abans or despres):
                canvis.append({
                    "hora": sub.get("hora", ""),
                    "professor_absent": sub.get("professor_absent", ""),
                    "assignatura": sub.get("assignatura", ""),
                    "grup": sub.get("grup", ""),
                    "abans": abans,
                    "despres": despres
                })

        return {
            "success": True,
            "cleared": cleared,
            "changes": canvis,
            "message": "Reassignació de substitucions completada"
        }

    except MissingXmlError as e:
        _raise_missing_xml(e)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en reassignar problemàtics: {str(e)}")


@router.get("/{data}/hores-professor/{professor}")
async def get_hores_professor(data: str, professor: str, db: Session = Depends(get_db)):
    """Retorna les hores on el professor té classe, i les hores que és al centre sense classe."""
    try:
        from repositories import NoSubstituirRepository
        horari = get_horari(data_iso=data)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{data}/{hora}/disponibles")
async def get_disponibles(data: str, hora: str, db: Session = Depends(get_db)):
    """
    Retorna professors disponibles per una hora específica,
    ordenats per prioritat amb informació del que estan fent.
    Format igual que el programa desktop.
    """
    try:
        # Validar format data
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid")

    try:
        from config.constants import ORDRE_PRIORITATS, get_professor_emoji

        # Carregar vigilants ocupats a aquesta hora (SQLite)
        vigilants_ocupats = set(VigilanciaRepository.get_vigilants_per_hora(db, data, hora))

        # Carregar professors ja assignats com a substituts a aquesta hora (SQLite)
        substitucions_hora = SubstitucioRepository.get_by_date(db, data)
        substituts_ocupats = set()
        professors_absents = set()
        for sub in substitucions_hora:
            if sub.get('hora') == hora:
                # Afegir absents
                prof_absent = sub.get('professor_absent')
                if prof_absent:
                    professors_absents.add(prof_absent)
                # Afegir substituts ocupats
                if sub.get('substitut'):
                    substituts_ocupats.add(sub['substitut'])

        # Carregar professors de baixa per aquesta data
        from config.constants import PROFESSORS_BAIXA
        professors_baixa = set()
        try:
            data_obj = datetime.strptime(data, "%Y-%m-%d").date()
            for baixa in PROFESSORS_BAIXA:
                data_inici = datetime.strptime(baixa['data_inici'], '%Y-%m-%d').date()
                data_final = datetime.strptime(baixa['data_final'], '%Y-%m-%d').date()
                if data_inici <= data_obj <= data_final:
                    professors_baixa.add(baixa['professor'])
        except:
            pass

        # Obtenir gestors
        substitucions_mgr, horari, alliberats, absencies = get_gestors(data_iso=data)

        # Convertir data ISO a nom del dia de l'XML
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        weekday_idx = date_obj.weekday()
        dia_name = horari.get_dia_name(weekday_idx)

        # Carregar grups sense classe des de SQLite
        grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
        grups_hora = set(grups_sense_classe.get(hora, []))

        # Obtenir disponibles (igual que l'app desktop)
        disponibles = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)

        # Estadístiques de substitucions (dia/hora i total) per mostrar al combo
        estadistiques_subs = _calcular_estadistiques_substitucions(db, horari)

        # Funció per obtenir categoria de prioritat
        def get_categoria_prioritat(tipus_activitat: str) -> int:
            """Retorna l'índex de categoria segons ORDRE_PRIORITATS (0 = prioritat màxima)"""
            for i, categoria in enumerate(ORDRE_PRIORITATS):
                if tipus_activitat in categoria:
                    return i
            return len(ORDRE_PRIORITATS)

        # Funció per obtenir color segons estat (igual que desktop program)
        def get_color_for_status(professor: str, tipus: str) -> tuple[str, str]:
            """
            Retorna (color_hex, status) segons l'estat del professor.
            Colors iguals que _get_color_for_status() de widgets.py del desktop.

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

            if professor in professors_baixa:
                return "rgba(255, 160, 122, 0.5)", "DE BAIXA"

            if professor in vigilants_ocupats:
                return "rgba(138, 43, 226, 0.4)", "OCUPAT VIGILÀNCIA"

            if professor in substituts_ocupats:
                return "rgba(255, 0, 0, 0.4)", "JA ASSIGNAT"

            if tipus.lower() == "alliberat":
                return "rgba(0, 0, 255, 0.4)", "alliberat"

            # Disponible (default)
            return "rgba(0, 255, 0, 0.4)", "disponible"

        # Convertir a format API amb text_display igual que desktop
        result = []
        for disp in disponibles:
            professor, tipus, detall = disp
            categoria = get_categoria_prioritat(tipus)
            color, status = get_color_for_status(professor, tipus)

            # Obtenir emoji
            emoji = get_professor_emoji(tipus)

            # Estadístiques de guàrdies (num_guardies_dia/num_guardies_total) com al desktop
            stats_key_dia_hora = f"{professor}|{dia_name}|{hora}"
            stats_key_total = f"{professor}|TOTAL"
            num_guardies_dia_hora = estadistiques_subs.get(stats_key_dia_hora, 0)
            num_guardies_total = estadistiques_subs.get(stats_key_total, 0)
            stats_text = f" ({num_guardies_dia_hora}/{num_guardies_total})"

            # Flags d'ocupació
            es_absent = professor in professors_absents
            es_de_baixa = professor in professors_baixa
            es_vigilant = professor in vigilants_ocupats
            es_ja_assignat = professor in substituts_ocupats
            es_ocupat = es_absent or es_de_baixa or es_vigilant or es_ja_assignat

            # Indicadors
            indicador_alliberat = " [alliberat]" if tipus.lower() == "alliberat" else ""
            indicador_baixa = " 🏥 [DE BAIXA]" if es_de_baixa else ""
            indicador_vigilancia = " [VIGILÀNCIA]" if es_vigilant else ""

            # Format text igual que desktop: emoji nom (detall) (stats) [alliberat] [DE BAIXA] [VIGILÀNCIA]
            text_display = f"{emoji} {professor} ({detall}){stats_text}{indicador_alliberat}{indicador_baixa}{indicador_vigilancia}"

            result.append({
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
                "ja_assignat": es_ja_assignat
            })

        # Ordenar: primer disponibles, després ocupats, i professors de baixa al final
        # Prioritat d'ordenació:
        # 1. Disponibles (ocupat=False, de_baixa=False)
        # 2. Ocupats normals (ocupat=True, de_baixa=False) - ABSENT, VIGILÀNCIA, JA ASSIGNAT
        # 3. De baixa (de_baixa=True) - al final de tot
        # Dins de cada grup: per categoria i nom
        result.sort(key=lambda x: (x["de_baixa"], x["ocupat"], x["categoria"], x["professor"]))

        return {
            "disponibles": result
        }

    except MissingXmlError as e:
        _raise_missing_xml(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir disponibles: {str(e)}")
