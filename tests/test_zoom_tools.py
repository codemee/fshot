import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QPushButton, QToolBar

from fshot.canvas import CANVAS_PADDING
from fshot.main_window import ArrowSpinBox, EditorWindow


def test_fit_uses_available_viewport_without_changing_image(qt_app, tmp_path):
    window = EditorWindow()
    window.resize(700, 500)
    image = QImage(3000, 2000, QImage.Format.Format_ARGB32)
    window._add_image(image, "large", path=tmp_path / "large.png", dirty=False)
    qt_app.processEvents()
    canvas = window._current_canvas()
    try:
        window.zoom_fit_action.trigger()
        qt_app.processEvents()
        area = window._current_area()
        assert canvas.width() <= area.viewport().width()
        assert canvas.height() <= area.viewport().height()
        assert canvas.width() > CANVAS_PADDING * 2
        assert canvas.image.size() == image.size()
        assert not window._current_doc().is_dirty
        assert canvas.zoom < 1
        assert window.zoom_percent_action.text() != "100%"
    finally:
        window.hide()
        window.deleteLater()


def test_zoom_display_tracks_tabs_and_reset(qt_app, tmp_path):
    window = EditorWindow()
    try:
        assert not window.zoom_percent_action.isEnabled()
        assert not window.zoom_fit_action.isEnabled()
        window._add_image(QImage(100, 100, QImage.Format.Format_ARGB32), "first", path=tmp_path / "first.png", dirty=False)
        first = window._current_canvas()
        window.zoom_in()
        assert window.zoom_percent_action.text() == "125%"
        window._add_image(QImage(100, 100, QImage.Format.Format_ARGB32), "second", dirty=False)
        assert window.zoom_percent_action.text() == "100%"
        window.tabs.setCurrentIndex(0)
        assert window.zoom_percent_action.text() == "125%"
        window.zoom_reset()
        assert first.zoom == 1
        assert window.zoom_percent_action.text() == "100%"
        assert not window._current_doc().is_dirty
    finally:
        window.hide()
        window.deleteLater()


@pytest.mark.parametrize("method", ["button", "enter", "cancel"])
def test_zoom_input_applies_only_on_confirmation(qt_app, tmp_path, method):
    window = EditorWindow()
    window._add_image(QImage(100, 100, QImage.Format.Format_ARGB32), "image", path=tmp_path / "image.png", dirty=False)

    def edit():
        menu = QApplication.activePopupWidget()
        assert isinstance(menu, QMenu)
        spin = menu.findChild(ArrowSpinBox, "zoomPercentSpin")
        spin.setValue(175)
        if method == "button":
            menu.findChild(QPushButton, "zoomApplyButton").click()
        elif method == "enter":
            QTest.keyClick(spin, Qt.Key.Key_Return)
        else:
            menu.close()

    QTimer.singleShot(0, edit)
    try:
        window._show_zoom_panel()
        assert window._current_canvas().zoom == (1 if method == "cancel" else 1.75)
        assert window.zoom_percent_action.text() == ("100%" if method == "cancel" else "175%")
        assert not window._current_doc().is_dirty
    finally:
        window.hide()
        window.deleteLater()


def test_zoom_group_separator_and_overflow(qt_app):
    window = EditorWindow()
    window._add_image(QImage(100, 100, QImage.Format.Format_ARGB32), "image")
    window.resize(420, 400)
    qt_app.processEvents()
    try:
        toolbar = window.findChild(QToolBar)
        actions = toolbar.actions()
        cursor_index = actions.index(window.cursor_action)
        assert actions[cursor_index - 1].isSeparator()
        menu = QMenu()
        window._populate_toolbar_overflow(toolbar, menu)
        assert window.zoom_fit_action in menu.actions()
        assert window.zoom_percent_action in menu.actions()
    finally:
        window.hide()
        window.deleteLater()
