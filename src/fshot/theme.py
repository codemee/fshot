from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class ThemeMode(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class ThemeManager(QObject):
    changed = Signal(ThemeMode, ThemeMode)

    def __init__(self, app: QApplication, settings: QSettings | None = None) -> None:
        super().__init__(app)
        self.app = app
        self.settings = settings or QSettings()
        self.mode = self._stored_mode()
        self.app.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)
        self.apply()

    @property
    def effective_mode(self) -> ThemeMode:
        if self.mode != ThemeMode.SYSTEM:
            return self.mode
        return (
            ThemeMode.DARK
            if self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            else ThemeMode.LIGHT
        )

    def set_mode(self, mode: ThemeMode) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self.settings.setValue("appearance/theme", mode.value)
        self.apply()

    def apply(self) -> None:
        effective = self.effective_mode
        self.app.setPalette(_palette(effective))
        self.app.setStyleSheet(_stylesheet(effective))
        self.changed.emit(self.mode, effective)

    def _stored_mode(self) -> ThemeMode:
        value = self.settings.value("appearance/theme", ThemeMode.SYSTEM.value)
        try:
            return ThemeMode(str(value))
        except ValueError:
            return ThemeMode.SYSTEM

    def _system_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self.mode == ThemeMode.SYSTEM:
            self.apply()


def _palette(mode: ThemeMode) -> QPalette:
    palette = QPalette()
    if mode == ThemeMode.DARK:
        colors = {
            QPalette.ColorRole.Window: "#202124",
            QPalette.ColorRole.WindowText: "#e8eaed",
            QPalette.ColorRole.Base: "#17181a",
            QPalette.ColorRole.AlternateBase: "#292b2f",
            QPalette.ColorRole.Text: "#e8eaed",
            QPalette.ColorRole.Button: "#292b2f",
            QPalette.ColorRole.ButtonText: "#e8eaed",
            QPalette.ColorRole.Highlight: "#3b82c4",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.PlaceholderText: "#9aa0a6",
        }
    else:
        colors = {
            QPalette.ColorRole.Window: "#f8f9fa",
            QPalette.ColorRole.WindowText: "#343a40",
            QPalette.ColorRole.Base: "#ffffff",
            QPalette.ColorRole.AlternateBase: "#f1f3f5",
            QPalette.ColorRole.Text: "#343a40",
            QPalette.ColorRole.Button: "#ffffff",
            QPalette.ColorRole.ButtonText: "#343a40",
            QPalette.ColorRole.Highlight: "#1971c2",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.PlaceholderText: "#868e96",
        }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#868e96"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#868e96"))
    return palette


def _stylesheet(mode: ThemeMode) -> str:
    if mode == ThemeMode.DARK:
        return """
            QMainWindow { background: #202124; }
            QToolBar { background: #252629; border: 0; border-bottom: 1px solid #3c4043; spacing: 4px; padding: 0px 4px; }
            QToolBar::separator { background: #3c4043; width: 1px; margin: 11px 2px; }
            QToolButton { padding: 6px; border-radius: 4px; border: 1px solid transparent; }
            /* 6 px padding + 1 px border = 7 px around the 20 px icon. */
            QToolBar QToolButton { padding: 6px; }
            QToolBar QToolButton[lineToolDropdown="true"] { padding: 6px 0px; }
            QToolBar QToolButton[lineToolMain="true"] { border-top-right-radius: 0; border-bottom-right-radius: 0; }
            QToolBar QToolButton[lineToolDropdown="true"] { border-top-left-radius: 0; border-bottom-left-radius: 0; }
            QToolButton::menu-indicator { image: none; width: 0px; }
            QToolButton:hover, QToolButton:checked, QToolButton[lineSelected="true"] { background: #3c4043; border-color: transparent; }
            QTabWidget::pane { border: 0; }
            QTabWidget::tab-bar { alignment: left; }
            QTabBar::tab { padding: 7px 12px; background: #292b2f; border: 0; margin-right: 1px; }
            QTabBar::tab:selected { background: #202124; border-bottom: 2px solid #5da9e9; }
            QScrollArea { background: #111315; border: 0; }
            QScrollBar:vertical { background: #292b2f; width: 12px; margin: 0; }
            QScrollBar:horizontal { background: #292b2f; height: 12px; margin: 0; }
            QScrollBar::handle:vertical {
                background: #5f6368;
                min-height: 28px;
                margin: 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #5f6368;
                min-width: 28px;
                margin: 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:hover { background: #8ab4f8; }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0;
                height: 0;
                background: transparent;
            }
            QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
            QMenu { background: #292b2f; border: 1px solid #4b4f54; }
            QMenu#toolbarOverflowMenu { padding: 4px 8px; }
            QMenu::item { padding: 6px 18px; }
            QMenu::item:selected { background: #3c4043; }
            QMenu QWidget { color: #e8eaed; }
            QMenu QPushButton {
                background: #3c4043;
                color: #f1f3f4;
                border: 1px solid #5f6368;
                border-radius: 3px;
                padding: 4px 10px;
            }
            QMenu QPushButton:hover { background: #4b4f54; border-color: #8ab4f8; }
            QMenu QPushButton:checked { background: #1976c9; color: #ffffff; border-color: #5da9e9; }
            QSpinBox {
                background: #3c4043;
                color: #f1f3f4;
                border: 1px solid #5f6368;
                border-radius: 3px;
                padding: 3px 22px 3px 7px;
                selection-background-color: #3b82c4;
            }
            QSpinBox:hover, QSpinBox:focus { border-color: #8ab4f8; }
            QSpinBox:disabled { background: #303134; color: #9aa0a6; border-color: #4b4f54; }
            QComboBox {
                background: #3c4043;
                color: #f1f3f4;
                border: 1px solid #5f6368;
                border-radius: 3px;
                padding: 3px 22px 3px 7px;
                selection-background-color: #3b82c4;
            }
            QComboBox:hover, QComboBox:focus { border-color: #8ab4f8; }
            QComboBox::drop-down { border: 0; width: 22px; }
            QComboBox QAbstractItemView {
                background: #3c4043;
                color: #f1f3f4;
                border: 1px solid #5f6368;
                selection-background-color: #3b82c4;
                selection-color: #ffffff;
                outline: 0;
            }
            QSpinBox QToolButton[spinArrow="true"] {
                background: #4b4f54;
                border: 0;
                border-left: 1px solid #5f6368;
                border-radius: 0;
                padding: 0;
            }
            QSpinBox QToolButton[spinArrow="true"]:hover { background: #5f6368; }
            QSlider::groove:horizontal { height: 4px; background: #5f6368; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #5da9e9; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: #e8eaed;
                border: 1px solid #5f6368;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
        """
    return """
        QMainWindow { background: #f8f9fa; }
        QToolBar { background: #ffffff; border: 0; border-bottom: 1px solid #dee2e6; spacing: 4px; padding: 0px 4px; }
        QToolBar::separator { background: #dee2e6; width: 1px; margin: 11px 2px; }
        QToolButton { padding: 6px; border-radius: 4px; border: 1px solid transparent; }
        /* 6 px padding + 1 px border = 7 px around the 20 px icon. */
        QToolBar QToolButton { padding: 6px; }
        QToolBar QToolButton[lineToolDropdown="true"] { padding: 6px 0px; }
        QToolBar QToolButton[lineToolMain="true"] { border-top-right-radius: 0; border-bottom-right-radius: 0; }
        QToolBar QToolButton[lineToolDropdown="true"] { border-top-left-radius: 0; border-bottom-left-radius: 0; }
        QToolButton::menu-indicator { image: none; width: 0px; }
        QToolButton:hover, QToolButton:checked, QToolButton[lineSelected="true"] { background: #e9ecef; border-color: transparent; }
        QTabWidget::pane { border: 0; }
        QTabWidget::tab-bar { alignment: left; }
        QTabBar::tab { padding: 7px 12px; background: #e9ecef; border: 0; margin-right: 1px; }
        QTabBar::tab:selected { background: #ffffff; border-bottom: 2px solid #1971c2; }
        QScrollArea { background: #ced4da; border: 0; }
        QScrollBar:vertical { background: #dee2e6; width: 12px; margin: 0; }
        QScrollBar:horizontal { background: #dee2e6; height: 12px; margin: 0; }
        QScrollBar::handle:vertical {
            background: #868e96;
            min-height: 28px;
            margin: 2px;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal {
            background: #868e96;
            min-width: 28px;
            margin: 2px;
            border-radius: 4px;
        }
        QScrollBar::handle:hover { background: #339af0; }
        QScrollBar::add-line, QScrollBar::sub-line {
            width: 0;
            height: 0;
            background: transparent;
        }
        QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
        QMenu { background: #ffffff; border: 1px solid #ced4da; }
        QMenu#toolbarOverflowMenu { padding: 4px 8px; }
        QMenu::item { padding: 6px 18px; }
        QMenu::item:selected { background: #e7f5ff; }
        QMenu QWidget { color: #343a40; }
        QMenu QPushButton {
            background: #ffffff;
            color: #343a40;
            border: 1px solid #ced4da;
            border-radius: 3px;
            padding: 4px 10px;
        }
        QMenu QPushButton:hover { background: #f1f3f5; border-color: #74c0fc; }
        QMenu QPushButton:checked { background: #1971c2; color: #ffffff; border-color: #1971c2; }
        QSpinBox {
            background: #ffffff;
            color: #343a40;
            border: 1px solid #adb5bd;
            border-radius: 3px;
            padding: 3px 22px 3px 7px;
            selection-background-color: #1971c2;
        }
        QSpinBox:hover, QSpinBox:focus { border-color: #339af0; }
        QComboBox {
            background: #ffffff;
            color: #343a40;
            border: 1px solid #adb5bd;
            border-radius: 3px;
            padding: 3px 22px 3px 7px;
            selection-background-color: #1971c2;
        }
        QComboBox:hover, QComboBox:focus { border-color: #339af0; }
        QComboBox::drop-down { border: 0; width: 22px; }
        QComboBox QAbstractItemView {
            background: #ffffff;
            color: #343a40;
            border: 1px solid #adb5bd;
            selection-background-color: #1971c2;
            selection-color: #ffffff;
            outline: 0;
        }
        QSpinBox QToolButton[spinArrow="true"] {
            background: #f1f3f5;
            border: 0;
            border-left: 1px solid #adb5bd;
            border-radius: 0;
            padding: 0;
        }
        QSpinBox QToolButton[spinArrow="true"]:hover { background: #e7f5ff; }
        QSlider::groove:horizontal { height: 4px; background: #ced4da; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #339af0; border-radius: 2px; }
        QSlider::handle:horizontal {
            background: #ffffff;
            border: 1px solid #868e96;
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
    """
