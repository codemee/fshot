from PySide6.QtCore import QLocale, QRect, QSettings
from PySide6.QtGui import QImage
from fshot.i18n import LanguageManager, LanguageMode
from fshot.main_window import EditorWindow


def test_status_tracks_active_tabs_panes_and_empty_state(qt_app, tmp_path):
    manager = LanguageManager(QSettings(str(tmp_path / 'lang.ini'), QSettings.Format.IniFormat), QLocale('en_US'))
    window = EditorWindow(language_manager=manager)
    try:
        assert window.image_size_label.text() == 'No image'
        window._add_image(QImage(640, 480, QImage.Format.Format_ARGB32), 'first')
        first = window.tabs
        assert window.image_size_label.text() == 'Image size: 640 × 480 px'
        window._add_image(QImage(320, 200, QImage.Format.Format_ARGB32), 'second')
        assert window.image_size_label.text() == 'Image size: 320 × 200 px'
        window._move_tab(first, 0, first, 'right')
        assert window.image_size_label.text() == 'Image size: 640 × 480 px'
        window._activate_pane(first)
        assert window.image_size_label.text() == 'Image size: 320 × 200 px'
        manager.set_mode(LanguageMode.ZH_TW)
        assert window.image_size_label.text() == '圖片尺寸：320 × 200 像素'
        window._discard_all_tabs()
        assert window.image_size_label.text() == '沒有圖片'
    finally:
        window.hide()
        window.deleteLater()


def test_status_uses_image_pixels_and_updates_after_geometry_changes(qt_app):
    window = EditorWindow()
    try:
        window._add_image(QImage(640, 480, QImage.Format.Format_ARGB32), 'image')
        canvas = window._current_canvas()
        original = window.image_size_label.text()
        canvas.set_zoom(.5)
        assert window.image_size_label.text() == original
        canvas.rotate_clockwise()
        assert '480 × 640' in window.image_size_label.text()
        canvas.scale_down(50)
        assert '240 × 320' in window.image_size_label.text()
        canvas.undo()
        assert '480 × 640' in window.image_size_label.text()
        canvas._crop_rect = QRect(0, 0, 100, 80)
        canvas._apply_crop()
        assert '100 × 80' in window.image_size_label.text()
        canvas.undo()
        assert '480 × 640' in window.image_size_label.text()
    finally:
        window.hide()
        window.deleteLater()
