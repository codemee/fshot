from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette

from fshot.theme import ThemeManager, ThemeMode, _palette


def test_theme_defaults_to_system(qt_app, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = ThemeManager(qt_app, settings)

    assert manager.mode == ThemeMode.SYSTEM
    assert manager.effective_mode in {ThemeMode.LIGHT, ThemeMode.DARK}


def test_theme_selection_is_persisted(qt_app, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = ThemeManager(qt_app, settings)

    manager.set_mode(ThemeMode.DARK)
    settings.sync()

    restored = ThemeManager(
        qt_app,
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )
    assert restored.mode == ThemeMode.DARK
    assert restored.effective_mode == ThemeMode.DARK


def test_invalid_stored_theme_falls_back_to_system(qt_app, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("appearance/theme", "unknown")

    manager = ThemeManager(qt_app, settings)

    assert manager.mode == ThemeMode.SYSTEM


def test_explicit_theme_cycles_in_expected_order(qt_app, tmp_path):
    from fshot.main_window import EditorWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = ThemeManager(qt_app, settings)
    window = EditorWindow(manager)

    window._cycle_theme()
    assert manager.mode == ThemeMode.LIGHT
    window._cycle_theme()
    assert manager.mode == ThemeMode.DARK
    window._cycle_theme()
    assert manager.mode == ThemeMode.SYSTEM


def test_arrow_spinbox_buttons_change_value(qt_app):
    from fshot.main_window import ArrowSpinBox

    spinbox = ArrowSpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)

    spinbox.up_button.click()
    assert spinbox.value() == 6
    spinbox.down_button.click()
    assert spinbox.value() == 5


def test_dark_palette_preserves_text_contrast(qt_app):
    palette = _palette(ThemeMode.DARK)

    def luminance(color):
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                  for value in channels]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    for foreground, background in (
        (QPalette.ColorRole.WindowText, QPalette.ColorRole.Window),
        (QPalette.ColorRole.Text, QPalette.ColorRole.Base),
        (QPalette.ColorRole.ButtonText, QPalette.ColorRole.Button),
        (QPalette.ColorRole.HighlightedText, QPalette.ColorRole.Highlight),
        (QPalette.ColorRole.ToolTipText, QPalette.ColorRole.ToolTipBase),
    ):
        values = sorted((luminance(palette.color(foreground)), luminance(palette.color(background))))
        assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5, (foreground, background)
