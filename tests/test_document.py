from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QMimeData, QSettings, QUrl
from PySide6.QtGui import QImage

from fshot.document import ShotDocument, make_tab_title


def test_make_tab_title_format():
    assert make_tab_title(datetime(2026, 7, 9, 5, 6, 7)) == "26-07-09-050607"


def test_dirty_state_transitions():
    doc = ShotDocument(title="26-07-09-050607", image=None)
    assert doc.is_unsaved
    assert doc.is_dirty
    assert doc.can_save
    assert doc.display_title == "26-07-09-050607"

    doc.mark_saved("C:/tmp/example.png")
    assert not doc.is_unsaved
    assert not doc.is_dirty
    assert not doc.can_save

    doc.mark_dirty()
    assert doc.can_save


def test_rename_updates_path_and_title_without_clearing_dirty_state():
    doc = ShotDocument("old", None, path=Path("C:/tmp/old.png"), dirty=True)

    doc.mark_renamed("C:/tmp/new.png")

    assert doc.path == Path("C:/tmp/new.png")
    assert doc.title == "new"
    assert doc.is_dirty


def test_reindex_after_middle_tab_close(qt_app):
    from fshot.main_window import EditorWindow

    window = EditorWindow()
    docs = {
        0: ShotDocument("first", None),
        1: ShotDocument("second", None),
        2: ShotDocument("third", None),
    }
    window.documents = docs

    window._reindex_documents(1)

    assert window.documents[0].title == "first"
    assert window.documents[1].title == "third"
    assert 2 not in window.documents


def test_windows_dirty_marker_is_left_of_tab_title(qt_app, monkeypatch):
    from PySide6.QtWidgets import QTabBar

    import fshot.main_window as main_window

    monkeypatch.setattr(main_window.sys, "platform", "win32")
    window = main_window.EditorWindow()
    index = window.tabs.addTab(main_window.QWidget(), "example")

    status = window._ensure_tab_status_widget(index)

    assert window.tabs.tabBar().tabButton(index, QTabBar.ButtonPosition.LeftSide) is status
    assert status.layout().contentsMargins().right() == 6
    assert window.tabs.tabBar().tabButton(index, QTabBar.ButtonPosition.RightSide) is not None


def test_open_image_uses_supplied_filename_as_tab_title(qt_app, tmp_path):
    from fshot.main_window import EditorWindow

    path = tmp_path / "sample-image.png"
    Image.new("RGB", (12, 8), "red").save(path)
    window = EditorWindow()

    assert window._open_image_path(path, path.name, remember_path=True)
    assert window.tabs.tabText(0) == "sample-image.png"
    assert window.documents[0].path == path
    assert not window.documents[0].is_dirty
    assert not window.save_action.isEnabled()


def test_mime_image_paths_accepts_local_files(tmp_path):
    from fshot.main_window import EditorWindow

    path = tmp_path / "drop.png"
    Image.new("RGB", (4, 4), "blue").save(path)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])

    assert EditorWindow._image_paths_from_mime(mime) == [path]


def test_paste_image_uses_screenshot_title(qt_app):
    from fshot.main_window import EditorWindow

    qt_app.clipboard().setImage(QImage(6, 5, QImage.Format.Format_ARGB32))
    window = EditorWindow()
    window.paste_image()

    assert window.tabs.count() == 1
    assert len(window.tabs.tabText(0)) == len("26-07-09-050607")


def test_unsaved_document_uses_persisted_last_save_directory(qt_app, tmp_path):
    from fshot.main_window import LAST_SAVE_DIRECTORY_KEY, EditorWindow

    settings_path = tmp_path / "settings.ini"
    save_directory = tmp_path / "screenshots"
    save_directory.mkdir()
    settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    settings.setValue(LAST_SAVE_DIRECTORY_KEY, str(save_directory))
    settings.sync()

    reloaded_settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    window = EditorWindow(app_settings=reloaded_settings)
    doc = ShotDocument("new-shot", None)

    assert window._default_save_path(doc) == save_directory / "new-shot.png"


def test_document_path_takes_priority_over_last_save_directory(qt_app, tmp_path):
    from fshot.main_window import LAST_SAVE_DIRECTORY_KEY, EditorWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(LAST_SAVE_DIRECTORY_KEY, str(tmp_path / "recent"))
    window = EditorWindow(app_settings=settings)
    document_path = tmp_path / "original" / "existing.jpg"

    assert (
        window._default_save_path(ShotDocument("existing", None, path=document_path))
        == document_path
    )


def test_missing_last_save_directory_falls_back_to_working_directory(
    qt_app, tmp_path, monkeypatch
):
    from fshot.main_window import LAST_SAVE_DIRECTORY_KEY, EditorWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(LAST_SAVE_DIRECTORY_KEY, str(tmp_path / "missing"))
    window = EditorWindow(app_settings=settings)
    monkeypatch.chdir(tmp_path)

    assert window._default_save_path(ShotDocument("new-shot", None)) == tmp_path / "new-shot.png"


def test_successful_save_updates_last_save_directory(qt_app, tmp_path):
    from fshot.main_window import LAST_SAVE_DIRECTORY_KEY, EditorWindow

    settings_path = tmp_path / "settings.ini"
    settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    window = EditorWindow(app_settings=settings)
    image = QImage(6, 5, QImage.Format.Format_ARGB32)
    image.fill(0)
    window._add_image(image, "new-shot")
    target_directory = tmp_path / "saved"
    target_directory.mkdir()

    window._save_to_path(window.documents[0], target_directory / "result.png")
    settings.sync()
    reloaded_settings = QSettings(str(settings_path), QSettings.Format.IniFormat)

    assert reloaded_settings.value(LAST_SAVE_DIRECTORY_KEY) == str(target_directory)


def test_failed_save_does_not_replace_last_save_directory(qt_app, tmp_path, monkeypatch):
    import fshot.main_window as main_window

    previous_directory = tmp_path / "previous"
    previous_directory.mkdir()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(main_window.LAST_SAVE_DIRECTORY_KEY, str(previous_directory))
    window = main_window.EditorWindow(app_settings=settings)
    image = QImage(6, 5, QImage.Format.Format_ARGB32)
    window._add_image(image, "new-shot")
    monkeypatch.setattr(main_window.MessageDialog, "warning", lambda *_args: None)

    window._save_to_path(window.documents[0], tmp_path / "missing" / "failed.png")

    assert settings.value(main_window.LAST_SAVE_DIRECTORY_KEY) == str(previous_directory)


def test_cancelled_save_does_not_replace_last_save_directory(qt_app, tmp_path, monkeypatch):
    import fshot.main_window as main_window

    previous_directory = tmp_path / "previous"
    previous_directory.mkdir()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(main_window.LAST_SAVE_DIRECTORY_KEY, str(previous_directory))
    window = main_window.EditorWindow(app_settings=settings)
    image = QImage(6, 5, QImage.Format.Format_ARGB32)
    window._add_image(image, "new-shot")
    monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName", lambda *_args: ("", ""))

    window.save_current_as()

    assert settings.value(main_window.LAST_SAVE_DIRECTORY_KEY) == str(previous_directory)
