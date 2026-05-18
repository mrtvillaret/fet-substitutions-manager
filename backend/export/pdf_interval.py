"""
Funcions per generar PDFs d'intervals de dates
Reutilitza export.pdf.PDFCompletExporter
"""
from typing import List, Dict
from datetime import datetime
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox, QDialog

from export.pdf import PDFCompletExporter
from utils.date_context import DateContext

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text


def generate_pdf_interval(vigilancia_window) -> bool:
    """Generate PDF for an interval of dates using existing PDF system"""
    try:
        # Comprova canvis no desats abans d'exportar
        from utils.unsaved_changes import comprovar_canvis_no_desats
        if not comprovar_canvis_no_desats(vigilancia_window.parent_window):
            # L'usuari ha cancel·lat
            return False

        from gui.dialogs import IntervalDatesDialog

        # Obrir dialog per seleccionar interval
        data_actual_qdate = QDate.fromString(vigilancia_window.data_actual, "yyyy-MM-dd") if vigilancia_window.data_actual else QDate.currentDate()
        dialog = IntervalDatesDialog(data_actual_qdate, vigilancia_window.nivells, vigilancia_window)

        if dialog.exec() != QDialog.Accepted:
            return False

        config = dialog.get_configuracio()
        data_inici = config['data_inici']
        data_final = config['data_final']
        incluir_caps_setmana = config['incluir_caps_setmana']
        incloure_dies_buits = config['incloure_dies_buits']

        # Opcions noves del diàleg millorat
        nivells_seleccionats = dialog.get_nivells_seleccionats()
        comprimir_pdf = dialog.get_comprimir_pdf()

        # Generar llista de dates
        dates_interval = _generate_dates_list(data_inici, data_final, incluir_caps_setmana)

        if not dates_interval:
            QMessageBox.warning(vigilancia_window, _("Atenció"), _("No hi ha dates vàlides a l'interval seleccionat"))
            return False

        # Validar que almenys un nivell estigui seleccionat
        if not nivells_seleccionats:
            QMessageBox.warning(vigilancia_window, _("Cap nivell seleccionat"),
                              _("❌ Has de seleccionar almenys un nivell per generar el PDF."))
            return False

        # Generar PDF per cada dia + concatenar
        result = generate_concatenated_pdf_interval(
            vigilancia_window, dates_interval, incloure_dies_buits,
            nivells_seleccionats, comprimir_pdf
        )

        if result:
            # Informació per mostrar a l'usuari
            data_inici_cat = DateContext.from_iso(data_inici.toString("yyyy-MM-dd")).full_format
            data_final_cat = DateContext.from_iso(data_final.toString("yyyy-MM-dd")).full_format

            # Comptar vigilàncies totals
            total_vigilancies = 0
            dies_amb_vigilancies = 0
            for date_obj in dates_interval:
                date_iso = date_obj.toString("yyyy-MM-dd")
                date_vigilancies = vigilancia_window.data_manager.load_vigilancies(date_iso)
                if date_vigilancies:
                    day_count = sum(len(vigilancies_list) for vigilancies_list in date_vigilancies.values())
                    if day_count > 0:
                        total_vigilancies += day_count
                        dies_amb_vigilancies += 1

            # Nom del fitxer generat (sense path complet)
            filename = result.split("/")[-1] if "/" in result else result

            QMessageBox.information(
                vigilancia_window,
                _("PDF d'Interval Generat"),
                _("✅ PDF generat correctament:\n\n"
                  "📅 Període: {data_inici_cat} - {data_final_cat}\n"
                  "🎓 Nivells: {nivells}\n"
                  "📊 {total_vigilancies} vigilàncies en {dies_amb_vigilancies} dies\n"
                  "📄 Fitxer: {filename}").format(
                      data_inici_cat=data_inici_cat,
                      data_final_cat=data_final_cat,
                      nivells=', '.join(nivells_seleccionats),
                      total_vigilancies=total_vigilancies,
                      dies_amb_vigilancies=dies_amb_vigilancies,
                      filename=filename
                  )
            )
        else:
            QMessageBox.warning(vigilancia_window, _("Error"), _("No s'ha pogut exportar el PDF d'interval"))

        return result is not None

    except Exception as e:
        QMessageBox.critical(vigilancia_window, _("Error"), _("Error en generar PDF d'interval: {e}").format(e=e))
        return False


def generate_concatenated_pdf_interval(vigilancia_window, dates_interval: List[QDate],
                                     incloure_dies_buits: bool, nivells_seleccionats: List[str],
                                     comprimir_pdf: bool) -> str:
    """Genera PDF concatenat amb format exacte: dies consecutius + pàgina conflictes"""
    try:
        from data.storage import storage
        from models import converters

        # Recopilar totes les vigilàncies dia per dia (mantenint separació)
        interval_vigilancies = []
        interval_substitucions = []
        all_conflicts = []

        # Header de l'interval
        data_inici_str = dates_interval[0].toString("yyyy-MM-dd")
        data_final_str = dates_interval[-1].toString("yyyy-MM-dd")
        # Format més compacte per al títol
        data_inici_obj = datetime.fromisoformat(data_inici_str)
        data_final_obj = datetime.fromisoformat(data_final_str)
        data_inici_curta = data_inici_obj.strftime("%d/%m/%Y")
        data_final_curta = data_final_obj.strftime("%d/%m/%Y")
        interval_title = f"{data_inici_curta} - {data_final_curta}"

        # Processar cada dia mantenint format exacte
        for date_obj in dates_interval:
            date_iso = date_obj.toString("yyyy-MM-dd")
            date_ctx = DateContext.from_iso(date_iso)

            # Carrega vigilàncies del dia
            date_vigilancies = vigilancia_window.data_manager.load_vigilancies(date_iso)

            if not date_vigilancies and not incloure_dies_buits:
                continue

            # Afegir vigilàncies del dia amb tag de data, filtrant pels nivells seleccionats
            day_vigilancies = []
            for nivell in vigilancia_window.nivells:
                # Només processar nivells seleccionats
                if nivell in nivells_seleccionats and nivell in date_vigilancies:
                    # Convert Vigilancia dataclass objects to dicts
                    vigilancies_list = date_vigilancies[nivell]
                    vigilancies_dicts = converters.vigilancies_list_to_dicts(vigilancies_list)

                    for vigilancia_dict in vigilancies_dicts:
                        vigilancia_copy = vigilancia_dict.copy()
                        # Marcar amb data per generar format correcte
                        vigilancia_copy['_dia_interval'] = date_ctx.full_format
                        vigilancia_copy['_data_iso'] = date_iso  # Afegir ISO per ordenació

                        grups = vigilancia_dict.get("grups", "") or vigilancia_dict.get("grup", "")
                        if grups and grups.strip():
                            vigilancia_copy['nivell'] = nivell

                        day_vigilancies.append(vigilancia_copy)

            if day_vigilancies:
                interval_vigilancies.extend(day_vigilancies)

            # Carrega substitucions de vigilàncies del dia
            totes_substitucions = storage.carregar_substitucions(date_iso)
            substitucions_vigilancies_dia_totals = [
                sub for sub in totes_substitucions
                if sub.get("tipus_absencia") == "VIGILANCIA"
            ]

            # Filtra substitucions segons vigilàncies dels nivells seleccionats
            vigilants_dia = set()
            for vig in day_vigilancies:
                hora = vig.get("hora", "")
                vigilant = vig.get("vigilant", "")
                if hora and vigilant:
                    vigilants_dia.add((hora, vigilant))

            substitucions_vigilancies_dia = [
                sub for sub in substitucions_vigilancies_dia_totals
                if (sub.get("hora", ""), sub.get("professor_absent", "")) in vigilants_dia
            ]

            # Afegir camps necessaris per interval (igual que vigilàncies)
            for sub in substitucions_vigilancies_dia:
                sub['_dia_interval'] = date_ctx.full_format
                sub['_data_iso'] = date_iso
            if substitucions_vigilancies_dia:
                interval_substitucions.extend(substitucions_vigilancies_dia)

            # Detectar conflictes del dia
            day_conflicts = _get_conflicts_for_date(vigilancia_window, date_iso, date_vigilancies)
            if day_conflicts:
                all_conflicts.append(f"{date_ctx.full_format}:")
                for conflict in day_conflicts:
                    all_conflicts.append(f"  • {conflict}")

        if not interval_vigilancies:
            return None

        # Actualitzar títol amb nivells seleccionats si no són tots
        if len(nivells_seleccionats) < len(vigilancia_window.nivells):
            nivells_text = " - ".join(nivells_seleccionats)
            interval_title = f"{interval_title} ({nivells_text})"

        print(_("📋 Substitucions de vigilàncies en l'interval: {count}").format(count=len(interval_substitucions)))

        # Usar PDFCompletExporter amb tipus especial per interval
        # Get hores from parent window's horari
        hores = vigilancia_window.parent_window.horari.hores if hasattr(vigilancia_window.parent_window, 'horari') else []
        pdf_exporter = PDFCompletExporter(hores=hores)

        # Configura compressió manual si s'ha seleccionat
        if comprimir_pdf:
            print(_("🗜️ Compressió manual activada per a interval de vigilàncies"))
            pdf_exporter._auto_compression_active = True
        else:
            pdf_exporter._auto_compression_active = False

        result = pdf_exporter.exportar(
            interval_substitucions, interval_vigilancies, interval_title, all_conflicts,
            data_iso=data_inici_str, tipus_pdf="vigilancies_interval"
        )

        return result

    except Exception as e:
        print(_("Error en generar PDF concatenat: {error}").format(error=e))
        return None


def _get_conflicts_for_date(vigilancia_window, date_iso: str, date_vigilancies: Dict) -> List[str]:
    """Obté conflictes per una data específica reutilitzant funcions existents"""
    original_data_actual = vigilancia_window.data_actual
    original_dia_actual = vigilancia_window.dia_actual
    original_vigilancies = vigilancia_window.vigilancies.copy()

    try:
        # Simular temporalment aquest dia
        vigilancia_window.data_actual = date_iso
        # Convertir data ISO al nom del dia XML
        from utils.date_context import DateContext
        date_ctx = DateContext.from_iso(date_iso)
        weekday_idx = date_ctx.weekday_index
        # Get day name from horari_gestor
        if hasattr(vigilancia_window, 'horari_gestor') and vigilancia_window.horari_gestor:
            dia_setmana = vigilancia_window.horari_gestor.get_dia_name(weekday_idx)
        else:
            dia_setmana = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres"][weekday_idx]
        vigilancia_window.dia_actual = dia_setmana
        vigilancia_window.vigilancies[date_iso] = date_vigilancies

        # Carregar absents específics per aquesta data
        vigilancia_window._carrega_absents_de_data(date_iso)

        # Actualitzar configuració de core_logic amb la nova data
        vigilancia_window._update_core_logic_config()

        # Reutilitzar funcions existents
        day_conflicts = vigilancia_window._find_conflicts()
        day_discrepancies = vigilancia_window._find_discrepancies()
        return day_conflicts + day_discrepancies

    finally:
        # Restaurar estat original
        vigilancia_window.data_actual = original_data_actual
        vigilancia_window.dia_actual = original_dia_actual
        vigilancia_window.vigilancies = original_vigilancies
        # Restaurar configuració original de core_logic
        vigilancia_window._update_core_logic_config()


def _generate_dates_list(data_inici: QDate, data_final: QDate, incluir_caps_setmana: bool) -> List[QDate]:
    """Genera llista de dates vàlides entre dues dates"""
    dates = []
    current_date = data_inici

    while current_date <= data_final:
        # Si no incloem caps de setmana, saltar dissabte (6) i diumenge (7)
        if incluir_caps_setmana or current_date.dayOfWeek() < 6:
            dates.append(current_date)
        current_date = current_date.addDays(1)

    return dates
