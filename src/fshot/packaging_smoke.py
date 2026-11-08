"""Offline packaged GUI smoke check, without hotkeys or user settings."""
from pathlib import Path
import tempfile


def main() -> int:
    from PySide6.QtCore import QSettings, QLocale
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    from fshot.main_window import EditorWindow
    from fshot.theme import ThemeManager
    from fshot.i18n import LanguageManager
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='fshot-smoke-') as folder:
        settings = QSettings(str(Path(folder) / 'settings.ini'), QSettings.Format.IniFormat)
        window = EditorWindow(theme_manager=ThemeManager(app, settings),
                              language_manager=LanguageManager(settings, QLocale('en_US')),
                              app_settings=settings)
        image = QImage(320, 200, QImage.Format.Format_ARGB32)
        image.fill(0xFFFFFFFF)
        window._add_image(image, 'Packaging smoke check')
        app.processEvents()
        if '320 × 200' not in window.image_size_label.text() or window.windowIcon().isNull():
            raise RuntimeError('Packaged GUI validation failed')
        window.hide()
        window.deleteLater()
        app.processEvents()
    return 0
