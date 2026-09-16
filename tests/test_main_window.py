from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QImage, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyleOptionViewItem,
    QToolBar,
    QToolButton,
    QWidget,
)

from fshot import __version__
from fshot.canvas import CANVAS_PADDING
from fshot.main_window import _align_scrollbars_to_image


def test_editor_window_title_includes_installed_version(qt_app):
    from fshot.main_window import EditorWindow

    window = EditorWindow()

    assert window.windowTitle() == f"FShot {__version__}"

    window._add_image(QImage(6, 5, QImage.Format.Format_ARGB32), "example.png")

    assert window.windowTitle() == f"FShot {__version__} - example.png"


def test_editor_toolbar_uses_compact_buttons(qt_app):
    from fshot.main_window import EditorWindow

    window = EditorWindow()
    toolbar = window.findChild(QToolBar, "editorToolbar")
    buttons = [
        toolbar.widgetForAction(action)
        for action in toolbar.actions()
        if isinstance(toolbar.widgetForAction(action), QToolButton)
    ]

    assert toolbar.iconSize() == QSize(20, 20)
    assert buttons
    assert window.line_button.size() == QSize(34, 34)
    line_end_button = window.line_end_button
    assert line_end_button.size() == QSize(20, 34)
    assert all(
        button.size() == QSize(34, 34)
        for button in buttons
        if button is not line_end_button
    )
    assert window.measure_action.shortcut() == QKeySequence("Alt+D")
    assert window.rotate_action.shortcut() == QKeySequence("Alt+C")
    assert window.resize_image_action.shortcut() == QKeySequence("Alt+S")
    assert window.flip_horizontal_action.shortcut() == QKeySequence("Alt+H")
    assert window.flip_vertical_action.shortcut() == QKeySequence("Alt+V")
    assert window.style_action.shortcut().isEmpty()
    actions = toolbar.actions()
    assert actions.index(window.mosaic_action) < actions.index(window.rotate_action)
    assert actions.index(window.rotate_action) < actions.index(window.flip_horizontal_action)
    assert actions.index(window.flip_horizontal_action) < actions.index(window.flip_vertical_action)
    assert actions.index(window.flip_vertical_action) < actions.index(window.resize_image_action)
    assert actions.index(window.rotate_action) < actions.index(window.resize_image_action)
    assert actions.index(window.resize_image_action) < actions.index(window.style_action)


def test_image_transform_actions_modify_current_canvas(qt_app):
    from fshot.main_window import ArrowSpinBox, EditorWindow

    window = EditorWindow()
    window._add_image(QImage(10, 8, QImage.Format.Format_ARGB32), "example.png")
    window.show()
    qt_app.processEvents()
    canvas = window._current_canvas()

    window.rotate_current_clockwise()
    assert (canvas.image.width(), canvas.image.height()) == (8, 10)

    window.flip_current_horizontal()
    window.flip_current_vertical()
    assert (canvas.image.width(), canvas.image.height()) == (8, 10)

    menu = window._create_resize_menu()
    percent = menu.findChild(ArrowSpinBox, "resizePercentSpin")
    apply_button = menu.findChild(QPushButton, "resizeApplyButton")

    assert percent is not None
    assert apply_button is not None
    assert percent.buttonSymbols() == QSpinBox.ButtonSymbols.NoButtons
    assert percent.minimumWidth() >= 110
    assert percent.up_button.property("spinArrow") is True
    assert percent.down_button.property("spinArrow") is True
    percent.setValue(50)
    apply_button.click()

    assert (canvas.image.width(), canvas.image.height()) == (4, 5)
    assert window._resize_percent == 50
    assert window._current_doc().is_dirty

    enter_menu = window._create_resize_menu()
    enter_percent = enter_menu.findChild(ArrowSpinBox, "resizePercentSpin")
    enter_percent.setValue(50)
    enter_menu.popup(QPoint(0, 0))
    enter_percent.setFocus()
    qt_app.processEvents()
    QTest.keyClick(enter_percent.lineEdit(), Qt.Key.Key_Return)

    assert (canvas.image.width(), canvas.image.height()) == (2, 2)


def test_line_button_and_dropdown_are_flush(qt_app):
    from fshot.main_window import EditorWindow

    window = EditorWindow()
    window.show()
    qt_app.processEvents()

    assert window.line_button.parentWidget() is window.line_tool_group
    assert window.line_end_button.parentWidget() is window.line_tool_group
    assert window.line_button.geometry().right() + 1 == window.line_end_button.geometry().left()
    assert window.line_button.property("lineToolMain")
    assert window.line_end_button.property("lineToolDropdown")


def test_line_tool_has_independent_endpoint_style_menu(qt_app):
    from fshot.main_window import EditorWindow
    from fshot.settings import LineEndStyle

    window = EditorWindow()

    assert not hasattr(window, "arrow_action")
    assert window.line_end_button.menu() is window.line_end_menu
    assert window.line_start_combo.count() == 3
    assert window.line_end_combo.count() == 3
    for combo in (window.line_start_combo, window.line_end_combo):
        assert combo.iconSize() == QSize(64, 24)
        assert combo.view().iconSize() == combo.iconSize()
        hint = combo.itemDelegate().sizeHint(
            QStyleOptionViewItem(), combo.model().index(0, 0)
        )
        assert hint.width() >= 72
        assert hint.height() >= 32

    original_icon = window.line_action.icon().cacheKey()
    window.line_start_combo.setCurrentIndex(
        window.line_start_combo.findData(LineEndStyle.ARROW.value)
    )
    window.line_end_combo.setCurrentIndex(
        window.line_end_combo.findData(LineEndStyle.CIRCLE.value)
    )

    assert window.settings.line_start_style is LineEndStyle.ARROW
    assert window.settings.line_end_style is LineEndStyle.CIRCLE
    assert window.line_action.icon().cacheKey() != original_icon

    window.line_action.setChecked(True)
    assert window.line_end_button.property("lineSelected") is True


def test_update_can_proceed_without_unsaved_documents(qt_app):
    from fshot.main_window import EditorWindow

    window = EditorWindow()

    assert window.confirm_discard_all("update_discard_all")


def test_image_scrollbars_exclude_canvas_padding(qt_app):
    area = QScrollArea()
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    _align_scrollbars_to_image(area)
    area.resize(600, 400)
    area.show()
    qt_app.processEvents()

    vertical = area.verticalScrollBar()
    horizontal = area.horizontalScrollBar()
    padding = area.findChildren(QWidget, "imageScrollBarPadding")

    assert len(padding) == 5
    assert all(widget.autoFillBackground() for widget in padding)
    assert area.cornerWidget() in padding
    assert vertical.y() == CANVAS_PADDING
    assert vertical.height() == vertical.parentWidget().height() - CANVAS_PADDING * 2
    assert horizontal.x() == CANVAS_PADDING
    assert horizontal.width() == horizontal.parentWidget().width() - CANVAS_PADDING * 2


def test_saved_tab_can_rename_file_inline(qt_app, tmp_path):
    from fshot.main_window import EditorWindow

    source = tmp_path / "old-name.png"
    source.write_bytes(b"image")
    window = EditorWindow()
    image = QImage(6, 5, QImage.Format.Format_ARGB32)
    window._add_image(image, source.name, path=source, dirty=False)

    window.rename_current()

    assert window._tab_name_editor.isVisible()
    assert window._tab_name_editor.text() == "old-name"
    window._tab_name_editor.setText("new-name")
    window._commit_tab_rename()

    target = tmp_path / "new-name.png"
    assert target.exists()
    assert not source.exists()
    assert window.documents[0].path == target
    assert window.tabs.tabText(0) == "new-name"


def test_unsaved_tab_cannot_be_renamed(qt_app):
    from fshot.main_window import EditorWindow

    window = EditorWindow()
    window._add_image(QImage(6, 5, QImage.Format.Format_ARGB32), "new-shot")

    assert not window.rename_action.isEnabled()
    window.rename_current()
    assert not window._tab_name_editor.isVisible()


def test_rename_preserves_dirty_state_and_does_not_replace_existing_file(
    qt_app, tmp_path, monkeypatch
):
    import fshot.main_window as main_window

    source = tmp_path / "old.png"
    existing = tmp_path / "existing.png"
    source.write_bytes(b"old")
    existing.write_bytes(b"existing")
    warnings = []
    monkeypatch.setattr(main_window.QMessageBox, "warning", lambda *args: warnings.append(args))
    window = main_window.EditorWindow()
    window._add_image(
        QImage(6, 5, QImage.Format.Format_ARGB32), source.name, path=source, dirty=True
    )

    window.rename_current()
    window._tab_name_editor.setText("existing")
    window._commit_tab_rename()

    assert source.exists()
    assert existing.read_bytes() == b"existing"
    assert window.documents[0].path == source
    assert window.documents[0].is_dirty
    assert warnings


def test_rename_shortcut_matches_platform_file_manager(qt_app, monkeypatch):
    import fshot.main_window as main_window

    monkeypatch.setattr(main_window.sys, "platform", "darwin")
    mac_window = main_window.EditorWindow()
    assert mac_window.rename_action.shortcut() == QKeySequence("Return")

    monkeypatch.setattr(main_window.sys, "platform", "win32")
    windows_window = main_window.EditorWindow()
    assert windows_window.rename_action.shortcut() == QKeySequence("F2")
