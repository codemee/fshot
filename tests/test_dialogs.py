import pytest
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from fshot.dialogs import MessageDialog
from fshot.main_window import EditorWindow
from fshot.theme import ThemeManager, ThemeMode


@pytest.mark.parametrize("mode", [ThemeMode.LIGHT, ThemeMode.DARK])
@pytest.mark.parametrize("kind", ["warning", "information", "question", "unsaved", "update", "capture"])
@pytest.mark.parametrize("long_message", [False, True])
def test_message_dialogs_use_content_height(qt_app, tmp_path, monkeypatch, mode, kind, long_message):
    manager = ThemeManager(qt_app, QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat))
    manager.set_mode(mode)
    parent = EditorWindow(manager)
    text = ("Details\n" * 80 if long_message else
            "Native global hotkeys unavailable: [WinError 1409] 快速鍵已登錄。")
    original_exec = MessageDialog.exec
    observations = []

    def inspect(dialog):
        # Reproduce oversized initial geometry, including before app.exec().
        dialog.resize(560, 2000)

        def record():
            observations.append((dialog.height(), dialog.body.height(),
                                 dialog.heading.height(), dialog.body.verticalScrollBar().maximum()))
            dialog.reject()

        QTimer.singleShot(0, record)
        return original_exec(dialog)

    monkeypatch.setattr(MessageDialog, "exec", inspect)
    try:
        if kind == "unsaved":
            MessageDialog.unsaved(parent, "未儲存的截圖", text, multiple=True)
        elif kind in {"update", "capture"}:
            dialog = MessageDialog(parent)
            dialog.setText(text)
            for label in (["Update", "Later", "Skip"] if kind == "update" else ["OK"]):
                dialog.addButton(label, MessageDialog.ButtonRole.AcceptRole)
            dialog.exec()
            dialog.deleteLater()
        else:
            getattr(MessageDialog, kind)(parent, "FShot", text)
        height, body_height, heading_height, scroll_max = observations[0]
        assert height < (500 if long_message else 300)
        assert body_height <= 240
        assert heading_height < 80
        assert scroll_max > 0 if long_message else scroll_max == 0
    finally:
        parent.hide()
        parent.deleteLater()
        manager.set_mode(ThemeMode.SYSTEM)
        manager.deleteLater()


@pytest.mark.parametrize("key", [Qt.Key.Key_Escape, Qt.Key.Key_Return])
def test_unsaved_dialog_keyboard_defaults_to_cancel(qt_app, key):
    def cancel():
        dialog = QApplication.activeModalWidget()
        assert dialog.findChild(QPushButton, "cancel").isDefault()
        QTest.keyClick(dialog, key)

    QTimer.singleShot(0, cancel)
    assert MessageDialog.unsaved(None, "Unsaved screenshots", "3 screenshots", multiple=True) == MessageDialog.StandardButton.Cancel


@pytest.mark.parametrize("button,result", [
    ("save", MessageDialog.StandardButton.Save),
    ("discard", MessageDialog.StandardButton.Discard),
])
def test_unsaved_dialog_returns_explicit_action(qt_app, button, result):
    QTimer.singleShot(0, lambda: QApplication.activeModalWidget().findChild(QPushButton, button).click())
    assert MessageDialog.unsaved(None, "Unsaved screenshots", "3 screenshots", multiple=True) == result


@pytest.mark.parametrize("existing_paths", [False, True])
def test_save_all_before_closing_saves_each_document_image(qt_app, tmp_path, monkeypatch, existing_paths):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = EditorWindow(app_settings=settings)
    colors = (QColor("red"), QColor("blue"))
    targets = [tmp_path / f"saved-{index}.png" for index in range(2)]
    for index, color in enumerate(colors):
        image = QImage(20, 10, QImage.Format.Format_ARGB32)
        image.fill(color)
        window._add_image(image, f"image-{index}", path=targets[index] if existing_paths else None)
    monkeypatch.setattr(MessageDialog, "unsaved", lambda *args, **kwargs: MessageDialog.StandardButton.Save)
    choices = iter(targets)
    monkeypatch.setattr("fshot.main_window.QFileDialog.getSaveFileName", lambda *args: (str(next(choices)), "PNG"))
    try:
        window.close()
        assert window.tabs.count() == 0
        assert not window.isVisible()
        for path, color in zip(targets, colors):
            assert QImage(str(path)).pixelColor(0, 0) == color
    finally:
        window.hide()
        window.deleteLater()


@pytest.mark.parametrize("failure", ["cancel", "write_error"])
def test_cancelled_or_failed_save_keeps_window_and_tabs(qt_app, tmp_path, monkeypatch, failure):
    window = EditorWindow()
    image = QImage(20, 10, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    window._add_image(image, "unsaved")
    doc = window._current_doc()
    monkeypatch.setattr(MessageDialog, "unsaved", lambda *args, **kwargs: MessageDialog.StandardButton.Save)
    target = "" if failure == "cancel" else str(tmp_path / "missing" / "image.png")
    monkeypatch.setattr("fshot.main_window.QFileDialog.getSaveFileName", lambda *args: (target, "PNG"))
    warnings = []
    monkeypatch.setattr(MessageDialog, "warning", lambda *args: warnings.append(args))
    try:
        window.close()
        assert window.isVisible()
        assert window.tabs.count() == 1
        assert doc.is_dirty
        assert doc.path is None
        assert bool(warnings) == (failure == "write_error")
    finally:
        window.hide()
        window.deleteLater()


def test_partial_save_does_not_discard_remaining_documents(qt_app, tmp_path, monkeypatch):
    window = EditorWindow()
    for title in ("first", "second"):
        window._add_image(QImage(20, 10, QImage.Format.Format_ARGB32), title)
    docs = list(window.documents.values())
    choices = iter((str(tmp_path / "first.png"), ""))
    monkeypatch.setattr(MessageDialog, "unsaved", lambda *args, **kwargs: MessageDialog.StandardButton.Save)
    monkeypatch.setattr("fshot.main_window.QFileDialog.getSaveFileName", lambda *args: (next(choices), "PNG"))
    try:
        window.close()
        assert window.tabs.count() == 2
        assert not docs[0].is_dirty
        assert docs[1].is_dirty
        assert window.isVisible()
    finally:
        window.hide()
        window.deleteLater()


def test_question_escape_does_not_confirm(qt_app):
    QTimer.singleShot(0, lambda: QApplication.activeModalWidget().reject())
    assert MessageDialog.question(None, "Confirm action", "Continue?") == MessageDialog.StandardButton.No


def test_long_error_is_bounded_scrollable_plain_text(qt_app):
    dialog = MessageDialog()
    text = "<b>literal filename</b>\n" + "Error details\n" * 80
    dialog.setText(text)
    dialog.addButton("OK", MessageDialog.ButtonRole.AcceptRole)
    dialog.show()
    qt_app.processEvents()
    try:
        assert dialog.body.toPlainText() == text
        assert dialog.body.height() <= 240
        assert dialog.height() < 500
        assert dialog.body.verticalScrollBar().maximum() > 0
    finally:
        dialog.hide()
        dialog.deleteLater()


def test_save_noncurrent_tab_before_closing_it(qt_app, tmp_path, monkeypatch):
    window = EditorWindow()
    target = tmp_path / "first.png"
    first = QImage(20, 10, QImage.Format.Format_ARGB32)
    first.fill(QColor("red"))
    second = first.copy()
    second.fill(QColor("blue"))
    window._add_image(first, "first.png", path=target)
    window._add_image(second, "second.png", path=tmp_path / "second.png")
    remaining = window._current_doc()
    monkeypatch.setattr(MessageDialog, "unsaved", lambda *args, **kwargs: MessageDialog.StandardButton.Save)
    try:
        window._close_tab(0)
        assert QImage(str(target)).pixelColor(0, 0) == QColor("red")
        assert window.tabs.count() == 1
        assert window._current_doc() is remaining
        assert remaining.is_dirty
    finally:
        window.hide()
        window.deleteLater()
