import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtTest import QTest
from fshot.canvas import ImageCanvas
from fshot.settings import DrawingSettings, LineEndStyle, ShapeStyle, Tool
from fshot.main_window import EditorWindow


def mouse(canvas, kind, point, shift=False):
    position = QPointF(canvas._to_widget(point))
    event = QMouseEvent(kind, position, position,
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier)
    {QEvent.Type.MouseButtonPress: canvas.mousePressEvent,
     QEvent.Type.MouseMove: canvas.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: canvas.mouseReleaseEvent}[kind](event)


def make_canvas():
    image=QImage(200,180,QImage.Format.Format_ARGB32)
    image.fill(QColor('white'))
    settings=DrawingSettings(QColor('red'), line_width=1,
        line_start_style=LineEndStyle.NONE, line_end_style=LineEndStyle.NONE)
    return ImageCanvas(image,settings)


@pytest.mark.parametrize('end,expected',[(QPoint(130,80),QPoint(130,50)),(QPoint(70,130),QPoint(50,130))])
def test_shift_line_previews_and_draws_axis_aligned(qt_app,end,expected):
    canvas=make_canvas();canvas.set_tool(Tool.LINE)
    mouse(canvas,QEvent.Type.MouseButtonPress,QPoint(50,50))
    mouse(canvas,QEvent.Type.MouseMove,end,True)
    assert canvas._preview == expected
    mouse(canvas,QEvent.Type.MouseButtonRelease,end,True)
    midpoint=(QPoint(50,50)+expected)/2
    assert canvas.image.pixelColor(midpoint).red() > canvas.image.pixelColor(midpoint).green()
    assert canvas.can_undo
    canvas.undo()
    assert canvas.image.pixelColor(midpoint) == QColor('white')


def test_shift_press_and_release_update_preview_without_moving(qt_app):
    canvas=make_canvas();canvas.set_tool(Tool.LINE)
    mouse(canvas,QEvent.Type.MouseButtonPress,QPoint(50,50))
    mouse(canvas,QEvent.Type.MouseMove,QPoint(130,80))
    QTest.keyPress(canvas,Qt.Key.Key_Shift)
    assert canvas._preview == QPoint(130,50)
    QTest.keyRelease(canvas,Qt.Key.Key_Shift)
    assert canvas._preview == QPoint(130,80)


@pytest.mark.parametrize('shape',list(ShapeStyle))
@pytest.mark.parametrize('end',[QPoint(160,100),QPoint(5,100),QPoint(160,5),QPoint(5,5),QPoint(199,179)])
def test_shift_shapes_keep_equal_sides_and_stay_inside_image(qt_app,shape,end):
    canvas=make_canvas();canvas.set_tool(Tool.RECTANGLE);canvas.settings.shape_style=shape
    start=QPoint(50,50)
    mouse(canvas,QEvent.Type.MouseButtonPress,start)
    mouse(canvas,QEvent.Type.MouseMove,end,True)
    preview=canvas._preview
    assert abs(preview.x()-start.x()) == abs(preview.y()-start.y())
    assert 0 <= preview.x() < 200 and 0 <= preview.y() < 180
    mouse(canvas,QEvent.Type.MouseButtonRelease,end,True)
    assert canvas._preview is None
    assert canvas.image != make_canvas().image
    canvas.undo()
    assert canvas.image == make_canvas().image


def test_ellipse_and_rectangle_draw_distinct_outlines(qt_app):
    images=[]
    for shape in ShapeStyle:
        canvas=make_canvas();canvas.set_tool(Tool.RECTANGLE);canvas.settings.shape_style=shape
        mouse(canvas,QEvent.Type.MouseButtonPress,QPoint(40,40))
        mouse(canvas,QEvent.Type.MouseButtonRelease,QPoint(140,100))
        images.append(canvas.image.copy())
    assert images[0] != images[1]
    assert images[0].pixelColor(40,40) != QColor('white')
    assert images[1].pixelColor(40,40) == QColor('white')


def test_shape_menu_selects_tool_and_updates_icon(qt_app):
    window=EditorWindow()
    try:
        window._add_image(QImage(50,50,QImage.Format.Format_ARGB32),'test')
        original=window.rect_action.icon().cacheKey()
        window.shape_actions[ShapeStyle.ELLIPSE].trigger()
        assert window.settings.shape_style is ShapeStyle.ELLIPSE
        assert window.active_tool is Tool.RECTANGLE
        assert window.rect_action.isChecked()
        assert window.shape_actions[ShapeStyle.ELLIPSE].isChecked()
        assert window.rect_action.icon().cacheKey() != original
        window.shape_actions[ShapeStyle.RECTANGLE].trigger()
        assert window.settings.shape_style is ShapeStyle.RECTANGLE
    finally:
        window.hide();window.deleteLater()
