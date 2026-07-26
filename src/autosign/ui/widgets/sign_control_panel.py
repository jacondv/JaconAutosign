"""Sign controls: template picker, sign scope, certificate status, and the
Sign/Cancel/progress row. Purely presentational - the caller supplies
template/cert data and reacts to the request signals; this widget holds no
service references.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ...models import SignPageScope

_PAGE_SCOPE_LABELS = {
    SignPageScope.CURRENT: "Current page",
    SignPageScope.FIRST: "First page",
    SignPageScope.LAST: "Last page",
    SignPageScope.ALL: "All pages",
}


class SignControlPanel(QWidget):
    template_changed = Signal(str)  # template_id, "" if none selected
    manage_templates_requested = Signal()
    sign_requested = Signal()
    cancel_requested = Signal()
    file_scope_changed = Signal(bool)  # True = current file only
    page_scope_changed = Signal(str)  # SignPageScope value

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._template_combo = QComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_index_changed)
        tpl_group = QGroupBox("Template")
        tpl_layout = QVBoxLayout(tpl_group)
        tpl_layout.addWidget(self._template_combo)
        manage_btn = QPushButton("Manage templates (Settings)")
        manage_btn.clicked.connect(self.manage_templates_requested.emit)
        tpl_layout.addWidget(manage_btn)
        layout.addWidget(tpl_group)

        self._scope_current_radio = QRadioButton("Current file only")
        self._scope_all_radio = QRadioButton("All files in the list")
        self._scope_all_radio.setChecked(True)
        self._scope_current_radio.toggled.connect(
            lambda checked: checked and self.file_scope_changed.emit(True)
        )
        self._scope_all_radio.toggled.connect(
            lambda checked: checked and self.file_scope_changed.emit(False)
        )
        scope_group = QGroupBox("Sign scope")
        scope_layout = QVBoxLayout(scope_group)
        scope_layout.addWidget(self._scope_current_radio)
        scope_layout.addWidget(self._scope_all_radio)
        layout.addWidget(scope_group)

        self._page_scope_radios: dict[SignPageScope, QRadioButton] = {}
        page_scope_group = QGroupBox("Page scope")
        page_scope_layout = QVBoxLayout(page_scope_group)
        for scope, text in _PAGE_SCOPE_LABELS.items():
            radio = QRadioButton(text)
            radio.toggled.connect(
                lambda checked, s=scope: checked and self.page_scope_changed.emit(s.value)
            )
            self._page_scope_radios[scope] = radio
            page_scope_layout.addWidget(radio)
        self._page_scope_radios[SignPageScope.ALL].setChecked(True)
        layout.addWidget(page_scope_group)

        self._cert_status_label = QLabel("")
        self._cert_status_label.setWordWrap(True)
        layout.addWidget(self._cert_status_label)

        self._sign_btn = QPushButton("Sign")
        self._sign_btn.setObjectName("primaryButton")
        self._sign_btn.setMinimumHeight(48)
        self._sign_btn.clicked.connect(self.sign_requested.emit)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self._sign_btn)
        layout.addWidget(self._cancel_btn)

        self._progress_bar = QProgressBar()
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._summary_label)

    def _on_template_index_changed(self, _index: int) -> None:
        self.template_changed.emit(self._template_combo.currentData() or "")

    # ----------------------------------------------------------- templates
    def set_templates(self, templates: list[tuple[str, str]], selected_id: str | None) -> None:
        """`templates` is a list of (template_id, template_name). Selecting
        `selected_id` here does not emit template_changed (this mirrors a
        saved-preference reload, not a user action)."""
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        for template_id, name in templates:
            self._template_combo.addItem(name, template_id)
        if selected_id:
            index = self._template_combo.findData(selected_id)
            if index >= 0:
                self._template_combo.setCurrentIndex(index)
        self._template_combo.blockSignals(False)

    def current_template_id(self) -> str | None:
        return self._template_combo.currentData() or None

    # ----------------------------------------------------------------- scope
    def is_current_file_only(self) -> bool:
        return self._scope_current_radio.isChecked()

    def set_file_scope(self, current_only: bool) -> None:
        """Restore a saved preference - does not emit file_scope_changed
        (mirrors set_templates(), a reload rather than a user action)."""
        radio = self._scope_current_radio if current_only else self._scope_all_radio
        radio.blockSignals(True)
        radio.setChecked(True)
        radio.blockSignals(False)

    def current_page_scope(self) -> SignPageScope:
        for scope, radio in self._page_scope_radios.items():
            if radio.isChecked():
                return scope
        return SignPageScope.ALL

    def set_page_scope(self, scope: SignPageScope) -> None:
        """Restore a saved preference - does not emit page_scope_changed."""
        radio = self._page_scope_radios.get(scope)
        if radio is None:
            return
        radio.blockSignals(True)
        radio.setChecked(True)
        radio.blockSignals(False)

    # ------------------------------------------------------------ cert status
    def set_cert_status(self, text: str) -> None:
        self._cert_status_label.setText(text)

    # -------------------------------------------------------------- run state
    def set_running(self, running: bool) -> None:
        self._sign_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._template_combo.setEnabled(not running)
        self._scope_current_radio.setEnabled(not running)
        self._scope_all_radio.setEnabled(not running)
        for radio in self._page_scope_radios.values():
            radio.setEnabled(not running)

    def disable_cancel(self) -> None:
        """Cancel was clicked - grey it out while the worker winds down,
        without touching the other run-state controls."""
        self._cancel_btn.setEnabled(False)

    def start_progress(self, total: int) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(0)
        self._summary_label.setText("")

    def set_progress_value(self, value: int) -> None:
        self._progress_bar.setValue(value)

    def set_summary(self, text: str) -> None:
        self._summary_label.setText(text)
