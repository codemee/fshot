from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest

from fshot.canvas import CANVAS_PADDING, ImageCanvas
from fshot.settings import DrawingSettings, LineEndStyle, Tool


def _colored_pixels(image: QImage, left: int, top: int, right: int, bottom: int) -> int:
    white = QColor("white")
    return sum(
        QColor(image.pixel(x, y)) != white
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
    )


def test_line_draws_independent_circle_and_arrow_endpoints(qt_app):
    image = QImage(60, 40, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    settings = DrawingSettings(
        color=QColor("#e03131"),
        line_width=3,
        line_start_style=LineEndStyle.CIRCLE,
        line_end_style=LineEndStyle.ARROW,
    )
    canvas = ImageCanvas(image, settings)
    painter = QPainter(canvas.image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(canvas._pen())

    canvas._draw_line(painter, QPoint(10, 20), QPoint(45, 20), scaled=False)
    painter.end()

    # The circle colors pixels away from the horizontal shaft at the start.
    assert _colored_pixels(canvas.image, 8, 16, 12, 18) > 0
    # The open arrow colors pixels above the shaft near the end.
    assert _colored_pixels(canvas.image, 30, 11, 44, 18) > 0


def test_measure_tool_reports_pixel_deltas_without_modifying_image(qt_app):
    image = QImage(80, 60, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    canvas = ImageCanvas(image, DrawingSettings.default())
    canvas.set_tool(Tool.MEASURE)
    canvas.show()

    start = QPoint(CANVAS_PADDING + 10, CANVAS_PADDING + 12)
    end = QPoint(CANVAS_PADDING + 43, CANVAS_PADDING + 37)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, end)

    assert canvas.measurement == (33, 25)

    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)

    assert canvas.measurement == (33, 25)
    assert not canvas.can_undo
    exported = canvas.export_image()
    assert all(
        QColor(exported.pixel(x, y)) == QColor("white")
        for y in range(image.height())
        for x in range(image.width())
    )

    canvas.set_tool(Tool.RECTANGLE)
    assert canvas.measurement is None
