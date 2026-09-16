from PySide6.QtCore import QLocale, QSettings, Qt
from PySide6.QtGui import QKeySequence

from fshot.i18n import LanguageManager, LanguageMode, _is_traditional_chinese


def test_language_defaults_to_system_and_uses_traditional_chinese(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("zh_TW"))

    assert manager.mode == LanguageMode.SYSTEM
    assert manager.effective_mode == LanguageMode.ZH_TW
    assert manager.text("save") == "儲存"


def test_non_traditional_system_locale_uses_english(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("ja_JP"))

    assert manager.effective_mode == LanguageMode.EN
    assert manager.text("save") == "Save"


def test_macos_traditional_chinese_language_tag_is_recognized():
    assert _is_traditional_chinese("zh-Hant-TW")
    assert _is_traditional_chinese("zh-TW")
    assert not _is_traditional_chinese("zh-Hans-CN")


def test_language_selection_is_persisted(tmp_path):
    path = tmp_path / "settings.ini"
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("en_US"))

    manager.set_mode(LanguageMode.ZH_TW)
    settings.sync()

    restored = LanguageManager(
        QSettings(str(path), QSettings.Format.IniFormat),
        QLocale("en_US"),
    )
    assert restored.mode == LanguageMode.ZH_TW
    assert restored.effective_mode == LanguageMode.ZH_TW


def test_language_cycles_in_expected_order(qt_app, tmp_path):
    from fshot.main_window import EditorWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("en_US"))
    window = EditorWindow(language_manager=manager)

    window._cycle_language()
    assert manager.mode == LanguageMode.ZH_TW
    window._cycle_language()
    assert manager.mode == LanguageMode.EN
    window._cycle_language()
    assert manager.mode == LanguageMode.SYSTEM


def test_language_change_retranslates_toolbar(qt_app, tmp_path):
    from fshot.main_window import EditorWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("en_US"))
    window = EditorWindow(language_manager=manager)

    assert window.save_action.toolTip().startswith("Save (")
    manager.set_mode(LanguageMode.ZH_TW)

    assert window.save_action.toolTip().startswith("儲存 (")
    assert window.measure_action.toolTip().startswith("丈量像素 (")
    assert window.rotate_action.toolTip().startswith("順時針旋轉 90° (")
    assert window.flip_horizontal_action.toolTip().startswith("水平鏡射 (")
    assert window.flip_vertical_action.toolTip().startswith("垂直鏡射 (")
    assert window.resize_image_action.toolTip().startswith("依比例縮小圖片 (")
    assert "繁體中文" in window.language_action.toolTip()


def test_toolbar_tooltips_include_shortcuts(qt_app, tmp_path):
    from fshot.main_window import EditorWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("en_US"))
    window = EditorWindow(language_manager=manager)

    native_pen = QKeySequence("Alt+P").toString(QKeySequence.SequenceFormat.NativeText)
    native_save = QKeySequence.StandardKey.Save
    assert native_pen in window.pen_action.toolTip()
    native_save_text = QKeySequence(native_save).toString(QKeySequence.SequenceFormat.NativeText)
    native_zoom = window.zoom_in_action.shortcuts()[0].toString(
        QKeySequence.SequenceFormat.NativeText
    )
    assert native_save_text in window.save_action.toolTip()
    assert native_zoom in window.zoom_in_action.toolTip()
    native_rotate = QKeySequence("Alt+C").toString(QKeySequence.SequenceFormat.NativeText)
    native_resize = QKeySequence("Alt+S").toString(QKeySequence.SequenceFormat.NativeText)
    assert native_rotate in window.rotate_action.toolTip()
    assert native_resize in window.resize_image_action.toolTip()


def test_line_endpoint_panel_is_translated(qt_app, tmp_path):
    from fshot.main_window import EditorWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("en_US"))
    window = EditorWindow(language_manager=manager)

    assert window.line_start_label.text() == "Start"
    assert window.line_end_combo.itemText(2) == ""
    assert window.line_end_combo.itemIcon(2).isNull() is False
    assert window.line_end_combo.itemData(2, Qt.ItemDataRole.ToolTipRole) == "Solid circle"

    manager.set_mode(LanguageMode.ZH_TW)

    assert window.line_start_label.text() == "起點"
    assert window.line_end_combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == "無箭頭"
    assert window.line_end_combo.itemData(2, Qt.ItemDataRole.ToolTipRole) == "實心圓"


def test_update_messages_are_translated(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    manager = LanguageManager(settings, QLocale("en_US"))

    assert manager.text("check_updates") == "Check for updates..."
    assert manager.text("update_download") == "Open download page"

    manager.set_mode(LanguageMode.ZH_TW)

    assert manager.text("check_updates") == "檢查更新…"
    assert manager.text("update_download") == "開啟下載頁面"
    assert "1.1.0" in manager.text("update_available", current="1.0.0", latest="1.1.0")
