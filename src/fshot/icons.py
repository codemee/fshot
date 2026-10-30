from __future__ import annotations

from PySide6.QtCore import QLineF, QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFontInfo, QFontMetrics, QIcon, QImage, QPainter, QPainterPath, QPen, QPolygonF, QPixmap

from fshot.theme import DARK_COLORS

INK = QColor("#202124")
DARK_INK = QColor(DARK_COLORS["text"])
CAMERA_INK = QColor("#5c6269")
# Toolbar artwork is designed on a 24 px grid and rasterized once at 48 px.
TOOL_DESIGN_SIZE = 24
TOOL_RASTER_SIZE = 48
TOOL_STROKE_WIDTH = 1.0
# Most artwork fits 16 px inside the 20 px icon canvas. Dense glyphs use 20 px.
_COMPLEX_TOOL_ICONS = {"keyboard", "save_as"}
BLUE = QColor("#1971c2")
GREEN = QColor("#2f9e44")
RED = QColor("#e03131")

# Bounds of the artwork's geometry on its drawing grid, excluding empty canvas.
_TOOL_BOUNDS = {
    "screen_mode": (3.75, 3.75, 16.5, 15.75),
    "pen": (4.5, 4.5, 15, 15),
    "line": (5.25, 6, 13.5, 12),
    "arrow": (5.25, 6, 12.75, 12.75),
    "rectangle": (5.25, 6, 13.5, 12),
    "measure": (4.5, 3.75, 15.75, 15.75),
    "text": (6, 6, 12, 12.75),
    "mosaic": (5.25, 6, 14.25, 14.25),
    "style": (5.25, 8.25, 15, 12),
    "undo": (4.5, 6, 15, 12.75),
    "rotate_clockwise": (3, 3.75, 18.75, 18.75),
    "flip_horizontal": (3.75, 3.75, 16.5, 16.5),
    "flip_vertical": (3.75, 3.75, 16.5, 16.5),
    "resize_down": (3.75, 3.75, 16.5, 16.5),
    "copy": (5.25, 5.25, 12.75, 15),
    "save": (5.25, 4.5, 13.5, 15),
    "save_as": (4.5, 3.75, 13.5, 16.5),
    "zoom_in": (6, 6, 13.5, 13.5),
    "zoom_out": (6, 6, 13.5, 13.5),
    "zoom_fit": (3.75, 3.75, 16.5, 16.5),
    "cursor": (6.75, 4.5, 10.5, 15.75),
    "delay": (6, 3.75, 12, 14.25),
    "keyboard": (3, 6, 18, 12.75),
    "theme": (3.75, 3.75, 16.5, 16.5),
    "language": (3.75, 3.75, 16.5, 16.5),
}


def _tool_bounds(name, checked, badge, line_start, line_end) -> QRectF:
    bounds = QRectF(*_TOOL_BOUNDS.get(name, (0, 0, 24, 24)))
    if name == "line":
        if line_start == "circle":
            bounds = bounds.united(QRectF(3, 15.75, 4.5, 4.5))
        if line_end == "circle":
            bounds = bounds.united(QRectF(16.5, 3.75, 4.5, 4.5))
    elif name == "cursor" and checked:
        bounds = bounds.united(QRectF(15, 14.25, 7.5, 7.5))
    elif name == "delay":
        if badge == "off":
            bounds = bounds.united(QRectF(15.75, 16.5, 5.25, 5.25))
        elif badge:
            bounds = bounds.united(QRectF(14.25, 14.25, 9, 9))
    elif name == "theme" and badge == "dark":
        bounds = QRectF(4.5, 3.75, 15.75, 16.5)
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
    # Supply only the 48 px raster; QIcon scales it to the toolbar's 20 px slot.
    pixmap = QPixmap(TOOL_RASTER_SIZE, TOOL_RASTER_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = _ToolbarPainter(
        pixmap, _tool_bounds(name, checked, badge, line_start, line_end),
        artwork_size=48 if name in _COMPLEX_TOOL_ICONS else 38,
        reserve_stroke=name != "mosaic",
    )
    try:
        _draw_tool_icon(painter, name, color, width, checked, badge, dark, line_start, line_end)
    finally:
        painter.end()
    icon = QIcon(pixmap)
    active_pixmap = pixmap.copy()
    active_painter = QPainter(active_pixmap)
    active_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    active_painter.fillRect(active_pixmap.rect(), QColor(DARK_COLORS["accent"]) if dark else BLUE)
    active_painter.end()
    icon.addPixmap(active_pixmap, QIcon.Mode.Normal, QIcon.State.On)
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
    icon_width = TOOL_STROKE_WIDTH if name != "style" else max(0.9750000000000001, min(3.75, width * 0.3375))
    pen = QPen(ink, icon_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "screen_mode":
        if checked:
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setDashPattern([2, 2])
            painter.setPen(pen)
        painter.drawRoundedRect(QRectF(3.75, 3.75, 16.5, 12), 1.5, 1.5)
        painter.drawLine(12, 15.75, 12, 19.5)
        painter.drawLine(7.5, 19.5, 16.5, 19.5)
    elif name == "pen":
        # A single outline, with only the end cap and pencil-tip seams.
        path = QPainterPath(QPointF(4.5, 19.5))
        path.lineTo(6, 14.25)
        path.lineTo(15, 5.25)
        path.quadTo(15.75, 4.5, 16.5, 5.25)
        path.lineTo(18.75, 7.5)
        path.quadTo(19.5, 8.25, 18.75, 9)
        path.lineTo(9.75, 18)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(13.5, 6.75, 17.25, 10.5)
        painter.drawLine(6, 14.25, 9.75, 18)
    elif name == "line":
        start = QPointF(5.25, 18)
        end = QPointF(18.75, 6)
        painter.drawLine(start, end)
        _draw_line_end_icon(painter, start, ((6.75, 12.75), (11.25, 17.25)), line_start, ink, circle_radius=2.25)
        _draw_line_end_icon(painter, end, ((17.25, 11.25), (12.75, 6.75)), line_end, ink, circle_radius=2.25)
    elif name == "arrow":
        painter.drawLine(18, 6, 5.25, 18.75)
        painter.drawLine(5.25, 18.75, 6.75, 12.75)
        painter.drawLine(5.25, 18.75, 11.25, 17.25)
    elif name == "rectangle":
        painter.drawRoundedRect(5.25, 6, 13.5, 12, 1.5, 1.5)
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
            QPolygonF(
                [
                    QPointF(4.5, 3.75),
                    QPointF(9, 3.75),
                    QPointF(9, 15),
                    QPointF(20.25, 15),
                    QPointF(20.25, 19.5),
                    QPointF(4.5, 19.5),
                ]
            )
        )
        for y in (7.5, 10.5, 13.5):
            painter.drawLine(4.5, y, 6.75, y)
        for x in (12, 15, 18):
            painter.drawLine(x, 19.5, x, 17.25)
    elif name == "text":
        painter.drawLine(6, 6, 18, 6)
        painter.drawLine(12, 6, 12, 18.75)
    elif name == "mosaic":
        painter.setPen(QPen(base_ink, 0.675))
        for row, y in enumerate((6, 11.25, 16.5)):
            for column, x in enumerate((5.25, 10.5, 15.75)):
                painter.fillRect(x, y, 3.75, 3.75, QColor("#9aa0a6") if dark and (row + column) % 2 else QColor("#495057") if (row + column) % 2 else QColor("#adb5bd"))
    elif name == "style":
        painter.drawLine(5.25, 17.25, 18.75, 8.25)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawEllipse(15, 15, 5.25, 5.25)
    elif name == "undo":
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPointF(9, 9))
        path.cubicTo(12.75, 6, 18.75, 7.5, 19.5, 12.75)
        path.cubicTo(20.25, 18, 13.5, 21, 8.25, 17.25)
        painter.drawPath(path)
        painter.drawLine(9, 9, 4.5, 9)
        painter.drawLine(4.5, 9, 7.5, 6)
        painter.drawLine(4.5, 9, 7.5, 12)
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
        arrow = QPainterPath(QPointF(3, 11.25))
        arrow.cubicTo(3.75, 6, 7.5, 4.5, 13.5, 6)
        painter.drawPath(arrow)
        painter.drawLine(13.5, 6, 10.5, 3.75)
        painter.drawLine(13.5, 6, 10.5, 8.25)

        painter.save()
        painter.translate(13.5, 15)
        painter.rotate(18)
        painter.drawRoundedRect(-6, -5.25, 12, 10.5, 1.125, 1.125)
        painter.drawEllipse(-3.75, -3, 1.5, 1.5)
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(-4.5, 3.75),
                    QPointF(-1.5, 0.75),
                    QPointF(0.75, 3),
                    QPointF(3, 0.75),
                    QPointF(4.5, 3.75),
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
        painter.drawPolygon(QPolygonF([QPointF(3.75, 19.5), QPointF(9, 19.5), QPointF(9, 4.5)]))
        painter.drawPolygon(QPolygonF([QPointF(20.25, 19.5), QPointF(15, 19.5), QPointF(15, 4.5)]))
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
        painter.drawPolygon(QPolygonF([QPointF(4.5, 9), QPointF(19.5, 9), QPointF(4.5, 3.75)]))
        painter.drawPolygon(QPolygonF([QPointF(4.5, 15), QPointF(19.5, 15), QPointF(4.5, 20.25)]))
        painter.draw_mirror_axis(vertical=False)
    elif name == "resize_down":
        painter.setPen(QPen(base_ink, 0.9375, Qt.PenStyle.DashLine))
        painter.drawRect(3.75, 3.75, 16.5, 16.5)
        painter.setPen(
            QPen(
                base_ink,
                TOOL_STROKE_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawLine(18.75, 18.75, 11.25, 11.25)
        painter.drawLine(11.25, 11.25, 12, 15.75)
        painter.drawLine(11.25, 11.25, 15.75, 12)
    elif name == "copy":
        painter.drawRoundedRect(8.25, 5.25, 9.75, 12, 1.5, 1.5)
        painter.drawRoundedRect(5.25, 8.25, 9.75, 12, 1.5, 1.5)
    elif name == "save":
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(5.25, 4.5, 13.5, 15, 1.5, 1.5)
        painter.drawLine(7.5, 4.5, 16.5, 4.5)
        painter.drawLine(16.5, 4.5, 18.75, 6.75)
        painter.drawRect(8.25, 6, 7.5, 4.5)
        painter.drawLine(14.25, 6.75, 14.25, 9.75)
        painter.drawRoundedRect(8.25, 13.5, 7.5, 4.5, 0.75, 0.75)
        painter.drawLine(9.75, 15.75, 14.25, 15.75)
    elif name == "save_as":
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(6.75, 3.75, 11.25, 12.75, 1.5, 1.5)
        painter.drawLine(9, 3.75, 15.75, 3.75)
        painter.drawLine(15.75, 3.75, 18, 6)
        painter.drawRect(9.75, 5.25, 5.25, 3)
        painter.drawRoundedRect(9.75, 12, 5.25, 3, 0.75, 0.75)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(DARK_COLORS["panel"]) if dark else QColor("#ffffff"))
        painter.drawRoundedRect(3.75, 6.75, 12.75, 14.25, 2.25, 2.25)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(4.5, 7.5, 11.25, 12.75, 1.5, 1.5)
        painter.drawLine(6.75, 7.5, 13.5, 7.5)
        painter.drawLine(13.5, 7.5, 15.75, 9.75)
        painter.drawRect(7.5, 9, 5.25, 3)
        painter.drawRoundedRect(7.5, 15.75, 5.25, 3, 0.75, 0.75)
    elif name == "zoom_in":
        _draw_magnifier(painter)
        painter.drawLine(11.25, 8.25, 11.25, 14.25)
        painter.drawLine(8.25, 11.25, 14.25, 11.25)
    elif name == "zoom_out":
        _draw_magnifier(painter)
        painter.drawLine(8.25, 11.25, 14.25, 11.25)
    elif name == "zoom_fit":
        for x, y, dx, dy in ((3.75, 3.75, 1, 1), (20.25, 3.75, -1, 1), (3.75, 20.25, 1, -1), (20.25, 20.25, -1, -1)):
            painter.drawLine(x, y, x + dx * 4.5, y)
            painter.drawLine(x, y, x, y + dy * 4.5)
        painter.drawRect(8.25, 8.25, 7.5, 7.5)
    elif name == "cursor":
        path = QPainterPath(QPointF(6.75, 4.5))
        path.lineTo(17.25, 14.25)
        path.lineTo(12, 15)
        path.lineTo(9.75, 20.25)
        path.lineTo(6.75, 4.5)
        painter.setBrush(QColor(DARK_COLORS["raised"]) if dark and checked else BLUE if checked
                         else QColor(DARK_COLORS["panel"]) if dark else QColor("#ffffff"))
        painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH))
        painter.drawPath(path)
        if checked:
            check_pen = QPen(QColor(DARK_COLORS["accent"]) if dark else GREEN, 1.35)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(check_pen)
            painter.drawLine(15, 18.75, 18, 21.75)
            painter.drawLine(18, 21.75, 22.5, 14.25)
    elif name == "delay":
        painter.drawEllipse(6, 6, 12, 12)
        painter.drawLine(12, 12, 12, 7.5)
        painter.drawLine(12, 12, 15.75, 13.5)
        painter.drawLine(9.75, 3.75, 14.25, 3.75)
        if badge == "off":
            painter.setPen(QPen(RED, 1.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(15.75, 16.5, 21, 21.75)
            painter.drawLine(21, 16.5, 15.75, 21.75)
        elif badge:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(DARK_COLORS["warning"]) if dark else BLUE)
            painter.drawEllipse(14.25, 14.25, 9, 9)
            painter.setPen(QColor(DARK_COLORS["on_accent"] if dark else "#ffffff"))
            font = painter.font()
            font.setPointSizeF(5.25 if len(badge) <= 1 else 4.5)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(14.25, 14.25, 9, 9), Qt.AlignmentFlag.AlignCenter, badge)
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
        painter.drawRoundedRect(3, 6, 18, 12.75, 2.25, 2.25)
        painter.setBrush(base_ink)
        painter.setPen(Qt.PenStyle.NoPen)
        for y in (9, 12.75):
            for x in (6, 9.75, 13.5, 17.25):
                painter.drawRoundedRect(x, y, 1.875, 1.875, 0.375, 0.375)
        painter.drawRoundedRect(7.5, 15.75, 9, 1.5, 0.45, 0.45)
    elif name == "theme":
        if badge == "system":
            painter.drawEllipse(3.75, 3.75, 16.5, 16.5)
            half = QPainterPath()
            half.moveTo(12, 3.75)
            half.arcTo(3.75, 3.75, 16.5, 16.5, 90, 180)
            half.closeSubpath()
            painter.setBrush(base_ink)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(half)
        elif badge == "dark":
            moon = QPainterPath()
            moon.addEllipse(4.5, 3.75, 15.75, 16.5)
            cutout = QPainterPath()
            cutout.addEllipse(9, 1.5, 15, 15)
            painter.drawPath(moon.subtracted(cutout))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(base_ink, TOOL_STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawEllipse(8.25, 8.25, 7.5, 7.5)
            for start, end in (
                ((12, 3.75), (12, 6)),
                ((12, 18), (12, 20.25)),
                ((3.75, 12), (6, 12)),
                ((18, 12), (20.25, 12)),
                ((6, 6), (7.5, 7.5)),
                ((16.5, 16.5), (18, 18)),
                ((18, 6), (16.5, 7.5)),
                ((7.5, 16.5), (6, 18)),
            ):
                painter.drawLine(*start, *end)
    elif name == "language":
        if badge == "system":
            painter.drawEllipse(3.75, 3.75, 16.5, 16.5)
            painter.drawEllipse(8.25, 3.75, 7.5, 16.5)
            painter.drawLine(3.75, 12, 20.25, 12)
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
    tip: QPoint | QPointF,
    arrow_points: tuple[tuple[int, int], tuple[int, int]],
    style: str,
    ink: QColor,
    circle_radius: float = 3,
) -> None:
    if style == "arrow":
        for point in arrow_points:
            painter.drawLine(tip, QPointF(*point))
    elif style == "circle":
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawEllipse(tip, circle_radius, circle_radius)
        painter.restore()


def _draw_magnifier(painter: QPainter) -> None:
    painter.drawEllipse(6, 6, 10.5, 10.5)
    painter.drawLine(15, 15, 19.5, 19.5)


class _ToolbarPainter(QPainter):
    """Rasterize 24-grid geometry at 48 px without final-size pixel snapping."""

    def __init__(self, pixmap, bounds, *, artwork_size, reserve_stroke=True):
        super().__init__(pixmap)
        self._size = pixmap.width()
        self._artwork_size = artwork_size
        self._raster_scale = self._size / TOOL_DESIGN_SIZE
        margin = (self._size - artwork_size) / 2
        self.setClipRect(QRectF(margin, margin, artwork_size, artwork_size))
        stroke = TOOL_STROKE_WIDTH * self._raster_scale if reserve_stroke else 0
        self._scale = (artwork_size - stroke) / max(bounds.width(), bounds.height())
        self.translate(self._size / 2, self._size / 2)
        self.scale(self._scale, self._scale)
        self.translate(-bounds.center().x(), -bounds.center().y())
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    def setPen(self, pen):
        if isinstance(pen, QPen) and pen.style() != Qt.PenStyle.NoPen:
            pen = QPen(pen)
            pen.setWidthF(pen.widthF() * self._raster_scale / self._scale)
        super().setPen(pen)

    def drawLine(self, *args):
        line = QLineF(QPointF(args[0]), QPointF(args[1])) if len(args) == 2 else QLineF(*args)
        super().drawLine(line)

    def drawRect(self, *args):
        super().drawRect(QRectF(args[0]) if len(args) == 1 else QRectF(*args))

    def drawRoundedRect(self, *args):
        if len(args) == 3:
            super().drawRoundedRect(QRectF(args[0]), args[1], args[2])
        else:
            super().drawRoundedRect(QRectF(*args[:4]), args[4], args[5])

    def drawEllipse(self, *args):
        if len(args) == 3:
            super().drawEllipse(QPointF(args[0]), args[1], args[2])
        else:
            super().drawEllipse(QRectF(*args))

    def fillRect(self, x, y, width, height, color):
        super().fillRect(QRectF(x, y, width, height), color)

    def draw_mirror_axis(self, *, vertical):
        extent = self._artwork_size
        margin = (self._size - extent) / 2
        thickness = 0.6 * self._raster_scale
        dash = extent / 3
        cross = (self._size - thickness) / 2
        starts = (margin, self._size - margin - dash)
        self.save()
        self.resetTransform()
        for start in starts:
            rect = QRectF(cross, start, thickness, dash) if vertical else QRectF(start, cross, dash, thickness)
            QPainter.fillRect(self, rect, self.pen().color())
        self.restore()

    def drawText(self, rect, flags, text):
        mapped = self.worldTransform().mapRect(QRectF(rect))
        font = self.font()
        font.setPixelSize(max(1, round(QFontInfo(font).pixelSize() * self._scale)))
        self.save()
        self.resetTransform()
        self.setFont(font)
        super().drawText(mapped, flags, text)
        self.restore()

    def draw_label(self, text: str) -> None:
        # Letter glyphs need less visual weight than outlined pictograms.
        target_size = round(self._artwork_size * (0.8 if text == "A" else 0.875))
        font = self.font()
        font.setBold(False)
        best_size = 1
        for size in range(1, target_size * 3):
            font.setPixelSize(size)
            bounds = QFontMetrics(font).tightBoundingRect(text)
            if max(bounds.width(), bounds.height()) > target_size:
                break
            best_size = size
        # Fallback CJK fonts can have ink bounds smaller than their font metrics.
        # Fit the actual native glyph pixels, then remove their empty surround.
        best = None
        for size in range(max(1, best_size - 2), best_size + target_size // 2 + 4):
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
            if extent > target_size:
                break
            best = glyph.copy(bounds)
            if extent == target_size:
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
