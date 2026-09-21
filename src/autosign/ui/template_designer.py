"""Template designer screen: open a sample PDF, draw signature boxes on its
pages, save as a reusable JSON template for batch signing (F2.x).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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

from ..models import SignatureBox, Template, TitleBlockField
from ..services import PdfInfo, PdfInspectService, TemplateService
from ..services.pdf_inspect_service import PdfInspectError
from .box_edit_dialog import BoxEditDialog
from .coordinates import pdf_rect_to_pixel as _pdf_rect_to_pixel
from .coordinates import pixel_rect_to_pdf as _pixel_rect_to_pdf
from .pdf_render import DEFAULT_PREVIEW_DPI, render_page_to_qimage
from .title_block_field_dialog import TitleBlockFieldDialog
from .widgets import PageCanvas

_TITLE_FIELD_PREFIX = "tb-"


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
        self._title_fields: dict[str, TitleBlockField] = {}
        self._title_field_order: list[str] = []

        self._template_id = existing_template.template_id if existing_template else ""
        self._created_at = existing_template.created_at if existing_template else ""
        if existing_template:
            for box in existing_template.signature_boxes:
                self._boxes[box.box_id] = box
                self._box_order.append(box.box_id)
            for tb_field in existing_template.title_block_fields:
                self._title_fields[tb_field.field_id] = tb_field
                self._title_field_order.append(tb_field.field_id)

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

        self._draw_mode_combo = QComboBox()
        self._draw_mode_combo.addItem("Draw: Signature box", "signature")
        self._draw_mode_combo.addItem("Draw: Title block field", "title_block")

        page_nav = QHBoxLayout()
        page_nav.addWidget(self._prev_btn)
        page_nav.addWidget(self._page_label)
        page_nav.addWidget(self._next_btn)
        page_nav.addStretch(1)
        page_nav.addWidget(self._draw_mode_combo)

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

        self._title_field_list = QListWidget()
        self._title_field_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._title_field_list.currentItemChanged.connect(self._on_title_field_list_selection_changed)

        edit_title_field_btn = QPushButton("Edit field")
        edit_title_field_btn.clicked.connect(self._edit_selected_title_field)
        delete_title_field_btn = QPushButton("Delete field")
        delete_title_field_btn.clicked.connect(self._delete_selected_title_field)

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Signature boxes:"))
        right_panel.addWidget(self._box_list, 1)
        right_panel.addWidget(edit_box_btn)
        right_panel.addWidget(delete_box_btn)
        right_panel.addWidget(
            QLabel("Tip: drag on the page to draw a new box.\nDrag the corner handle to resize.")
        )
        right_panel.addWidget(QLabel("Title block fields (optional):"))
        right_panel.addWidget(self._title_field_list, 1)
        right_panel.addWidget(edit_title_field_btn)
        right_panel.addWidget(delete_title_field_btn)

        body = QHBoxLayout()
        body.addLayout(left_panel, 3)
        body.addLayout(right_panel, 1)

        root = QVBoxLayout(self)
        root.addLayout(top_bar)
        root.addLayout(body, 1)

        self._refresh_box_list()
        self._refresh_title_field_list()

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
        image = render_page_to_qimage(
            str(self._pdf_path), self._current_page, device_pixel_ratio=self.devicePixelRatioF() or 1.0
        )
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

    def _title_fields_on_current_page(self) -> list[TitleBlockField]:
        if not self._pdf_info:
            return []
        return [
            tb_field
            for tb_field in self._title_fields.values()
            if tb_field.page_ref.resolve_index(self._pdf_info.page_count) == self._current_page
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
        for tb_field in self._title_fields_on_current_page():
            pixel_boxes[tb_field.field_id] = _pdf_rect_to_pixel(
                tb_field.rect, page_size, DEFAULT_PREVIEW_DPI
            )
            labels[tb_field.field_id] = tb_field.field_type.value
        self._canvas.set_boxes(pixel_boxes, labels)

    def _on_box_created(self, pixel_rect: QRectF) -> None:
        if not self._pdf_info:
            return
        page_size = self._pdf_info.page_size(self._current_page)
        rect = _pixel_rect_to_pdf(pixel_rect, page_size, DEFAULT_PREVIEW_DPI)
        if self._draw_mode_combo.currentData() == "title_block":
            self._create_title_field(rect, page_size)
            return

        dialog = BoxEditDialog(
            page_count=self._pdf_info.page_count,
            current_page_number=self._current_page + 1,
            box_width_pt=rect.width,
            box_height_pt=rect.height,
            parent=self,
        )
        if dialog.exec() != BoxEditDialog.DialogCode.Accepted:
            return

        box_id = f"box-{uuid.uuid4().hex[:8]}"
        box = SignatureBox(
            box_id=box_id,
            label=dialog.result_label(),
            page_ref=dialog.result_page_ref(),
            rect=rect,
            page_size_at_design_time=page_size,
            appearance=dialog.result_appearance(),
        )
        self._boxes[box_id] = box
        self._box_order.append(box_id)
        self._refresh_box_list()
        self._sync_canvas_boxes()
        self._canvas.select_box(box_id)

    def _create_title_field(self, rect, page_size) -> None:
        dialog = TitleBlockFieldDialog(current_page_number=self._current_page + 1, parent=self)
        if dialog.exec() != TitleBlockFieldDialog.DialogCode.Accepted:
            return
        field_id = f"{_TITLE_FIELD_PREFIX}{uuid.uuid4().hex[:8]}"
        tb_field = TitleBlockField(
            field_id=field_id,
            field_type=dialog.result_field_type(),
            page_ref=dialog.result_page_ref(),
            rect=rect,
            page_size_at_design_time=page_size,
        )
        self._title_fields[field_id] = tb_field
        self._title_field_order.append(field_id)
        self._refresh_title_field_list()
        self._sync_canvas_boxes()
        self._canvas.select_box(field_id)

    def _on_box_changed(self, box_id: str, pixel_rect: QRectF) -> None:
        if not self._pdf_info:
            return
        page_size = self._pdf_info.page_size(self._current_page)
        rect = _pixel_rect_to_pdf(pixel_rect, page_size, DEFAULT_PREVIEW_DPI)
        if box_id in self._boxes:
            self._boxes[box_id].rect = rect
        elif box_id in self._title_fields:
            self._title_fields[box_id].rect = rect

    def _on_canvas_box_selected(self, box_id: str) -> None:
        # Deselecting the *other* list is purely cosmetic bookkeeping here -
        # block its signal so that clear doesn't bounce back through
        # _on_title_field_list_selection_changed and immediately clear the
        # canvas selection this method is trying to set.
        if box_id in self._boxes:
            self._blocked_set_current(self._title_field_list, None)
            for i in range(self._box_list.count()):
                item = self._box_list.item(i)
                if item.data(1000) == box_id:
                    self._box_list.setCurrentItem(item)
                    return
        elif box_id in self._title_fields:
            self._blocked_set_current(self._box_list, None)
            for i in range(self._title_field_list.count()):
                item = self._title_field_list.item(i)
                if item.data(1000) == box_id:
                    self._title_field_list.setCurrentItem(item)
                    return
        if not box_id:
            self._blocked_set_current(self._box_list, None)
            self._blocked_set_current(self._title_field_list, None)

    @staticmethod
    def _blocked_set_current(list_widget: QListWidget, item: QListWidgetItem | None) -> None:
        list_widget.blockSignals(True)
        list_widget.setCurrentItem(item)
        list_widget.blockSignals(False)

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
            box_width_pt=box.rect.width,
            box_height_pt=box.rect.height,
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

    # ------------------------------------------------------ title block list
    def _refresh_title_field_list(self) -> None:
        self._title_field_list.clear()
        for field_id in self._title_field_order:
            tb_field = self._title_fields[field_id]
            item = QListWidgetItem(tb_field.field_type.value.replace("_", " ").title())
            item.setData(1000, field_id)
            self._title_field_list.addItem(item)

    def _on_title_field_list_selection_changed(self) -> None:
        item = self._title_field_list.currentItem()
        field_id = item.data(1000) if item else None
        self._canvas.select_box(field_id)

    def _edit_selected_title_field(self) -> None:
        item = self._title_field_list.currentItem()
        if not item or not self._pdf_info:
            return
        field_id = item.data(1000)
        tb_field = self._title_fields[field_id]
        dialog = TitleBlockFieldDialog(
            current_page_number=self._current_page + 1,
            field_type=tb_field.field_type,
            page_ref=tb_field.page_ref,
            parent=self,
        )
        if dialog.exec() != TitleBlockFieldDialog.DialogCode.Accepted:
            return
        tb_field.field_type = dialog.result_field_type()
        tb_field.page_ref = dialog.result_page_ref()
        self._refresh_title_field_list()
        self._sync_canvas_boxes()

    def _delete_selected_title_field(self) -> None:
        item = self._title_field_list.currentItem()
        if not item:
            return
        field_id = item.data(1000)
        del self._title_fields[field_id]
        self._title_field_order.remove(field_id)
        self._refresh_title_field_list()
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
            title_block_fields=[self._title_fields[fid] for fid in self._title_field_order],
        )
        saved = self._templates.save(template)
        self._template_id = saved.template_id
        self._created_at = saved.created_at
        QMessageBox.information(self, "Saved", f"Template '{name}' saved.")
        self.saved.emit()
