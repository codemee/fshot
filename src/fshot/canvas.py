from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QImage, QMouseEvent, QPainter, QPen, QPolygon, QPixmap
from PySide6.QtWidgets import QInputDialog, QSizePolicy, QWidget

from fshot.settings import DrawingSettings, LineEndStyle, Tool

CANVAS_PADDING = 14
HANDLE_SIZE = 8


class ImageCanvas(QWidget):
    changed = Signal()

    def __init__(self, image: QImage, settings: DrawingSettings) -> None:
        super().__init__()
        self.image = image.convertToFormat(QImage.Format.Format_ARGB32)
        self.settings = settings
        self.tool = Tool.PEN
        self.zoom = 1.0
        self._start: QPoint | None = None
        self._last: QPoint | None = None
        self._preview: QPoint | None = None
        self._crop_rect = QRect(0, 0, self.image.width(), self.image.height())
        self._crop_handle: str | None = None
        self._crop_start_rect: QRect | None = None
        self._undo: list[QImage] = []
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._sync_size()
        self._update_cursor()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def measurement(self) -> tuple[int, int] | None:
        if self.tool is not Tool.MEASURE or self._start is None or self._preview is None:
            return None
        return (
            abs(self._preview.x() - self._start.x()),
            abs(self._preview.y() - self._start.y()),
        )

    def set_tool(self, tool: Tool) -> None:
        if self.tool is Tool.MEASURE and tool is not Tool.MEASURE:
            self._start = None
            self._last = None
            self._preview = None
        self.tool = tool
        self._update_cursor()
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.1, min(8.0, zoom))
        self._sync_size()
        self.update()

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom + 0.25)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom - 0.25)

    def undo(self) -> None:
        if not self._undo:
            return
        self.image = self._undo.pop()
        self._crop_rect = QRect(0, 0, self.image.width(), self.image.height())
        self._sync_size()
        self.changed.emit()
        self.update()

    def export_image(self) -> QImage:
        return self.image.copy()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        target = QRect(
            CANVAS_PADDING,
            CANVAS_PADDING,
            int(self.image.width() * self.zoom),
            int(self.image.height() * self.zoom),
        )
        painter.drawImage(target, self.image)
        self._draw_crop_handles(painter)
        if (
            self._start is not None
            and self._preview is not None
            and self.tool in {Tool.LINE, Tool.RECTANGLE, Tool.MEASURE, Tool.MOSAIC}
        ):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRect(self._to_widget(self._start), self._to_widget(self._preview)).normalized()
            if self.tool == Tool.MOSAIC:
                self._draw_selection_rect(painter, rect)
            elif self.tool == Tool.MEASURE:
                self._draw_measurement(painter, rect, self._to_widget(self._preview))
            elif self.tool == Tool.LINE:
                pen = QPen(self.settings.color, max(1, int(self.settings.line_width * self.zoom)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                self._draw_line(
                    painter,
                    self._to_widget(self._start),
                    self._to_widget(self._preview),
                    scaled=True,
                )
            else:
                pen = QPen(self.settings.color, max(1, int(self.settings.line_width * self.zoom)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawRect(rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        handle = self._crop_handle_at(event.position().toPoint())
        if handle:
            self._crop_handle = handle
            self._crop_start_rect = QRect(self._crop_rect)
            return
        point = self._to_image(event.position().toPoint())
        if not self._contains(point):
            return
        if self.tool == Tool.TEXT:
            self._place_text(point)
            return
        if self.tool is not Tool.MEASURE:
            self._push_undo()
        self._start = point
        self._last = point
        self._preview = point

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._crop_handle and self._crop_start_rect:
            self._drag_crop_handle(event.position().toPoint())
            self.update()
            return
        handle = self._crop_handle_at(event.position().toPoint())
        if handle:
            self.setCursor(self._cursor_for_crop_handle(handle))
            return
        self._update_cursor()
        if self._start is None:
            return
        point = self._to_image(event.position().toPoint())
        point = self._clamp(point)
        if self.tool == Tool.PEN and self._last:
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(self._pen())
            painter.drawLine(self._last, point)
            self._last = point
            self.changed.emit()
        self._preview = point
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._crop_handle:
            if self._crop_rect != QRect(0, 0, self.image.width(), self.image.height()):
                self._apply_crop()
            self._crop_handle = None
            self._crop_start_rect = None
            self.update()
            return
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        end = self._clamp(self._to_image(event.position().toPoint()))
        if self.tool == Tool.LINE:
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(self._pen())
            self._draw_line(painter, self._start, end, scaled=False)
            self.changed.emit()
        elif self.tool == Tool.RECTANGLE:
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(self._pen())
            painter.drawRect(QRect(self._start, end).normalized())
            self.changed.emit()
        elif self.tool == Tool.MOSAIC:
            self._apply_mosaic(QRect(self._start, end).normalized())
            self.changed.emit()
        elif self.tool == Tool.MEASURE:
            self._preview = end
            self._last = None
            self.update()
            return
        self._start = None
        self._last = None
        self._preview = None
        self.update()

    def _place_text(self, point: QPoint) -> None:
        text, ok = QInputDialog.getText(self, "Text", "Text")
        if not ok or not text:
            return
        self._push_undo()
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self.settings.color)
        painter.setFont(QFont(self.settings.font_family, self.settings.font_size))
        painter.drawText(point, text)
        self.changed.emit()
        self.update()

    def _apply_mosaic(self, rect: QRect) -> None:
        rect = rect.intersected(QRect(0, 0, self.image.width(), self.image.height()))
        if rect.width() < 2 or rect.height() < 2:
            return
        block = max(2, min(80, self.settings.line_width * 3))
        painter = QPainter(self.image)
        for y in range(rect.top(), rect.bottom() + 1, block):
            for x in range(rect.left(), rect.right() + 1, block):
                sample = QColor(self.image.pixel(x, y))
                painter.fillRect(QRect(x, y, block, block).intersected(rect), sample)

    def _push_undo(self) -> None:
        self._undo.append(self.image.copy())
        if len(self._undo) > 50:
            self._undo.pop(0)

    def _pen(self) -> QPen:
        pen = QPen(self.settings.color, self.settings.line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _draw_line(self, painter: QPainter, start: QPoint, end: QPoint, scaled: bool) -> None:
        painter.drawLine(start, end)
        self._draw_line_end(painter, start, end, self.settings.line_start_style, scaled)
        self._draw_line_end(painter, end, start, self.settings.line_end_style, scaled)

    def _draw_line_end(
        self,
        painter: QPainter,
        tip: QPoint,
        opposite: QPoint,
        style: LineEndStyle,
        scaled: bool,
    ) -> None:
        if style is LineEndStyle.NONE:
            return

        scale = self.zoom if scaled else 1.0
        if style is LineEndStyle.CIRCLE:
            radius = max(4.0, self.settings.line_width * 1.75) * scale
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.settings.color)
            painter.drawEllipse(QPointF(tip), radius, radius)
            painter.restore()
            return

        dx = tip.x() - opposite.x()
        dy = tip.y() - opposite.y()
        length = math.hypot(dx, dy)
        if length < 2:
            return
        angle = math.atan2(dy, dx)
        head_len = max(10, self.settings.line_width * 5) * scale
        head_angle = math.radians(28)
        for sign in (-1, 1):
            point = QPointF(
                tip.x() - head_len * math.cos(angle + sign * head_angle),
                tip.y() - head_len * math.sin(angle + sign * head_angle),
            )
            painter.drawLine(tip, point.toPoint())

    def _draw_selection_rect(self, painter: QPainter, rect: QRect) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor("#868e96"), 1)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.drawRect(rect)

    def _draw_measurement(self, painter: QPainter, rect: QRect, end: QPoint) -> None:
        measurement = self.measurement
        if measurement is None:
            return
        horizontal, vertical = measurement
        painter.save()
        outline = QPen(QColor("#1971c2"), 1.5, Qt.PenStyle.DashLine)
        outline.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(outline)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        text = f"↔ {horizontal} px   ↕ {vertical} px"
        label = painter.fontMetrics().boundingRect(text).adjusted(-6, -4, 6, 4)
        label.moveTopLeft(end + QPoint(12, 12))
        bounds = self.rect().adjusted(2, 2, -2, -2)
        if label.right() > bounds.right():
            label.moveRight(end.x() - 12)
        if label.bottom() > bounds.bottom():
            label.moveBottom(end.y() - 12)
        if label.left() < bounds.left():
            label.moveLeft(bounds.left())
        if label.top() < bounds.top():
            label.moveTop(bounds.top())
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.setBrush(QColor(33, 37, 41, 225))
        painter.drawRoundedRect(label, 4, 4)
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _draw_crop_handles(self, painter: QPainter) -> None:
        rect = self._crop_widget_rect()
        painter.setPen(QPen(QColor("#868e96"), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.setBrush(QColor("#f8f9fa"))
        painter.setPen(QPen(QColor("#868e96"), 1))
        for handle_rect in self._crop_handle_rects(rect).values():
            painter.drawRect(handle_rect)

    def _crop_widget_rect(self) -> QRect:
        return QRect(
            int(self._crop_rect.x() * self.zoom) + CANVAS_PADDING,
            int(self._crop_rect.y() * self.zoom) + CANVAS_PADDING,
            int(self._crop_rect.width() * self.zoom),
            int(self._crop_rect.height() * self.zoom),
        )

    def _crop_handle_rects(self, rect: QRect) -> dict[str, QRect]:
        size = HANDLE_SIZE
        half = size // 2
        cx = rect.center().x()
        cy = rect.center().y()
        points = {
            "nw": rect.topLeft() + QPoint(-half, -half),
            "n": QPoint(cx, rect.top() - half),
            "ne": rect.topRight() + QPoint(half, -half),
            "e": QPoint(rect.right() + half, cy),
            "se": rect.bottomRight() + QPoint(half, half),
            "s": QPoint(cx, rect.bottom() + half),
            "sw": rect.bottomLeft() + QPoint(-half, half),
            "w": QPoint(rect.left() - half, cy),
        }
        return {name: QRect(point.x() - half, point.y() - half, size, size) for name, point in points.items()}

    def _crop_handle_at(self, point: QPoint) -> str | None:
        for name, rect in self._crop_handle_rects(self._crop_widget_rect()).items():
            if rect.contains(point):
                return name
        return None

    def _drag_crop_handle(self, point: QPoint) -> None:
        if not self._crop_handle or self._crop_start_rect is None:
            return
        image_point = self._clamp(self._to_image(point))
        rect = QRect(self._crop_start_rect)
        if "n" in self._crop_handle:
            rect.setTop(image_point.y())
        if "s" in self._crop_handle:
            rect.setBottom(image_point.y())
        if "w" in self._crop_handle:
            rect.setLeft(image_point.x())
        if "e" in self._crop_handle:
            rect.setRight(image_point.x())
        rect = rect.normalized().intersected(QRect(0, 0, self.image.width(), self.image.height()))
        if rect.width() >= 8 and rect.height() >= 8:
            self._crop_rect = rect

    def _apply_crop(self) -> None:
        rect = self._crop_rect.intersected(QRect(0, 0, self.image.width(), self.image.height()))
        if rect.width() < 8 or rect.height() < 8:
            self._crop_rect = QRect(0, 0, self.image.width(), self.image.height())
            return
        self._push_undo()
        self.image = self.image.copy(rect)
        self._crop_rect = QRect(0, 0, self.image.width(), self.image.height())
        self._sync_size()
        self.changed.emit()

    def _cursor_for_crop_handle(self, handle: str) -> Qt.CursorShape:
        if handle in {"nw", "se"}:
            return Qt.CursorShape.SizeFDiagCursor
        if handle in {"ne", "sw"}:
            return Qt.CursorShape.SizeBDiagCursor
        if handle in {"n", "s"}:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.SizeHorCursor

    def _sync_size(self) -> None:
        self.setFixedSize(
            int(self.image.width() * self.zoom) + CANVAS_PADDING * 2,
            int(self.image.height() * self.zoom) + CANVAS_PADDING * 2,
        )

    def _to_image(self, point: QPoint) -> QPoint:
        return QPoint(
            int((point.x() - CANVAS_PADDING) / self.zoom),
            int((point.y() - CANVAS_PADDING) / self.zoom),
        )

    def _to_widget(self, point: QPoint) -> QPoint:
        return QPoint(
            int(point.x() * self.zoom) + CANVAS_PADDING,
            int(point.y() * self.zoom) + CANVAS_PADDING,
        )

    def _contains(self, point: QPoint) -> bool:
        return 0 <= point.x() < self.image.width() and 0 <= point.y() < self.image.height()

    def _clamp(self, point: QPoint) -> QPoint:
        return QPoint(
            max(0, min(self.image.width() - 1, point.x())),
            max(0, min(self.image.height() - 1, point.y())),
        )

    def _update_cursor(self) -> None:
        if self.tool in {Tool.RECTANGLE, Tool.MEASURE, Tool.MOSAIC}:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.tool == Tool.TEXT:
            self.setCursor(Qt.CursorShape.IBeamCursor)
        elif self.tool == Tool.PEN:
            self.setCursor(_pencil_cursor())
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)


def _pencil_cursor() -> QCursor:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor("#343a40"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QColor("#ffd43b"))
    painter.drawPolygon(QPolygon([QPoint(5, 18), QPoint(8, 21), QPoint(20, 9), QPoint(17, 6)]))
    painter.setBrush(QColor("#f3d19c"))
    painter.drawPolygon(QPolygon([QPoint(5, 18), QPoint(8, 21), QPoint(3, 22)]))
    painter.setBrush(QColor("#343a40"))
    painter.drawPolygon(QPolygon([QPoint(3, 22), QPoint(5, 18), QPoint(6, 20)]))
    painter.drawLine(8, 18, 18, 8)
    painter.end()
    return QCursor(pixmap, 3, 22)
