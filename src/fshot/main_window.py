from __future__ import annotations

import string
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabBar,
    QTabWidget,
    QToolButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from fshot import __version__
from fshot.canvas import CANVAS_PADDING, ImageCanvas
from fshot.document import ShotDocument, make_tab_title
from fshot.icons import camera_icon, line_end_style_icon, tool_icon
from fshot.hotkeys import HOTKEY_ACTIONS, HotkeyAction, HotkeyCombination, default_hotkeys
from fshot.i18n import LanguageManager, LanguageMode
from fshot.qt_image import pil_to_qimage
from fshot.settings import CaptureMode, CaptureSettings, DrawingSettings, LineEndStyle, Tool
from fshot.theme import ThemeManager, ThemeMode

IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

LAST_SAVE_DIRECTORY_KEY = "files/last_save_directory"
TOOLBAR_ICON_SIZE = QSize(20, 20)
TOOLBAR_BUTTON_SIZE = QSize(34, 34)
TOOLBAR_DROPDOWN_SIZE = QSize(20, 34)
LINE_END_STYLE_ICON_SIZE = QSize(64, 24)


class LineEndStyleDelegate(QStyledItemDelegate):
    """Draw full-size line previews in combo popups on every platform."""

    _PADDING = 4

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(
            max(hint.width(), LINE_END_STYLE_ICON_SIZE.width() + self._PADDING * 2),
            max(hint.height(), LINE_END_STYLE_ICON_SIZE.height() + self._PADDING * 2),
        )

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        preview_option = QStyleOptionViewItem(option)
        self.initStyleOption(preview_option, index)
        preview_option.icon = QIcon()
        preview_option.text = ""
        style = preview_option.widget.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, preview_option, painter)

        target = QRect(
            preview_option.rect.left() + self._PADDING,
            preview_option.rect.center().y() - LINE_END_STYLE_ICON_SIZE.height() // 2,
            LINE_END_STYLE_ICON_SIZE.width(),
            LINE_END_STYLE_ICON_SIZE.height(),
        )
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(icon, QIcon) or icon.isNull():
            return
        pixmap = icon.pixmap(LINE_END_STYLE_ICON_SIZE)
        painter.drawPixmap(target, pixmap, pixmap.rect())


def _align_scrollbars_to_image(area: QScrollArea) -> None:
    for alignment in (Qt.AlignmentFlag.AlignTop, Qt.AlignmentFlag.AlignBottom):
        spacer = QWidget()
        spacer.setObjectName("imageScrollBarPadding")
        spacer.setAutoFillBackground(True)
        spacer.setFixedHeight(CANVAS_PADDING)
        area.addScrollBarWidget(spacer, alignment)
    for alignment in (Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight):
        spacer = QWidget()
        spacer.setObjectName("imageScrollBarPadding")
        spacer.setAutoFillBackground(True)
        spacer.setFixedWidth(CANVAS_PADDING)
        area.addScrollBarWidget(spacer, alignment)
    corner = QWidget()
    corner.setObjectName("imageScrollBarPadding")
    corner.setAutoFillBackground(True)
    area.setCornerWidget(corner)


class ArrowSpinBox(QSpinBox):
    BUTTON_WIDTH = 20

    def __init__(self) -> None:
        super().__init__()
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.lineEdit().setTextMargins(0, 0, self.BUTTON_WIDTH, 0)
        self.up_button = self._arrow_button(Qt.ArrowType.UpArrow, self.stepUp)
        self.down_button = self._arrow_button(Qt.ArrowType.DownArrow, self.stepDown)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        half = self.height() // 2
        left = self.width() - self.BUTTON_WIDTH
        self.up_button.setGeometry(left, 0, self.BUTTON_WIDTH, half)
        self.down_button.setGeometry(left, half, self.BUTTON_WIDTH, self.height() - half)

    def _arrow_button(self, arrow: Qt.ArrowType, callback) -> QToolButton:
        button = QToolButton(self)
        button.setProperty("spinArrow", True)
        button.setArrowType(arrow)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(350)
        button.setAutoRepeatInterval(80)
        button.clicked.connect(callback)
        return button


class TabStatusWidget(QWidget):
    def __init__(self, close_button: QWidget | None = None, marker_on_left: bool = False) -> None:
        super().__init__()
        self.has_close_button = close_button is not None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7 if marker_on_left else 6, 0, 6 if marker_on_left else 14, 0)
        layout.setSpacing(5)
        self.marker = QLabel()
        self.marker.setFixedSize(7, 7)
        self.marker.setStyleSheet("background: #e03131; border: 0;")
        layout.addWidget(self.marker, 0, Qt.AlignmentFlag.AlignVCenter)
        self.close_button = close_button if isinstance(close_button, QAbstractButton) else None
        if close_button is not None:
            close_button.setParent(self)
            layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_dirty(self, dirty: bool) -> None:
        self.marker.setVisible(dirty)
        self.setVisible(dirty or self.has_close_button)


class TabCloseWidget(QWidget):
    def __init__(self, close_button: QAbstractButton) -> None:
        super().__init__()
        self.close_button = close_button
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        close_button.setParent(self)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignVCenter)


class TabNameEditor(QLineEdit):
    accepted = Signal()
    cancelled = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accepted.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.accepted.emit()


class EditorWindow(QMainWindow):
    hiddenByMinimize = Signal()

    def __init__(
        self,
        theme_manager: ThemeManager | None = None,
        language_manager: LanguageManager | None = None,
        app_settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        from PySide6.QtWidgets import QApplication

        self.theme_manager = theme_manager or ThemeManager(QApplication.instance())
        self.language_manager = language_manager or LanguageManager()
        self.app_settings = app_settings if app_settings is not None else QSettings()
        self.setWindowIcon(camera_icon())
        self.setAcceptDrops(True)
        self.settings = DrawingSettings.default()
        self.capture_settings = CaptureSettings()
        self.hotkey_bindings = default_hotkeys()
        self._hotkey_validator: Callable | None = None
        self._hotkey_applier: Callable | None = None
        self.active_tool = Tool.PEN
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.currentChanged.connect(self._current_changed)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.tabBarDoubleClicked.connect(self._start_tab_rename)
        self.setCentralWidget(self.tabs)
        self.documents: dict[int, ShotDocument] = {}
        self._rename_tab_index: int | None = None
        self._rename_commit_active = False
        self._tab_name_editor = TabNameEditor(self.tabs.tabBar())
        self._tab_name_editor.setObjectName("tabNameEditor")
        self._tab_name_editor.hide()
        self._tab_name_editor.accepted.connect(self._commit_tab_rename)
        self._tab_name_editor.cancelled.connect(self._cancel_tab_rename)
        self.tab_menu_button = QToolButton()
        self.tab_menu_button.setArrowType(Qt.ArrowType.DownArrow)
        self.tab_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.tab_menu_button.setAutoRaise(True)
        self.tab_menu_button.setToolTip("Open tabs")
        self.tab_menu = QMenu(self)
        self.tab_menu_button.setMenu(self.tab_menu)
        self.tab_menu_button.hide()
        self.tabs.setCornerWidget(self.tab_menu_button, Qt.Corner.TopRightCorner)
        self._build_toolbar()
        self.theme_manager.changed.connect(self._theme_changed)
        self.language_manager.changed.connect(self._language_changed)
        self._retranslate_ui()
        self._update_title()
        self._update_actions()
        self.resize(1100, 760)

    def add_shot(self, image: Image.Image) -> None:
        self._add_image(pil_to_qimage(image), make_tab_title())

    def _add_image(
        self,
        qimage,
        title: str,
        path: Path | None = None,
        dirty: bool = True,
    ) -> None:
        canvas = ImageCanvas(qimage, self.settings)
        canvas.set_tool(self.active_tool)
        canvas.changed.connect(self._mark_current_dirty)
        area = QScrollArea()
        _align_scrollbars_to_image(area)
        area.setWidget(canvas)
        area.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        index = self.tabs.addTab(area, title)
        self._ensure_tab_status_widget(index)
        self.documents[index] = ShotDocument(
            title=title,
            image=canvas,
            path=path,
            dirty=dirty,
        )
        self.tabs.setCurrentIndex(index)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._refresh_tabs()

    def dragEnterEvent(self, event) -> None:
        if self._image_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._image_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        paths = self._image_paths_from_mime(event.mimeData())
        if not paths:
            super().dropEvent(event)
            return
        for path in paths:
            self._open_image_path(path, path.name, remember_path=True)
        event.acceptProposedAction()

    def paste_image(self) -> None:
        from PySide6.QtWidgets import QApplication

        mime = QApplication.clipboard().mimeData()
        paths = self._image_paths_from_mime(mime)
        if paths:
            for path in paths:
                self._open_image_path(path, make_tab_title())
            return
        image = QApplication.clipboard().image()
        if not image.isNull():
            self._add_image(image.copy(), make_tab_title())

    def _open_image_path(self, path: Path, title: str, remember_path: bool = False) -> bool:
        try:
            with Image.open(path) as image:
                qimage = pil_to_qimage(image)
        except (OSError, ValueError):
            QMessageBox.warning(self, "FShot", self._tr("open_image_failed", path=path))
            return False
        self._add_image(
            qimage,
            title,
            path=path if remember_path else None,
            dirty=not remember_path,
        )
        return True

    @staticmethod
    def _image_paths_from_mime(mime) -> list[Path]:
        if mime is None or not mime.hasUrls():
            return []
        paths: list[Path] = []
        for url in mime.urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                    paths.append(path)
        return paths

    def set_active_tool(self, tool: Tool) -> None:
        self.active_tool = tool
        canvas = self._current_canvas()
        if canvas:
            canvas.set_tool(tool)

    def copy_current(self) -> None:
        canvas = self._current_canvas()
        if canvas is None:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setImage(canvas.export_image())

    def save_current(self) -> None:
        doc = self._current_doc()
        if doc is None or not doc.can_save:
            return
        if doc.path is None:
            self.save_current_as()
            return
        self._save_to_path(doc, doc.path)

    def save_current_as(self) -> None:
        doc = self._current_doc()
        canvas = self._current_canvas()
        if doc is None or canvas is None:
            return
        default_path = self._default_save_path(doc)
        path, selected = QFileDialog.getSaveFileName(
            self,
            self._tr("save_screenshot"),
            str(default_path),
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)",
            "PNG Image (*.png)" if default_path.suffix.lower() != ".jpg" else "JPEG Image (*.jpg *.jpeg)",
        )
        if not path:
            return
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".jpg" if "JPEG" in selected else ".png")
        self._save_to_path(doc, target)

    def _default_save_path(self, doc: ShotDocument) -> Path:
        if doc.path is not None:
            return doc.path
        default_name = doc.title if Path(doc.title).suffix else f"{doc.title}.png"
        stored_directory = str(self.app_settings.value(LAST_SAVE_DIRECTORY_KEY, "") or "")
        last_directory = Path(stored_directory) if stored_directory else None
        default_directory = (
            last_directory if last_directory is not None and last_directory.is_dir() else Path.cwd()
        )
        return default_directory / default_name

    def zoom_in(self) -> None:
        canvas = self._current_canvas()
        if canvas:
            canvas.zoom_in()

    def zoom_out(self) -> None:
        canvas = self._current_canvas()
        if canvas:
            canvas.zoom_out()

    def zoom_reset(self) -> None:
        canvas = self._current_canvas()
        if canvas:
            canvas.set_zoom(1.0)

    def closeEvent(self, event) -> None:
        if not self.confirm_discard_all():
            event.ignore()
            return
        self._discard_all_tabs()
        self.hide()
        event.ignore()

    def confirm_discard_all(self, message_key: str = "close_discard_all") -> bool:
        if not self._has_dirty_documents():
            return True
        reply = QMessageBox.question(
            self,
            "FShot",
            self._tr(message_key),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def changeEvent(self, event) -> None:
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self.hiddenByMinimize.emit()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_tab_overflow()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Tools")
        toolbar.setObjectName("editorToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setIconSize(TOOLBAR_ICON_SIZE)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)

        self.pen_action = self._tool_action("Pen", "Alt+P", Tool.PEN, "pen")
        self.line_action = self._tool_action("Line", "Alt+L", Tool.LINE, "line")
        self.rect_action = self._tool_action("Rectangle", "Alt+R", Tool.RECTANGLE, "rectangle")
        self.measure_action = self._tool_action("Measure pixels", "Alt+D", Tool.MEASURE, "measure")
        self.text_action = self._tool_action("Text", "Alt+T", Tool.TEXT, "text")
        self.mosaic_action = self._tool_action("Mosaic", "Alt+M", Tool.MOSAIC, "mosaic")
        for action in [
            self.pen_action,
            self.line_action,
            self.rect_action,
            self.measure_action,
            self.text_action,
            self.mosaic_action,
        ]:
            self.tool_group.addAction(action)
            if action is self.line_action:
                self.line_end_menu = self._create_line_end_menu()
                self.line_tool_group = QWidget()
                self.line_tool_group.setObjectName("lineToolGroup")
                line_tool_layout = QHBoxLayout(self.line_tool_group)
                line_tool_layout.setContentsMargins(0, 0, 0, 0)
                line_tool_layout.setSpacing(0)
                self.line_button = QToolButton()
                self.line_button.setObjectName("lineToolButton")
                self.line_button.setProperty("lineToolMain", True)
                self.line_button.setDefaultAction(self.line_action)
                self.line_end_button = QToolButton()
                self.line_end_button.setObjectName("lineEndButton")
                self.line_end_button.setProperty("lineToolDropdown", True)
                self.line_end_button.setProperty("lineSelected", False)
                self.line_end_button.setArrowType(Qt.ArrowType.DownArrow)
                self.line_end_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                self.line_end_button.setMenu(self.line_end_menu)
                line_tool_layout.addWidget(self.line_button)
                line_tool_layout.addWidget(self.line_end_button)
                toolbar.addWidget(self.line_tool_group)
                self.line_action.toggled.connect(self._sync_line_tool_group)
            else:
                toolbar.addAction(action)
        self.pen_action.setChecked(True)

        self.style_action = QAction(self._style_icon(), "Line and color", self)
        self.style_action.setShortcut("Alt+C")
        self.style_action.triggered.connect(self._show_style_panel)
        toolbar.addAction(self.style_action)
        toolbar.addSeparator()

        self.undo_action = QAction(tool_icon("undo"), "Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(lambda: self._current_canvas() and self._current_canvas().undo())
        toolbar.addAction(self.undo_action)

        self.copy_action = QAction(tool_icon("copy"), "Copy", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.triggered.connect(self.copy_current)
        toolbar.addAction(self.copy_action)

        self.paste_action = QAction(self._tr("paste"), self)
        self.paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_action.triggered.connect(self.paste_image)
        self.addAction(self.paste_action)

        self.save_action = QAction(tool_icon("save"), "Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save_current)
        toolbar.addAction(self.save_action)

        self.save_as_action = QAction(tool_icon("save_as"), "Save As", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self.save_current_as)
        toolbar.addAction(self.save_as_action)

        self.rename_action = QAction("Rename", self)
        self.rename_action.setShortcut(QKeySequence("Return" if sys.platform == "darwin" else "F2"))
        self.rename_action.triggered.connect(self.rename_current)
        self.addAction(self.rename_action)
        toolbar.addSeparator()

        self.zoom_in_action = QAction(tool_icon("zoom_in"), "Zoom in", self)
        self.zoom_in_action.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        self.zoom_in_action.triggered.connect(self.zoom_in)
        toolbar.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction(tool_icon("zoom_out"), "Zoom out", self)
        self.zoom_out_action.setShortcuts([QKeySequence("Ctrl+-")])
        self.zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addAction(self.zoom_out_action)

        self.zoom_reset_action = QAction("Reset zoom", self)
        self.zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        self.zoom_reset_action.triggered.connect(self.zoom_reset)
        self.addAction(self.zoom_reset_action)

        self.cursor_action = QAction(tool_icon("cursor", checked=False), "Include cursor", self)
        self.cursor_action.setCheckable(True)
        self.cursor_action.toggled.connect(self._set_include_cursor)
        toolbar.addAction(self.cursor_action)

        self.delay_action = QAction(self._delay_icon(), "Delay", self)
        self.delay_action.triggered.connect(self._show_delay_panel)
        toolbar.addAction(self.delay_action)

        toolbar.addSeparator()
        self.hotkey_action = QAction(tool_icon("keyboard"), "Capture shortcuts", self)
        self.hotkey_action.triggered.connect(self._show_hotkey_panel)
        toolbar.addAction(self.hotkey_action)

        self.theme_action = QAction(self._theme_icon(), "Theme: follow system", self)
        self.theme_action.triggered.connect(self._cycle_theme)
        toolbar.addAction(self.theme_action)

        self.language_action = QAction(tool_icon("language", badge="system"), "Language", self)
        self.language_action.triggered.connect(self._cycle_language)
        toolbar.addAction(self.language_action)
        for action in toolbar.actions():
            button = toolbar.widgetForAction(action)
            if isinstance(button, QToolButton):
                button.setFixedSize(TOOLBAR_BUTTON_SIZE)
        self.line_button.setFixedSize(TOOLBAR_BUTTON_SIZE)
        self.line_end_button.setFixedSize(TOOLBAR_DROPDOWN_SIZE)
        self.line_tool_group.setFixedSize(
            TOOLBAR_BUTTON_SIZE.width() + TOOLBAR_DROPDOWN_SIZE.width(),
            TOOLBAR_BUTTON_SIZE.height(),
        )
        self._refresh_toolbar_icons()

    def _tool_action(self, text: str, shortcut: str, tool: Tool, icon_name: str) -> QAction:
        action = QAction(tool_icon(icon_name), text, self)
        action.setCheckable(True)
        action.setShortcut(shortcut)
        action.triggered.connect(lambda: self.set_active_tool(tool))
        return action

    def _create_line_end_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("lineEndMenu")
        panel = QWidget(menu)
        panel.setObjectName("lineEndPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        self.line_start_label = QLabel()
        self.line_end_label = QLabel()
        self.line_start_combo = QComboBox()
        self.line_end_combo = QComboBox()
        self.line_start_combo.setObjectName("lineStartStyle")
        self.line_end_combo.setObjectName("lineEndStyle")
        for combo in (self.line_start_combo, self.line_end_combo):
            combo.setIconSize(LINE_END_STYLE_ICON_SIZE)
            combo.view().setIconSize(LINE_END_STYLE_ICON_SIZE)
            # The macOS style caps popup decorations at its native small-icon
            # size, so draw these wide previews explicitly in the item view.
            combo.setItemDelegate(LineEndStyleDelegate(combo))
            combo.setMinimumWidth(88)
        layout.addWidget(self.line_start_label, 0, 0)
        layout.addWidget(self.line_start_combo, 0, 1)
        layout.addWidget(self.line_end_label, 1, 0)
        layout.addWidget(self.line_end_combo, 1, 1)

        self.line_start_combo.currentIndexChanged.connect(
            lambda: self._set_line_end_style("start", self.line_start_combo)
        )
        self.line_end_combo.currentIndexChanged.connect(
            lambda: self._set_line_end_style("end", self.line_end_combo)
        )
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        self._refresh_line_end_panel()
        return menu

    def _refresh_line_end_panel(self) -> None:
        self.line_start_label.setText(self._tr("line_start"))
        self.line_end_label.setText(self._tr("line_end"))
        choices = (
            (LineEndStyle.NONE, "line_end_none"),
            (LineEndStyle.ARROW, "line_end_arrow"),
            (LineEndStyle.CIRCLE, "line_end_circle"),
        )
        for combo, endpoint, selected, accessible_name in (
            (self.line_start_combo, "start", self.settings.line_start_style, self._tr("line_start")),
            (self.line_end_combo, "end", self.settings.line_end_style, self._tr("line_end")),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.setAccessibleName(accessible_name)
            for style, label_key in choices:
                label = self._tr(label_key)
                combo.addItem(
                    line_end_style_icon(style.value, endpoint, dark=self._is_dark_theme()),
                    "",
                    style.value,
                )
                index = combo.count() - 1
                combo.setItemData(index, label, Qt.ItemDataRole.ToolTipRole)
                combo.setItemData(index, label, Qt.ItemDataRole.AccessibleDescriptionRole)
            combo.setCurrentIndex(combo.findData(selected.value))
            combo.blockSignals(False)

    def _set_line_end_style(self, endpoint: str, combo: QComboBox) -> None:
        value = combo.currentData()
        if value is None:
            return
        style = LineEndStyle(value)
        if endpoint == "start":
            self.settings.line_start_style = style
        else:
            self.settings.line_end_style = style
        self.line_action.setIcon(self._line_icon())

    def _sync_line_tool_group(self, checked: bool) -> None:
        self.line_end_button.setProperty("lineSelected", checked)
        self.line_end_button.style().unpolish(self.line_end_button)
        self.line_end_button.style().polish(self.line_end_button)

    def _show_style_panel(self) -> None:
        menu = QMenu(self)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        width_row = QHBoxLayout()
        width_row.addWidget(QLabel(self._tr("width")))
        width_slider = QSlider(Qt.Orientation.Horizontal)
        width_slider.setRange(1, 48)
        width_slider.setValue(self.settings.line_width)
        width_spin = ArrowSpinBox()
        width_spin.setRange(1, 48)
        width_spin.setValue(self.settings.line_width)
        width_slider.valueChanged.connect(width_spin.setValue)
        width_spin.valueChanged.connect(width_slider.setValue)
        width_spin.valueChanged.connect(self._set_line_width)
        width_row.addWidget(width_slider)
        width_row.addWidget(width_spin)
        layout.addLayout(width_row)

        swatches = QGridLayout()
        colors = [
            "#000000",
            "#212529",
            "#343a40",
            "#495057",
            "#868e96",
            "#adb5bd",
            "#ced4da",
            "#ffffff",
            "#fff5f5",
            "#ffe3e3",
            "#ffc9c9",
            "#ff8787",
            "#fa5252",
            "#e03131",
            "#c92a2a",
            "#fff4e6",
            "#ffe8cc",
            "#ffc078",
            "#ff922b",
            "#f76707",
            "#e8590c",
            "#fff9db",
            "#fff3bf",
            "#ffe066",
            "#ffd43b",
            "#fab005",
            "#f08c00",
            "#ebfbee",
            "#d3f9d8",
            "#8ce99a",
            "#51cf66",
            "#37b24d",
            "#2b8a3e",
            "#e6fcf5",
            "#c3fae8",
            "#63e6be",
            "#20c997",
            "#0ca678",
            "#087f5b",
            "#e3fafc",
            "#c5f6fa",
            "#66d9e8",
            "#22b8cf",
            "#15aabf",
            "#0b7285",
            "#e7f5ff",
            "#d0ebff",
            "#74c0fc",
            "#339af0",
            "#228be6",
            "#1971c2",
            "#edf2ff",
            "#dbe4ff",
            "#91a7ff",
            "#5c7cfa",
            "#4263eb",
            "#364fc7",
            "#f3f0ff",
            "#e5dbff",
            "#b197fc",
            "#845ef7",
            "#7048e8",
            "#5f3dc4",
            "#f8f0fc",
            "#eebefa",
            "#da77f2",
            "#be4bdb",
            "#ae3ec9",
            "#862e9c",
            "#fff0f6",
            "#fcc2d7",
            "#f783ac",
            "#f06595",
            "#d6336c",
            "#a61e4d",
        ]
        for index, value in enumerate(colors):
            button = QPushButton()
            button.setFixedSize(18, 18)
            button.setStyleSheet(f"background: {value}; border: 0; border-radius: 2px;")
            button.clicked.connect(lambda _checked=False, color=value: self._set_line_color(QColor(color)))
            swatches.addWidget(button, index // 12, index % 12)
        layout.addLayout(swatches)

        custom_button = QPushButton(self._tr("custom_color"))
        custom_button.clicked.connect(self._choose_custom_line_color)
        layout.addWidget(custom_button)

        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        menu.exec(self.mapToGlobal(self._toolbar_anchor(self.style_action)))

    def _show_delay_panel(self) -> None:
        menu = QMenu(self)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        row = QHBoxLayout()
        for seconds in (0, 1, 3, 5):
            button = QPushButton(self._tr("off") if seconds == 0 else f"{seconds}s")
            button.setCheckable(True)
            button.setChecked(self.capture_settings.delay_seconds == seconds)
            button.clicked.connect(lambda _checked=False, value=seconds, popup=menu: self._set_delay(value, popup))
            row.addWidget(button)
        layout.addLayout(row)
        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel(self._tr("custom")))
        custom = ArrowSpinBox()
        custom.setRange(0, 60)
        custom.setSuffix(" s")
        custom.setValue(round(self.capture_settings.delay_seconds))
        custom.valueChanged.connect(lambda value: self._set_delay(float(value), None))
        custom_row.addWidget(custom)
        layout.addLayout(custom_row)
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        menu.exec(self.mapToGlobal(self._toolbar_anchor(self.delay_action)))

    def configure_hotkeys(
        self,
        bindings,
        validator: Callable,
        applier: Callable,
    ) -> None:
        self.hotkey_bindings = dict(bindings)
        self._hotkey_validator = validator
        self._hotkey_applier = applier

    def _show_hotkey_panel(self) -> None:
        menu = self._create_hotkey_menu()
        menu.exec(self.mapToGlobal(self._toolbar_anchor(self.hotkey_action)))

    def _create_hotkey_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("hotkeyMenu")
        panel = QWidget()
        panel.setObjectName("hotkeyPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(7)
        for column, key in enumerate(("capture_type", "ctrl", "shift", "alt", "letter")):
            layout.addWidget(QLabel(self._tr(key)), 0, column)

        controls = {}
        mode_keys = {
            CaptureMode.ACTIVE_WINDOW: "capture_active_window",
            CaptureMode.REGION: "capture_region",
            CaptureMode.FULLSCREEN: "capture_fullscreen",
            CaptureMode.WINDOW_UNDER_CURSOR: "capture_window_under_cursor",
            HotkeyAction.REPEAT: "capture_repeat",
        }
        for row, mode in enumerate(HOTKEY_ACTIONS, start=1):
            combination = self.hotkey_bindings[mode]
            ctrl = QCheckBox()
            shift = QCheckBox()
            alt = QCheckBox()
            letter = QComboBox()
            ctrl.setObjectName(f"{mode.value}Ctrl")
            shift.setObjectName(f"{mode.value}Shift")
            alt.setObjectName(f"{mode.value}Alt")
            letter.setObjectName(f"{mode.value}Letter")
            letter.addItems(string.ascii_uppercase)
            ctrl.setChecked(combination.ctrl)
            shift.setChecked(combination.shift)
            alt.setChecked(combination.alt)
            letter.setCurrentText(combination.letter)
            controls[mode] = (ctrl, shift, alt, letter)
            layout.addWidget(QLabel(self._tr(mode_keys[mode])), row, 0)
            layout.addWidget(ctrl, row, 1, Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(shift, row, 2, Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(alt, row, 3, Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(letter, row, 4)

        warning = QLabel()
        warning.setObjectName("hotkeyWarning")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #e03131;")
        layout.addWidget(warning, len(HOTKEY_ACTIONS) + 1, 0, 1, 5)
        buttons = QHBoxLayout()
        default_button = QPushButton(self._tr("use_defaults"))
        default_button.setObjectName("hotkeyDefaultButton")
        buttons.addWidget(default_button)
        buttons.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setObjectName("hotkeyOkButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("hotkeyCancelButton")
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons, len(HOTKEY_ACTIONS) + 2, 0, 1, 5)

        def selected_bindings():
            return {
                mode: HotkeyCombination(
                    letter.currentText(), ctrl.isChecked(), shift.isChecked(), alt.isChecked()
                )
                for mode, (ctrl, shift, alt, letter) in controls.items()
            }

        def update_state() -> None:
            for ctrl, shift, alt, _letter in controls.values():
                has_primary_modifier = ctrl.isChecked() or alt.isChecked()
                if not has_primary_modifier and shift.isChecked():
                    shift.setChecked(False)
                shift.setEnabled(has_primary_modifier)
            if self._hotkey_validator is None:
                valid, message = True, ""
            else:
                valid, message = self._hotkey_validator(selected_bindings())
            warning.setText(message)
            warning.setVisible(not valid)
            ok_button.setEnabled(valid)

        def apply() -> None:
            if self._hotkey_applier is None:
                menu.close()
                return
            valid, message = self._hotkey_applier(selected_bindings())
            if valid:
                menu.close()
                return
            warning.setText(message)
            warning.show()
            ok_button.setEnabled(False)

        def use_defaults() -> None:
            for mode, combination in default_hotkeys().items():
                ctrl, shift, alt, letter = controls[mode]
                ctrl.setChecked(combination.ctrl)
                alt.setChecked(combination.alt)
                shift.setChecked(combination.shift)
                letter.setCurrentText(combination.letter)
            update_state()

        for ctrl, shift, alt, letter in controls.values():
            ctrl.toggled.connect(update_state)
            shift.toggled.connect(update_state)
            alt.toggled.connect(update_state)
            letter.currentTextChanged.connect(update_state)
        ok_button.clicked.connect(apply)
        cancel_button.clicked.connect(menu.close)
        default_button.clicked.connect(use_defaults)
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        update_state()
        return menu

    def _cycle_theme(self) -> None:
        modes = (ThemeMode.SYSTEM, ThemeMode.LIGHT, ThemeMode.DARK)
        index = modes.index(self.theme_manager.mode)
        self.theme_manager.set_mode(modes[(index + 1) % len(modes)])

    def _cycle_language(self) -> None:
        modes = (LanguageMode.SYSTEM, LanguageMode.ZH_TW, LanguageMode.EN)
        index = modes.index(self.language_manager.mode)
        self.language_manager.set_mode(modes[(index + 1) % len(modes)])

    def _set_line_width(self, width: int) -> None:
        self.settings.line_width = width
        self.style_action.setIcon(self._style_icon())

    def _set_line_color(self, color: QColor) -> None:
        self.settings.color = color
        self.style_action.setIcon(self._style_icon())

    def _choose_custom_line_color(self) -> None:
        color = QColorDialog.getColor(self.settings.color, self, self._tr("line_color_dialog"))
        if color.isValid():
            self._set_line_color(color)

    def _set_delay(self, seconds: float, popup: QMenu | None) -> None:
        self.capture_settings.delay_seconds = seconds
        self.delay_action.setToolTip(self._tr("delay_value", seconds=seconds))
        self.delay_action.setIcon(self._delay_icon())
        if popup is not None:
            popup.close()

    def _set_include_cursor(self, checked: bool) -> None:
        self.capture_settings.include_cursor = checked
        self.cursor_action.setIcon(tool_icon("cursor", checked=checked, dark=self._is_dark_theme()))
        self.cursor_action.setToolTip(
            self._tr("include_cursor_on") if checked else self._tr("include_cursor_off")
        )

    def rename_current(self) -> None:
        self._start_tab_rename(self.tabs.currentIndex())

    def _start_tab_rename(self, index: int) -> None:
        doc = self.documents.get(index)
        if doc is None or doc.path is None:
            return
        self._rename_tab_index = index
        self.tabs.setCurrentIndex(index)
        self._position_tab_name_editor()
        self._tab_name_editor.setText(doc.path.stem)
        self._tab_name_editor.show()
        self._tab_name_editor.raise_()
        self._tab_name_editor.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._tab_name_editor.selectAll()
        self.rename_action.setEnabled(False)

    def _position_tab_name_editor(self) -> None:
        index = self._rename_tab_index
        if index is None:
            return
        tab_bar = self.tabs.tabBar()
        rect = tab_bar.tabRect(index)
        left = tab_bar.tabButton(index, QTabBar.ButtonPosition.LeftSide)
        right = tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
        left_width = left.width() if left is not None and left.isVisible() else 0
        right_width = right.width() if right is not None and right.isVisible() else 0
        rect.adjust(left_width + 4, 2, -(right_width + 4), -2)
        self._tab_name_editor.setGeometry(rect)

    def _commit_tab_rename(self) -> None:
        if self._rename_commit_active:
            return
        self._rename_commit_active = True
        try:
            self._try_commit_tab_rename()
        finally:
            self._rename_commit_active = False

    def _try_commit_tab_rename(self) -> None:
        index = self._rename_tab_index
        if index is None:
            return
        doc = self.documents.get(index)
        name = self._tab_name_editor.text().strip()
        if doc is None or doc.path is None:
            self._finish_tab_rename()
            return
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            QMessageBox.warning(self, "FShot", self._tr("rename_invalid"))
            self._tab_name_editor.setFocus(Qt.FocusReason.OtherFocusReason)
            self._tab_name_editor.selectAll()
            return

        source = doc.path
        target = source.with_name(f"{name}{source.suffix}")
        if target.name == source.name:
            self._finish_tab_rename()
            return
        try:
            target_is_other_file = target.exists() and not target.samefile(source)
        except OSError:
            target_is_other_file = target.exists()
        if target_is_other_file:
            QMessageBox.warning(self, "FShot", self._tr("rename_exists", name=target.name))
            self._tab_name_editor.setFocus(Qt.FocusReason.OtherFocusReason)
            self._tab_name_editor.selectAll()
            return
        try:
            source.rename(target)
        except OSError:
            QMessageBox.warning(self, "FShot", self._tr("rename_failed", path=source))
            self._tab_name_editor.setFocus(Qt.FocusReason.OtherFocusReason)
            self._tab_name_editor.selectAll()
            return
        doc.mark_renamed(target)
        self._finish_tab_rename()
        self._refresh_tabs()

    def _cancel_tab_rename(self) -> None:
        if self._rename_tab_index is not None:
            self._finish_tab_rename()

    def _finish_tab_rename(self) -> None:
        self._rename_tab_index = None
        self._tab_name_editor.hide()
        self._update_actions()

    def _save_to_path(self, doc: ShotDocument, path: Path) -> None:
        canvas = self._current_canvas()
        if canvas is None:
            return
        suffix = path.suffix.lower()
        image = canvas.export_image()
        formats = {
            ".bmp": "BMP",
            ".jpeg": "JPG",
            ".jpg": "JPG",
            ".png": "PNG",
            ".tif": "TIFF",
            ".tiff": "TIFF",
            ".webp": "WEBP",
        }
        fmt = formats.get(suffix, "PNG")
        if not image.save(str(path), fmt):
            QMessageBox.warning(self, "FShot", self._tr("save_failed", path=path))
            return
        doc.mark_saved(path)
        self.app_settings.setValue(LAST_SAVE_DIRECTORY_KEY, str(path.parent))
        self._refresh_tabs()

    def _current_area(self) -> QScrollArea | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, QScrollArea) else None

    def _current_canvas(self) -> ImageCanvas | None:
        area = self._current_area()
        if area is None:
            return None
        widget = area.widget()
        return widget if isinstance(widget, ImageCanvas) else None

    def _current_doc(self) -> ShotDocument | None:
        return self.documents.get(self.tabs.currentIndex())

    def _mark_current_dirty(self) -> None:
        doc = self._current_doc()
        if doc:
            doc.mark_dirty()
        self._refresh_tabs()

    def _current_changed(self, _index: int) -> None:
        if self._rename_tab_index is not None and self._rename_tab_index != _index:
            self._cancel_tab_rename()
        self._update_title()
        self._update_actions()

    def _close_tab(self, index: int) -> None:
        if self._rename_tab_index is not None:
            self._cancel_tab_rename()
        doc = self.documents.get(index)
        if doc and doc.is_dirty:
            reply = QMessageBox.question(
                self,
                "FShot",
                self._tr("close_discard_tab", title=doc.title),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.tabs.removeTab(index)
        self._reindex_documents(index)
        self._refresh_tabs()

    def _pick_tab(self, picker_index: int) -> None:
        if picker_index >= 0 and picker_index != self.tabs.currentIndex():
            self.tabs.setCurrentIndex(picker_index)

    def _reindex_documents(self, closed_index: int) -> None:
        new_docs: dict[int, ShotDocument] = {}
        for index, doc in self.documents.items():
            if index < closed_index:
                new_docs[index] = doc
            elif index > closed_index:
                new_docs[index - 1] = doc
        self.documents = new_docs

    def _discard_all_tabs(self) -> None:
        self.tabs.clear()
        self.documents.clear()
        self._refresh_tabs()

    def _refresh_tabs(self) -> None:
        current = self.tabs.currentIndex()
        for i in range(self.tabs.count()):
            doc = self.documents.get(i)
            if doc:
                self.tabs.setTabText(i, doc.display_title)
                self._ensure_tab_status_widget(i).set_dirty(doc.is_dirty)
        self.tab_menu.clear()
        for i in range(self.tabs.count()):
            action = self.tab_menu.addAction(self.tabs.tabText(i))
            action.setCheckable(True)
            action.setChecked(i == current)
            action.triggered.connect(lambda _checked=False, index=i: self.tabs.setCurrentIndex(index))
        self._update_title()
        self._update_actions()
        self._update_tab_overflow()

    def _ensure_tab_status_widget(self, index: int) -> TabStatusWidget:
        tab_bar = self.tabs.tabBar()
        if sys.platform == "win32":
            left = tab_bar.tabButton(index, QTabBar.ButtonPosition.LeftSide)
            if not isinstance(left, TabStatusWidget):
                left = TabStatusWidget(marker_on_left=True)
                tab_bar.setTabButton(index, QTabBar.ButtonPosition.LeftSide, left)

            right = tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if isinstance(right, TabCloseWidget):
                self._style_tab_close_button(right.close_button)
            else:
                close_button = self._new_tab_close_button()
                right = TabCloseWidget(close_button)
                close_button.clicked.connect(
                    lambda _checked=False, widget=right: self._close_tab_widget(widget)
                )
                tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, right)
            return left

        close_side = QTabBar.ButtonPosition(
            tab_bar.style().styleHint(QStyle.StyleHint.SH_TabBar_CloseButtonPosition)
        )
        if close_side == QTabBar.ButtonPosition.LeftSide:
            left_button = tab_bar.tabButton(index, QTabBar.ButtonPosition.LeftSide)
            if isinstance(left_button, TabCloseWidget):
                self._style_tab_close_button(left_button.close_button)
            else:
                close_button = self._new_tab_close_button()
                close_widget = TabCloseWidget(close_button)
                close_button.clicked.connect(
                    lambda _checked=False, widget=close_widget: self._close_tab_widget(widget)
                )
                tab_bar.setTabButton(
                    index,
                    QTabBar.ButtonPosition.LeftSide,
                    close_widget,
                )

        button_side = QTabBar.ButtonPosition.RightSide
        current = tab_bar.tabButton(index, button_side)
        if isinstance(current, TabStatusWidget):
            if current.close_button is not None:
                self._style_tab_close_button(current.close_button)
            return current
        close_button = self._new_tab_close_button() if close_side == button_side else None
        status = TabStatusWidget(close_button)
        if close_button is not None:
            close_button.clicked.connect(
                lambda _checked=False, widget=status: self._close_tab_widget(widget)
            )
        tab_bar.setTabButton(index, button_side, status)
        return status

    def _new_tab_close_button(self) -> QToolButton:
        button = QToolButton()
        button.setAutoRaise(True)
        button.setFixedSize(18, 18)
        button.setStyleSheet("padding: 0; border: 0; background: transparent;")
        self._style_tab_close_button(button)
        return button

    def _close_tab_widget(self, widget: QWidget) -> None:
        tab_bar = self.tabs.tabBar()
        for index in range(tab_bar.count()):
            if widget in (
                tab_bar.tabButton(index, QTabBar.ButtonPosition.LeftSide),
                tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide),
            ):
                self._close_tab(index)
                return

    def _style_tab_close_button(self, button: QAbstractButton) -> None:
        button.setIcon(self._tab_close_icon())
        button.setIconSize(QSize(11, 11))

    def _tab_close_icon(self) -> QIcon:
        pixmap = QPixmap(12, 12)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#ced4da") if self._is_dark_theme() else QColor("#495057")
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(3, 3, 9, 9)
        painter.drawLine(9, 3, 3, 9)
        painter.end()
        return QIcon(pixmap)

    def _update_title(self) -> None:
        doc = self._current_doc()
        app_title = f"FShot {__version__}"
        self.setWindowTitle(f"{app_title} - {doc.title}" if doc else app_title)

    def _update_actions(self) -> None:
        has_doc = self._current_doc() is not None
        doc = self._current_doc()
        canvas = self._current_canvas()
        for action in [
            self.pen_action,
            self.line_action,
            self.rect_action,
            self.measure_action,
            self.text_action,
            self.mosaic_action,
        ]:
            action.setEnabled(has_doc)
        self.line_end_button.setEnabled(has_doc)
        self.style_action.setEnabled(has_doc)
        self.copy_action.setEnabled(has_doc)
        self.save_action.setEnabled(bool(doc and doc.can_save))
        self.save_as_action.setEnabled(has_doc)
        self.rename_action.setEnabled(bool(doc and doc.path) and self._rename_tab_index is None)
        self.undo_action.setEnabled(bool(canvas and canvas.can_undo))
        self.zoom_in_action.setEnabled(has_doc)
        self.zoom_out_action.setEnabled(has_doc)
        self.zoom_reset_action.setEnabled(has_doc)

    def _has_dirty_documents(self) -> bool:
        return any(doc.is_dirty for doc in self.documents.values())

    def _style_icon(self) -> QIcon:
        return tool_icon("style", self.settings.color, self.settings.line_width, dark=self._is_dark_theme())

    def _line_icon(self) -> QIcon:
        return tool_icon(
            "line",
            dark=self._is_dark_theme(),
            line_start=self.settings.line_start_style.value,
            line_end=self.settings.line_end_style.value,
        )

    def _delay_icon(self) -> QIcon:
        seconds = self.capture_settings.delay_seconds
        if seconds <= 0:
            return tool_icon("delay", badge="off", dark=self._is_dark_theme())
        return tool_icon("delay", badge=f"{seconds:g}", dark=self._is_dark_theme())

    def _theme_icon(self) -> QIcon:
        badge = (
            "system"
            if self.theme_manager.mode == ThemeMode.SYSTEM
            else self.theme_manager.effective_mode.value
        )
        return tool_icon("theme", badge=badge, dark=self._is_dark_theme())

    def _theme_changed(self, mode: ThemeMode, effective: ThemeMode) -> None:
        self._refresh_toolbar_icons()
        self._retranslate_ui()

    def _language_changed(self, _mode: LanguageMode, _effective: LanguageMode) -> None:
        self._retranslate_ui()
        self._refresh_toolbar_icons()

    def _tr(self, key: str, **values) -> str:
        return self.language_manager.text(key, **values)

    def _tooltip_with_shortcuts(self, label: str, action: QAction) -> str:
        shortcuts = [
            shortcut.toString(QKeySequence.SequenceFormat.NativeText)
            for shortcut in action.shortcuts()
            if not shortcut.isEmpty()
        ]
        if not shortcuts:
            return label
        return self._tr("tooltip_shortcut", label=label, shortcut=" / ".join(shortcuts))

    def _retranslate_ui(self) -> None:
        labels = (
            (self.pen_action, "pen"),
            (self.line_action, "line"),
            (self.rect_action, "rectangle"),
            (self.measure_action, "measure"),
            (self.text_action, "text"),
            (self.mosaic_action, "mosaic"),
            (self.style_action, "line_color"),
            (self.undo_action, "undo"),
            (self.copy_action, "copy"),
            (self.paste_action, "paste"),
            (self.save_action, "save"),
            (self.save_as_action, "save_as"),
            (self.rename_action, "rename"),
            (self.zoom_in_action, "zoom_in"),
            (self.zoom_out_action, "zoom_out"),
            (self.zoom_reset_action, "reset_zoom"),
            (self.delay_action, "delay"),
            (self.hotkey_action, "capture_shortcuts"),
        )
        for action, key in labels:
            label = self._tr(key)
            action.setText(label)
            action.setToolTip(self._tooltip_with_shortcuts(label, action))
        self.line_end_button.setToolTip(self._tr("line_end_settings"))
        self._refresh_line_end_panel()
        self.tab_menu_button.setToolTip(self._tr("open_tabs"))
        self.cursor_action.setText(self._tr("include_cursor"))
        self._set_include_cursor(self.capture_settings.include_cursor)
        self._set_delay(self.capture_settings.delay_seconds, None)
        mode = self.theme_manager.mode.value
        effective = self.theme_manager.effective_mode.value
        self.theme_action.setToolTip(
            self._tr(
                "theme",
                mode=self._tr(f"theme_{mode}"),
                effective=self._tr(f"theme_{effective}"),
            )
        )
        language_mode = self.language_manager.mode.value
        language_effective = self.language_manager.effective_mode.value
        self.language_action.setToolTip(
            self._tr(
                "language",
                mode=self._tr(f"language_{language_mode}"),
                effective=self._tr(f"language_{language_effective}"),
            )
        )

    def _is_dark_theme(self) -> bool:
        return self.theme_manager.effective_mode == ThemeMode.DARK

    def _refresh_toolbar_icons(self) -> None:
        dark = self._is_dark_theme()
        for action, name in (
            (self.pen_action, "pen"),
            (self.rect_action, "rectangle"),
            (self.measure_action, "measure"),
            (self.text_action, "text"),
            (self.mosaic_action, "mosaic"),
            (self.undo_action, "undo"),
            (self.copy_action, "copy"),
            (self.save_action, "save"),
            (self.save_as_action, "save_as"),
            (self.zoom_in_action, "zoom_in"),
            (self.zoom_out_action, "zoom_out"),
            (self.hotkey_action, "keyboard"),
        ):
            action.setIcon(tool_icon(name, dark=dark))
        self.line_action.setIcon(self._line_icon())
        self.style_action.setIcon(self._style_icon())
        self.cursor_action.setIcon(tool_icon("cursor", checked=self.capture_settings.include_cursor, dark=dark))
        self.delay_action.setIcon(self._delay_icon())
        self.theme_action.setIcon(self._theme_icon())
        self.language_action.setIcon(
            tool_icon("language", badge=self.language_manager.mode.value, dark=dark)
        )
        for index in range(self.tabs.count()):
            self._ensure_tab_status_widget(index)

    def _toolbar_anchor(self, action: QAction) -> QPoint:
        for toolbar in self.findChildren(QToolBar):
            widget = toolbar.widgetForAction(action)
            if widget:
                point = widget.mapTo(self, widget.rect().bottomLeft())
                return point
        return QPoint(0, 0)

    def _update_tab_overflow(self) -> None:
        tab_bar = self.tabs.tabBar()
        total_width = sum(tab_bar.tabRect(i).width() for i in range(tab_bar.count()))
        available = max(0, self.tabs.width() - 8)
        self.tab_menu_button.setVisible(total_width > available and self.tabs.count() > 0)
        self._position_tab_name_editor()
