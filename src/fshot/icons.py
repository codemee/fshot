from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPolygon, QPixmap


INK = QColor("#5c6269")
DARK_INK = QColor("#c7cbd1")
BLUE = QColor("#1971c2")
GREEN = QColor("#2f9e44")
RED = QColor("#e03131")


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
    painter.setBrush(INK)
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
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = _painter(pixmap)
    base_ink = DARK_INK if dark else INK
    ink = color or base_ink
    icon_width = 1.45 if name != "style" else max(1.3, min(5.0, width * 0.45))
    pen = QPen(ink, icon_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "pen":
        # The pencil artwork extends farther toward the lower-left than the
        # other toolbar glyphs, so align its visual center with its peers.
        painter.save()
        painter.translate(0, -4)
        painter.setPen(QPen(base_ink, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
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
                1.35,
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
        painter.setPen(QPen(INK, 0.9))
        for y in (8, 15, 22):
            for x in (7, 14, 21):
                painter.fillRect(x, y, 5, 5, QColor("#9aa0a6") if dark and (x + y) % 2 else QColor("#495057") if (x + y) % 2 else QColor("#adb5bd"))
    elif name == "style":
        painter.drawLine(7, 23, 25, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawEllipse(20, 20, 7, 7)
    elif name == "undo":
        painter.setPen(QPen(base_ink, 1.45, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPoint(12, 12))
        path.cubicTo(17, 8, 25, 10, 26, 17)
        path.cubicTo(27, 24, 18, 28, 11, 23)
        painter.drawPath(path)
        painter.drawLine(12, 12, 6, 12)
        painter.drawLine(6, 12, 10, 8)
        painter.drawLine(6, 12, 10, 16)
    elif name == "copy":
        painter.drawRoundedRect(11, 7, 13, 16, 2, 2)
        painter.drawRoundedRect(7, 11, 13, 16, 2, 2)
    elif name == "save":
        painter.setPen(QPen(base_ink, 1.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(7, 6, 18, 20, 2, 2)
        painter.drawLine(10, 6, 22, 6)
        painter.drawLine(22, 6, 25, 9)
        painter.drawRect(11, 8, 10, 6)
        painter.drawLine(19, 9, 19, 13)
        painter.drawRoundedRect(11, 18, 10, 6, 1, 1)
        painter.drawLine(13, 21, 19, 21)
    elif name == "save_as":
        painter.setPen(QPen(base_ink, 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
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
        painter.setPen(QPen(base_ink, 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
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
        painter.setPen(QPen(base_ink, 1.35))
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
                1.3,
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
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(base_ink, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawEllipse(6, 5, 8, 8)
            for start, end in (
                ((10, 2), (10, 4)),
                ((10, 14), (10, 16)),
                ((3, 9), (5, 9)),
                ((15, 9), (17, 9)),
                ((5, 4), (6, 5)),
                ((14, 13), (15, 14)),
            ):
                painter.drawLine(*start, *end)
            painter.setBrush(base_ink)
            painter.setPen(Qt.PenStyle.NoPen)
            moon = QPainterPath()
            moon.addEllipse(18, 18, 10, 11)
            cutout = QPainterPath()
            cutout.addEllipse(22, 16, 9, 10)
            painter.drawPath(moon.subtracted(cutout))
            painter.setPen(QPen(base_ink, 1.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(7, 25, 25, 7)
        elif badge == "dark":
            painter.setBrush(base_ink)
            painter.setPen(Qt.PenStyle.NoPen)
            moon = QPainterPath()
            moon.addEllipse(7, 6, 19, 20)
            cutout = QPainterPath()
            cutout.addEllipse(13, 3, 17, 18)
            painter.drawPath(moon.subtracted(cutout))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(base_ink, 1.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
        painter.setPen(base_ink)
        font = painter.font()
        font.setBold(True)
        if badge == "system":
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(QRect(2, 2, 16, 15), Qt.AlignmentFlag.AlignCenter, "文")
            painter.drawText(QRect(15, 15, 15, 15), Qt.AlignmentFlag.AlignCenter, "A")
            painter.setPen(QPen(base_ink, 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(8, 25, 25, 8)
        else:
            font.setPointSize(11 if badge == "zh_TW" else 10)
            painter.setFont(font)
            label = "中" if badge == "zh_TW" else "En"
            painter.drawText(QRect(1, 3, 30, 26), Qt.AlignmentFlag.AlignCenter, label)

    painter.end()
    return QIcon(pixmap)


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


def _painter(pixmap: QPixmap) -> QPainter:
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return painter


def _rect(x: int, y: int, w: int, h: int, scale: float) -> QRect:
    return QRect(round(x * scale), round(y * scale), round(w * scale), round(h * scale))
