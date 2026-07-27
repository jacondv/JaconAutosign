"""Settings tab: default signing certificate, signer name, output folder, and
signature template management (create/edit/duplicate/delete) - laid out as
columns (certificate, output, templates) so everything is visible at once.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .appearance_preview import render_template_preview
from ..services import SettingsService, TemplateService
from ..services.settings_service import (
    OUTPUT_MODE_CUSTOM,
    OUTPUT_MODE_SUBFOLDER,
    THEME_DARK,
    THEME_LIGHT,
)
from ..signing import CertificateLoadError, Pkcs12CertificateProvider

_ROLE_TEMPLATE_ID = 1000
_PREVIEW_MAX_WIDTH = 300


class SettingsScreen(QWidget):
    create_template_requested = Signal()
    edit_template_requested = Signal(str)  # template_id
    settings_saved = Signal()
    theme_changed = Signal(str)  # "light" | "dark" - applied live, before Save is clicked

    def __init__(
        self,
        template_service: TemplateService,
        settings_service: SettingsService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._templates = template_service
        self._settings_service = settings_service
        self._settings = settings_service.load()

        self._build_ui()
        self._load_fields_from_settings()
        self.refresh_templates()

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.addLayout(self._build_certificate_column(), 1)
        root.addLayout(self._build_output_column(), 1)
        root.addLayout(self._build_templates_column(), 1)
        root.addLayout(self._build_preferences_column(), 1)

    def _build_certificate_column(self) -> QVBoxLayout:
        self._pfx_path_edit = QLineEdit()
        browse_pfx_btn = QPushButton("Browse...")
        browse_pfx_btn.clicked.connect(self._browse_pfx)
        pfx_row = QHBoxLayout()
        pfx_row.addWidget(self._pfx_path_edit, 1)
        pfx_row.addWidget(browse_pfx_btn)

        self._signer_name_edit = QLineEdit()
        self._signer_name_edit.setPlaceholderText("Name shown in the signature (Signed by: ...)")
        self._signer_name_edit.textChanged.connect(self._refresh_preview)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._remember_password_check = QCheckBox("Remember password (encrypted with Windows DPAPI)")
        self._remember_password_check.setToolTip(
            "The password is encrypted with Windows DPAPI, tied to the current\n"
            "Windows account - never stored as plain text, and only this\n"
            "account on this machine can decrypt it."
        )
        test_btn = QPushButton("Test certificate")
        test_btn.clicked.connect(self._test_certificate)

        cert_form = QFormLayout()
        cert_form.addRow("Certificate file (.p12/.pfx):", pfx_row)
        cert_form.addRow("Signer name:", self._signer_name_edit)
        cert_form.addRow("Password:", self._password_edit)
        cert_form.addRow("", self._remember_password_check)
        cert_form.addRow("", test_btn)
        cert_group = QGroupBox("Signing certificate")
        cert_group.setLayout(cert_form)

        save_btn = QPushButton("Save settings")
        save_btn.setObjectName("primaryButton")
        save_btn.setMinimumHeight(36)
        save_btn.clicked.connect(self._save_settings)

        column = QVBoxLayout()
        column.addWidget(cert_group)
        column.addWidget(save_btn)
        column.addStretch(1)
        return column

    def _build_output_column(self) -> QVBoxLayout:
        self._subfolder_radio = QRadioButton("Subfolder named \"Signed_<signer name>\" next to the source file")
        self._subfolder_radio.setToolTip(
            "e.g. signing a file in Downloads writes to Downloads/Signed_<your name>/.\n"
            "To sign in place, point the custom folder below at the source folder itself."
        )
        self._custom_radio = QRadioButton("Custom folder:")
        self._custom_dir_edit = QLineEdit()
        browse_out_btn = QPushButton("Browse...")
        browse_out_btn.clicked.connect(self._browse_output_dir)
        custom_row = QHBoxLayout()
        custom_row.addWidget(self._custom_radio)
        custom_row.addWidget(self._custom_dir_edit, 1)
        custom_row.addWidget(browse_out_btn)

        output_layout = QVBoxLayout()
        output_layout.addWidget(self._subfolder_radio)
        output_layout.addLayout(custom_row)
        output_group = QGroupBox("Output folder")
        output_group.setLayout(output_layout)

        preview_group = QGroupBox("Signature preview")
        preview_layout = QVBoxLayout(preview_group)
        self._preview_label = QLabel("Select a template to preview its signature.")
        self._preview_label.setWordWrap(True)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(120)
        preview_layout.addWidget(self._preview_label)

        column = QVBoxLayout()
        column.addWidget(output_group)
        column.addWidget(preview_group, 1)
        return column

    def _build_templates_column(self) -> QVBoxLayout:
        self._template_list = QListWidget()
        self._template_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._template_list.itemDoubleClicked.connect(self._edit_selected_template)
        self._template_list.currentItemChanged.connect(self._refresh_preview)
        new_tpl_btn = QPushButton("New template")
        new_tpl_btn.clicked.connect(self.create_template_requested.emit)
        edit_tpl_btn = QPushButton("Edit")
        edit_tpl_btn.clicked.connect(self._edit_selected_template)
        dup_tpl_btn = QPushButton("Duplicate")
        dup_tpl_btn.clicked.connect(self._duplicate_selected_template)
        del_tpl_btn = QPushButton("Delete")
        del_tpl_btn.clicked.connect(self._delete_selected_template)
        tpl_buttons = QHBoxLayout()
        for btn in (new_tpl_btn, edit_tpl_btn, dup_tpl_btn, del_tpl_btn):
            tpl_buttons.addWidget(btn)

        tpl_layout = QVBoxLayout()
        tpl_layout.addWidget(self._template_list, 1)
        tpl_layout.addLayout(tpl_buttons)
        tpl_group = QGroupBox("Signature templates")
        tpl_group.setLayout(tpl_layout)

        column = QVBoxLayout()
        column.addWidget(tpl_group, 1)
        return column

    def _build_preferences_column(self) -> QVBoxLayout:
        self._light_radio = QRadioButton("Light")
        self._dark_radio = QRadioButton("Dark")
        self._light_radio.toggled.connect(self._on_theme_toggled)
        appearance_layout = QVBoxLayout()
        appearance_layout.addWidget(self._light_radio)
        appearance_layout.addWidget(self._dark_radio)
        appearance_group = QGroupBox("Appearance")
        appearance_group.setLayout(appearance_layout)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(0, 72)
        self._font_size_spin.setSpecialValueText("Auto")
        self._font_size_spin.setToolTip(
            "Font size (pt) for the \"Digitally signed by / Date\" text next to the\n"
            "signature image. 0 = auto (shrinks to fit the signature box)."
        )
        self._font_size_spin.valueChanged.connect(self._refresh_preview)
        signature_text_form = QFormLayout()
        signature_text_form.addRow("Font size:", self._font_size_spin)
        signature_text_group = QGroupBox("Signature text")
        signature_text_group.setLayout(signature_text_form)

        self._shortcut_open_files_edit = QKeySequenceEdit()
        self._shortcut_open_folder_edit = QKeySequenceEdit()
        self._shortcut_sign_edit = QKeySequenceEdit()
        shortcuts_form = QFormLayout()
        shortcuts_form.addRow("Open Files:", self._shortcut_open_files_edit)
        shortcuts_form.addRow("Open Folder:", self._shortcut_open_folder_edit)
        shortcuts_form.addRow("Sign:", self._shortcut_sign_edit)
        shortcuts_group = QGroupBox("Keyboard Shortcuts")
        shortcuts_group.setLayout(shortcuts_form)

        column = QVBoxLayout()
        column.addWidget(appearance_group)
        column.addWidget(signature_text_group)
        column.addWidget(shortcuts_group)
        column.addStretch(1)
        return column

    def _load_fields_from_settings(self) -> None:
        s = self._settings
        if s.last_pfx_path:
            self._pfx_path_edit.setText(s.last_pfx_path)
        if s.signer_name:
            self._signer_name_edit.setText(s.signer_name)
        if s.output_mode == OUTPUT_MODE_CUSTOM:
            self._custom_radio.setChecked(True)
        else:
            self._subfolder_radio.setChecked(True)
        if s.custom_output_dir:
            self._custom_dir_edit.setText(s.custom_output_dir)
        remembered = self._settings_service.get_remembered_password(s)
        if remembered:
            self._password_edit.setText(remembered)
            self._remember_password_check.setChecked(True)

        # Block signals: selecting the saved theme here must not re-trigger
        # a "theme changed, save + re-apply" round trip on startup.
        self._light_radio.blockSignals(True)
        (self._dark_radio if s.theme_mode == THEME_DARK else self._light_radio).setChecked(True)
        self._light_radio.blockSignals(False)

        self._font_size_spin.blockSignals(True)
        self._font_size_spin.setValue(s.signature_font_size)
        self._font_size_spin.blockSignals(False)

        self._shortcut_open_files_edit.setKeySequence(QKeySequence(s.shortcut_open_files))
        self._shortcut_open_folder_edit.setKeySequence(QKeySequence(s.shortcut_open_folder))
        self._shortcut_sign_edit.setKeySequence(QKeySequence(s.shortcut_sign))

    # -------------------------------------------------------------- actions
    def _browse_pfx(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose certificate file", "", "PKCS#12 (*.pfx *.p12)"
        )
        if path:
            self._pfx_path_edit.setText(path)

    def _browse_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self._custom_dir_edit.setText(folder)
            self._custom_radio.setChecked(True)

    def _test_certificate(self) -> None:
        path = self._pfx_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing certificate", "Choose a .p12/.pfx file first.")
            return
        try:
            provider = Pkcs12CertificateProvider(Path(path), self._password_edit.text())
        except CertificateLoadError as exc:
            QMessageBox.critical(self, "Certificate error", str(exc))
            return
        info = provider.get_info()
        if info.common_name:
            self._signer_name_edit.setText(info.common_name)
        status = "EXPIRED" if info.is_expired else f"valid for {info.days_until_expiry()} more day(s)"
        QMessageBox.information(
            self,
            "Certificate OK",
            f"Subject: {info.subject}\n"
            f"Issuer: {info.issuer}\n"
            f"Expires: {info.not_valid_after:%Y-%m-%d} ({status})",
        )

    def _save_settings(self) -> None:
        self._settings.last_pfx_path = self._pfx_path_edit.text().strip() or None
        self._settings.signer_name = self._signer_name_edit.text().strip() or None
        self._settings.output_mode = (
            OUTPUT_MODE_CUSTOM if self._custom_radio.isChecked() else OUTPUT_MODE_SUBFOLDER
        )
        self._settings.custom_output_dir = self._custom_dir_edit.text().strip() or None
        if self._remember_password_check.isChecked() and self._password_edit.text():
            self._settings_service.set_remembered_password(
                self._settings, self._password_edit.text()
            )
        else:
            self._settings_service.clear_remembered_password(self._settings)
        self._settings.theme_mode = THEME_DARK if self._dark_radio.isChecked() else THEME_LIGHT
        self._settings.signature_font_size = self._font_size_spin.value()
        self._settings.shortcut_open_files = self._shortcut_open_files_edit.keySequence().toString()
        self._settings.shortcut_open_folder = self._shortcut_open_folder_edit.keySequence().toString()
        self._settings.shortcut_sign = self._shortcut_sign_edit.keySequence().toString()
        self._settings_service.save(self._settings)
        QMessageBox.information(self, "Saved", "Settings saved.")
        self.settings_saved.emit()

    def _on_theme_toggled(self, light_checked: bool) -> None:
        """Applied and persisted immediately (not gated behind Save settings)
        - a theme pick is a display preference, not something that should be
        lost if the user forgets to click Save."""
        mode = THEME_LIGHT if light_checked else THEME_DARK
        self._settings.theme_mode = mode
        self._settings_service.save(self._settings)
        self.theme_changed.emit(mode)

    def current_password_field(self) -> str:
        """Lets the Sign tab reuse the password typed here for this session
        without requiring a save, if the user hasn't saved settings yet."""
        return self._password_edit.text()

    # ------------------------------------------------------------ templates
    def refresh_templates(self) -> None:
        self._template_list.clear()
        for template in self._templates.list_templates():
            item = QListWidgetItem(
                f"{template.template_name}  ({len(template.signature_boxes)} box(es))"
            )
            item.setData(_ROLE_TEMPLATE_ID, template.template_id)
            self._template_list.addItem(item)
        self._refresh_preview()

    def _selected_template_id(self) -> str | None:
        item = self._template_list.currentItem()
        return item.data(_ROLE_TEMPLATE_ID) if item else None

    def _edit_selected_template(self) -> None:
        template_id = self._selected_template_id()
        if template_id:
            self.edit_template_requested.emit(template_id)

    def _duplicate_selected_template(self) -> None:
        template_id = self._selected_template_id()
        if not template_id:
            return
        original = self._templates.load(template_id)
        name, ok = QInputDialog.getText(
            self, "Duplicate template", "New template name:", text=f"{original.template_name} (copy)"
        )
        if ok and name.strip():
            self._templates.duplicate(template_id, name.strip())
            self.refresh_templates()

    def _delete_selected_template(self) -> None:
        template_id = self._selected_template_id()
        if not template_id:
            return
        confirm = QMessageBox.question(
            self, "Delete template", "Are you sure you want to delete this template?"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._templates.delete(template_id)
            self.refresh_templates()

    # -------------------------------------------------------------- preview
    def _refresh_preview(self) -> None:
        template_id = self._selected_template_id()
        if not template_id:
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("Select a template to preview its signature.")
            return
        template = self._templates.load(template_id)
        pixmap = render_template_preview(
            template, self._signer_name_edit.text().strip(), self._font_size_spin.value() or None
        )
        if pixmap is None:
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("This template has no signature boxes yet.")
            return
        if pixmap.width() > _PREVIEW_MAX_WIDTH:
            pixmap = pixmap.scaledToWidth(_PREVIEW_MAX_WIDTH, Qt.TransformationMode.SmoothTransformation)
        self._preview_label.setText("")
        self._preview_label.setPixmap(pixmap)
