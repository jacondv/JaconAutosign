"""Template designer screen: open a sample PDF, draw signature boxes on its
pages, save as a reusable JSON template for batch signing (F2.x).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import SignatureBox, Template
from ..services import PdfInfo, PdfInspectService, TemplateService
from ..services.pdf_inspect_service import PdfInspectError
from .box_edit_dialog import BoxEditDialog
from .coordinates import pdf_rect_to_pixel as _pdf_rect_to_pixel
from .coordinates import pixel_rect_to_pdf as _pixel_rect_to_pdf
from .pdf_render import DEFAULT_PREVIEW_DPI, render_page_to_qimage
from .widgets import PageCanvas


class TemplateDesignerScreen(QWidget):
    back_requested = Signal()
    saved = Signal()

    def __init__(
        self,
        template_service: TemplateService,
        pdf_inspect_service: PdfInspectService,
        existing_template: Template | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._templates = template_service
        self._pdf_inspect = pdf_inspect_service

        self._pdf_path: Path | None = None
        self._pdf_info: PdfInfo | None = None
        self._current_page = 0
        self._boxes: dict[str, SignatureBox] = {}
        self._box_order: list[str] = []

        self._template_id = existing_template.template_id if existing_template else ""
        self._created_at = existing_template.created_at if existing_template else ""
        if existing_template:
            for box in existing_template.signature_boxes:
                self._boxes[box.box_id] = box
                self._box_order.append(box.box_id)

        self._build_ui(existing_template)

        if existing_template and existing_template.source_sample_file:
            sample = Path(existing_template.source_sample_file)
            if sample.exists():
                self._load_pdf(sample)

    # ------------------------------------------------------------------- UI
    def _build_ui(self, existing_template: Template | None) -> None:
        back_btn = QPushButton("<- Back")
        back_btn.clicked.connect(self.back_requested.emit)

        self._name_edit = QLineEdit(existing_template.template_name if existing_template else "")
        self._name_edit.setPlaceholderText("Template name (e.g. Employment contract)")

        open_btn = QPushButton("Choose sample PDF...")
        open_btn.clicked.connect(self._choose_pdf)

        save_btn = QPushButton("Save template")
        save_btn.clicked.connect(self._save_template)

        top_bar = QHBoxLayout()
        top_bar.addWidget(back_btn)
        top_bar.addWidget(QLabel("Name:"))
        top_bar.addWidget(self._name_edit, 1)
        top_bar.addWidget(open_btn)
        top_bar.addWidget(save_btn)

        self._prev_btn = QPushButton("< Previous page")
        self._prev_btn.clicked.connect(self._go_prev_page)
        self._next_btn = QPushButton("Next page >")
        self._next_btn.clicked.connect(self._go_next_page)
        self._page_label = QLabel("No PDF loaded")

        page_nav = QHBoxLayout()
        page_nav.addWidget(self._prev_btn)
        page_nav.addWidget(self._page_label)
        page_nav.addWidget(self._next_btn)
        page_nav.addStretch(1)

        self._canvas = PageCanvas()
        self._canvas.box_created.connect(self._on_box_created)
        self._canvas.box_changed.connect(self._on_box_changed)
        self._canvas.box_selected.connect(self._on_canvas_box_selected)

        scroll = QScrollArea()
        scroll.setWidget(self._canvas)
        scroll.setWidgetResizable(False)

        left_panel = QVBoxLayout()
        left_panel.addLayout(page_nav)
        left_panel.addWidget(scroll, 1)

        self._box_list = QListWidget()
        self._box_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._box_list.currentItemChanged.connect(self._on_list_selection_changed)

        edit_box_btn = QPushButton("Edit box")
        edit_box_btn.clicked.connect(self._edit_selected_box)
        delete_box_btn = QPushButton("Delete box")
        delete_box_btn.clicked.connect(self._delete_selected_box)

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Signature boxes:"))
        right_panel.addWidget(self._box_list, 1)
        right_panel.addWidget(edit_box_btn)
        right_panel.addWidget(delete_box_btn)
        right_panel.addWidget(
            QLabel("Tip: drag on the page to draw a new box.\nDrag the corner handle to resize.")
        )

        body = QHBoxLayout()
        body.addLayout(left_panel, 3)
        body.addLayout(right_panel, 1)

        root = QVBoxLayout(self)
        root.addLayout(top_bar)
        root.addLayout(body, 1)

        self._refresh_box_list()

    # -------------------------------------------------------------- PDF load
    def _choose_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose sample PDF", "", "PDF (*.pdf)")
        if path:
            self._load_pdf(Path(path))

    def _load_pdf(self, path: Path) -> None:
        try:
            info = self._pdf_inspect.get_info(path)
        except PdfInspectError as exc:
            QMessageBox.critical(self, "Error reading PDF", str(exc))
            return
        self._pdf_path = path
        self._pdf_info = info
        self._current_page = 0
        self._render_current_page()

    def _render_current_page(self) -> None:
        if not self._pdf_info:
            return
        image = render_page_to_qimage(str(self._pdf_path), self._current_page)
        self._canvas.set_page_image(image)
        self._page_label.setText(f"Page {self._current_page + 1}/{self._pdf_info.page_count}")
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < self._pdf_info.page_count - 1)
        self._sync_canvas_boxes()

    def _go_prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._render_current_page()

    def _go_next_page(self) -> None:
        if self._pdf_info and self._current_page < self._pdf_info.page_count - 1:
            self._current_page += 1
            self._render_current_page()

    # ------------------------------------------------------------- box sync
    def _boxes_on_current_page(self) -> list[SignatureBox]:
        if not self._pdf_info:
            return []
        return [
            box
            for box in self._boxes.values()
            if self._current_page in box.page_ref.resolve_indices(self._pdf_info.page_count)
        ]

    def _sync_canvas_boxes(self) -> None:
        if not self._pdf_info:
            return
        page_size = self._pdf_info.page_size(self._current_page)
        pixel_boxes = {}
        labels = {}
        for box in self._boxes_on_current_page():
            pixel_boxes[box.box_id] = _pdf_rect_to_pixel(box.rect, page_size, DEFAULT_PREVIEW_DPI)
            labels[box.box_id] = box.label
        self._canvas.set_boxes(pixel_boxes, labels)

    def _on_box_created(self, pixel_rect: QRectF) -> None:
        if not self._pdf_info:
            return
        page_size = self._pdf_info.page_size(self._current_page)
        dialog = BoxEditDialog(
            page_count=self._pdf_info.page_count,
            current_page_number=self._current_page + 1,
            parent=self,
        )
        if dialog.exec() != BoxEditDialog.DialogCode.Accepted:
            return

        box_id = f"box-{uuid.uuid4().hex[:8]}"
        box = SignatureBox(
            box_id=box_id,
            label=dialog.result_label(),
            page_ref=dialog.result_page_ref(),
            rect=_pixel_rect_to_pdf(pixel_rect, page_size, DEFAULT_PREVIEW_DPI),
            page_size_at_design_time=page_size,
            appearance=dialog.result_appearance(),
        )
        self._boxes[box_id] = box
        self._box_order.append(box_id)
        self._refresh_box_list()
        self._sync_canvas_boxes()
        self._canvas.select_box(box_id)

    def _on_box_changed(self, box_id: str, pixel_rect: QRectF) -> None:
        if not self._pdf_info or box_id not in self._boxes:
            return
        page_size = self._pdf_info.page_size(self._current_page)
        box = self._boxes[box_id]
        box.rect = _pixel_rect_to_pdf(pixel_rect, page_size, DEFAULT_PREVIEW_DPI)

    def _on_canvas_box_selected(self, box_id: str) -> None:
        for i in range(self._box_list.count()):
            item = self._box_list.item(i)
            if item.data(1000) == box_id:
                self._box_list.setCurrentItem(item)
                return
        if not box_id:
            self._box_list.setCurrentItem(None)

    # ------------------------------------------------------------ box list
    def _refresh_box_list(self) -> None:
        self._box_list.clear()
        for box_id in self._box_order:
            box = self._boxes[box_id]
            item = QListWidgetItem(box.label)
            item.setData(1000, box_id)
            self._box_list.addItem(item)

    def _on_list_selection_changed(self) -> None:
        item = self._box_list.currentItem()
        box_id = item.data(1000) if item else None
        self._canvas.select_box(box_id)

    def _edit_selected_box(self) -> None:
        item = self._box_list.currentItem()
        if not item or not self._pdf_info:
            return
        box_id = item.data(1000)
        box = self._boxes[box_id]
        dialog = BoxEditDialog(
            page_count=self._pdf_info.page_count,
            current_page_number=self._current_page + 1,
            label=box.label,
            appearance=box.appearance,
            parent=self,
        )
        if dialog.exec() != BoxEditDialog.DialogCode.Accepted:
            return
        box.label = dialog.result_label()
        box.page_ref = dialog.result_page_ref()
        box.appearance = dialog.result_appearance()
        self._refresh_box_list()
        self._sync_canvas_boxes()

    def _delete_selected_box(self) -> None:
        item = self._box_list.currentItem()
        if not item:
            return
        box_id = item.data(1000)
        del self._boxes[box_id]
        self._box_order.remove(box_id)
        self._refresh_box_list()
        self._sync_canvas_boxes()

    # ----------------------------------------------------------------- save
    def _save_template(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Please enter a template name.")
            return
        if not self._boxes:
            QMessageBox.warning(
                self, "No signature box", "Draw at least one signature box before saving."
            )
            return

        template = Template(
            template_id=self._template_id,
            template_name=name,
            created_at=self._created_at,
            source_sample_file=str(self._pdf_path) if self._pdf_path else None,
            signature_boxes=[self._boxes[bid] for bid in self._box_order],
        )
        saved = self._templates.save(template)
        self._template_id = saved.template_id
        self._created_at = saved.created_at
        QMessageBox.information(self, "Saved", f"Template '{name}' saved.")
        self.saved.emit()
