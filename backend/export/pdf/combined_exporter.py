"""
Coordinador d'exportació de PDFs combinats (substitucions + vigilàncies)
Extret de main_window.py per modularització
"""
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from utils.date_context import DateContext

# GUI opcional (només per desktop app, no necessari per web backend)
try:
    from PySide6.QtWidgets import QMessageBox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    QMessageBox = None

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

try:
    from .engine import pdf_complet_exporter
except ImportError:
    # Fallback per a compatibilitat
    from export.pdf.engine import pdf_complet_exporter

try:
    from .dialogs import mostrar_dialeg_pdf_combinat
except ImportError:
    # Fallback per evitar errors
    def mostrar_dialeg_pdf_combinat(parent):
        # Retorna una configuració per defecte
        return {
            'substitucions': True,
            'vigilancies': True,
            'comprimir': False,
            'nivells_seleccionats': []
        }


class CombinedPDFExporter:
    """Gestió d'exportació de PDFs combinats des de la finestra principal"""

    def __init__(self, main_window):
        """
        Args:
            main_window: Referència a la finestra principal MainWindow
        """
        self.window = main_window

    def exportar_pdf_complet(self) -> None:
        """Exporta PDF complet amb vigilàncies + substitucions"""
        from PySide6.QtWidgets import QApplication
        from data.storage import storage

        try:
            # 1. Comprova que hi hagi dades per exportar
            substitucions = self.window.substitucions_widget.substitucions
            subs_reals = [s for s in substitucions if not s.get("separador")] if substitucions else []

            # Comptadors detallats per substitucions
            subs_assignades = [s for s in subs_reals if s.get('substitut')]
            subs_totals = len(subs_reals)

            # 2. Obté vigilàncies si la finestra està oberta
            vigilancies = []
            if hasattr(self.window, 'vigilancies_window') and self.window.vigilancies_window:
                try:
                    for nivell in self.window.vigilancies_window.nivells:
                        vigilancies_nivell = self.window.vigilancies_window._recopilar_vigilancies(nivell)
                        vigilancies.extend(vigilancies_nivell)
                except Exception as e:
                    print(_("Error en obtenir vigilàncies: {error}").format(error=e))
            else:
                # Carrega vigilàncies del JSON si la finestra no està oberta
                vigilancies = self._carregar_vigilancies_del_json()

            # Comptadors separats per mostrar info més detallada
            # Filtra vigilàncies amb vigilant real (no buit i no placeholder)
            # No depèn de traduccions: simplement comprova que no comença amb "--"
            vigilancies_assignades = [
                v for v in vigilancies
                if v.get('vigilant', '').strip() and
                   not v.get('vigilant', '').startswith('--')
            ]
            vigilancies_totals = len(vigilancies)

            # Mantenim vigilancies_reals per compatibilitat amb PDF
            vigilancies_reals = vigilancies

            # 3. Continua sempre amb la generació, independentment del contingut

            # 4. Comprova millors prioritats abans de l'exportació (si hi ha substitucions)
            if subs_reals:
                # 🔧 MILLORA: Força actualització completa abans de comprovar prioritats
                self.window.substitucions_widget._refresh_all_tipus_substitut()

                avisos_prioritat = self.window._comprovar_millors_prioritats(substitucions)
                if avisos_prioritat:
                    missatge_prioritat = _("⚠️ AVÍS: Hi ha professors de major prioritat disponibles:\n\n")
                    missatge_prioritat += "\n".join(avisos_prioritat)
                    missatge_prioritat += _("\n\nVoleu continuar amb l'exportació?")

                    msg_box_prioritat = QMessageBox(self.window)
                    msg_box_prioritat.setIcon(QMessageBox.Question)
                    msg_box_prioritat.setWindowTitle(_("Professors de major prioritat disponibles"))
                    msg_box_prioritat.setText(missatge_prioritat)
                    btn_si_prioritat = msg_box_prioritat.addButton(_("Sí"), QMessageBox.YesRole)
                    btn_no_prioritat = msg_box_prioritat.addButton(_("No"), QMessageBox.NoRole)
                    msg_box_prioritat.setDefaultButton(btn_no_prioritat)
                    msg_box_prioritat.exec()

                    if msg_box_prioritat.clickedButton() == btn_no_prioritat:
                        return

            # 5. Confirma exportació final
            missatge = _("📋 PDF Complet per {data}\n\n").format(
                data=DateContext(self.window.date_selector.date()).full_format)
            if subs_totals > 0:
                missatge += _("📝 Substitucions: {assignades} assignades de {totals}\n").format(
                    assignades=len(subs_assignades), totals=subs_totals)
            if vigilancies_totals > 0:
                missatge += _("👁️ Vigilàncies: {assignades} assignades de {totals}\n").format(
                    assignades=len(vigilancies_assignades), totals=vigilancies_totals)

            # Diàleg avançat amb selecció de contingut i nivells
            opcions_pdf = mostrar_dialeg_pdf_combinat(self.window)
            if not opcions_pdf:
                return

            incloure_substitucions = opcions_pdf['substitucions']
            incloure_vigilancies = opcions_pdf['vigilancies']
            comprimir_pdf = opcions_pdf['comprimir']
            nivells_vigilancia = opcions_pdf['nivells_seleccionats']

            # Filtrar vigilàncies pels nivells seleccionats si és necessari
            if incloure_vigilancies and nivells_vigilancia:
                vigilancies_originals = vigilancies[:]  # Còpia de seguretat
                vigilancies_filtrades = []

                for vigilancia in vigilancies:
                    nivell_vigilancia = vigilancia.get('nivell', '')
                    # Si no té nivell explícit, acceptar-la (pot ser de GENERAL)
                    if not nivell_vigilancia or nivell_vigilancia in nivells_vigilancia:
                        vigilancies_filtrades.append(vigilancia)

                vigilancies = vigilancies_filtrades
                vigilancies_assignades = [
                    v for v in vigilancies
                    if v.get('vigilant', '').strip() and
                       not v.get('vigilant', '').startswith('--')
                ]
                vigilancies_totals = len(vigilancies)

            # Actualitza missatge segons opcions seleccionades
            missatge_final = _("📋 PDF per {data}\n\n").format(
                data=DateContext(self.window.date_selector.date()).full_format)
            if incloure_substitucions and subs_totals > 0:
                missatge_final += _("📝 Substitucions: {assignades} assignades de {totals}\n").format(
                    assignades=len(subs_assignades), totals=subs_totals)
            if incloure_vigilancies and vigilancies_totals > 0:
                if nivells_vigilancia and len(nivells_vigilancia) < 3:  # No tots els nivells
                    nivells_text = " - ".join(nivells_vigilancia)
                    missatge_final += _("👁️ Vigilàncies ({nivells}): {assignades} assignades de {totals}\n").format(
                        nivells=nivells_text, assignades=len(vigilancies_assignades), totals=vigilancies_totals)
                else:
                    missatge_final += _("👁️ Vigilàncies: {assignades} assignades de {totals}\n").format(
                        assignades=len(vigilancies_assignades), totals=vigilancies_totals)

            # 5. Genera PDF complet
            self.window.status_label.setText(_("S'està generant el PDF complet..."))
            QApplication.processEvents()

            date_ctx = DateContext(self.window.date_selector.date())
            data_text = date_ctx.full_format
            data_iso = date_ctx.iso_format
            filename = self._generar_pdf_combinat(
                substitucions, vigilancies, data_text, data_iso,
                incloure_substitucions, incloure_vigilancies,
                subs_totals, subs_assignades, vigilancies_totals, vigilancies_assignades,
                comprimir_pdf, opcions_pdf
            )

            if filename:
                # 6. Desa substitucions i sincronitza amb Google Sheets
                data_iso = DateContext(self.window.date_selector.date()).iso_format
                # 🔧 FIX: Usar get_absents_with_tipus() per preservar tipus d'absència
                absents_info = self.window.absents_widget.get_absents_with_tipus()
                absents_actuals = {prof: info['hores'] for prof, info in absents_info.items()}
                absents_tipus_actuals = {prof: info['tipus_absencia'] for prof, info in absents_info.items()}

                try:
                    success = storage.desar_substitucions(data_iso, substitucions, absents_actuals, absents_tipus_actuals)
                    if success:
                        sync_msg = self.window._get_sync_status_message()
                        if storage.get_last_sync_error()[0]:  # If sync successful
                            self.window._carregar_estadistiques_substitucions()
                    else:
                        sync_msg = _("\n❌ Error en desar dades localment")
                except Exception as e:
                    sync_msg = _("\n❌ Error inesperat: {error}").format(error=str(e)[:100])

                # 7. Mostra èxit PDF amb info de sincronització
                # Construeix missatge final segons opcions seleccionades
                missatge_confirmacio = _("✅ PDF creat i obert correctament!\n\n📄 Fitxer: {filename}\n").format(filename=filename)
                if incloure_substitucions and subs_totals > 0:
                    missatge_confirmacio += _("📝 Substitucions: {assignades} assignades de {totals}\n").format(
                        assignades=len(subs_assignades), totals=subs_totals)
                if incloure_vigilancies and vigilancies_totals > 0:
                    missatge_confirmacio += _("👁️ Vigilàncies: {assignades} assignades de {totals}\n").format(
                        assignades=len(vigilancies_assignades), totals=vigilancies_totals)
                missatge_confirmacio += sync_msg

                QMessageBox.information(self.window, _("PDF generat"), missatge_confirmacio)

                self.window.status_label.setText(_("✅ PDF creat: {filename}").format(filename=filename))
            else:
                QMessageBox.warning(self.window, _("Error"), _("❌ No s'ha pogut generar el PDF complet"))
                self.window.status_label.setText(_("❌ Error en generar PDF complet"))

        except Exception as e:
            QMessageBox.critical(self.window, _("Error"), f"❌ {_('Error en exportar el PDF complet')}: {e}")
            self.window.status_label.setText(_("❌ Error d'exportació"))
            import traceback
            traceback.print_exc()

    def _generar_pdf_combinat(self, substitucions, vigilancies, data_text, data_iso,
                             incloure_substitucions=True, incloure_vigilancies=True,
                             subs_totals=0, subs_assignades=None, vigilancies_totals=0, vigilancies_assignades=None,
                             comprimir_pdf=False, opcions_pdf=None):
        """Utilitza l'exportador per generar el PDF complet"""
        if subs_assignades is None:
            subs_assignades = []
        if vigilancies_assignades is None:
            vigilancies_assignades = []

        try:
            # Filtra les dades segons les opcions abans de validar conflictes
            substitucions_per_validar = substitucions if incloure_substitucions else []
            vigilancies_per_validar = vigilancies if incloure_vigilancies else []

            # Use the unified validation from PDF complete exporter
            conflictes = pdf_complet_exporter._validar_conflictes_complets(
                substitucions_per_validar, vigilancies_per_validar, getattr(self.window, 'absents_actuals', {})
            )

            if conflictes:
                # Agrupem conflictes per hora
                conflictes_per_hora = defaultdict(list)
                for conflicte in conflictes:
                    # Extreure hora del conflicte (ex: "08:00")
                    if ' ' in conflicte:
                        hora = conflicte.split(' ')[1].replace(':', '')
                        conflictes_per_hora[hora].append(conflicte)

                # Construïm missatge agrupat per hores
                missatge = _("S'han detectat conflictes:\n\n")

                # Ordena hores cronològicament
                hores_ordenades = sorted(conflictes_per_hora.keys(),
                                         key=lambda h: int(h[:2]) if h.isdigit() else 0)

                for hora in hores_ordenades:
                    # Formata hora correctament (ex: "0800" -> "08:00")
                    hora_formatejada = f"{hora[:2]}:{hora[2:]}"
                    missatge += f"🕐 HORA {hora_formatejada}:\n"

                    for c in conflictes_per_hora[hora]:
                        # Mantenim l'icona original del conflicte
                        missatge += f"   {c}\n"

                    missatge += "\n"  # Línia en blanc entre hores

                missatge += _("\nVoleu continuar amb l'exportació?")

                msg_box_conflictes = QMessageBox(self.window)
                msg_box_conflictes.setIcon(QMessageBox.Warning)
                msg_box_conflictes.setWindowTitle(_("Conflictes detectats"))
                msg_box_conflictes.setText(missatge)
                btn_si_conflictes = msg_box_conflictes.addButton(_("Sí"), QMessageBox.YesRole)
                btn_no_conflictes = msg_box_conflictes.addButton(_("No"), QMessageBox.NoRole)
                msg_box_conflictes.setDefaultButton(btn_no_conflictes)
                msg_box_conflictes.exec()

                if msg_box_conflictes.clickedButton() == btn_no_conflictes:
                    return ""  # Cancel·la l'exportació

            # Genera PDF si no hi ha conflictes o l'usuari vol continuar
            # Filtra les dades segons les opcions seleccionades
            substitucions_filtrades = substitucions if incloure_substitucions else []
            vigilancies_filtrades = vigilancies if incloure_vigilancies else []

            # Determina el tipus de PDF segons les opcions seleccionades
            if incloure_substitucions and incloure_vigilancies:
                tipus_pdf = "complet"
            elif incloure_substitucions:
                tipus_pdf = "substitucions"
            elif incloure_vigilancies:
                tipus_pdf = "vigilancies"
            else:
                tipus_pdf = "complet"  # Fallback, no hauria de passar

            # Configurar opcions de columnes opcionals
            if opcions_pdf:
                if 'show_comments_column' in opcions_pdf:
                    self.window.pdf_exporter.show_comments_column = opcions_pdf['show_comments_column']
                if 'show_hours_column' in opcions_pdf:
                    self.window.pdf_exporter.show_hours_column = opcions_pdf['show_hours_column']

            # Activa compressió manual si s'ha seleccionat
            if comprimir_pdf:
                print(_("🗜️ Compressió manual activada per l'usuari"))
                self.window.pdf_exporter._auto_compression_active = True
            else:
                # Reset compression state per assegurar comportament consistent
                self.window.pdf_exporter._auto_compression_active = False

            return self.window.pdf_exporter.exportar(
                substitucions_filtrades,
                vigilancies_filtrades,
                data_text,
                conflictes=conflictes,
                data_iso=data_iso,
                tipus_pdf=tipus_pdf
            )

        except Exception as e:
            print(_("Error en generar PDF combinat: {error}").format(error=e))
            return ""

    def _carregar_vigilancies_del_json(self) -> List[Dict]:
        """Carrega vigilàncies del JSON per la data actual"""
        vigilancies = []
        try:
            from pathlib import Path
            import json

            data_iso = DateContext(self.window.date_selector.date()).iso_format
            from config.settings import config
            json_path = config.vigilancies_path

            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)

                vigilancies_dia = all_data.get(data_iso, {})

                for nivell, vigilancies_nivell in vigilancies_dia.items():
                    vigilancies.extend(vigilancies_nivell)

            else:
                print(_("⚠️ Fitxer vigilancies_examens.json no trobat"))

        except Exception as e:
            print(_("❌ Error en carregar vigilàncies del JSON: {error}").format(error=e))

        return vigilancies

    def _obtenir_professors_ocupats_vigilancies(self) -> Dict[str, set]:
        """
        Obté professors ocupats amb vigilàncies sempre -
        usa finestra existent o carrega dades directament
        """
        professors_ocupats = {}

        # Primer: prova amb finestra existent si està oberta i té la mateixa data
        if hasattr(self.window, 'vigilancies_window') and self.window.vigilancies_window:
            try:
                data_actual = DateContext(self.window.date_selector.date()).iso_format
                # Només usar vigilancies_window si té la mateixa data
                if hasattr(self.window.vigilancies_window, 'data_actual') and self.window.vigilancies_window.data_actual == data_actual:
                    vigilancies_actives = self.window.vigilancies_window.get_vigilancies_actives()
                    if vigilancies_actives:
                        professors_ocupats = vigilancies_actives
                        return professors_ocupats
                else:
                    # Si les dates són diferents, respecta la selecció de l'usuari i usa el data manager directament
                    pass
            except Exception as e:
                print(_("⚠️ Error en obtenir vigilàncies de finestra existent: {error}").format(error=e))

        # Segon: carrega vigilàncies directament del data manager
        try:
            from core.vigilancia_data import VigilanciaDataManager
            from core.vigilancia_core import VigilanciaCore
            from collections import defaultdict
            from config.settings import config

            data_iso = DateContext(self.window.date_selector.date()).iso_format

            # 🚀 PERF: Reutilitza data_manager del widget de vigilàncies si existeix (aprofita cache)
            data_manager = None
            if hasattr(self.window, 'vigilancies_widget') and self.window.vigilancies_widget:
                # vigilancies_widget és VigilanciaWidgetWrapper, accedim a vigilancia_window
                if hasattr(self.window.vigilancies_widget, 'vigilancia_window') and self.window.vigilancies_widget.vigilancia_window:
                    vigilancia_window = self.window.vigilancies_widget.vigilancia_window
                    if hasattr(vigilancia_window, 'data_manager'):
                        data_manager = vigilancia_window.data_manager

            if data_manager is None:
                data_manager = VigilanciaDataManager(data_dir=config.data_dir)

            vigilancies_data = data_manager.load_vigilancies(data_iso)

            # Processament similar a get_vigilancies_actives()
            result = defaultdict(list)
            core_logic = VigilanciaCore()

            for nivell, vigilancies_list in vigilancies_data.items():
                for vigilance in vigilancies_list:
                    hora = vigilance.get("hora", "")
                    vigilant = vigilance.get("vigilant", "")
                    if hora and vigilant and not vigilant.startswith("-- "):
                        # Neteja el nom del professor
                        vigilant_net = core_logic.extract_professor_name(vigilant)
                        if vigilant_net:
                            result[hora].append(vigilant_net)

            professors_ocupats = dict(result)

        except Exception as e:
            print(_("❌ Error en carregar vigilàncies directament: {error}").format(error=e))

        return professors_ocupats

    def _comptar_canvis_respecte_pdf_publicat(self, substitucions_actuals: List[Dict]) -> int:
        """Compta canvis respecte a les substitucions desades"""
        canvis = 0

        try:
            # Obté substitucions publicades
            data_iso = DateContext(self.window.date_selector.date()).iso_format
            substitucions_publicades = self.window.substitucions_mgr._carregar_substitucions_publicades(data_iso)

            if not substitucions_publicades:
                return 0  # No hi ha substitucions desades, no hi ha canvis a comptar

            # Comprova cada substitució actual
            for sub in substitucions_actuals:
                if sub.get("separador"):
                    continue

                professor_absent = sub.get('professor_absent', sub.get('professor', ''))
                tipus_absencia = sub.get('tipus_absencia', 'ABSENCIA')
                clau = f"{professor_absent}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}|{tipus_absencia}"

                substitut_actual = sub.get("substitut", "")

                if clau in substitucions_publicades:
                    substitut_publicat = substitucions_publicades[clau].get("substitut", "")
                    if substitut_actual != substitut_publicat:
                        canvis += 1
                        sub["_canvi_pdf"] = True  # Marca per possibles indicadors visuals
                elif substitut_actual:
                    # Nova substitució que no existia al PDF publicat
                    canvis += 1
                    sub["_nova_pdf"] = True

            # Comprova substitucions que existien al PDF però ara no
            for clau_pub, sub_pub in substitucions_publicades.items():
                # Busca si aquesta substitució segueix existint
                existeix = any(
                    f"{s.get('professor_absent', s.get('professor', ''))}|{s.get('hora', '')}|{s.get('assignatura', '')}|{s.get('grup', '')}|{s.get('tipus_absencia', 'ABSENCIA')}" == clau_pub
                    for s in substitucions_actuals if not s.get("separador")
                )

                if not existeix:
                    canvis += 1  # Substitució eliminada

        except Exception as e:
            print(_("⚠️ Error en comptar canvis respecte al PDF: {error}").format(error=e))

        return canvis
