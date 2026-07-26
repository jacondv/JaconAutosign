"""Flat monochrome icons for the ribbon toolbar, drawn with QPainter so the
app ships with zero external icon assets (keeps the PyInstaller build small
and the startup-time budget untouched). Every icon takes the current theme's
text color as its stroke, so they stay legible on both the light and dark
skins - see RibbonBar.set_theme(), which regenerates them on a theme switch.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF

_DEFAULT_STROKE = "#4a4a4a"


def _icon(draw, size: int, color: str) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    stroke = QColor(color)
    pen = QPen(stroke)
    pen.setWidthF(size * 0.07)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    draw(painter, size, stroke)
    painter.end()
    return QIcon(pixmap)


def open_files_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        back = QRectF(s * 0.30, s * 0.12, s * 0.48, s * 0.62)
        p.drawRect(back)
        front = QRectF(s * 0.16, s * 0.28, s * 0.48, s * 0.62)
        p.setBrush(QColor("#ffffff"))
        p.drawRect(front)
        for i in range(3):
            y = front.top() + s * 0.18 + i * s * 0.13
            p.drawLine(QPointF(front.left() + s * 0.08, y), QPointF(front.right() - s * 0.08, y))

    return _icon(draw, size, color)


def open_folder_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawLine(QPointF(s * 0.14, s * 0.30), QPointF(s * 0.14, s * 0.22))
        p.drawLine(QPointF(s * 0.14, s * 0.22), QPointF(s * 0.38, s * 0.22))
        p.drawLine(QPointF(s * 0.38, s * 0.22), QPointF(s * 0.44, s * 0.30))
        p.drawLine(QPointF(s * 0.44, s * 0.30), QPointF(s * 0.86, s * 0.30))
        body = QPolygonF(
            [
                QPointF(s * 0.10, s * 0.30),
                QPointF(s * 0.86, s * 0.30),
                QPointF(s * 0.78, s * 0.82),
                QPointF(s * 0.18, s * 0.82),
            ]
        )
        p.drawPolygon(body)

    return _icon(draw, size, color)


def prev_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawPolyline(
            QPolygonF([QPointF(s * 0.62, s * 0.20), QPointF(s * 0.32, s * 0.5), QPointF(s * 0.62, s * 0.80)])
        )

    return _icon(draw, size, color)


def next_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawPolyline(
            QPolygonF([QPointF(s * 0.38, s * 0.20), QPointF(s * 0.68, s * 0.5), QPointF(s * 0.38, s * 0.80)])
        )

    return _icon(draw, size, color)


def _magnifier(p: QPainter, s: int) -> QPointF:
    center = QPointF(s * 0.42, s * 0.42)
    radius = s * 0.26
    p.drawEllipse(center, radius, radius)
    handle_start = center + QPointF(radius * 0.75, radius * 0.75)
    p.drawLine(handle_start, QPointF(s * 0.86, s * 0.86))
    return center


def zoom_in_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        c = _magnifier(p, s)
        r = s * 0.12
        p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))

    return _icon(draw, size, color)


def zoom_out_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        c = _magnifier(p, s)
        r = s * 0.12
        p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))

    return _icon(draw, size, color)


def fit_width_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawRect(QRectF(s * 0.30, s * 0.14, s * 0.40, s * 0.72))
        y = s * 0.5
        p.drawLine(QPointF(s * 0.06, y), QPointF(s * 0.26, y))
        p.drawLine(QPointF(s * 0.74, y), QPointF(s * 0.94, y))
        p.drawPolyline(QPolygonF([QPointF(s * 0.14, s * 0.42), QPointF(s * 0.06, y), QPointF(s * 0.14, s * 0.58)]))
        p.drawPolyline(QPolygonF([QPointF(s * 0.86, s * 0.42), QPointF(s * 0.94, y), QPointF(s * 0.86, s * 0.58)]))

    return _icon(draw, size, color)


def fit_page_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawRect(QRectF(s * 0.30, s * 0.18, s * 0.40, s * 0.64))
        arm = s * 0.16
        corners = [(s * 0.08, s * 0.08, 1, 1), (s * 0.92, s * 0.08, -1, 1), (s * 0.08, s * 0.92, 1, -1), (s * 0.92, s * 0.92, -1, -1)]
        for x, y, dx, dy in corners:
            p.drawLine(QPointF(x, y), QPointF(x + arm * dx, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + arm * dy))

    return _icon(draw, size, color)


def reset_zoom_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawRect(QRectF(s * 0.10, s * 0.10, s * 0.80, s * 0.80))
        font = QFont()
        font.setPixelSize(round(s * 0.30))
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "1:1")

    return _icon(draw, size, color)


def sign_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    """A fountain pen mid-stroke over a signature flourish."""

    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.save()
        p.translate(s * 0.5, s * 0.40)
        p.rotate(-40)
        body = QRectF(-s * 0.34, -s * 0.065, s * 0.60, s * 0.13)
        p.drawRoundedRect(body, s * 0.05, s * 0.05)
        nib = QPolygonF(
            [
                QPointF(-s * 0.34, -s * 0.065),
                QPointF(-s * 0.34, s * 0.065),
                QPointF(-s * 0.48, 0),
            ]
        )
        p.setBrush(stroke)
        p.drawPolygon(nib)
        p.restore()

        p.drawPolyline(
            QPolygonF(
                [
                    QPointF(s * 0.12, s * 0.82),
                    QPointF(s * 0.30, s * 0.70),
                    QPointF(s * 0.44, s * 0.86),
                    QPointF(s * 0.62, s * 0.72),
                    QPointF(s * 0.82, s * 0.84),
                ]
            )
        )

    return _icon(draw, size, color)


def export_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawLine(QPointF(s * 0.5, s * 0.10), QPointF(s * 0.5, s * 0.56))
        p.drawPolyline(
            QPolygonF([QPointF(s * 0.34, s * 0.42), QPointF(s * 0.5, s * 0.58), QPointF(s * 0.66, s * 0.42)])
        )
        p.drawPolyline(
            QPolygonF(
                [
                    QPointF(s * 0.16, s * 0.68),
                    QPointF(s * 0.16, s * 0.88),
                    QPointF(s * 0.84, s * 0.88),
                    QPointF(s * 0.84, s * 0.68),
                ]
            )
        )

    return _icon(draw, size, color)


def wheel_page_turn_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    """A mouse body with a scroll wheel, flanked by up/down chevrons - wheel
    past the page edge to turn the page."""

    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        body = QRectF(s * 0.36, s * 0.10, s * 0.28, s * 0.50)
        p.drawRoundedRect(body, s * 0.12, s * 0.12)
        p.drawLine(QPointF(s * 0.5, s * 0.18), QPointF(s * 0.5, s * 0.30))
        p.drawPolyline(
            QPolygonF([QPointF(s * 0.06, s * 0.20), QPointF(s * 0.14, s * 0.10), QPointF(s * 0.22, s * 0.20)])
        )
        p.drawPolyline(
            QPolygonF([QPointF(s * 0.06, s * 0.72), QPointF(s * 0.14, s * 0.82), QPointF(s * 0.22, s * 0.72)])
        )
        p.drawPolyline(
            QPolygonF([QPointF(s * 0.78, s * 0.20), QPointF(s * 0.86, s * 0.10), QPointF(s * 0.94, s * 0.20)])
        )
        p.drawPolyline(
            QPolygonF([QPointF(s * 0.78, s * 0.72), QPointF(s * 0.86, s * 0.82), QPointF(s * 0.94, s * 0.72)])
        )

    return _icon(draw, size, color)


def panel_icon(size: int = 28, color: str = _DEFAULT_STROKE) -> QIcon:
    def draw(p: QPainter, s: int, stroke: QColor) -> None:
        p.drawRect(QRectF(s * 0.10, s * 0.16, s * 0.80, s * 0.68))
        x = s * 0.62
        p.drawLine(QPointF(x, s * 0.16), QPointF(x, s * 0.84))
        p.setBrush(stroke)
        p.drawPolygon(
            QPolygonF([QPointF(x + s * 0.06, s * 0.42), QPointF(x + s * 0.06, s * 0.58), QPointF(x + s * 0.18, s * 0.5)])
        )

    return _icon(draw, size, color)
