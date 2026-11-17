"""Select native pixels from a frozen virtual display on a physical screen."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QDialog

from fshot.qt_image import pil_to_qimage


class RegionPreview(QDialog):
    def __init__(self, image, tr):
        super().__init__()
        self.image = pil_to_qimage(image)
        self.tr = tr
        self.start = self.end = None
        self.box = None
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()
        self.setGeometry(geometry.adjusted(32, 32, -32, -32))

    def image_area(self):
        area = self.rect().adjusted(12, 64, -12, -12)
        scale = min(area.width()/self.image.width(), area.height()/self.image.height())
        width, height = max(1, round(self.image.width()*scale)), max(1, round(self.image.height()*scale))
        return QRect(area.center().x()-width//2, area.center().y()-height//2, width, height)

    def pixel_point(self, point):
        area = self.image_area()
        return QPoint(min(self.image.width(), max(0, round((point.x()-area.x())*self.image.width()/area.width()))),
                      min(self.image.height(), max(0, round((point.y()-area.y())*self.image.height()/area.height()))))

    def selection_box(self):
        if self.start is None or self.end is None:
            return None
        a, b = self.pixel_point(self.start), self.pixel_point(self.end)
        left, right = sorted((a.x(), b.x()))
        top, bottom = sorted((a.y(), b.y()))
        return (left, top, right, bottom) if right > left and bottom > top else None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.reject()
        elif event.button() == Qt.MouseButton.LeftButton and self.image_area().contains(event.position().toPoint()):
            self.start = self.end = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start is not None:
            self.end = event.position().toPoint()
            self.box = self.selection_box()
            if self.box is not None:
                self.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202124"))
        painter.setPen(QColor("white"))
        text = self.tr("virtual_region_hint")
        box = self.selection_box()
        if box:
            text += f"  {box[2]-box[0]} × {box[3]-box[1]} px"
        painter.drawText(self.rect().adjusted(12, 8, -12, -8), Qt.AlignmentFlag.AlignTop, text)
        area = self.image_area()
        painter.drawImage(area, self.image)
        if self.start is not None:
            painter.setClipRect(area)
            painter.setPen(QPen(QColor("#48d6ff"), 2))
            painter.drawRect(QRect(self.start, self.end).normalized())


def crop_snapshot(image, tr, previous=None):
    """Return a crop and repeat data; reject changed pixel geometry on repeat."""
    if previous is not None:
        size, box = previous
        if image.size != size:
            raise RuntimeError(tr("virtual_region_changed"))
    else:
        view = RegionPreview(image, tr)
        try:
            if view.exec() != QDialog.DialogCode.Accepted:
                return None, None
            box = view.box
        finally:
            view.hide()
            view.deleteLater()
    return image.crop(box), (image.size, box)
