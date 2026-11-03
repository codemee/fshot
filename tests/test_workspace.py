from pathlib import Path
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QSplitter
from fshot.main_window import EditorWindow
from fshot.settings import Tool


@pytest.fixture
def editor(qt_app):
    window = EditorWindow()
    for name in ('first', 'second', 'third'):
        window._add_image(QImage(80, 60, QImage.Format.Format_ARGB32), name, path=Path(name + '.png'), dirty=False)
    window.show()
    qt_app.processEvents()
    yield window
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.parametrize('edge,orientation,position', [
    ('left', Qt.Orientation.Horizontal, 0),
    ('right', Qt.Orientation.Horizontal, 1),
    ('bottom', Qt.Orientation.Vertical, 1),
])
def test_split_preserves_document_and_canvas(editor, qt_app, edge, orientation, position):
    source = editor.tabs
    page = source.widget(0)
    doc = source.documents[0]
    doc.image.set_zoom(1.75)
    editor._move_tab(source, 0, source, edge)
    qt_app.processEvents()
    assert len(editor.workspace.panes) == 2
    target = editor.tabs
    assert target.currentWidget() is page
    assert editor._current_doc() is doc
    assert editor._current_canvas().zoom == 1.75
    assert source.count() == 2
    root = editor.workspace.root
    assert root.orientation() == orientation
    assert root.widget(position) is target
    assert sum(root.sizes()) > 0
    assert source.tabBar() is not target.tabBar()
    assert len(editor._all_documents()) == 3


def test_nested_split_merge_and_empty_pane_collapse(editor, qt_app):
    first = editor.tabs
    editor._move_tab(first, 0, first, 'right')
    second = editor.tabs
    editor._move_tab(first, 0, second, 'bottom')
    third = editor.tabs
    assert len(editor.workspace.panes) == 3
    assert isinstance(second.parentWidget(), QSplitter)
    assert second.parentWidget().orientation() == Qt.Orientation.Vertical
    editor._move_tab(third, 0, first)
    assert len(editor.workspace.panes) == 2
    assert editor.workspace.root.count() == 2
    editor._move_tab(second, 0, first)
    assert len(editor.workspace.panes) == 1
    assert editor.workspace.root is first
    assert first.count() == 3
    assert {doc.title for doc in editor._all_documents()} == {'first', 'second', 'third'}


def test_dirty_changes_and_actions_use_the_correct_pane(editor, qt_app, monkeypatch):
    first = editor.tabs
    doc = first.documents[0]
    editor._move_tab(first, 0, first, 'right')
    second = editor.tabs
    editor._activate_pane(first)
    doc.image.changed.emit()
    assert doc.is_dirty
    assert not first.documents[0].is_dirty
    observed = []
    monkeypatch.setattr(editor, '_confirm_unsaved', lambda docs, key: observed.extend(docs) or False)
    assert not editor.confirm_discard_all()
    assert observed == [doc]
    editor._activate_pane(second)
    editor.zoom_in()
    assert doc.image.zoom == 1.25
    editor._activate_pane(first)
    assert editor._current_canvas().zoom == 1


def test_close_last_tab_collapses_pane_and_preserves_other_documents(editor):
    first = editor.tabs
    editor._move_tab(first, 0, first, 'bottom')
    editor._close_tab(0)
    assert editor.workspace.panes == [first]
    assert first.count() == 2
    assert len(editor._all_documents()) == 2


def test_reorder_and_single_tab_split_noop(editor):
    pane = editor.tabs
    editor._move_tab(pane, 0, pane, insertion=2)
    assert [pane.documents[i].title for i in range(3)] == ['second', 'third', 'first']
    editor._discard_all_tabs()
    editor._add_image(QImage(10, 10, QImage.Format.Format_ARGB32), 'only', dirty=False)
    editor._move_tab(pane, 0, pane, 'right')
    assert len(editor.workspace.panes) == 1


def test_drop_regions_include_tab_merge_and_directional_split(editor):
    pane = editor.tabs
    pane.resize(800, 500)
    assert pane.drop_edge(QPoint(10, 250)) == 'left'
    assert pane.drop_edge(QPoint(790, 250)) == 'right'
    assert pane.drop_edge(QPoint(400, 490)) == 'bottom'
    assert pane.drop_edge(QPoint(400, 250)) == 'center'
    assert pane.drop_edge(QPoint(10, 5)) == 'center'

def test_drop_event_moves_tab_and_dismisses_preview(editor, qt_app):
    from PySide6.QtCore import QMimeData, QPointF
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
    from PySide6.QtWidgets import QApplication
    from fshot.workspace import TAB_MIME
    pane = editor.tabs
    page = pane.widget(0)
    editor.workspace.dragged = (pane, page)
    mime = QMimeData()
    mime.setData(TAB_MIME, editor.workspace.token.encode())
    point = QPoint(pane.width() - 5, pane.height() // 2)
    enter = QDragEnterEvent(point, Qt.DropAction.MoveAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(pane, enter)
    assert enter.isAccepted()
    move = QDragMoveEvent(point, Qt.DropAction.MoveAction, mime,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(pane, move)
    assert not pane.preview.isHidden()
    drop = QDropEvent(QPointF(point), Qt.DropAction.MoveAction, mime,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(pane, drop)
    assert drop.isAccepted()
    assert editor.tabs.currentWidget() is page
    assert len(editor.workspace.panes) == 2
    assert pane.preview.isHidden()
    editor.workspace.dragged = None


def test_splitter_ratio_and_click_activation(editor, qt_app):
    from PySide6.QtTest import QTest
    first = editor.tabs
    editor._move_tab(first, 0, first, 'right')
    second = editor.tabs
    qt_app.processEvents()
    root = editor.workspace.root
    root.setSizes([250, 750])
    qt_app.processEvents()
    left, right = root.sizes()
    assert right > left * 2
    QTest.mouseClick(first.currentWidget().widget(), Qt.MouseButton.LeftButton, pos=QPoint(35, 35))
    assert editor.tabs is first
    assert first.property('activePane') is True
    assert second.property('activePane') is False


def test_save_in_other_pane_and_close_cancellation(editor, tmp_path, monkeypatch):
    first = editor.tabs
    doc = first.documents[0]
    editor._move_tab(first, 0, first, 'right')
    second = editor.tabs
    editor._activate_pane(first)
    target = tmp_path / 'saved.png'
    assert editor._save_to_path(doc, target)
    assert target.exists()
    assert not doc.is_dirty
    assert second.tabText(0) == 'saved'
    doc.mark_dirty()
    monkeypatch.setattr(editor, '_confirm_unsaved', lambda docs, key: False)
    editor._activate_pane(second)
    editor._close_tab(0)
    assert second.count() == 1
    assert len(editor.workspace.panes) == 2

def test_drag_gesture_and_cancel_preserve_documents(editor, monkeypatch):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from fshot.workspace import QDrag, TAB_MIME
    pane = editor.tabs
    bar = pane.tabBar()
    origin = bar.tabRect(0).center()
    calls = []
    def cancel_drag(drag, actions):
        calls.append(bytes(drag.mimeData().data(TAB_MIME)))
        assert editor.workspace.dragged == (pane, pane.widget(0))
        return Qt.DropAction.IgnoreAction
    monkeypatch.setattr(QDrag, 'exec', cancel_drag)
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(origin), QPointF(bar.mapToGlobal(origin)),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(bar, press)
    point = origin + QPoint(50, 50)
    move = QMouseEvent(QEvent.Type.MouseMove, QPointF(point), QPointF(bar.mapToGlobal(point)),
                       Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(bar, move)
    assert calls == [editor.workspace.token.encode()]
    assert editor.workspace.dragged is None
    assert pane.count() == 3
    assert len(editor.workspace.panes) == 1

def test_external_image_drop_opens_in_target_pane(editor, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, QUrl
    from PySide6.QtGui import QDropEvent
    first = editor.tabs
    editor._move_tab(first, 0, first, 'right')
    second = editor.tabs
    path = tmp_path / 'dropped.png'
    image = QImage(20, 20, QImage.Format.Format_ARGB32)
    image.fill(0)
    assert image.save(str(path))
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    event = QDropEvent(QPointF(40, 50), Qt.DropAction.CopyAction, mime,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    first.dropEvent(event)
    assert event.isAccepted()
    assert editor.tabs is first
    assert editor._current_doc().path == path
    assert second.count() == 1
