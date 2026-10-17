from __future__ import annotations

import math

from PySide6.QtCore import QLineF, QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFontInfo, QFontMetrics, QIcon, QImage, QPainter, QPainterPath, QPen, QPolygon, QPolygonF, QPixmap


INK = QColor("#202124")
DARK_INK = QColor("#e8eaed")
CAMERA_INK = QColor("#5c6269")
# Icons use a 32 px drawing grid; 1.6 becomes a 1 px stroke at toolbar size.
TOOL_STROKE_WIDTH = 1.6
# Most artwork fits 16 px inside the 20 px icon canvas. Dense glyphs use 20 px.
_COMPLEX_TOOL_ICONS = {"keyboard", "save_as"}
BLUE = QColor("#1971c2")
GREEN = QColor("#2f9e44")
RED = QColor("#e03131")

# Bounds of the artwork's geometry on its drawing grid, excluding empty canvas.
_TOOL_BOUNDS = {
    "screen_mode": (5, 5, 22, 21),
    "pen": (6, 7, 19, 19),
    "line": (7, 8, 18, 16),
    "arrow": (7, 8, 17, 17),
    "rectangle": (7, 8, 18, 16),
    "measure": (6, 5, 21, 21),
    "text": (8, 8, 16, 17),
    "mosaic": (7, 8, 19, 19),
    "style": (7, 11, 20, 16),
    "undo": (6, 8, 20, 17),
    "rotate_clockwise": (4, 5, 25, 25),
    "flip_horizontal": (5, 5, 22, 22),
    "flip_vertical": (5, 5, 22, 22),
    "resize_down": (5, 5, 22, 22),
    "copy": (7, 7, 17, 20),
    "save": (7, 6, 18, 20),
    "save_as": (6, 5, 18, 22),
    "zoom_in": (8, 8, 18, 18),
    "zoom_out": (8, 8, 18, 18),
    "cursor": (9, 6, 14, 21),
    "delay": (8, 5, 16, 19),
    "keyboard": (4, 8, 24, 17),
    "theme": (5, 5, 22, 22),
    "language": (5, 5, 22, 22),
}


def _tool_bounds(name, checked, badge, line_start, line_end) -> QRectF:
    bounds = QRectF(*_TOOL_BOUNDS.get(name, (0, 0, 32, 32)))
    if name == "line":
        if line_start == "circle":
            bounds = bounds.united(QRectF(4, 21, 6, 6))
        if line_end == "circle":
            bounds = bounds.united(QRectF(22, 5, 6, 6))
    elif name == "cursor" and checked:
        bounds = bounds.united(QRectF(20, 19, 10, 10))
    elif name == "delay":
        if badge == "off":
            bounds = bounds.united(QRectF(21, 22, 7, 7))
        elif badge:
            bounds = bounds.united(QRectF(19, 19, 12, 12))
    elif name == "theme" and badge == "dark":
        bounds = QRectF(6, 5, 21, 22)
    return bounds


def camera_icon(size: int = 64) -> QIcon:
    icon = QIcon()
    sizes = {candidate for candidate in (16, 20, 24, 32, 48, 64) if candidate <= size}
    sizes.add(size)
    for pixmap_size in sorted(sizes):
        icon.addPixmap(_camera_pixmap(pixmap_size, tray=False))
    return icon


def tray_icon(*, macos: bool = False) -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        icon.addPixmap(_camera_pixmap(size, tray=True, macos=macos))
    return icon


def _camera_pixmap(size: int, tray: bool, macos: bool = False) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = _painter(pixmap)
    scale = size / 64
    painter.setBrush(CAMERA_INK)
    painter.setPen(Qt.PenStyle.NoPen)
    if tray and macos:
        # macOS menu-bar slots are shorter than Windows tray slots. Use a
        # squarer camera that fills the available height instead of scaling
        # the wider Windows artwork down to an undersized glyph.
        body = (2, 14, 60, 48)
        top = (15, 2, 28, 14)
        outer_lens = (18, 23, 28, 28)
        inner_lens = (26, 31, 12, 12)
        radius = 7
    elif tray:
        body = (3, 17, 58, 43)
        top = (17, 9, 24, 10)
        outer_lens = (20, 26, 24, 24)
        inner_lens = (27, 33, 10, 10)
        radius = 7
    else:
        body = (5, 15, 54, 44)
        top = (18, 7, 22, 10)
        outer_lens = (21, 25, 22, 22)
        inner_lens = (27, 31, 10, 10)
        radius = 7
    painter.drawRoundedRect(_rect(*body, scale), radius * scale, radius * scale)
    painter.drawRect(_rect(*top, scale))
    painter.setBrush(QColor("#f8f9fa"))
    painter.drawEllipse(_rect(*outer_lens, scale))
    painter.setBrush(BLUE)
    painter.drawEllipse(_rect(*inner_lens, scale))
    painter.end()
    return pixmap


def tool_icon(
    name: str,
    color: QColor | None = None,
    width: int = 3,
    checked: bool = False,
    badge: str | None = None,
    dark: bool = False,
    line_start: str = "none",
    line_end: str = "none",
) -> QIcon:
    icon = QIcon()
    # Render native pixels for Windows fractional scaling and Retina displays.
    # Keep a separate 32 px representation for documentation and larger views.
    for size, dpr in ((20, 1), (25, 1.25), (30, 1.5), (32, 1),
                      (35, 1.75), (40, 2), (50, 2.5), (60, 3)):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = _ToolbarPainter(pixmap, size / 32,
                                  _tool_bounds(name, checked, badge, line_start, line_end),
                                  artwork_size=round(size * (1 if name in _COMPLEX_TOOL_ICONS else 0.8)),
                                  reserve_stroke=name != "mosaic")
        try:
            _draw_tool_icon(painter, name, color, width, checked, badge, dark, line_start, line_end)
        finally:
            painter.end()
        pixmap.setDevicePixelRatio(dpr)
        icon.addPixmap(pixmap)
    return icon


def _draw_tool_icon(
    painter: QPainter,
    name: str,
    color: QColor | None,
    width: int,
    checked: bool,
    badge: str | None,
    dark: bool,
    line_start: str,
    line_end: str,
) -> None:
    base_ink = DARK_INK if dark else INK
    ink = color or base_ink
    icon_width = TOOL_STROKE_WIDTH if name != "style" else max(1.3, min(5.0, width * 0.45))
    pen = QPen(ink, icon_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "screen_mode":
        if checked:
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setDashPattern([2, 2])
            painter.setPen(pen)
        painter.drawRoundedRect(QRect(5, 5, 22, 16), 2, 2)
        painter.drawLine(16, 21, 16, 26)
        painter.drawLine(10, 26, 22, 26)
    elif name == "pen":
        # The pencil artwork extends farther toward the lower-left than the
        # other toolbar glyphs, so align its visual center with its peers.
        painter.save()
        painter.translate(0, -4)
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(QPolygon([QPoint(8, 24), QPoint(12, 28), QPoint(25, 15), QPoint(21, 11)]))
        painter.drawLine(19, 13, 23, 17)
        painter.drawLine(17, 15, 21, 19)
        painter.drawPolygon(QPolygon([QPoint(8, 24), QPoint(12, 28), QPoint(6, 30)]))
        painter.drawLine(10, 25, 18, 17)
        painter.drawEllipse(12, 23, 2, 2)
        painter.restore()
    elif name == "line":
        start = QPoint(7, 24)
        end = QPoint(25, 8)
        painter.drawLine(start, end)
        _draw_line_end_icon(painter, start, ((9, 17), (15, 23)), line_start, ink)
        _draw_line_end_icon(painter, end, ((23, 15), (17, 9)), line_end, ink)
    elif name == "arrow":
        painter.drawLine(24, 8, 7, 25)
        painter.drawLine(7, 25, 9, 17)
        painter.drawLine(7, 25, 15, 23)
    elif name == "rectangle":
        painter.drawRoundedRect(7, 8, 18, 16, 2, 2)
    elif name == "measure":
        painter.setPen(
            QPen(
                base_ink,
                TOOL_STROKE_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(6, 5),
                    QPoint(12, 5),
                    QPoint(12, 20),
                    QPoint(27, 20),
                    QPoint(27, 26),
                    QPoint(6, 26),
                ]
            )
        )
        for y, length in ((10, 3), (14, 4), (18, 3)):
            painter.drawLine(6, y, 6 + length, y)
        for x, length in ((16, 3), (20, 4), (24, 3)):
            painter.drawLine(x, 26, x, 26 - length)
    elif name == "text":
        painter.drawLine(8, 8, 24, 8)
        painter.drawLine(16, 8, 16, 25)
    elif name == "mosaic":
        painter.setPen(QPen(base_ink, 0.9))
        for y in (8, 15, 22):
            for x in (7, 14, 21):
                painter.fillRect(x, y, 5, 5, QColor("#9aa0a6") if dark and (x + y) % 2 else QColor("#495057") if (x + y) % 2 else QColor("#adb5bd"))
    elif name == "style":
        painter.drawLine(7, 23, 25, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawEllipse(20, 20, 7, 7)
    elif name == "undo":
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPoint(12, 12))
        path.cubicTo(17, 8, 25, 10, 26, 17)
        path.cubicTo(27, 24, 18, 28, 11, 23)
        painter.drawPath(path)
        painter.drawLine(12, 12, 6, 12)
        painter.drawLine(6, 12, 10, 8)
        painter.drawLine(6, 12, 10, 16)
    elif name == "rotate_clockwise":
        painter.setPen(
            QPen(
                base_ink,
                TOOL_STROKE_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        # Put the clockwise arrow at the upper-left and show the picture
        # itself falling toward the right.
        arrow = QPainterPath(QPoint(4, 15))
        arrow.cubicTo(5, 8, 10, 6, 18, 8)
        painter.drawPath(arrow)
        painter.drawLine(18, 8, 14, 5)
        painter.drawLine(18, 8, 14, 11)

        painter.save()
        painter.translate(18, 20)
        painter.rotate(18)
        painter.drawRoundedRect(-8, -7, 16, 14, 1.5, 1.5)
        painter.drawEllipse(-5, -4, 2, 2)
        painter.drawPolyline(
            QPolygon(
                [
                    QPoint(-6, 5),
                    QPoint(-2, 1),
                    QPoint(1, 4),
                    QPoint(4, 1),
                    QPoint(6, 5),
                ]
            )
        )
        painter.restore()
    elif name == "flip_horizontal":
        painter.setPen(
            QPen(
                base_ink,
                TOOL_STROKE_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPolygon(QPolygon([QPoint(5, 26), QPoint(13, 26), QPoint(13, 6)]))
        painter.drawPolygon(QPolygon([QPoint(27, 26), QPoint(19, 26), QPoint(19, 6)]))
        painter.draw_mirror_axis(vertical=True)
    elif name == "flip_vertical":
        painter.setPen(
            QPen(
                base_ink,
                TOOL_STROKE_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPolygon(QPolygon([QPoint(6, 13), QPoint(26, 13), QPoint(6, 5)]))
        painter.drawPolygon(QPolygon([QPoint(6, 19), QPoint(26, 19), QPoint(6, 27)]))
        painter.draw_mirror_axis(vertical=False)
    elif name == "resize_down":
        painter.setPen(QPen(base_ink, 1.25, Qt.PenStyle.DashLine))
        painter.drawRect(5, 5, 22, 22)
        painter.setPen(
            QPen(
                base_ink,
                TOOL_STROKE_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawLine(25, 25, 15, 15)
        painter.drawLine(15, 15, 16, 21)
        painter.drawLine(15, 15, 21, 16)
    elif name == "copy":
        painter.drawRoundedRect(11, 7, 13, 16, 2, 2)
        painter.drawRoundedRect(7, 11, 13, 16, 2, 2)
    elif name == "save":
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(7, 6, 18, 20, 2, 2)
        painter.drawLine(10, 6, 22, 6)
        painter.drawLine(22, 6, 25, 9)
        painter.drawRect(11, 8, 10, 6)
        painter.drawLine(19, 9, 19, 13)
        painter.drawRoundedRect(11, 18, 10, 6, 1, 1)
        painter.drawLine(13, 21, 19, 21)
    elif name == "save_as":
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(9, 5, 15, 17, 2, 2)
        painter.drawLine(12, 5, 21, 5)
        painter.drawLine(21, 5, 24, 8)
        painter.drawRect(13, 7, 7, 4)
        painter.drawRoundedRect(13, 16, 7, 4, 1, 1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#252629") if dark else QColor("#ffffff"))
        painter.drawRoundedRect(5, 9, 17, 19, 3, 3)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(6, 10, 15, 17, 2, 2)
        painter.drawLine(9, 10, 18, 10)
        painter.drawLine(18, 10, 21, 13)
        painter.drawRect(10, 12, 7, 4)
        painter.drawRoundedRect(10, 21, 7, 4, 1, 1)
    elif name == "zoom_in":
        _draw_magnifier(painter)
        painter.drawLine(15, 11, 15, 19)
        painter.drawLine(11, 15, 19, 15)
    elif name == "zoom_out":
        _draw_magnifier(painter)
        painter.drawLine(11, 15, 19, 15)
    elif name == "cursor":
        path = QPainterPath(QPoint(9, 6))
        path.lineTo(23, 19)
        path.lineTo(16, 20)
        path.lineTo(13, 27)
        path.lineTo(9, 6)
        painter.setBrush(BLUE if checked else QColor("#252629") if dark else QColor("#ffffff"))
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH))
        painter.drawPath(path)
        if checked:
            check_pen = QPen(GREEN, 1.8)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(check_pen)
            painter.drawLine(20, 25, 24, 29)
            painter.drawLine(24, 29, 30, 19)
    elif name == "delay":
        painter.drawEllipse(8, 8, 16, 16)
        painter.drawLine(16, 16, 16, 10)
        painter.drawLine(16, 16, 21, 18)
        painter.drawLine(13, 5, 19, 5)
        if badge == "off":
            painter.setPen(QPen(RED, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(21, 22, 28, 29)
            painter.drawLine(28, 22, 21, 29)
        elif badge:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(BLUE)
            painter.drawEllipse(19, 19, 12, 12)
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setPointSize(7 if len(badge) <= 1 else 6)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRect(19, 19, 12, 12), Qt.AlignmentFlag.AlignCenter, badge)
    elif name == "keyboard":
        painter.setPen(
            QPen(
                base_ink,
                TOOL_STROKE_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawRoundedRect(4, 8, 24, 17, 3, 3)
        painter.setBrush(base_ink)
        painter.setPen(Qt.PenStyle.NoPen)
        for y in (12, 17):
            for x in (8, 13, 18, 23):
                painter.drawRoundedRect(x, y, 2.5, 2.5, 0.5, 0.5)
        painter.drawRoundedRect(10, 21, 12, 2, 0.6, 0.6)
    elif name == "theme":
        if badge == "system":
            painter.drawEllipse(5, 5, 22, 22)
            half = QPainterPath()
            half.moveTo(16, 5)
            half.arcTo(5, 5, 22, 22, 90, 180)
            half.closeSubpath()
            painter.setBrush(base_ink)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(half)
        elif badge == "dark":
            moon = QPainterPath()
            moon.addEllipse(6, 5, 21, 22)
            cutout = QPainterPath()
            cutout.addEllipse(12, 2, 20, 20)
            painter.drawPath(moon.subtracted(cutout))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawEllipse(11, 11, 10, 10)
            for start, end in (
                ((16, 5), (16, 8)),
                ((16, 24), (16, 27)),
                ((5, 16), (8, 16)),
                ((24, 16), (27, 16)),
                ((8, 8), (10, 10)),
                ((22, 22), (24, 24)),
                ((24, 8), (22, 10)),
                ((10, 22), (8, 24)),
            ):
                painter.drawLine(*start, *end)
    elif name == "language":
        if badge == "system":
            painter.drawEllipse(5, 5, 22, 22)
            painter.drawEllipse(11, 5, 10, 22)
            painter.drawLine(5, 16, 27, 16)
        else:
            painter.setPen(base_ink)
            label = "中" if badge == "zh_TW" else "A"
            painter.draw_label(label)


def line_end_style_icon(style: str, endpoint: str, dark: bool = False) -> QIcon:
    pixmap = QPixmap(64, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = _painter(pixmap)
    ink = DARK_INK if dark else INK
    painter.setPen(
        QPen(
            ink,
            2.0,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    start = QPoint(8, 12)
    end = QPoint(56, 12)
    painter.drawLine(start, end)
    if endpoint == "start":
        _draw_line_end_icon(painter, start, ((16, 6), (16, 18)), style, ink, circle_radius=4)
    else:
        _draw_line_end_icon(painter, end, ((48, 6), (48, 18)), style, ink, circle_radius=4)
    painter.end()
    return QIcon(pixmap)


def _draw_line_end_icon(
    painter: QPainter,
    tip: QPoint,
    arrow_points: tuple[tuple[int, int], tuple[int, int]],
    style: str,
    ink: QColor,
    circle_radius: int = 3,
) -> None:
    if style == "arrow":
        for point in arrow_points:
            painter.drawLine(tip, QPoint(*point))
    elif style == "circle":
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawEllipse(tip, circle_radius, circle_radius)
        painter.restore()


def _draw_magnifier(painter: QPainter) -> None:
    painter.drawEllipse(8, 8, 14, 14)
    painter.drawLine(20, 20, 26, 26)


class _ToolbarPainter(QPainter):
    """Hint icon geometry to physical pixels before rasterizing each size."""

    def __init__(self, pixmap: QPixmap, scale: float, bounds: QRectF, *, artwork_size: int,
                 reserve_stroke: bool = True) -> None:
        super().__init__(pixmap)
        self._stroke_scale = scale
        self._size = pixmap.width()
        self._artwork_size = artwork_size
        margin = (self._size - self._artwork_size) // 2
        self.setClipRect(QRect(margin, margin, self._artwork_size, self._artwork_size))
        stroke_pixels = max(1, math.floor(TOOL_STROKE_WIDTH * scale + 0.5)) if reserve_stroke else 0
        self._scale = (self._artwork_size - stroke_pixels) / max(bounds.width(), bounds.height())
        self.translate(margin + self._artwork_size / 2, margin + self._artwork_size / 2)
        self.scale(self._scale, self._scale)
        self.translate(-bounds.center().x(), -bounds.center().y())
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    def setPen(self, pen) -> None:
        if isinstance(pen, QPen) and pen.style() != Qt.PenStyle.NoPen:
            pen = QPen(pen)
            pixels = max(1, math.floor(pen.widthF() * self._stroke_scale + 0.5))
            pen.setWidthF(pixels / self._scale)
        super().setPen(pen)

    def _point(self, point: QPointF, *, stroke: bool = True) -> QPointF:
        transform = self.worldTransform()
        if abs(transform.m12()) > 1e-6 or abs(transform.m21()) > 1e-6:
            return point  # Keep intentionally rotated artwork smooth.
        offset = 0.0
        if stroke and self.pen().style() != Qt.PenStyle.NoPen:
            pixels = round(self.pen().widthF() * self._scale)
            offset = 0.5 if pixels % 2 else 0.0
        mapped = transform.map(point)
        mapped.setX(math.floor(mapped.x() - offset + 0.5) + offset)
        mapped.setY(math.floor(mapped.y() - offset + 0.5) + offset)
        return mapped

    def _draw_pixels(self, method, *args) -> None:
        transform = self.worldTransform()
        if abs(transform.m12()) > 1e-6 or abs(transform.m21()) > 1e-6:
            method(*args)
            return
        # Paint snapped coordinates directly. Mapping them back through the
        # source grid introduces rounding errors at fractional display scales.
        self.save()
        try:
            pen = QPen(self.pen())
            pen.setWidthF(pen.widthF() * self._scale)
            self.resetTransform()
            super().setPen(pen)
            method(*args)
        finally:
            self.restore()

    def _bounds(self, rect: QRectF, *, stroke: bool = True) -> QRectF:
        return QRectF(self._point(rect.topLeft(), stroke=stroke),
                      self._point(rect.bottomRight(), stroke=stroke))

    def drawLine(self, *args) -> None:
        if len(args) == 2:
            start, end = (QPointF(point) for point in args)
        else:
            start, end = QPointF(args[0], args[1]), QPointF(args[2], args[3])
        self._draw_pixels(super().drawLine, QLineF(self._point(start), self._point(end)))

    def draw_mirror_axis(self, *, vertical: bool) -> None:
        # An odd-width stroke snaps half a pixel away from an even-size glyph's
        # center. Use even-width, symmetric dashes on the physical pixel grid.
        extent = self._artwork_size
        margin = (self._size - extent) // 2
        thickness = max(2, 2 * math.floor(TOOL_STROKE_WIDTH * self._stroke_scale / 2 + 0.5))
        dash = max(2, 2 * round(extent / 8))
        cross = margin + (extent - thickness) // 2
        starts = (margin, margin + (extent - dash) // 2, margin + extent - dash)
        self.save()
        try:
            self.resetTransform()
            for start in starts:
                rect = QRect(cross, start, thickness, dash) if vertical else QRect(start, cross, dash, thickness)
                super().fillRect(rect, self.pen().color())
        finally:
            self.restore()

    def drawRect(self, *args) -> None:
        rect = QRectF(args[0]) if len(args) == 1 else QRectF(*args)
        self._draw_pixels(super().drawRect, self._bounds(rect))

    def drawRoundedRect(self, *args) -> None:
        if len(args) == 3:
            rect, rx, ry = QRectF(args[0]), args[1], args[2]
        else:
            rect, rx, ry = QRectF(*args[:4]), args[4], args[5]
        transform = self.worldTransform()
        if abs(transform.m12()) <= 1e-6 and abs(transform.m21()) <= 1e-6:
            rx, ry = rx * self._scale, ry * self._scale
        self._draw_pixels(super().drawRoundedRect, self._bounds(rect), rx, ry)

    def drawEllipse(self, *args) -> None:
        if len(args) == 3:
            center, rx, ry = args
            rect = QRectF(center.x() - rx, center.y() - ry, rx * 2, ry * 2)
        else:
            rect = QRectF(*args)
        self._draw_pixels(self._paint_ellipse, self._bounds(rect))

    def _paint_ellipse(self, rect: QRectF) -> None:
        # Filling an annulus avoids Qt's thin-pen rasterizer, which produces
        # visibly lighter breaks where diagonal arc segments meet.
        self.save()
        try:
            pen = self.pen()
            super().setPen(Qt.PenStyle.NoPen)
            body = QPainterPath()
            body.addEllipse(rect)
            super().drawPath(body)
            if pen.style() == Qt.PenStyle.NoPen:
                return
            half = pen.widthF() / 2
            ring = QPainterPath()
            ring.setFillRule(Qt.FillRule.OddEvenFill)
            ring.addEllipse(rect.adjusted(-half, -half, half, half))
            if rect.width() > 2 * half and rect.height() > 2 * half:
                ring.addEllipse(rect.adjusted(half, half, -half, -half))
            self.setBrush(pen.brush())
            super().drawPath(ring)
        finally:
            self.restore()

    def drawPolygon(self, polygon) -> None:
        self._draw_pixels(super().drawPolygon, QPolygonF([self._point(QPointF(point)) for point in polygon]))

    def drawPolyline(self, polygon) -> None:
        self._draw_pixels(super().drawPolyline, QPolygonF([self._point(QPointF(point)) for point in polygon]))

    def fillRect(self, x, y, width, height, color) -> None:
        self._draw_pixels(super().fillRect, self._bounds(QRectF(x, y, width, height), stroke=False), color)

    def drawText(self, rect, flags, text) -> None:
        # Let the font engine hint glyphs at the final pixel size, too.
        mapped = self.worldTransform().mapRect(QRectF(rect))
        font = self.font()
        font.setPixelSize(max(1, round(QFontInfo(font).pixelSize() * self._scale)))
        self.save()
        self.resetTransform()
        self.setFont(font)
        super().drawText(mapped, flags, text)
        self.restore()

    def draw_label(self, text: str) -> None:
        font = self.font()
        font.setBold(False)
        best_size = 1
        for size in range(1, self._artwork_size * 3):
            font.setPixelSize(size)
            bounds = QFontMetrics(font).tightBoundingRect(text)
            if max(bounds.width(), bounds.height()) > self._artwork_size:
                break
            best_size = size
        # Fallback CJK fonts can have ink bounds smaller than their font metrics.
        # Fit the actual native glyph pixels, then remove their empty surround.
        best = None
        for size in range(max(1, best_size - 2), best_size + self._artwork_size // 2 + 4):
            font.setPixelSize(size)
            glyph = QPixmap(self._size * 3, self._size * 3)
            glyph.fill(Qt.GlobalColor.transparent)
            painter = _painter(glyph)
            painter.setFont(font)
            painter.setPen(self.pen().color())
            painter.drawText(glyph.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.end()
            bounds = _ink_bounds(glyph)
            extent = max(bounds.width(), bounds.height())
            if extent > self._artwork_size:
                break
            best = glyph.copy(bounds)
            if extent == self._artwork_size:
                break
        if best is None:
            return
        self.save()
        self.resetTransform()
        self.drawPixmap((self._size - best.width()) // 2, (self._size - best.height()) // 2, best)
        self.restore()


def _ink_bounds(pixmap: QPixmap) -> QRect:
    alpha = pixmap.toImage().convertToFormat(QImage.Format.Format_Alpha8)
    data = bytes(alpha.constBits())
    left, top, right, bottom = alpha.width(), alpha.height(), 0, 0
    for y in range(alpha.height()):
        row = data[y * alpha.bytesPerLine():y * alpha.bytesPerLine() + alpha.width()]
        if row.strip(b"\0"):
            left = min(left, len(row) - len(row.lstrip(b"\0")))
            right = max(right, len(row.rstrip(b"\0")))
            top = min(top, y)
            bottom = y + 1
    return QRect(left, top, right - left, bottom - top)


def _painter(device: QPixmap) -> QPainter:
    painter = QPainter(device)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return painter


def _rect(x: int, y: int, w: int, h: int, scale: float) -> QRect:
    return QRect(round(x * scale), round(y * scale), round(w * scale), round(h * scale))
