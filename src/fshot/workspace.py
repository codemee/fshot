"""Tab dragging and a nested, resizable editor workspace."""
from uuid import uuid4

from PySide6.QtCore import QEvent, QMimeData, Qt
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import QApplication, QSplitter, QTabWidget, QVBoxLayout, QWidget

from fshot.theme import DARK_COLORS

TAB_MIME = 'application/x-fshot-tab'


class DropPreview(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        color = self.palette().highlight().color()
        painter.setPen(color)
        color.setAlpha(65)
        painter.setBrush(color)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))


class PaneFrame(DropPreview):
    def paintEvent(self, event):
        pane = self.parentWidget()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = pane.palette().highlight().color() if pane.property('activePane') else QColor(
            DARK_COLORS['raised'] if pane.workspace.editor._is_dark_theme() else '#d6d8dc')
        painter.setPen(QPen(color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().toRectF().adjusted(.5, .5, -.5, -.5), 6, 6)


class EditorPane(QTabWidget):
    def __init__(self, workspace):
        super().__init__()
        self.workspace = workspace
        self.documents = {}
        self.setMinimumSize(120, 100)
        self.setAcceptDrops(True)
        self.preview = DropPreview(self)
        self.frame = PaneFrame(self)
        self.frame.show()

    def paintEvent(self, event):
        super().paintEvent(event)
        self.frame.setGeometry(self.rect())
        self.frame.raise_()
        self.frame.update()

    def drop_edge(self, point):
        if point.y() <= self.tabBar().height():
            return 'center'
        if point.x() < self.width() * .25:
            return 'left'
        if point.x() > self.width() * .75:
            return 'right'
        if point.y() > self.height() * .75:
            return 'bottom'
        return 'center'

    def accepts(self, event):
        return (bytes(event.mimeData().data(TAB_MIME)) == self.workspace.token.encode()
                and self.workspace.dragged is not None)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.workspace.editor.dragEnterEvent(event)
            return
        if self.accepts(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            self.workspace.editor.dragMoveEvent(event)
            return
        if not self.accepts(event):
            event.ignore()
            return
        edge = self.drop_edge(event.position().toPoint())
        rect = self.rect()
        if edge == 'left':
            rect.setWidth(rect.width() // 2)
        elif edge == 'right':
            rect.setLeft(rect.center().x())
        elif edge == 'bottom':
            rect.setTop(rect.center().y())
        self.preview.setGeometry(rect)
        self.preview.show()
        self.preview.raise_()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.preview.hide()
        event.accept()

    def dropEvent(self, event):
        self.preview.hide()
        if event.mimeData().hasUrls():
            self.workspace.editor._activate_pane(self)
            self.workspace.editor.dropEvent(event)
            return
        if not self.accepts(event):
            event.ignore()
            return
        source, page = self.workspace.dragged
        index = source.indexOf(page)
        if index < 0:
            event.ignore()
            return
        point = event.position().toPoint()
        insertion = self.tabBar().tabAt(point)
        self.workspace.editor._move_tab(source, index, self, self.drop_edge(point), insertion)
        event.acceptProposedAction()


class SplitWorkspace(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.token = str(uuid4())
        self.dragged = None
        self.press = None
        self.panes = []
        self.splitters = []
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root = None

    def add_initial(self, pane):
        self.root = pane
        self.root_layout.addWidget(pane)

    def watch(self, pane):
        self.panes.append(pane)
        pane.tabBar().installEventFilter(self)
        pane.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.Type.Resize, QEvent.Type.MouseButtonPress,
                                QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease,
                                QEvent.Type.FocusIn):
            return False
        pane = next((p for p in self.panes if watched in (p, p.tabBar())), None)
        if pane is None:
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn) and isinstance(watched, QWidget):
                pane = next((p for p in self.panes if p.isAncestorOf(watched)), None)
                if pane is not None:
                    self.editor._activate_pane(pane)
            return False
        if event.type() == QEvent.Type.Resize and watched is pane:
            self.editor._pane_overflow(pane)
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn):
            self.editor._activate_pane(pane)
        if watched is pane.tabBar():
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.editor._activate_pane(pane)
                index = pane.tabBar().tabAt(event.position().toPoint())
                self.press = (pane, pane.widget(index), event.position().toPoint()) if index >= 0 else None
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self.press = None
            elif event.type() == QEvent.Type.MouseMove and self.press and event.buttons() & Qt.MouseButton.LeftButton:
                source, page, origin = self.press
                if (event.position().toPoint() - origin).manhattanLength() >= QApplication.startDragDistance():
                    self.press = None
                    self.editor._cancel_tab_rename()
                    self.dragged = (source, page)
                    drag = QDrag(source)
                    mime = QMimeData()
                    mime.setData(TAB_MIME, self.token.encode())
                    drag.setMimeData(mime)
                    rect = source.tabBar().tabRect(source.indexOf(page))
                    drag.setPixmap(source.tabBar().grab(rect))
                    try:
                        drag.exec(Qt.DropAction.MoveAction)
                    finally:
                        self.dragged = None
                        for pane in self.panes:
                            pane.preview.hide()
                    return True
        return False

    def split(self, target, new_pane, edge):
        parent = target.parentWidget()
        splitter = QSplitter(Qt.Orientation.Vertical if edge == 'bottom' else Qt.Orientation.Horizontal)
        self.splitters.append(splitter)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        if isinstance(parent, QSplitter):
            sizes = parent.sizes()
            parent.replaceWidget(parent.indexOf(target), splitter)
            parent.setSizes(sizes)
        else:
            self.root_layout.replaceWidget(target, splitter)
            target.setParent(None)
            self.root = splitter
        if edge == 'left':
            splitter.addWidget(new_pane)
            splitter.addWidget(target)
        else:
            splitter.addWidget(target)
            splitter.addWidget(new_pane)
        extent = target.height() if edge == "bottom" else target.width()
        splitter.setSizes([max(1, extent), max(1, extent)])

    def remove_empty(self, pane):
        if len(self.panes) <= 1 or pane.count():
            return
        self.panes.remove(pane)
        parent = pane.parentWidget()
        pane.setParent(None)
        pane.menu.deleteLater()
        pane.deleteLater()
        while isinstance(parent, QSplitter) and parent.count() == 1:
            grandparent = parent.parentWidget()
            child = parent.widget(0)
            child.setParent(None)
            if isinstance(grandparent, QSplitter):
                sizes = grandparent.sizes()
                grandparent.replaceWidget(grandparent.indexOf(parent), child)
                grandparent.setSizes(sizes)
            else:
                self.root_layout.replaceWidget(parent, child)
                self.root = child
            parent.setParent(None)
            self.splitters.remove(parent)
            parent.deleteLater()
            parent = grandparent
