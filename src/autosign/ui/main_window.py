"""Main window: a RibbonBar (Home/Settings tabs) drives a Home workspace
(PDF viewer + sign controls) and a Settings page, with the Template Designer
opening as a full-window overlay when creating/editing a template.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import settings_file, templates_dir
from ..services import PdfInspectService, SettingsService, TemplateService
from . import theme
from .settings_screen import SettingsScreen
from .sign_screen import SignScreen, ViewerStatus
from .template_designer import TemplateDesignerScreen
from .widgets import RibbonBar


class MainWindow(QMainWindow):
    def __init__(
        self, initial_theme: str = theme.THEME_LIGHT, startup_paths: list[Path] | None = None
    ):
        super().__init__()
        self._base_title = "AutoSign - Batch PDF Signing"
        self.setWindowTitle(self._base_title)
        self.resize(1400, 860)
        self._shortcuts: list[QShortcut] = []
        self._startup_paths = startup_paths or []

        self._template_service = TemplateService(templates_dir())
        self._pdf_inspect = PdfInspectService()
        self._settings_service = SettingsService(settings_file())

        self._outer_stack = QStackedWidget()
        self.setCentralWidget(self._outer_stack)

        self._sign_screen = SignScreen(
            self._template_service, self._pdf_inspect, self._settings_service
        )
        self._sign_screen.set_canvas_backdrop_color(
            QColor(theme.palette_for(initial_theme).canvas_backdrop)
        )
        self._settings_screen = SettingsScreen(self._template_service, self._settings_service)
        self._settings_screen.create_template_requested.connect(self._open_new_template)
        self._settings_screen.edit_template_requested.connect(self._open_edit_template)
        self._settings_screen.settings_saved.connect(self._sign_screen.refresh_cert_status)
        self._settings_screen.settings_saved.connect(self._apply_shortcuts)
        self._settings_screen.theme_changed.connect(self._apply_theme)
        self._sign_screen.current_file_changed.connect(self._update_title)

        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._sign_screen)
        self._content_stack.addWidget(self._settings_screen)

        self._ribbon = RibbonBar(theme_mode=initial_theme)
        self._wire_ribbon()

        main_page = QWidget()
        layout = QVBoxLayout(main_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._ribbon)
        layout.addWidget(self._content_stack, 1)
        self._outer_stack.addWidget(main_page)

        self._transient_screen: TemplateDesignerScreen | None = None
        self._clipboard_autoload_done = False
        self._apply_shortcuts()

        initial_settings = self._settings_service.load()
        self._ribbon.set_wheel_page_turn_enabled(initial_settings.wheel_page_turn_enabled)
        self._sign_screen.set_wheel_page_turn_enabled(initial_settings.wheel_page_turn_enabled)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._clipboard_autoload_done:
            self._clipboard_autoload_done = True
            # Deferred to the next event-loop iteration rather than done
            # directly here, same reasoning as the old startup password
            # prompt: touching things synchronously inside showEvent can
            # wedge showMaximized() on real Windows.
            QTimer.singleShot(0, self._autoload_from_startup)

    def _autoload_from_startup(self) -> None:
        """Prefer file(s) handed in on the command line (Explorer's "Open
        with AutoSign") over the clipboard-path fallback below - both feed
        into the same SignScreen open_from_startup_path(s) rule."""
        if self._startup_paths:
            self._sign_screen.open_from_startup_paths(self._startup_paths)
            return
        self._autoload_from_clipboard()

    def open_startup_paths(self, paths: list[Path]) -> None:
        """Called (via main.py's single-instance local-socket server) when
        a later AutoSign launch - e.g. Explorer invoking us again for
        another file in the same multi-select - hands off its files here
        instead of opening a second window."""
        if paths:
            self._sign_screen.open_from_startup_paths(paths)
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _autoload_from_clipboard(self) -> None:
        """If the user copied a path (e.g. "Copy as path" in Explorer)
        before opening the app, feed it to SignScreen.open_from_startup_path
        - a copied file opens directly, a copied folder pre-navigates the
        Open Files dialog to it, and anything else falls back to that
        dialog at the last folder used (see SignScreen for the full rule)."""
        app = QApplication.instance()
        path = None
        if isinstance(app, QApplication):
            clipboard_text = app.clipboard().text().strip()
            if clipboard_text:
                # "Copy as path" in Explorer wraps it in quotes; only look
                # at the first line if several paths were copied at once.
                text = clipboard_text.splitlines()[0].strip().strip('"')
                if text:
                    try:
                        path = Path(text)
                    except (OSError, ValueError):
                        path = None
        self._sign_screen.open_from_startup_path(path)

    def _wire_ribbon(self) -> None:
        r = self._ribbon
        r.home_activated.connect(lambda: self._content_stack.setCurrentIndex(0))
        r.settings_activated.connect(lambda: self._content_stack.setCurrentIndex(1))
        r.open_files_requested.connect(self._sign_screen.open_files)
        r.open_folder_requested.connect(self._sign_screen.open_folder)
        r.prev_page_requested.connect(self._sign_screen.prev_page)
        r.next_page_requested.connect(self._sign_screen.next_page)
        r.zoom_in_requested.connect(self._sign_screen.zoom_in)
        r.zoom_out_requested.connect(self._sign_screen.zoom_out)
        r.fit_width_requested.connect(self._sign_screen.fit_width)
        r.fit_page_requested.connect(self._sign_screen.fit_page)
        r.reset_zoom_requested.connect(self._sign_screen.reset_zoom)
        r.toggle_panel_requested.connect(self._sign_screen.toggle_panel)
        r.sign_requested.connect(self._sign_screen.start_signing)
        r.export_report_requested.connect(self._sign_screen.export_report)
        r.wheel_page_turn_toggled.connect(self._on_wheel_page_turn_toggled)

        self._sign_screen.settings_requested.connect(lambda: r.setCurrentIndex(1))
        self._sign_screen.viewer_status_changed.connect(self._on_viewer_status)
        self._sign_screen.panel_toggled.connect(r.set_panel_toggle_text)
        self._sign_screen.sign_running_changed.connect(lambda running: r.set_sign_enabled(not running))

    # ------------------------------------------------------------------ theme
    def _apply_theme(self, mode: str) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(theme.stylesheet(mode))
        self._ribbon.set_theme(mode)
        self._sign_screen.set_canvas_backdrop_color(QColor(theme.palette_for(mode).canvas_backdrop))

    # -------------------------------------------------------- wheel page turn
    def _on_wheel_page_turn_toggled(self, enabled: bool) -> None:
        self._sign_screen.set_wheel_page_turn_enabled(enabled)
        settings = self._settings_service.load()
        settings.wheel_page_turn_enabled = enabled
        self._settings_service.save(settings)

    # -------------------------------------------------------------- shortcuts
    def _apply_shortcuts(self) -> None:
        """(Re)bind the user-configurable Open Files / Open Folder / Sign
        shortcuts - called once at startup and again whenever Settings is
        saved, since the user may have just changed one."""
        for shortcut in self._shortcuts:
            shortcut.setParent(None)
        self._shortcuts.clear()

        settings = self._settings_service.load()
        bindings = (
            (settings.shortcut_open_files, self._sign_screen.open_files),
            (settings.shortcut_open_folder, self._sign_screen.open_folder),
            (settings.shortcut_sign, self._sign_screen.start_signing),
        )
        for sequence_text, handler in bindings:
            if not sequence_text:
                continue
            sequence = QKeySequence(sequence_text)
            if sequence.isEmpty():
                continue
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _update_title(self, path) -> None:
        self.setWindowTitle(f"{self._base_title} - {path.name}" if path else self._base_title)

    def _on_viewer_status(self, status: ViewerStatus) -> None:
        self._ribbon.set_page_label(status.page_label)
        self._ribbon.set_nav_enabled(status.has_prev, status.has_next)
        self._ribbon.set_page_signed(status.signed)
        self._ribbon.set_zoom_label(status.zoom_label)

    def _open_new_template(self) -> None:
        screen = TemplateDesignerScreen(self._template_service, self._pdf_inspect)
        screen.back_requested.connect(self._back_to_main)
        screen.saved.connect(self._back_to_main)
        self._show_transient(screen)

    def _open_edit_template(self, template_id: str) -> None:
        template = self._template_service.load(template_id)
        screen = TemplateDesignerScreen(
            self._template_service, self._pdf_inspect, existing_template=template
        )
        screen.back_requested.connect(self._back_to_main)
        screen.saved.connect(self._back_to_main)
        self._show_transient(screen)

    def _show_transient(self, screen: TemplateDesignerScreen) -> None:
        self._clear_transient()
        self._transient_screen = screen
        self._outer_stack.addWidget(screen)
        self._outer_stack.setCurrentWidget(screen)

    def _back_to_main(self) -> None:
        self._settings_screen.refresh_templates()
        self._sign_screen.reload_templates()
        self._outer_stack.setCurrentIndex(0)
        self._ribbon.setCurrentIndex(1)  # templates are managed from Settings
        self._clear_transient()

    def _clear_transient(self) -> None:
        if self._transient_screen is not None:
            self._outer_stack.removeWidget(self._transient_screen)
            self._transient_screen.deleteLater()
            self._transient_screen = None

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Block closing the app mid-batch - avoid cutting off file writes
        # (and avoid destroying a QThread while it's still running).
        if self._sign_screen.is_batch_running():
            QMessageBox.warning(
                self,
                "Signing in progress",
                "Please wait for the batch to finish, or click Cancel, before closing the app.",
            )
            event.ignore()
            return
        event.accept()
