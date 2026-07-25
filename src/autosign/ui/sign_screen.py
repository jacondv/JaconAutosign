"""Sign workspace: a Foxit-Reader-like PDF viewer takes up most of the
window, with a collapsible right-hand panel holding the file list and the
template/scope/sign controls. This is the screen shown on app start so the
user can jump straight into signing.

This widget has no toolbar of its own - MainWindow's RibbonBar drives page
navigation, zoom, open/sign/export and panel-collapse through the public
methods and signals below, so this class stays testable without a ribbon
(see the file/template/sign wiring, which is unchanged from before the
ribbon existed).
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..services import PdfInfo, PdfInspectService, SettingsService, TemplateService, get_signed_pages
from ..services.batch_sign_service import BatchSignService
from ..services.pdf_inspect_service import PdfInspectError
from ..signing import CertificateLoadError, Pkcs12CertificateProvider, SigningEngine
from .batch_sign_worker import BatchSignWorker
from .coordinates import pdf_rect_to_pixel
from .widgets import FileListPanel, PdfViewerWidget, SignControlPanel

_DEFAULT_PANEL_WIDTH = 340


@dataclass(frozen=True)
class ViewerStatus:
    """A snapshot of what the ribbon should show about the current page -
    emitted together so the ribbon never displays a stale combination
    (e.g. the previous file's zoom next to the new file's page number)."""

    page_label: str
    has_prev: bool
    has_next: bool
    signed: bool | None  # None = no file loaded / unknown
    zoom_label: str


class SignScreen(QWidget):
    settings_requested = Signal()
    viewer_status_changed = Signal(ViewerStatus)
    panel_toggled = Signal(str)  # new "Hide Panel"/"Show Panel" button text
    sign_running_changed = Signal(bool)

    def __init__(
        self,
        template_service: TemplateService,
        pdf_inspect_service: PdfInspectService,
        settings_service: SettingsService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._templates = template_service
        self._pdf_inspect = pdf_inspect_service
        self._settings_service = settings_service

        self._results: dict[Path, object] = {}
        self._current_file: Path | None = None
        self._current_pdf_info: PdfInfo | None = None
        self._current_signed_pages: set[int] = set()
        self._worker: BatchSignWorker | None = None
        self._session_password: str | None = None
        self._panel_collapsed = False
        self._last_panel_width = _DEFAULT_PANEL_WIDTH

        self._build_ui()
        self.reload_templates()

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._viewer = PdfViewerWidget(show_toolbar=False)
        self._viewer.page_changed.connect(lambda _index: self._on_viewer_state_changed())
        self._viewer.zoom_changed.connect(lambda _label: self._on_viewer_state_changed())
        self._splitter.addWidget(self._viewer)
        self._splitter.addWidget(self._build_right_panel())
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([1000, _DEFAULT_PANEL_WIDTH])
        root.addWidget(self._splitter, 1)

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(260)
        layout = QVBoxLayout(panel)

        self._file_panel = FileListPanel()
        self._file_panel.files_changed.connect(self._refresh_file_list)
        self._file_panel.selection_changed.connect(self._on_file_selection_changed)
        self._file_panel.file_activated.connect(self._open_output_for)
        layout.addWidget(self._file_panel, 2)

        self._control_panel = SignControlPanel()
        self._control_panel.template_changed.connect(self._on_template_changed)
        self._control_panel.manage_templates_requested.connect(self.settings_requested.emit)
        self._control_panel.sign_requested.connect(self.start_signing)
        self._control_panel.cancel_requested.connect(self._cancel_signing)
        layout.addWidget(self._control_panel)

        self._right_panel = panel
        return panel

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self.refresh_cert_status()

    def toggle_panel(self) -> None:
        if self._panel_collapsed:
            sizes = self._splitter.sizes()
            total = sum(sizes) or 1000
            self._splitter.setSizes([total - self._last_panel_width, self._last_panel_width])
            new_text = "Hide Panel >>"
        else:
            sizes = self._splitter.sizes()
            if len(sizes) == 2 and sizes[1] > 0:
                self._last_panel_width = sizes[1]
            total = sum(sizes) or 1000
            self._splitter.setSizes([total, 0])
            new_text = "<< Show Panel"
        self._panel_collapsed = not self._panel_collapsed
        self.panel_toggled.emit(new_text)

    # ------------------------------------------------------ viewer pass-through
    # RibbonBar drives navigation/zoom through these rather than reaching
    # into self._viewer directly, so this class stays the only thing that
    # knows the viewer widget exists.
    def prev_page(self) -> None:
        self._viewer.prev_page()

    def next_page(self) -> None:
        self._viewer.next_page()

    def zoom_in(self) -> None:
        self._viewer.zoom_in()

    def zoom_out(self) -> None:
        self._viewer.zoom_out()

    def set_canvas_backdrop_color(self, color) -> None:
        self._viewer.set_backdrop_color(color)

    def fit_width(self) -> None:
        self._viewer.fit_width()

    def fit_page(self) -> None:
        self._viewer.fit_page()

    def reset_zoom(self) -> None:
        self._viewer.set_zoom(1.0)

    def _on_viewer_state_changed(self) -> None:
        self._sync_preview_overlay()
        if not self._current_file:
            status = ViewerStatus("No file", False, False, None, self._viewer.zoom_label())
        else:
            page = self._viewer.current_page()
            count = self._viewer.page_count()
            status = ViewerStatus(
                page_label=f"Page {page + 1}/{count}",
                has_prev=page > 0,
                has_next=page < count - 1,
                signed=page in self._current_signed_pages,
                zoom_label=self._viewer.zoom_label(),
            )
        self.viewer_status_changed.emit(status)

    # -------------------------------------------------------------- files
    def open_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Open PDF files", "", "PDF (*.pdf)")
        self._file_panel.add_files(Path(p) for p in paths)

    def open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open folder")
        if folder:
            self._file_panel.add_files(sorted(Path(folder).glob("*.pdf")))

    def _refresh_file_list(self) -> None:
        template = self._current_template()
        warnings = {}
        if template:
            warnings = {
                r.file_path: r.warning
                for r in BatchSignService(self._pdf_inspect).precheck(self._file_panel.files, template)
                if r.warning
            }
        self._file_panel.refresh(warnings)
        if self._current_file is not None and self._current_file not in self._file_panel.files:
            self._current_file = None
            self._current_pdf_info = None
            self._current_signed_pages = set()
            self._viewer.clear()
            self._on_viewer_state_changed()

    # ----------------------------------------------------------- preview
    def _on_file_selection_changed(self, path: Path | None) -> None:
        if path is None or path == self._current_file:
            return
        self._load_preview(path)

    def _load_preview(self, path: Path) -> None:
        try:
            info = self._pdf_inspect.get_info(path)
        except PdfInspectError as exc:
            QMessageBox.warning(self, "Could not preview file", str(exc))
            return
        self._current_file = path
        self._current_pdf_info = info
        self._current_signed_pages = get_signed_pages(path)
        self._viewer.load(str(path), info.page_sizes)
        self._on_viewer_state_changed()

    def _sync_preview_overlay(self) -> None:
        template = self._current_template()
        pixel_boxes: dict[str, object] = {}
        labels: dict[str, str] = {}
        if template and self._current_pdf_info:
            page_index = self._viewer.current_page()
            dpi = self._viewer.dpi()
            for box in template.signature_boxes:
                indices = box.page_ref.resolve_indices(self._current_pdf_info.page_count)
                if page_index not in indices:
                    continue
                rect = box.rect
                actual_size = self._current_pdf_info.page_size(page_index)
                if actual_size.differs_from(box.page_size_at_design_time):
                    rect = rect.scaled_to(box.page_size_at_design_time, actual_size)
                pixel_boxes[box.box_id] = pdf_rect_to_pixel(rect, actual_size, dpi)
                labels[box.box_id] = box.label
        self._viewer.set_boxes(pixel_boxes, labels)

    # -------------------------------------------------------------- template
    def reload_templates(self) -> None:
        templates = [(t.template_id, t.template_name) for t in self._templates.list_templates()]
        settings = self._settings_service.load()
        self._control_panel.set_templates(templates, settings.last_template_id)

    def _current_template(self):
        template_id = self._control_panel.current_template_id()
        if not template_id:
            return None
        return self._templates.load(template_id)

    def _on_template_changed(self, template_id: str) -> None:
        if template_id:
            settings = self._settings_service.load()
            settings.last_template_id = template_id
            self._settings_service.save(settings)
        self._refresh_file_list()
        self._sync_preview_overlay()

    # ------------------------------------------------------------ cert status
    def refresh_cert_status(self) -> None:
        settings = self._settings_service.load()
        if settings.last_pfx_path:
            name = Path(settings.last_pfx_path).name
            signer = settings.signer_name or "(no name set)"
            self._control_panel.set_cert_status(f"Certificate: {name}\nSigner: {signer}")
        else:
            self._control_panel.set_cert_status(
                "No certificate configured yet - go to the Settings tab first."
            )

    # ------------------------------------------------------------------- run
    def is_batch_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def set_session_password(self, password: str) -> None:
        """Pre-fill the certificate password for this session (e.g. from
        MainWindow's once-per-launch prompt) so start_signing() doesn't ask
        again for the first sign of the session."""
        self._session_password = password

    def start_signing(self) -> None:
        template = self._current_template()
        if not template:
            QMessageBox.warning(self, "No template selected", "Please choose a template.")
            return

        files_to_sign = self._files_for_scope()
        if not files_to_sign:
            QMessageBox.warning(self, "No files", "Add PDF files and select a scope.")
            return

        settings = self._settings_service.load()
        if not settings.last_pfx_path:
            QMessageBox.warning(
                self, "No certificate", "Configure a certificate in the Settings tab first."
            )
            return

        password = self._session_password or self._settings_service.get_remembered_password(settings)
        if not password:
            password, ok = QInputDialog.getText(
                self, "Certificate password", "Enter the certificate password:", QLineEdit.EchoMode.Password
            )
            if not ok or not password:
                return

        try:
            cert_provider = Pkcs12CertificateProvider(Path(settings.last_pfx_path), password)
        except CertificateLoadError as exc:
            QMessageBox.critical(self, "Certificate error", str(exc))
            return
        self._session_password = password

        info = cert_provider.get_info()
        if info.is_expired:
            QMessageBox.critical(
                self, "Certificate expired", f"This certificate expired on {info.not_valid_after}."
            )
            return

        engine = SigningEngine(cert_provider, signer_display_name=settings.signer_name or "")
        service = BatchSignService(self._pdf_inspect, engine)
        output_dir = self._settings_service.resolve_output_dir(settings, files_to_sign[0])

        self._worker = BatchSignWorker(service, files_to_sign, template, output_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_all.connect(self._on_finished)
        self._control_panel.start_progress(len(files_to_sign))
        self._set_running(True)
        self._worker.start()

    def _files_for_scope(self) -> list[Path]:
        if self._control_panel.is_current_file_only():
            return [self._current_file] if self._current_file else []
        return self._file_panel.files

    def _cancel_signing(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()
            self._control_panel.disable_cancel()

    def _set_running(self, running: bool) -> None:
        self._control_panel.set_running(running)
        self.sign_running_changed.emit(running)

    def _on_progress(self, done: int, total: int, result) -> None:
        self._control_panel.set_progress_value(done)
        self._file_panel.set_status(result.file_path, "success" if result.is_success else (result.error_reason or "error"))
        self._results[result.file_path] = result
        self._refresh_file_list()

    def _on_finished(self, results: list) -> None:
        self._set_running(False)
        ok = sum(1 for r in results if r.is_success)
        failed = len(results) - ok
        self._control_panel.set_summary(f"Done: {ok} succeeded, {failed} failed / {len(results)} file(s).")
        if self._worker is not None:
            self._worker.wait()
            # deleteLater(), not dropping the reference outright: this slot
            # is itself running inside the worker's finished_all emission,
            # so destroying the QThread synchronously here would cancel any
            # other pending queued deliveries of that same signal.
            self._worker.deleteLater()
            self._worker = None

    # ---------------------------------------------------------------- output
    def _open_output_for(self, path: Path) -> None:
        result = self._results.get(path)
        target = result.output_path if result and result.is_success else path
        if target and Path(target).exists():
            self._open_in_os(Path(target))

    @staticmethod
    def _open_in_os(path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606 (opens the PDF with the OS default app)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def export_report(self) -> None:
        if not self._results:
            QMessageBox.information(self, "No results yet", "Run a signing batch before exporting a report.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export report", "signing_report.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["file_name", "file_path", "status", "error_reason", "signed_output_path", "signed_at"]
            )
            for file_path, result in self._results.items():
                writer.writerow(
                    [
                        file_path.name,
                        str(file_path),
                        result.status,
                        result.error_reason or "",
                        str(result.output_path) if result.output_path else "",
                        result.signed_at or "",
                    ]
                )
        QMessageBox.information(self, "Exported", f"Report exported to {path}")
