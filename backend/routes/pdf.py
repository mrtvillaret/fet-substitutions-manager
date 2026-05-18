"""
Routes per generació i validació de PDFs:
- Validació abans de generar PDF
- PDF complet (substitucions + vigilàncies)
- PDF vigilàncies per un dia
- PDF vigilàncies per interval de dates
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from collections import defaultdict
import tempfile
import shutil
import os

from dependencies import get_db
from auth_utils import get_current_user
from database import get_export_dir_for_institucio
from helpers import get_gestors, get_horari
from repositories import VigilanciaRepository, SubstitucioRepository, GrupsAlliberatsRepository
from export.pdf.engine import PDFCompletExporter
from i18n_setup import translate

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


def _extract_real_type(tipus_actual: str) -> str:
    if tipus_actual.startswith("disponible (") and tipus_actual.endswith(")"):
        return tipus_actual[12:-1]
    if tipus_actual.startswith("alliberat"):
        return "alliberat"
    return tipus_actual.split(" ")[0] if tipus_actual else ""


def _build_absents_by_professor(substitucions_data: list) -> dict:
    absents = defaultdict(list)
    for sub in substitucions_data:
        tipus_absencia = sub.get("tipus_absencia", "")
        if tipus_absencia not in ("ABSENCIA", "SERVEI"):
            continue
        professor = sub.get("professor_absent", "")
        hora = sub.get("hora", "")
        if professor and hora:
            absents[professor].append(hora)
    return absents


def _omplir_aula_substitucions(substitucions_data: list, horari_mgr, date_obj: datetime) -> None:
    """Omple l'aula de les substitucions si falta (només per al PDF)."""
    dia_name = horari_mgr.get_dia_name(date_obj.weekday())
    for sub in substitucions_data:
        if sub.get("aula"):
            continue
        hora = sub.get("hora", "")
        professor = sub.get("professor_absent", "") or sub.get("professor", "")
        if not hora or not professor:
            continue
        activitat = horari_mgr.get_activitat(dia_name, hora, professor)
        if activitat:
            aula = activitat.get("aula", "")
            if aula:
                sub["aula"] = aula


def _calcular_avisos_prioritat(
    data: str,
    substitucions_data: list,
    vigilancies_by_hora: dict,
    absents_per_hora: dict,
    grups_sense_classe: dict,
    db: Session,
    current_user
) -> list:
    avisos = []
    try:
        from routes.prioritats import _recarregar_prioritats_desde_bd
        _recarregar_prioritats_desde_bd(db)

        instit = getattr(current_user, "institucio", None)
        substitucions_mgr, horari, alliberats, _ = get_gestors(institucio=instit, data_iso=data)
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        dia_name = horari.get_dia_name(date_obj.weekday())

        substituts_per_hora = defaultdict(set)
        for sub in substitucions_data:
            hora = sub.get("hora", "")
            substitut = sub.get("substitut", "")
            if hora and substitut:
                substituts_per_hora[hora].add(substitut)

        vigilants_per_hora = {
            hora: {v.get("vigilant", "").strip() for v in vigs if v.get("vigilant", "").strip()}
            for hora, vigs in vigilancies_by_hora.items()
        }

        absents_actuals = _build_absents_by_professor(substitucions_data)

        for sub in substitucions_data:
            if sub.get("separador") or not sub.get("substitut"):
                continue

            hora = sub.get("hora", "")
            substitut_actual = sub.get("substitut", "")
            tipus_actual = sub.get("tipus_substitut", "")
            if not hora:
                continue

            grups_hora = set(grups_sense_classe.get(hora, []))
            disponibles_hora = alliberats.get_tots_disponibles(dia_name, hora, grups_hora)
            tipus_per_professor = {prof: tipus for prof, tipus, _ in disponibles_hora}

            disponibles_filtrats = []
            for prof, tipus, detall in disponibles_hora:
                if hora in absents_actuals.get(prof, []):
                    continue
                if prof in vigilants_per_hora.get(hora, set()):
                    continue
                if prof in substituts_per_hora.get(hora, set()):
                    continue
                disponibles_filtrats.append((prof, tipus, detall))

            tipus_real = tipus_per_professor.get(substitut_actual, _extract_real_type(tipus_actual))
            categoria_actual = substitucions_mgr._obtenir_categoria(tipus_real)

            millor_trobat = None
            for prof_disp, tipus_disp, _ in disponibles_filtrats:
                categoria_disponible = substitucions_mgr._obtenir_categoria(tipus_disp)
                if categoria_disponible < categoria_actual:
                    millor_trobat = (prof_disp, tipus_disp)
                    break

            if millor_trobat:
                prof_disp, tipus_disp = millor_trobat
                avisos.append(
                    translate("• {time}: {prof} ({type_disp}) disponible en lloc de {sub} ({type_curr})").format(
                        time=hora,
                        prof=prof_disp,
                        type_disp=tipus_disp,
                        sub=substitut_actual,
                        type_curr=tipus_real
                    )
                )
    except Exception as e:
        print(translate("⚠️ Error comprovant millors prioritats: {error}").format(error=e))
        return []

    return avisos



@router.get("/{data}/validacions")
async def validar_abans_pdf(
    data: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Valida vigilàncies i substitucions abans de generar PDF.
    Retorna conflictes crítics i avisos igual que el programa desktop.
    """
    try:
        # Validar format data
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid")

    try:
        # Carregar vigilàncies (SQLite)
        vigilancies_data = VigilanciaRepository.get_by_date(db, data)

        # Carregar substitucions (SQLite)
        substitucions_data = SubstitucioRepository.get_by_date(db, data)

        conflicts = []
        warnings = []

        # 1. Validar vigilàncies
        vigilancies_by_hora = defaultdict(list)
        for vig in vigilancies_data.values():
            for v in vig:
                hora = v.get("hora", "")
                vigilant = v.get("vigilant", "")
                aula = v.get("aula", "")
                tipus = v.get("tipus", "")

                if hora:
                    vigilancies_by_hora[hora].append(v)

                    # Conflicte crític: sense vigilant
                    if not vigilant or vigilant.strip() == "":
                        conflicts.append(translate("❌ {hora}: {tipus} sense vigilant assignat").format(hora=hora, tipus=tipus))

                    # Conflicte crític: sense aula
                    if not aula or aula.strip() == "":
                        conflicts.append(translate("🏫 {hora}: {tipus} sense aula assignada").format(hora=hora, tipus=tipus))

        # 2. Detectar vigilants duplicats a la mateixa hora
        for hora, vigs in vigilancies_by_hora.items():
            vigilants = [v.get("vigilant") for v in vigs if v.get("vigilant")]
            for vigilant in set(vigilants):
                count = vigilants.count(vigilant)
                if count > 1:
                    warnings.append(translate("🔄 {hora}: {vigilant} assignat {count} vegades com a vigilant").format(hora=hora, vigilant=vigilant, count=count))

        # 3. Detectar aules duplicades
        for hora, vigs in vigilancies_by_hora.items():
            aules = [v.get("aula") for v in vigs if v.get("aula") and v.get("aula") != "ENLLAÇ"]
            for aula in set(aules):
                count = aules.count(aula)
                if count > 1:
                    warnings.append(translate("🏫 {hora}: Aula {aula} duplicada").format(hora=hora, aula=aula))

        # 4. Detectar vigilants absents o amb classe
        absents_per_hora = defaultdict(set)
        absents_del_dia = set()  # Professors absents en qualsevol hora del dia
        professors_alliberats_per_vigilancia = defaultdict(dict)  # {hora: {prof: substitut}}
        # Vigilants absents amb cobertura ja assignada (VIGILANCIA_ABSENT amb substitut)
        vigilants_absents_coberts = {}  # {(professor, hora): substitut}

        for sub in substitucions_data:
            hora = sub.get("hora", "")
            prof_absent = sub.get("professor_absent", "")
            tipus_abs = (sub.get("tipus_absencia") or "").upper().strip()

            # Detectar si el professor ha estat alliberat específicament per vigilar
            if tipus_abs == "VIGILANCIA":
                if hora and prof_absent:
                    professors_alliberats_per_vigilancia[hora][prof_absent] = sub.get("substitut", "").strip()
                continue

            # Vigilant absent (Tipus A): registrar cobertura i avisar si sense substitut
            if tipus_abs == "VIGILANCIA_ABSENT":
                if hora and prof_absent:
                    absents_per_hora[hora].add(prof_absent)
                    absents_del_dia.add(prof_absent)
                    substitut = sub.get("substitut", "").strip()
                    if substitut:
                        vigilants_absents_coberts[(prof_absent, hora)] = substitut
                    else:
                        warnings.append(translate("❌ {hora}: {prof} - VIGILÀNCIA sense substitut assignat").format(hora=hora, prof=prof_absent))
                continue

            # Ignorar encadenades
            if tipus_abs in ["VIGILÀNCIA", "ENCADENADA"]:
                continue

            if hora and prof_absent:
                absents_per_hora[hora].add(prof_absent)
                absents_del_dia.add(prof_absent)  # Marcar com absent del dia

        # Carregar grups alliberats (grups sense classe) de la BD

        # Carregar grups alliberats (grups sense classe) de la BD
        grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data)

        # Carregar horari per comprovar si vigilants tenen classe
        try:
            horari_mgr = get_horari(current_user.institucio, data)

            # Convertir data ISO a dia de la setmana
            date_obj = datetime.strptime(data, "%Y-%m-%d")
            weekday_idx = date_obj.weekday()
            dia_name = horari_mgr.get_dia_name(weekday_idx)

            # Funció per comprovar si dos grups tenen overlap (grup alliberat)
            def grups_compatible(grup_classe: str, grup_examen: str) -> bool:
                """Retorna True si el grup de classe està inclòs en el grup d'examen"""
                if not grup_classe or not grup_examen:
                    return False

                # Normalitzar: eliminar espais i convertir a majúscules
                gc = grup_classe.strip().upper()
                ge = grup_examen.strip().upper()

                # Cas exacte
                if gc == ge:
                    return True

                # Cas grup combinat: "1-BATX-AB" conté "1-BATX-A"
                # Si el grup de classe conté el grup d'examen o viceversa
                if ge in gc or gc in ge:
                    return True

                # Cas grups múltiples separats per "-": "1-BATX-A" està a "1-BATX-A-B"
                parts_classe = gc.split('-')
                parts_examen = ge.split('-')

                # Si comparteixen el mateix prefix (nivell)
                if len(parts_classe) >= 2 and len(parts_examen) >= 2:
                    nivell_classe = '-'.join(parts_classe[:-1])
                    nivell_examen = '-'.join(parts_examen[:-1])
                    if nivell_classe == nivell_examen:
                        # Comprovar si la lletra de grup coincideix
                        lletra_classe = parts_classe[-1]
                        lletra_examen = parts_examen[-1]
                        # "AB" conté "A" o "B"
                        if lletra_examen in lletra_classe or lletra_classe in lletra_examen:
                            return True

                return False

            for hora, vigs in vigilancies_by_hora.items():
                # Recollir tots els grups que fan examen a aquesta hora + grups alliberats
                grups_examen = set()
                for vig in vigs:
                    grups_vig = vig.get("grups", "")
                    if grups_vig:
                        grups_examen.add(grups_vig)

                # Afegir grups alliberats d'aquesta hora
                if hora in grups_alliberats_data:
                    for grup_alliberat in grups_alliberats_data[hora]:
                        grups_examen.add(grup_alliberat)

                for vig in vigs:
                    vigilant = vig.get("vigilant", "")
                    if not vigilant:
                        continue

                    # Comprovar si està absent A AQUESTA HORA ESPECÍFICA
                    if vigilant in absents_per_hora.get(hora, set()):
                        if (vigilant, hora) in vigilants_absents_coberts:
                            substitut_cobert = vigilants_absents_coberts[(vigilant, hora)]
                            warnings.append(translate("ℹ️ {hora}: Vigilant {vigilant} absent (cobert per {substitut})").format(hora=hora, vigilant=vigilant, substitut=substitut_cobert))
                        else:
                            warnings.append(translate("⚠️ {hora}: Vigilant {vigilant} absent sense cobertura").format(hora=hora, vigilant=vigilant))
                        continue

                    # Comprovar si té classe a l'horari
                    activitat = horari_mgr.get_activitat(dia_name, hora, vigilant)
                    if activitat:
                        assignatura = activitat.get("assignatura", "")
                        grup = activitat.get("grup", "")

                        # Si no té grup específic → són disponibles (Guàrdia, Reforç, etc.)
                        if not grup or not grup.strip():
                            continue

                        # Si no té assignatura → també disponible
                        if not assignatura or not assignatura.strip():
                            continue

                        # Comprovar si el grup està alliberat (fa examen)
                        grup_alliberat = False
                        for grup_exam in grups_examen:
                            if grups_compatible(grup, grup_exam):
                                grup_alliberat = True
                                break

                        # Només avisar si NO està alliberat I NO té una substitució de vigilància ja creada
                        if not grup_alliberat and vigilant not in professors_alliberats_per_vigilancia.get(hora, {}):
                            warnings.append(translate("⚠️ {hora}: Vigilant {vigilant} té classe ({assignatura}, {grup})").format(hora=hora, vigilant=vigilant, assignatura=assignatura, grup=grup))
        except Exception as e:
            # Si no es pot carregar l'horari, només comprovar absències del dia
            for hora, vigs in vigilancies_by_hora.items():
                for vig in vigs:
                    vigilant = vig.get("vigilant", "")
                    if vigilant and vigilant in absents_del_dia:
                        if (vigilant, hora) in vigilants_absents_coberts:
                            continue
                        warnings.append(translate("⚠️ {hora}: Vigilant {vigilant} absent sense cobertura").format(hora=hora, vigilant=vigilant))

        # 5. Detectar substituts ja assignats múltiples vegades
        substituts_per_hora = defaultdict(list)
        for sub in substitucions_data:
            hora = sub.get("hora", "")
            substitut = sub.get("substitut", "")
            if hora and substitut:
                substituts_per_hora[hora].append(substitut)

        for hora, substituts in substituts_per_hora.items():
            for substitut in set(substituts):
                count = substituts.count(substitut)
                if count > 1:
                    warnings.append(translate("🔄 {hora}: {substitut} assignat {count} vegades com a substitut").format(hora=hora, substitut=substitut, count=count))

        # 5.5 Detectar professors que són vigilant i substitut a la mateixa hora
        for hora, vigs in vigilancies_by_hora.items():
            vigilants_hora = {
                v.get("vigilant", "").strip()
                for v in vigs
                if v.get("vigilant") and v.get("vigilant").strip()
            }
            substituts_hora = {
                s.get("substitut", "").strip()
                for s in substitucions_data
                if s.get("hora") == hora and s.get("substitut") and s.get("substitut").strip()
            }
            for professor in sorted(vigilants_hora.intersection(substituts_hora)):
                warnings.append(translate("⚠️ {hora}: {professor} és vigilant i substitut alhora").format(hora=hora, professor=professor))

        # 6. Detectar absències sense substitut (només si necessiten substitut)
        for sub in substitucions_data:
            hora = sub.get("hora", "")
            prof_absent = sub.get("professor_absent", "")
            substitut = sub.get("substitut", "")
            assignatura = sub.get("assignatura", "")
            grup = sub.get("grup", "")

            # Conflicte crític: absència AMB GRUP sense substitut assignat
            # Si NO té grup (Guàrdia-R, hores fora horari, etc.) → NO generar avís
            if (not substitut or substitut.strip() == "") and grup and grup.strip():
                grups_hora = grups_alliberats_data.get(hora, [])
                if grup not in grups_hora:
                    conflicts.append(translate("❌ {hora}: {prof_absent} ({assignatura}, {grup}) sense substitut").format(hora=hora, prof_absent=prof_absent, assignatura=assignatura, grup=grup))

        # 7. Detectar professors de baixa assignats com a vigilants o substituts
        from config.constants import PROFESSORS_BAIXA
        from datetime import datetime as dt

        professors_baixa_avui = set()
        try:
            data_obj = datetime.strptime(data, "%Y-%m-%d").date()
            for baixa in PROFESSORS_BAIXA:
                data_inici = dt.strptime(baixa['data_inici'], '%Y-%m-%d').date()
                data_final = dt.strptime(baixa['data_final'], '%Y-%m-%d').date()
                if data_inici <= data_obj <= data_final:
                    professors_baixa_avui.add(baixa['professor'])
        except:
            pass

        # Comprovar vigilants
        for hora, vigs in vigilancies_by_hora.items():
            for vig in vigs:
                vigilant = vig.get("vigilant", "")
                if vigilant and vigilant in professors_baixa_avui:
                    warnings.append(translate("🏥 {hora}: {vigilant} està de baixa però assignat com a vigilant").format(hora=hora, vigilant=vigilant))

        # Comprovar substituts
        for sub in substitucions_data:
            hora = sub.get("hora", "")
            substitut = sub.get("substitut", "")
            if substitut and substitut in professors_baixa_avui:
                warnings.append(translate("🏥 {hora}: {substitut} està de baixa però assignat com a substitut").format(hora=hora, substitut=substitut))

        # 8. Detectar substituts absents o amb classe
        try:
            for sub in substitucions_data:
                hora = sub.get("hora", "")
                substitut = sub.get("substitut", "")
                if not substitut or not substitut.strip():
                    continue

                # Comprovar si el substitut està REALMENT absent (ABSENCIA o SERVEI, NO ENCADENADA)
                absents_reals_hora = set()
                for prof in absents_per_hora.get(hora, set()):
                    # Buscar el tipus d'absència d'aquest professor a aquesta hora
                    for sub_data in substitucions_data:
                        if sub_data.get("hora") == hora and sub_data.get("professor_absent") == prof:
                            tipus = sub_data.get("tipus_absencia", "")
                            # Només comptar ABSENCIA i SERVEI com absències reals
                            if tipus in ("ABSENCIA", "SERVEI"):
                                absents_reals_hora.add(prof)
                            break

                if substitut in absents_reals_hora:
                    conflicts.append(translate("❌ {hora}: Substitut {substitut} està absent!").format(hora=hora, substitut=substitut))

                # Comprovar si té classe a l'horari
                try:
                    activitat_sub = horari_mgr.get_activitat(dia_name, hora, substitut)
                    if activitat_sub:
                        assignatura_sub = activitat_sub.get("assignatura", "")
                        grup_sub = activitat_sub.get("grup", "")

                        # Si té grup específic, comprovar si està alliberat
                        if grup_sub and grup_sub.strip():
                            # Comprovar si el grup està alliberat (fa examen o grups sense classe)
                            grups_examen_hora = set()
                            for vig in vigilancies_by_hora.get(hora, []):
                                grups_vig = vig.get("grups", "")
                                if grups_vig:
                                    grups_examen_hora.add(grups_vig)

                            # Afegir grups alliberats (grups sense classe)
                            if hora in grups_alliberats_data:
                                for grup_alliberat in grups_alliberats_data[hora]:
                                    grups_examen_hora.add(grup_alliberat)

                            grup_alliberat = False
                            for grup_exam in grups_examen_hora:
                                if grups_compatible(grup_sub, grup_exam):
                                    grup_alliberat = True
                                    break

                            # Només avisar si NO està alliberat
                            if not grup_alliberat:
                                warnings.append(translate("⚠️ {hora}: Substitut {substitut} té classe ({assignatura_sub}, {grup_sub})").format(hora=hora, substitut=substitut, assignatura_sub=assignatura_sub, grup_sub=grup_sub))
                except:
                    pass
        except:
            pass

        avisos_prioritat = _calcular_avisos_prioritat(
            data,
            substitucions_data,
            vigilancies_by_hora,
            absents_per_hora,
            grups_alliberats_data,
            db,
            current_user
        )
        warnings.extend(avisos_prioritat)

        # 9. Informar sobre vigilàncies cobertes (Tipus B)
        total_vigs_cobertes = sum(1 for profs in professors_alliberats_per_vigilancia.values() for s in profs.values() if s)
        total_vigs_pendents = sum(1 for profs in professors_alliberats_per_vigilancia.values() for s in profs.values() if not s)
        if total_vigs_cobertes > 0:
            warnings.append(f"ℹ️ {total_vigs_cobertes} vigilàncies cobertes automàticament (substitució tècnica)")
        if total_vigs_pendents > 0:
            warnings.append(f"❌ {total_vigs_pendents} vigilàncies cobertes automàticament sense substitut assignat")

        # Ordenar per hora
        def get_hour_sort_key(text):
            """Extreu l'hora d'un text per ordenar"""
            try:
                parts = text.split(":")
                if len(parts) >= 2:
                    hour = int(parts[0].split()[-1])
                    minute = int(parts[1].split()[0])
                    return (hour, minute)
            except:
                pass
            return (99, 99)

        conflicts.sort(key=get_hour_sort_key)
        warnings.sort(key=get_hour_sort_key)

        return {
            "conflicts": conflicts,
            "warnings": warnings,
            "total": len(conflicts) + len(warnings),
            "has_critical": len(conflicts) > 0
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en validar PDF: {str(e)}")


@router.get("/complete/{data}")
async def generar_pdf_complet(
    data: str,
    include_substitutions: bool = True,
    include_vigilancies: bool = True,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    show_conflicts: bool = True,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Genera PDF complet del dia amb substitucions i/o vigilàncies (TOTS els nivells) (SQLite)
    """
    try:
        # Validar data
        try:
            date_obj = datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")

        from utils.date_context import DateContext
        data_text = DateContext.from_iso(data).full_format

        # Carregar dades
        substitucions_data = []
        vigilancies_list = []

        if include_substitutions:
            # Carregar substitucions des de SQLite
            substitucions_raw = SubstitucioRepository.get_by_date(db, data)

            # FILTRAR: només mostrar al PDF les que generen substitució real
            # Lògica del desktop:
            # 1. Té grup I el grup NO està alliberat, O
            # 2. NO té grup però l'assignatura NO està a no_substituir
            grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)

            from repositories import NoSubstituirRepository
            no_substituir = NoSubstituirRepository.get_all(db)

            for sub in substitucions_raw:
                grup = sub.get("grup", "")
                hora = sub.get("hora", "")
                assignatura = sub.get("assignatura", "")
                tipus_absencia = sub.get("tipus_absencia", "")

                mostrar = False

                # VIGILANCIA_ABSENT: sempre mostrar (substitució de vigilant absent)
                # El grup pot estar alliberat perquè fa examen, però igualment cal el substitut
                if tipus_absencia == "VIGILANCIA_ABSENT":
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
                    substitucions_data.append(sub)

        if include_vigilancies:
            # Carregar vigilàncies (TOTS els nivells) des de SQLite i flatten a llista
            vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
            # Flatten: combinar totes les vigilàncies de tots els nivells
            for nivell_vigs in vigilancies_dict.values():
                vigilancies_list.extend(nivell_vigs)

        # Determinar tipus de PDF
        if include_substitutions and include_vigilancies:
            tipus_pdf = "complet"
        elif include_substitutions:
            tipus_pdf = "substitucions"
        elif include_vigilancies:
            tipus_pdf = "vigilancies"
        else:
            tipus_pdf = "complet"

        # Inicialitzar exporter amb hores
        horari_mgr = get_horari(current_user.institucio, data)
        hores = horari_mgr.hores

        if include_substitutions and substitucions_data:
            _omplir_aula_substitucions(substitucions_data, horari_mgr, date_obj)

        export_dir = get_export_dir_for_institucio(current_user.institucio)
        exporter = PDFCompletExporter(hores=hores, export_dir=str(export_dir))

        # Configurar opcions via atributs
        exporter.show_comments_column = show_comments
        exporter.show_hours_column = show_hours
        if compress:
            exporter._auto_compression_active = True

        # Obtenir conflictes i avisos
        validacio_response = await validar_abans_pdf(data, db, current_user)
        all_issues = []
        if show_conflicts:
            all_issues = (validacio_response.get("conflicts") or []) + (validacio_response.get("warnings") or [])

        # Generar PDF (es desa a exports/)
        filename = exporter.exportar(
            substitucions=substitucions_data,
            vigilancies=vigilancies_list,
            data_text=data_text,
            data_iso=data,
            tipus_pdf=tipus_pdf,
            conflictes=all_issues  # Passar conflictes al PDF
        )

        # Moure PDF a temp dir
        if not filename:
            raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
        exports_path = export_dir / filename
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"complet_{data}_{timestamp}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)

        shutil.copy(str(exports_path), pdf_path)

        # Retornar fitxer
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=pdf_filename,
            headers={"Content-Disposition": f"attachment; filename={pdf_filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en generar PDF complet: {str(e)}")


# ===== PDF VIGILÀNCIES =====

@router.get("/vigilancies/interval")
async def generar_pdf_interval(
    data_inici: str,
    data_final: str,
    nivells: str = "",
    include_weekends: bool = False,
    include_empty_days: bool = False,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    include_substitucions: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Genera PDF d'interval de dates per vigilàncies (SQLite)
    """
    print(f"🚀 INICI generar_pdf_interval")
    print(f"  data_inici={data_inici!r}, data_final={data_final!r}, nivells={nivells!r}")

    # Debug logging
    print(f"📅 PDF Interval - Paràmetres rebuts:")
    print(f"  data_inici: {data_inici!r} (type: {type(data_inici)})")
    print(f"  data_final: {data_final!r} (type: {type(data_final)})")
    print(f"  nivells: {nivells!r}")

    # Validar dates
    date_inici = datetime.strptime(data_inici, "%Y-%m-%d")
    date_final = datetime.strptime(data_final, "%Y-%m-%d")

    try:

        if date_inici > date_final:
            raise HTTPException(status_code=400, detail="La data inicial ha de ser anterior a la final")

        # Parsejar nivells
        nivells_list = [n.strip() for n in nivells.split(',') if n.strip()] if nivells else []
        nivells_specified = bool(nivells_list)

        # Generar llista de dates
        dates_list = []
        current_date = date_inici

        while current_date <= date_final:
            # Si no volem caps de setmana, saltar dissabte (5) i diumenge (6)
            if include_weekends or current_date.weekday() < 5:
                dates_list.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)

        # Inicialitzar exporter amb hores (només una vegada)
        horari_mgr = get_horari(current_user.institucio, data_inici)
        hores = horari_mgr.hores

        # Recopilar totes les vigilàncies de tots els dies (com fa desktop app)
        from utils.date_context import DateContext
        interval_vigilancies = []
        interval_substitucions = []

        for data_str in dates_list:
            # Carregar vigilàncies per aquest dia des de SQLite
            vigilancies_dict = VigilanciaRepository.get_by_date(db, data_str)

            if not vigilancies_dict:
                if include_empty_days:
                    date_ctx = DateContext.from_iso(data_str)
                    interval_vigilancies.append({
                        "_dia_interval": date_ctx.full_format,
                        "_data_iso": data_str,
                        "_empty_day": True
                    })
                if not include_empty_days:
                    continue  # Saltar dies sense vigilàncies
                day_vigilancies = []
            else:
                # Filtrar nivells i flatten a llista
                day_vigilancies = []
                for nivell, vigs in vigilancies_dict.items():
                    if not nivells_specified or nivell in nivells_list:
                        # Copiar cada vigilància i marcar amb dia
                        for vig in vigs:
                            vig_copy = vig.copy()
                            # Marcar amb data per generar format correcte (igual que desktop)
                            date_ctx = DateContext.from_iso(data_str)
                            vig_copy['_dia_interval'] = date_ctx.full_format
                            vig_copy['_data_iso'] = data_str
                            day_vigilancies.append(vig_copy)

                # Si no hi ha vigilàncies per aquest dia als nivells seleccionats
                if not include_empty_days and not day_vigilancies:
                    continue
                if include_empty_days and not day_vigilancies:
                    date_ctx = DateContext.from_iso(data_str)
                    interval_vigilancies.append({
                        "_dia_interval": date_ctx.full_format,
                        "_data_iso": data_str,
                        "_empty_day": True
                    })
            if day_vigilancies:
                interval_vigilancies.extend(day_vigilancies)

            if include_substitucions:
                subs_raw = SubstitucioRepository.get_by_date(db, data_str)
                TIPUS_VIGILANCIA = {'VIGILANCIA', 'VIGILANCIA_ABSENT'}
                date_ctx_sub = DateContext.from_iso(data_str)
                for sub in subs_raw:
                    if sub.get('tipus_absencia', '') in TIPUS_VIGILANCIA:
                        sub_copy = sub.copy()
                        sub_copy['_dia_interval'] = date_ctx_sub.full_format
                        sub_copy['_data_iso'] = data_str
                        interval_substitucions.append(sub_copy)

        if not interval_vigilancies:
            raise HTTPException(status_code=404, detail="No hi ha vigilàncies a l'interval seleccionat")

        # Format títol interval (com desktop app)
        data_inici_obj = datetime.strptime(data_inici, "%Y-%m-%d")
        data_final_obj = datetime.strptime(data_final, "%Y-%m-%d")
        data_inici_curta = data_inici_obj.strftime("%d/%m/%Y")
        data_final_curta = data_final_obj.strftime("%d/%m/%Y")
        interval_title = f"{data_inici_curta} - {data_final_curta}"

        # Afegir nivells al títol si no són tots
        if nivells_specified:
            nivells_text = " - ".join(nivells_list)
            interval_title = f"{interval_title} ({nivells_text})"

        # Generar PDF UNA SOLA VEGADA amb totes les vigilàncies (com desktop)
        export_dir = get_export_dir_for_institucio(current_user.institucio)
        exporter = PDFCompletExporter(hores=hores, export_dir=str(export_dir), horari_mgr=horari_mgr)

        # Configurar opcions via atributs
        exporter.show_comments_column = show_comments
        exporter.show_hours_column = show_hours
        if compress:
            exporter._auto_compression_active = True

        # Cridar exportar() una sola vegada amb tipus especial "vigilancies_interval"
        filename = exporter.exportar(
            substitucions=interval_substitucions,
            vigilancies=interval_vigilancies,
            data_text=interval_title,
            data_iso=data_inici,
            tipus_pdf="vigilancies_interval"
        )

        # Copiar PDF generat a temp per retornar
        exports_path = export_dir / filename
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"vigilancies_interval_{data_inici}_a_{data_final}_{timestamp}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)

        shutil.copy(str(exports_path), pdf_path)

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=pdf_filename,
            headers={"Content-Disposition": f"attachment; filename={pdf_filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en generar PDF interval: {str(e)}")
@router.get("/vigilancies/{data}")
async def generar_pdf_vigilancies(
    data: str,
    nivells: str = "",  # Comma-separated: "1-BATX,2-BATX"
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    include_substitucions: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Genera PDF de vigilàncies per un dia amb selecció de nivells (SQLite)
    """
    try:
        # Validar data
        try:
            date_obj = datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")

        from utils.date_context import DateContext
        data_text = DateContext.from_iso(data).full_format

        # Parsejar nivells seleccionats
        nivells_list = [n.strip() for n in nivells.split(',') if n.strip()] if nivells else []

        # Carregar vigilàncies des de SQLite
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)

        if not vigilancies_dict:
            raise HTTPException(status_code=404, detail=f"No hi ha vigilàncies per {data}")

        if not nivells_list:
            nivells_list = list(vigilancies_dict.keys())

        # Filtrar només nivells seleccionats i flatten a llista
        vigilancies_list = []
        for nivell, vigs in vigilancies_dict.items():
            if nivell in nivells_list:
                vigilancies_list.extend(vigs)

        # Inicialitzar exporter amb hores
        horari_mgr = get_horari(current_user.institucio, data)
        hores = horari_mgr.hores

        export_dir = get_export_dir_for_institucio(current_user.institucio)
        exporter = PDFCompletExporter(hores=hores, export_dir=str(export_dir))

        # Configurar opcions via atributs
        exporter.show_comments_column = show_comments
        exporter.show_hours_column = show_hours
        if compress:
            exporter._auto_compression_active = True

        # Carregar substitucions de vigilància si cal
        subs_pdf = []
        if include_substitucions:
            subs_raw = SubstitucioRepository.get_by_date(db, data)
            TIPUS_VIGILANCIA = {'VIGILANCIA', 'VIGILANCIA_ABSENT'}
            subs_pdf = [s for s in subs_raw if s.get('tipus_absencia', '') in TIPUS_VIGILANCIA]

        # Generar PDF (conflictes=None → engine els calcula automàticament)
        filename = exporter.exportar(
            substitucions=subs_pdf,
            vigilancies=vigilancies_list,
            data_text=data_text,
            data_iso=data,
            tipus_pdf="vigilancies"
        )

        # Moure PDF a temp dir
        if not filename:
            raise HTTPException(status_code=500, detail="Error intern en generar el PDF")
        exports_path = export_dir / filename
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"vigilancies_{data}_{timestamp}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)

        shutil.copy(str(exports_path), pdf_path)

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=pdf_filename,
            headers={"Content-Disposition": f"attachment; filename={pdf_filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en generar PDF vigilàncies: {str(e)}")


@router.post("/disponibles-tots-dies")
async def generar_pdf_disponibles_tots_dies(
    data_inici: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Genera un PDF amb professors disponibles per N dies laborables consecutius,
    un full per dia. Comença des de data_inici (o avui si no s'especifica).
    """
    try:
        from datetime import timedelta, date
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Spacer, KeepTogether
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import tempfile
        import os

        # Data d'inici: la proporcionada o avui
        if data_inici:
            try:
                primer_dia = datetime.strptime(data_inici, "%Y-%m-%d").date()
            except ValueError:
                primer_dia = date.today()
        else:
            primer_dia = date.today()

        avui = primer_dia  # per al text "Generat el..."

        # Configurar idioma per traduccions
        from repositories import ConfiguracioRepository
        from i18n_setup import setup_translation
        config_db = ConfiguracioRepository.get_all_as_dict(db)
        idioma = config_db.get("idioma", "ca")  # Default català
        setup_translation(idioma)

        # Carregar horari per obtenir els dies configurats
        from helpers import get_gestors
        try:
            _, horari_temp, _, _ = get_gestors(current_user.institucio, primer_dia.strftime("%Y-%m-%d"))
            dies_xml = horari_temp.dies if hasattr(horari_temp, 'dies') else []
        except:
            dies_xml = []

        # Si no hi ha dies a l'XML, usar 5 dies laborables per defecte
        num_dies_laborables = len(dies_xml) if dies_xml else 5

        # Generar N dies laborables consecutius des de primer_dia (salta cap de setmana)
        dies_setmana = []
        actual = primer_dia
        while len(dies_setmana) < num_dies_laborables:
            if actual.weekday() < 5:  # 0=Dl, 4=Dv
                dies_setmana.append(actual)
            actual += timedelta(days=1)

        # Crear PDF temporal
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"disponibles_tots_dies_{timestamp}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)

        # Crear document PDF
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1*cm,
            bottomMargin=2*cm
        )

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=4,
            alignment=TA_CENTER
        )
        date_style = ParagraphStyle(
            'CustomDate',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=16,
            leading=24,
            alignment=TA_CENTER
        )

        from babel.dates import format_date
        import i18n_setup
        idioma_actual = i18n_setup.CURRENT_LANGUAGE

        story = []

        # Iterar per cada dia de la setmana
        for idx, current_date in enumerate(dies_setmana):
            data_iso = current_date.strftime("%Y-%m-%d")
            dia_idx = current_date.weekday()

            # Obtenir nom del dia de l'XML per usar amb get_tots_disponibles()
            if dia_idx < len(dies_xml):
                dia_name_xml = dies_xml[dia_idx]
            else:
                # Fallback: si no hi ha XML, usar Babel segons idioma configurat
                dia_name_xml = format_date(current_date, 'EEEE', locale=idioma_actual)
                dia_name_xml = dia_name_xml[:1].upper() + dia_name_xml[1:]

            # Capçalera: label petit + data del dia destacada
            titol = translate("📋 Llistat de Professors Substituts").replace("📋 ", "")
            data_dia = format_date(current_date, 'full', locale=idioma_actual)
            data_dia = data_dia[:1].upper() + data_dia[1:]
            story.append(Paragraph(titol, title_style))
            story.append(Paragraph(f"<b>{data_dia}</b>", date_style))
            story.append(Spacer(1, 0.5*cm))

            try:
                # Obtenir disponibles del dia
                from helpers import get_gestors
                substitucions_mgr, horari_mgr, alliberats_mgr, absencies_mgr = get_gestors(current_user.institucio, data_iso)

                # Obtenir professors de baixa
                from config.constants import PROFESSORS_BAIXA
                professors_baixa_avui = set()
                try:
                    data_obj = datetime.strptime(data_iso, "%Y-%m-%d").date()
                    for baixa in PROFESSORS_BAIXA:
                        data_inici_baixa = datetime.strptime(baixa['data_inici'], '%Y-%m-%d').date()
                        data_final_baixa = datetime.strptime(baixa['data_final'], '%Y-%m-%d').date()
                        if data_inici_baixa <= data_obj <= data_final_baixa:
                            professors_baixa_avui.add(baixa['professor'])
                except:
                    pass

                # Obtenir substitucions del dia
                from repositories import SubstitucioRepository, GrupsAlliberatsRepository, VigilanciaRepository
                substitucions_data = SubstitucioRepository.get_by_date(db, data_iso)

                from collections import defaultdict

                # Mapa de substituts per hora (ocupats fent substitució)
                substituts_per_hora = defaultdict(set)
                # Mapa de professors absents per hora
                absents_per_hora = defaultdict(set)
                for sub in substitucions_data:
                    h = sub.get("hora", "")
                    substitut = sub.get("substitut", "")
                    absent = sub.get("professor_absent", "")
                    if h and substitut:
                        substituts_per_hora[h].add(substitut)
                    if h and absent:
                        absents_per_hora[h].add(absent)

                # Mapa de vigilants per hora (ocupats fent vigilància)
                vigilants_per_hora = defaultdict(set)
                try:
                    vigilancies_data = VigilanciaRepository.get_by_date(db, data_iso)
                    for nivell_vigs in vigilancies_data.values():
                        for vig in nivell_vigs:
                            h = vig.get("hora", "")
                            vigilant = vig.get("vigilant", "")
                            if h and vigilant:
                                vigilants_per_hora[h].add(vigilant)
                except Exception:
                    pass

                # Obtenir grups alliberats
                grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data_iso)

                # Import necessari per categories
                from config.constants import ORDRE_PRIORITATS, PRIORITATS

                hora_header_style = ParagraphStyle(
                    'HoraHeader',
                    parent=styles['Normal'],
                    fontSize=10,
                    leading=14,
                    fontName='Courier-Bold',
                    leftIndent=10,
                    spaceAfter=2,
                )
                content_style = ParagraphStyle(
                    'Content',
                    parent=styles['Normal'],
                    fontSize=9,
                    leading=12,
                    fontName='Courier',
                    leftIndent=10,
                    spaceAfter=6,
                )

                hi_ha_contingut = False

                # Per cada hora — cada bloc va amb KeepTogether
                for hora in horari_mgr.hores:
                    grups_hora = grups_alliberats_data.get(hora, [])
                    # Llista completa (sense filtrar) per mostrar tots amb estat
                    disponibles_tots = alliberats_mgr.get_tots_disponibles(dia_name_xml, hora, grups_hora)

                    if not disponibles_tots:
                        continue

                    hi_ha_contingut = True

                    per_categoria_tipus = defaultdict(lambda: defaultdict(list))

                    for prof, tipus, detall in disponibles_tots:
                        categoria_idx = len(ORDRE_PRIORITATS)
                        for i, categoria in enumerate(ORDRE_PRIORITATS):
                            if tipus in categoria:
                                categoria_idx = i
                                break
                        # Determinar estat del professor
                        if prof in professors_baixa_avui or prof in absents_per_hora.get(hora, set()):
                            estat = 'absent'
                        elif prof in substituts_per_hora.get(hora, set()) or prof in vigilants_per_hora.get(hora, set()):
                            estat = 'ocupat'
                        else:
                            estat = 'disponible'
                        per_categoria_tipus[categoria_idx][tipus].append((prof, estat))

                    lines = []
                    for categoria_idx in sorted(per_categoria_tipus.keys()):
                        cat_label = f"Cat.{categoria_idx}" if categoria_idx < len(ORDRE_PRIORITATS) else "Cat.99"
                        for tipus in sorted(per_categoria_tipus[categoria_idx].keys()):
                            profs_amb_estat = per_categoria_tipus[categoria_idx][tipus]
                            pes = PRIORITATS.get(tipus, 1)
                            parts = []
                            for prof, estat in sorted(profs_amb_estat, key=lambda x: x[0]):
                                if estat == 'absent':
                                    parts.append(f'<strike><font color="#d97706">{prof}</font></strike>')
                                elif estat == 'ocupat':
                                    parts.append(f'<strike><font color="#9ca3af">{prof}</font></strike>')
                                else:
                                    parts.append(prof)
                            profs_text = ", ".join(parts)
                            meta = f'<font color="#94a3b8">  - {cat_label}:</font>'
                            suffix = f'<font color="#94a3b8"> ({tipus} [{pes}])</font>'
                            lines.append(f"{meta} {profs_text}{suffix}")

                    hora_block = [
                        Paragraph(hora, hora_header_style),
                        Paragraph("<br/>".join(lines), content_style),
                    ]
                    story.append(KeepTogether(hora_block))

                if not hi_ha_contingut:
                    story.append(Paragraph("<i>No hi ha professors disponibles</i>", styles['Normal']))

            except Exception as e:
                print(f"Error processant dia {data_iso}: {e}")
                story.append(Paragraph(f"<i>Error carregant dades per aquest dia</i>", styles['Normal']))

            # Page break entre dies (excepte l'últim)
            if idx < len(dies_setmana) - 1:
                story.append(PageBreak())

        # Generar PDF
        doc.build(story)

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=pdf_filename,
            headers={"Content-Disposition": f"attachment; filename={pdf_filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generant PDF disponibles: {str(e)}")
