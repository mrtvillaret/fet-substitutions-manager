"""
Diàlegs reutilitzables per exportació de PDFs
Unificació de tots els diàlegs relacionats amb PDFs
"""
from typing import Dict, List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QDialogButtonBox,
    QLabel, QGroupBox, QGridLayout, QPushButton, QWidget, QMessageBox
)
from i18n_setup import translate as _


def mostrar_dialeg_opcions_pdf(parent, nivells: List[str], titulo: str = _("Exportació del PDF de vigilàncies"), mostrar_nivells: bool = True) -> Optional[Dict]:
    """Mostra diàleg unificat per seleccionar opcions del PDF amb nivells i compressió"""
    # Carregar preferències des de config/pdf.json
    try:
        from export.pdf_styles import PDFStyleFactory
        # Forçar recàrrega del config invalidant cache
        PDFStyleFactory._config_cache = None
        PDFStyleFactory._config_last_modified = None
        pdf_config = PDFStyleFactory._load_pdf_config()
        show_comments_default = pdf_config.get('show_comments_column', True)
        show_hours_default = pdf_config.get('show_hours_column', False)
        compress_pdf_default = pdf_config.get('compress_pdf', False)
        print(f"📖 Carregant preferències: comentaris={show_comments_default}, hores={show_hours_default}, comprimir={compress_pdf_default}")
    except Exception as e:
        print(f"⚠️ Error carregant preferències, usant valors per defecte: {e}")
        show_comments_default = True
        show_hours_default = False
        compress_pdf_default = False

    dialog = QDialog(parent)
    dialog.setWindowTitle(titulo)

    # Mida adaptativa segons contingut
    if mostrar_nivells:
        # Mida inicial amb més altura per evitar solapament (augmentada per columnes opcionals)
        dialog.setMinimumSize(400, 500)
        dialog.resize(400, 500)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        # Missatge informatiu compacte
        info_label = QLabel(_("📄 Configureu les opcions:"))
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 8px; color: #2c3e50;")
        layout.addWidget(info_label)
    else:
        # Ultra-compacte per només compressió
        dialog.setMinimumSize(320, 200)
        dialog.resize(320, 200)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(15, 15, 15, 15)

    # Grup de selecció de nivells (només si s'ha demanat)
    nivells_checkboxes = {}
    if mostrar_nivells:
        nivells_group = QGroupBox(_("🎓 Nivells"))
        nivells_layout = QVBoxLayout(nivells_group)
        nivells_layout.setSpacing(6)

        # Botons Tots/Cap compactes
        controls_layout = QHBoxLayout()
        btn_tots = QPushButton(_("✅ Tots"))
        btn_tots.setMaximumWidth(70)
        btn_cap = QPushButton(_("❌ Cap"))
        btn_cap.setMaximumWidth(70)
        controls_layout.addWidget(btn_tots)
        controls_layout.addWidget(btn_cap)
        controls_layout.addStretch()
        nivells_layout.addLayout(controls_layout)

        # Layout simple i funcional amb bona distribució
        checkboxes_container = QWidget()
        checkboxes_layout = QGridLayout(checkboxes_container)
        checkboxes_layout.setHorizontalSpacing(12)
        checkboxes_layout.setVerticalSpacing(15)  # Espai vertical augmentat
        checkboxes_layout.setContentsMargins(8, 8, 4, 8)

        # Distribució fixa inicial: 3 columnes per defecte
        num_nivells = len(nivells)
        if num_nivells >= 3:
            cols = 3  # 3 columnes per defecte
        else:
            cols = num_nivells  # 1 o 2 columnes si menys nivells

        for i, nivell in enumerate(nivells):
            checkbox = QCheckBox(nivell)
            checkbox.setChecked(True)  # Tots seleccionats per defecte
            nivells_checkboxes[nivell] = checkbox
            row = i // cols
            col = i % cols
            checkboxes_layout.addWidget(checkbox, row, col)

        # Configurar stretch per centrar
        for c in range(cols):
            checkboxes_layout.setColumnStretch(c, 1)

        nivells_layout.addWidget(checkboxes_container)

        # Connexions dels botons
        btn_tots.clicked.connect(lambda: _toggle_all_nivells_dialog(nivells_checkboxes, True))
        btn_cap.clicked.connect(lambda: _toggle_all_nivells_dialog(nivells_checkboxes, False))

        layout.addWidget(nivells_group)

    # Opcions de compressió - adaptativa segons layout
    if mostrar_nivells:
        # Compacte per al diàleg amb nivells
        opcions_group = QGroupBox(_("⚙️ Opcions"))
        opcions_layout = QVBoxLayout(opcions_group)
        opcions_layout.setSpacing(4)
        opcions_layout.setContentsMargins(8, 6, 8, 6)

        checkbox_compressio = QCheckBox(_("🗜️ Compressió del PDF"))
        checkbox_compressio.setChecked(compress_pdf_default)
        checkbox_compressio.setToolTip(_("Redueix l'espaiat per a estalviar pàgines"))
        opcions_layout.addWidget(checkbox_compressio)

        checkbox_comentaris = QCheckBox(_("💬 Mostrar columna comentaris"))
        checkbox_comentaris.setChecked(show_comments_default)
        checkbox_comentaris.setToolTip(_("Mostra o amaga la columna d'observacions al PDF"))
        opcions_layout.addWidget(checkbox_comentaris)

        checkbox_hores = QCheckBox(_("🕒 Mostrar columna hores"))
        checkbox_hores.setChecked(show_hours_default)
        checkbox_hores.setToolTip(_("Afegeix una columna amb la franja horària"))
        opcions_layout.addWidget(checkbox_hores)

        layout.addWidget(opcions_group)
    else:
        # Sense grup per al diàleg simple
        checkbox_compressio = QCheckBox(_("🗜️ Compressió del PDF"))
        checkbox_compressio.setChecked(compress_pdf_default)
        checkbox_compressio.setToolTip(_("Redueix l'espaiat per a estalviar pàgines"))
        layout.addWidget(checkbox_compressio)

        checkbox_comentaris = QCheckBox(_("💬 Mostrar columna comentaris"))
        checkbox_comentaris.setChecked(show_comments_default)
        checkbox_comentaris.setToolTip(_("Mostra o amaga la columna d'observacions al PDF"))
        layout.addWidget(checkbox_comentaris)

        checkbox_hores = QCheckBox(_("🕒 Mostrar columna hores"))
        checkbox_hores.setChecked(show_hours_default)
        checkbox_hores.setToolTip(_("Afegeix una columna amb la franja horària"))
        layout.addWidget(checkbox_hores)

    # Botons
    buttons = QDialogButtonBox()
    btn_ok = buttons.addButton(_("D'acord"), QDialogButtonBox.AcceptRole)
    btn_cancel = buttons.addButton(_("Cancel·la"), QDialogButtonBox.RejectRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    # Mostrar diàleg
    if dialog.exec() == QDialog.Accepted:
        # Retornar opcions seleccionades
        result = {
            'comprimir': checkbox_compressio.isChecked(),
            'show_comments_column': checkbox_comentaris.isChecked(),
            'show_hours_column': checkbox_hores.isChecked(),
            'nivells_seleccionats': []
        }

        if mostrar_nivells:
            for nivell, checkbox in nivells_checkboxes.items():
                if checkbox.isChecked():
                    result['nivells_seleccionats'].append(nivell)

        # Desar preferències a config/pdf.json
        try:
            from export.pdf_styles import PDFStyleFactory
            import json
            from pathlib import Path

            config_path = Path(__file__).parent.parent.parent / 'config' / 'pdf.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                config['show_comments_column'] = result['show_comments_column']
                config['show_hours_column'] = result['show_hours_column']
                config['compress_pdf'] = result['comprimir']

                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                print(f"✅ Preferències PDF desades: comentaris={result['show_comments_column']}, hores={result['show_hours_column']}, comprimir={result['comprimir']}")

                # Invalidar cache
                PDFStyleFactory._config_cache = None
                PDFStyleFactory._config_last_modified = None
            else:
                print(f"❌ config/pdf.json no trobat a: {config_path}")
        except Exception as e:
            print(f"❌ Error desant preferències PDF: {e}")
            import traceback
            traceback.print_exc()

        return result
    else:
        return None  # Cancel·lat


def _toggle_all_nivells_dialog(checkboxes_dict: Dict, checked: bool):
    """Marca o desmarca tots els nivells en un diàleg"""
    for checkbox in checkboxes_dict.values():
        checkbox.setChecked(checked)


def mostrar_dialeg_compressio_pdf(parent, titulo: str = _("Exportació del PDF de vigilàncies")) -> Optional[Dict]:
    """Versió simplificada per compatibilitat amb codi existent - retorna diccionari complet"""
    result = mostrar_dialeg_opcions_pdf(parent, [], titulo, mostrar_nivells=False)
    return result


def mostrar_dialeg_pdf_combinat(parent, titulo: str = _("📄 Exportació del PDF complet")) -> Optional[Dict]:
    """Diàleg avançat amb selecció de contingut (substitucions/vigilàncies) i compressió"""
    # Carregar preferències des de config/pdf.json
    try:
        from export.pdf_styles import PDFStyleFactory
        # Forçar recàrrega del config invalidant cache
        PDFStyleFactory._config_cache = None
        PDFStyleFactory._config_last_modified = None
        pdf_config = PDFStyleFactory._load_pdf_config()
        show_comments_default = pdf_config.get('show_comments_column', True)
        show_hours_default = pdf_config.get('show_hours_column', False)
        include_substitutions_default = pdf_config.get('include_substitutions', True)
        include_vigilancies_default = pdf_config.get('include_vigilancies', True)
        compress_pdf_default = pdf_config.get('compress_pdf', False)
        print(f"📖 Carregant preferències combinat: subs={include_substitutions_default}, vigil={include_vigilancies_default}, comprimir={compress_pdf_default}, comentaris={show_comments_default}, hores={show_hours_default}")
    except Exception as e:
        print(f"⚠️ Error carregant preferències combinat, usant valors per defecte: {e}")
        show_comments_default = True
        show_hours_default = False
        include_substitutions_default = True
        include_vigilancies_default = True
        compress_pdf_default = False

    dialog = QDialog(parent)
    dialog.setWindowTitle(titulo)
    dialog.setMinimumSize(350, 250)
    dialog.resize(350, 250)
    layout = QVBoxLayout(dialog)

    # Layout ultra-compacte similar al PDF nivell
    info_label = QLabel(_("📄 Seleccioneu les opcions del PDF:"))
    info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
    layout.addWidget(info_label)

    checkbox_substitucions = QCheckBox(_("📚 Substitucions"))
    checkbox_substitucions.setChecked(include_substitutions_default)
    checkbox_substitucions.setToolTip(_("Inclou la llista de substitucions del dia"))
    layout.addWidget(checkbox_substitucions)

    checkbox_vigilancies = QCheckBox(_("👁️ Vigilàncies"))
    checkbox_vigilancies.setChecked(include_vigilancies_default)
    checkbox_vigilancies.setToolTip(_("Inclou les vigilàncies d'exàmens i activitats"))
    layout.addWidget(checkbox_vigilancies)

    checkbox_compressio = QCheckBox(_("🗜️ Compressió del PDF"))
    checkbox_compressio.setChecked(compress_pdf_default)
    checkbox_compressio.setToolTip(_("Redueix l'espaiat per a estalviar pàgines"))
    layout.addWidget(checkbox_compressio)

    checkbox_comentaris = QCheckBox(_("💬 Mostrar columna comentaris"))
    checkbox_comentaris.setChecked(show_comments_default)
    checkbox_comentaris.setToolTip(_("Mostra o amaga la columna d'observacions al PDF"))
    layout.addWidget(checkbox_comentaris)

    checkbox_hores = QCheckBox(_("🕒 Mostrar columna hores"))
    checkbox_hores.setChecked(show_hours_default)
    checkbox_hores.setToolTip(_("Afegeix una columna amb la franja horària"))
    layout.addWidget(checkbox_hores)

    # Botons
    buttons = QDialogButtonBox()
    btn_ok = buttons.addButton(_("D'acord"), QDialogButtonBox.AcceptRole)
    btn_cancel = buttons.addButton(_("Cancel·la"), QDialogButtonBox.RejectRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    # Mostrar diàleg
    if dialog.exec() == QDialog.Accepted:
        # Validar que almenys una opció estigui seleccionada
        if not checkbox_substitucions.isChecked() and not checkbox_vigilancies.isChecked():
            QMessageBox.warning(parent, _("Error"), _("Heu de seleccionar almenys una opció per a generar el PDF."))
            return None

        result = {
            'substitucions': checkbox_substitucions.isChecked(),
            'vigilancies': checkbox_vigilancies.isChecked(),
            'nivells_seleccionats': [],  # No cal selecció de nivells per PDF principal
            'comprimir': checkbox_compressio.isChecked(),
            'show_comments_column': checkbox_comentaris.isChecked(),
            'show_hours_column': checkbox_hores.isChecked()
        }

        # Desar preferències a config/pdf.json
        try:
            from export.pdf_styles import PDFStyleFactory
            import json
            from pathlib import Path

            config_path = Path(__file__).parent.parent.parent / 'config' / 'pdf.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                config['show_comments_column'] = result['show_comments_column']
                config['show_hours_column'] = result['show_hours_column']
                config['include_substitutions'] = result['substitucions']
                config['include_vigilancies'] = result['vigilancies']
                config['compress_pdf'] = result['comprimir']

                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                print(f"✅ Preferències PDF combinat desades: subs={result['substitucions']}, vigil={result['vigilancies']}, comprimir={result['comprimir']}, comentaris={result['show_comments_column']}, hores={result['show_hours_column']}")

                # Invalidar cache
                PDFStyleFactory._config_cache = None
                PDFStyleFactory._config_last_modified = None
            else:
                print(f"❌ config/pdf.json no trobat a: {config_path}")
        except Exception as e:
            print(f"❌ Error desant preferències PDF combinat: {e}")
            import traceback
            traceback.print_exc()

        return result
    else:
        return None
