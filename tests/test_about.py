import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction

import fshot.main_window as main_window
from fshot import __version__
from fshot.i18n import LanguageManager, LanguageMode


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_about_action_shares_version_and_license_information(qt_app, tmp_path, monkeypatch, platform):
    monkeypatch.setattr(main_window.sys, "platform", platform)
    language = LanguageManager(QSettings(str(tmp_path / "language.ini"), QSettings.Format.IniFormat))
    window = main_window.EditorWindow(language_manager=language)
    messages = []
    monkeypatch.setattr(main_window.MessageDialog, "information", lambda *args: messages.append(args))
    try:
        if platform == "darwin":
            assert window.application_menu_bar.parent() is None
            assert window.about_action in window.about_menu.actions()
            assert window.about_action.menuRole() == QAction.MenuRole.AboutRole
            assert not window.isVisible()
        else:
            assert window.application_menu_bar is None
        for mode in (LanguageMode.EN, LanguageMode.ZH_TW):
            language.set_mode(mode)
            assert window.about_action.text() == language.text("about_fshot")
            window.about_action.trigger()
            parent, title, text = messages[-1]
            assert parent is window
            assert title == language.text("about_fshot")
            assert __version__ in text
            assert "GPL-3.0-or-later" in text
            assert "https://github.com/codemee/fshot" in text
            if platform == "darwin":
                assert window.about_menu.title() == language.text("help_menu")
    finally:
        if window.application_menu_bar is not None:
            window.application_menu_bar.deleteLater()
        window.deleteLater()
