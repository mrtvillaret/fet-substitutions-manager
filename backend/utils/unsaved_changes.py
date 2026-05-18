"""
Sistema simple de detecció de canvis no desats
"""

from typing import List, Dict
from PySide6.QtWidgets import QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QDialog, QLabel, QHBoxLayout
from utils.date_context import DateContext
from data.storage import storage
import i18n_setup

_ = i18n_setup._


def comparar_substitucions(dia_iso: str, substitucions_interficie: List[Dict]) -> Dict:
    """
    Compara substitucions de la interfície amb les del JSON.
    Retorna dict amb diferències trobades.
    """
    try:
        # Carrega substitucions del JSON
        substitucions_json = storage.carregar_substitucions(dia_iso) or []

        # Filtra substitucions reals (no separadors)
        # Inclou VIGILANCIA i ENCADENADES encara que tinguin grup="" buit
        subs_interficie = [
            sub for sub in substitucions_interficie
            if not sub.get("separador") and sub.get("assignatura") and (sub.get("grup") or sub.get("tipus_absencia") in ["VIGILANCIA", "ENCADENADA"])
        ]

        subs_json = [
            sub for sub in substitucions_json
            if sub.get("assignatura") and (sub.get("grup") or sub.get("tipus_absencia") in ["VIGILANCIA", "ENCADENADA"])
        ]

        # Genera claus per comparació
        def generar_clau(sub):
            return f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"

        # Converteix a diccionaris clau -> (substitut, comentaris)
        claus_interficie = {generar_clau(sub): (sub.get('substitut', ''), sub.get('comentaris', '')) for sub in subs_interficie}
        claus_json = {generar_clau(sub): (sub.get('substitut', ''), sub.get('comentaris', '')) for sub in subs_json}

        # Troba diferències
        diferencies = {
            'noves': [],      # Només a la interfície
            'eliminades': [], # Només al JSON
            'modificades': [] # Diferent substitut o comentaris
        }

        # Noves substitucions (interfície però no JSON)
        for clau, (substitut, comentaris) in claus_interficie.items():
            if clau not in claus_json:
                parts = clau.split('|')
                diferencies['noves'].append({
                    'hora': parts[1],
                    'absent': parts[0],
                    'assignatura': parts[2],
                    'grup': parts[3],
                    'substitut': substitut,
                    'comentaris': comentaris
                })

        # Substitucions eliminades (JSON però no interfície)
        for clau, (substitut, comentaris) in claus_json.items():
            if clau not in claus_interficie:
                parts = clau.split('|')
                diferencies['eliminades'].append({
                    'hora': parts[1],
                    'absent': parts[0],
                    'assignatura': parts[2],
                    'grup': parts[3],
                    'substitut': substitut,
                    'comentaris': comentaris
                })

        # Substitucions modificades (clau igual, substitut o comentaris diferents)
        for clau in claus_interficie:
            if clau in claus_json and claus_interficie[clau] != claus_json[clau]:
                parts = clau.split('|')
                substitut_actual, comentaris_actual = claus_interficie[clau]
                substitut_anterior, comentaris_anterior = claus_json[clau]
                diferencies['modificades'].append({
                    'hora': parts[1],
                    'absent': parts[0],
                    'assignatura': parts[2],
                    'grup': parts[3],
                    'substitut_actual': substitut_actual,
                    'substitut_anterior': substitut_anterior,
                    'comentaris_actual': comentaris_actual,
                    'comentaris_anterior': comentaris_anterior
                })

        return diferencies

    except Exception as e:
        print(_("Error en comparar substitucions: {}").format(e))
        return {'noves': [], 'eliminades': [], 'modificades': []}


def mostrar_canvis_dialog(parent, dia_catalan: str, diferencies: Dict) -> str:
    """
    Mostra diàleg amb canvis específics.
    Retorna: 'desar', 'descartar', 'cancellar'
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(_("Canvis no desats"))
    dialog.resize(600, 400)

    layout = QVBoxLayout(dialog)

    # Text explicatiu
    layout.addWidget(QLabel(_("⚠️ Canvis no desats al dia {}").format(dia_catalan)))

    # Àrea de text amb els canvis
    text_area = QTextEdit()
    text_area.setReadOnly(True)

    contingut = ""

    # Handle new format with separate substitutions and absents
    if 'substitucions' in diferencies:
        subs = diferencies['substitucions']
        if subs['noves']:
            contingut += _("🆕 NOVES SUBSTITUCIONS:\n")
            for sub in subs['noves']:
                contingut += _("  • {hora} - {absent} ({assignatura}, {grup}) → {substitut}\n").format(
                    hora=sub['hora'], absent=sub['absent'], assignatura=sub['assignatura'], grup=sub['grup'], substitut=sub['substitut']
                )
                if sub.get('comentaris'):
                    contingut += _("    💬 Comentari: {comentaris}\n").format(comentaris=sub['comentaris'])
            contingut += "\n"

        if subs['eliminades']:
            contingut += _("🗑️ SUBSTITUCIONS ELIMINADES:\n")
            for sub in subs['eliminades']:
                contingut += _("  • {hora} - {absent} ({assignatura}, {grup}) → {substitut}\n").format(
                    hora=sub['hora'], absent=sub['absent'], assignatura=sub['assignatura'], grup=sub['grup'], substitut=sub['substitut']
                )
                if sub.get('comentaris'):
                    contingut += _("    💬 Comentari: {comentaris}\n").format(comentaris=sub['comentaris'])
            contingut += "\n"

        if subs['modificades']:
            contingut += _("✏️ SUBSTITUCIONS MODIFICADES:\n")
            for sub in subs['modificades']:
                contingut += _("  • {hora} - {absent} ({assignatura}, {grup})\n").format(
                    hora=sub['hora'], absent=sub['absent'], assignatura=sub['assignatura'], grup=sub['grup']
                )
                # Mostra canvis en substitut
                if sub['substitut_anterior'] != sub['substitut_actual']:
                    contingut += _("    Substitut: {anterior} → {actual}\n").format(
                        anterior=sub['substitut_anterior'] or _('(buit)'),
                        actual=sub['substitut_actual'] or _('(buit)')
                    )
                # Mostra canvis en comentaris
                if sub.get('comentaris_anterior') != sub.get('comentaris_actual'):
                    contingut += _("    💬 Comentari: {anterior} → {actual}\n").format(
                        anterior=sub.get('comentaris_anterior') or _('(buit)'),
                        actual=sub.get('comentaris_actual') or _('(buit)')
                    )
            contingut += "\n"

    # Handle absents changes
    if 'absents' in diferencies:
        absents = diferencies['absents']
        if absents['noves']:
            contingut += _("🆕 NOVES ABSÈNCIES:\n")
            for absent in absents['noves']:
                contingut += _("  • {absent}\n").format(absent=absent)
            contingut += "\n"

        if absents['eliminades']:
            contingut += _("🗑️ ABSÈNCIES ELIMINADES:\n")
            for absent in absents['eliminades']:
                contingut += _("  • {absent}\n").format(absent=absent)
            contingut += "\n"

        if absents.get('canvi_tipus'):
            contingut += _("🔄 CANVIS DE TIPUS D'ABSÈNCIA:\n")
            for canvi in absents['canvi_tipus']:
                contingut += _("  • {canvi}\n").format(canvi=canvi)
            contingut += "\n"
    else:
        # Backward compatibility with old format
        if diferencies.get('noves'):
            contingut += _("🆕 NOVES SUBSTITUCIONS:\n")
            for sub in diferencies['noves']:
                contingut += _("  • {hora} - {absent} ({assignatura}, {grup}) → {substitut}\n").format(
                    hora=sub['hora'], absent=sub['absent'], assignatura=sub['assignatura'], grup=sub['grup'], substitut=sub['substitut']
                )
                if sub.get('comentaris'):
                    contingut += _("    💬 Comentari: {comentaris}\n").format(comentaris=sub['comentaris'])
            contingut += "\n"

        if diferencies.get('eliminades'):
            contingut += _("🗑️ SUBSTITUCIONS ELIMINADES:\n")
            for sub in diferencies['eliminades']:
                contingut += _("  • {hora} - {absent} ({assignatura}, {grup}) → {substitut}\n").format(
                    hora=sub['hora'], absent=sub['absent'], assignatura=sub['assignatura'], grup=sub['grup'], substitut=sub['substitut']
                )
                if sub.get('comentaris'):
                    contingut += _("    💬 Comentari: {comentaris}\n").format(comentaris=sub['comentaris'])
            contingut += "\n"

        if diferencies.get('modificades'):
            contingut += _("✏️ SUBSTITUCIONS MODIFICADES:\n")
            for sub in diferencies['modificades']:
                contingut += _("  • {hora} - {absent} ({assignatura}, {grup})\n").format(
                    hora=sub['hora'], absent=sub['absent'], assignatura=sub['assignatura'], grup=sub['grup']
                )
                # Mostra canvis en substitut
                if sub.get('substitut_anterior') != sub.get('substitut_actual'):
                    contingut += _("    Substitut: {anterior} → {actual}\n").format(
                        anterior=sub.get('substitut_anterior') or _('(buit)'),
                        actual=sub.get('substitut_actual') or _('(buit)')
                    )
                # Mostra canvis en comentaris
                if sub.get('comentaris_anterior') != sub.get('comentaris_actual'):
                    contingut += _("    💬 Comentari: {anterior} → {actual}\n").format(
                        anterior=sub.get('comentaris_anterior') or _('(buit)'),
                        actual=sub.get('comentaris_actual') or _('(buit)')
                    )
            contingut += "\n"

    if not contingut:
        contingut = _("No s'han detectat canvis.")

    text_area.setText(contingut)
    layout.addWidget(text_area)

    # Botons
    button_layout = QHBoxLayout()

    btn_desar = QPushButton(_("💾 Desar canvis"))
    btn_descartar = QPushButton(_("🗑️ Descartar canvis"))
    btn_cancellar = QPushButton(_("❌ Cancel·lar"))

    button_layout.addWidget(btn_desar)
    button_layout.addWidget(btn_descartar)
    button_layout.addWidget(btn_cancellar)
    layout.addLayout(button_layout)

    # Resultat
    resultat = None

    def on_desar():
        nonlocal resultat
        resultat = 'desar'
        dialog.accept()

    def on_descartar():
        nonlocal resultat
        resultat = 'descartar'
        dialog.accept()

    def on_cancellar():
        nonlocal resultat
        resultat = 'cancellar'
        dialog.reject()

    btn_desar.clicked.connect(on_desar)
    btn_descartar.clicked.connect(on_descartar)
    btn_cancellar.clicked.connect(on_cancellar)

    dialog.exec()
    return resultat or 'cancellar'


def comparar_absents(dia_iso: str, absents_interficie: Dict[str, Dict]) -> Dict:
    """
    Compara absències de la interfície amb les del JSON.
    absents_interficie: {professor: {'hores': [hores], 'tipus_absencia': str}}
    Retorna dict amb diferències trobades.
    """
    try:
        # Extreu absents del JSON (només tipus_absencia = ABSENCIA o SERVEI)
        substitucions_json = storage.carregar_substitucions(dia_iso) or []
        absents_json = {}

        for sub in substitucions_json:
            if isinstance(sub, dict):
                professor_absent = sub.get("professor_absent", "").strip()
                hora = sub.get("hora", "").strip()
                tipus_absencia = sub.get("tipus_absencia", "ABSENCIA")
                assignatura = sub.get("assignatura", "").strip()
                grup = sub.get("grup", "").strip()

                # Comptar com absent si és ABSENCIA o SERVEI (amb o sense classe)
                if professor_absent and hora and tipus_absencia in ["ABSENCIA", "SERVEI"]:
                    if professor_absent not in absents_json:
                        absents_json[professor_absent] = {'hores': [], 'tipus_absencia': tipus_absencia}
                    if hora not in absents_json[professor_absent]['hores']:
                        absents_json[professor_absent]['hores'].append(hora)
                    # Actualitza tipus_absencia (en cas de múltiples entrades)
                    absents_json[professor_absent]['tipus_absencia'] = tipus_absencia

        # Troba diferències
        diferencies = {
            'noves': [],      # Absents nous (interfície però no JSON)
            'eliminades': [], # Absents eliminats (JSON però no interfície)
            'canvi_tipus': [] # Mateix professor/hora però tipus diferent
        }

        # Compara professors de la interfície
        for professor, info_interficie in absents_interficie.items():
            hores_interficie = info_interficie['hores']
            tipus_interficie = info_interficie['tipus_absencia']

            if professor in absents_json:
                info_json = absents_json[professor]
                hores_json = info_json['hores']
                tipus_json = info_json['tipus_absencia']

                # Compara tipus_absencia
                if tipus_interficie != tipus_json:
                    diferencies['canvi_tipus'].append(f"{professor}: {tipus_json} → {tipus_interficie}")

                # Compara hores noves
                for hora in hores_interficie:
                    if hora not in hores_json:
                        diferencies['noves'].append(f"{professor} a les {hora}")

                # Compara hores eliminades
                for hora in hores_json:
                    if hora not in hores_interficie:
                        diferencies['eliminades'].append(f"{professor} a les {hora}")
            else:
                # Professor nou
                for hora in hores_interficie:
                    diferencies['noves'].append(f"{professor} a les {hora}")

        # Compara professors del JSON que no estan a la interfície
        for professor, info_json in absents_json.items():
            if professor not in absents_interficie:
                for hora in info_json['hores']:
                    diferencies['eliminades'].append(f"{professor} a les {hora}")

        return diferencies

    except Exception as e:
        print(_("Error en comparar absents: {}").format(e))
        return {'noves': [], 'eliminades': [], 'canvi_tipus': []}


def comparar_grups(dia_iso: str, grups_interficie: Dict[str, set]) -> Dict:
    """
    Compara grups sense classe de la interfície amb els del JSON.
    grups_interficie: {hora: {grup1, grup2, ...}}
    Retorna dict amb diferències trobades.
    """
    try:
        # Carrega configuració del JSON
        config_dia = storage.carregar_configuracio_dia(dia_iso)
        grups_json = {}

        if config_dia and config_dia.grups_sense_classe:
            # Convertir List a Set per cada hora
            grups_json = {hora: set(llista) for hora, llista in config_dia.grups_sense_classe.items()}

        # Troba diferències
        diferencies = {
            'nous': [],      # Grups marcats a la interfície però no al JSON
            'eliminats': [], # Grups al JSON però no marcats a la interfície
        }

        # Totes les hores que apareixen (interfície o JSON)
        totes_hores = set(grups_interficie.keys()) | set(grups_json.keys())

        for hora in sorted(totes_hores):
            grups_hora_interficie = grups_interficie.get(hora, set())
            grups_hora_json = grups_json.get(hora, set())

            # Grups nous (interfície però no JSON)
            nous = grups_hora_interficie - grups_hora_json
            for grup in sorted(nous):
                diferencies['nous'].append(f"{hora}: {grup}")

            # Grups eliminats (JSON però no interfície)
            eliminats = grups_hora_json - grups_hora_interficie
            for grup in sorted(eliminats):
                diferencies['eliminats'].append(f"{hora}: {grup}")

        return diferencies

    except Exception as e:
        print(_("Error en comparar grups: {}").format(e))
        return {'nous': [], 'eliminats': []}


def comprovar_canvis_no_desats(parent, dia_iso: str = None) -> bool:
    """
    Comprova si hi ha canvis no desats.
    Retorna True si pot continuar, False si ha de cancel·lar.
    """
    try:
        if not dia_iso:
            dia_iso = DateContext(parent.date_selector.date()).iso_format

        # Comprova que els widgets estiguin inicialitzats
        if not hasattr(parent, 'substitucions_widget') or not parent.substitucions_widget:
            return True

        if not hasattr(parent.substitucions_widget, 'substitucions'):
            return True

        # Compara substitucions
        substitucions_interficie = parent.substitucions_widget.substitucions
        diferencies_subs = comparar_substitucions(dia_iso, substitucions_interficie)

        # Compara absències
        absents_interficie = parent.absents_widget.get_absents_with_tipus()
        diferencies_absents = comparar_absents(dia_iso, absents_interficie)

        # Nota: Els grups es comproven al sortir del tab, no aquí

        # Si no hi ha diferències en substitucions ni absències, continua
        total_canvis_subs = len(diferencies_subs['noves']) + len(diferencies_subs['eliminades']) + len(diferencies_subs['modificades'])
        total_canvis_absents = len(diferencies_absents['noves']) + len(diferencies_absents['eliminades']) + len(diferencies_absents['canvi_tipus'])

        if total_canvis_subs == 0 and total_canvis_absents == 0:
            return True

        # Combina diferències per al diàleg
        diferencies = {
            'substitucions': diferencies_subs,
            'absents': diferencies_absents
        }

        # Hi ha canvis, mostra diàleg
        dia_context = DateContext.from_iso(dia_iso)
        resposta = mostrar_canvis_dialog(parent, dia_context.catalan_format, diferencies)

        if resposta == "desar":
            # Desa les substitucions actuals
            absents_info = parent.absents_widget.get_absents_with_tipus()
            absents_actuals = {prof: info['hores'] for prof, info in absents_info.items()}
            absents_tipus_actuals = {prof: info['tipus_absencia'] for prof, info in absents_info.items()}
            success = storage.desar_substitucions(dia_iso, substitucions_interficie, absents_actuals, absents_tipus_actuals)

            if success:
                parent.status_label.setText(_("💾 Canvis desats i sincronitzats"))
                return True
            else:
                parent.status_label.setText(_("❌ Error en desar canvis"))
                return False

        elif resposta == "descartar":
            return True  # Continua sense desar
        else:  # cancellar
            return False  # No continua

    except Exception as e:
        print(_("Error en comprovar canvis no desats: {}").format(e))
        return True  # En cas d'error, deixa continuar
