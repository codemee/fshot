from __future__ import annotations

from enum import Enum
from string import Template

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


# Unit-01-inspired dark surfaces, purple panels, lime accents, and amber alerts.
DARK_COLORS = {
    "window": "#171322",
    "base": "#100d18",
    "panel": "#241b34",
    "raised": "#35264d",
    "hover": "#493565",
    "border": "#675085",
    "muted": "#b7a8ca",
    "text": "#f0ebfa",
    "accent": "#a8f02b",
    "on_accent": "#15121d",
    "warning": "#ff9d3d",
    "disabled": "#776a8b",
}


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
            QPalette.ColorRole.Window: DARK_COLORS["window"],
            QPalette.ColorRole.WindowText: DARK_COLORS["text"],
            QPalette.ColorRole.Base: DARK_COLORS["base"],
            QPalette.ColorRole.AlternateBase: DARK_COLORS["panel"],
            QPalette.ColorRole.Text: DARK_COLORS["text"],
            QPalette.ColorRole.Button: DARK_COLORS["panel"],
            QPalette.ColorRole.ButtonText: DARK_COLORS["text"],
            QPalette.ColorRole.Highlight: DARK_COLORS["accent"],
            QPalette.ColorRole.HighlightedText: DARK_COLORS["on_accent"],
            QPalette.ColorRole.PlaceholderText: DARK_COLORS["muted"],
            QPalette.ColorRole.ToolTipBase: DARK_COLORS["raised"],
            QPalette.ColorRole.ToolTipText: DARK_COLORS["text"],
            QPalette.ColorRole.BrightText: DARK_COLORS["warning"],
            QPalette.ColorRole.Link: DARK_COLORS["accent"],
            QPalette.ColorRole.LinkVisited: DARK_COLORS["muted"],
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
            QPalette.ColorRole.BrightText: "#e03131",
        }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    disabled = QColor(DARK_COLORS["disabled"] if mode == ThemeMode.DARK else "#868e96")
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def _stylesheet(mode: ThemeMode) -> str:
    if mode == ThemeMode.DARK:
        return Template("""
            QMainWindow, QDialog { background: $window; }
            QToolBar { background: $panel; border: 0; border-bottom: 1px solid $raised; spacing: 4px; padding: 0px 4px; }
            QToolBar::separator { background: $raised; width: 1px; margin: 11px 2px; }
            QToolButton { padding: 6px; border-radius: 4px; border: 1px solid transparent; }
            /* 6 px padding + 1 px border = 7 px around the 20 px icon. */
            QToolBar QToolButton { padding: 6px; }
            QToolBar QToolButton[lineToolDropdown="true"] { padding: 6px 0px; }
            QToolBar QToolButton[lineToolMain="true"] { border-top-right-radius: 0; border-bottom-right-radius: 0; }
            QToolBar QToolButton[lineToolDropdown="true"] { border-top-left-radius: 0; border-bottom-left-radius: 0; }
            QToolButton::menu-indicator { image: none; width: 0px; }
            QToolButton:hover { background: $hover; border-color: $border; }
            QToolButton:checked, QToolButton[lineSelected="true"] { background: $raised; border-color: $accent; }
            QTabWidget::pane { border: 0; }
            QTabWidget::tab-bar { alignment: left; }
            QTabBar::tab { padding: 7px 12px; background: $panel; border: 0; margin-right: 1px; }
            QTabBar::tab:!selected:hover { background: $hover; }
            QTabBar::tab:selected { background: $raised; color: $text; border-bottom: 2px solid $accent; }
            QScrollArea { background: $base; border: 0; }
            QScrollBar:vertical { background: $panel; width: 12px; margin: 0; }
            QScrollBar:horizontal { background: $panel; height: 12px; margin: 0; }
            QScrollBar::handle:vertical {
                background: $border;
                min-height: 28px;
                margin: 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: $border;
                min-width: 28px;
                margin: 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:hover { background: $accent; }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0;
                height: 0;
                background: transparent;
            }
            QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
            QMenu { background: $panel; border: 1px solid $hover; }
            QMenu#toolbarOverflowMenu { padding: 4px 8px; }
            QMenu::item { padding: 6px 18px; }
            QMenu::item:selected { background: $hover; color: $accent; }
            QMenu QWidget { color: $text; }
            QPushButton {
                background: $raised;
                color: $text;
                border: 1px solid $border;
                border-radius: 3px;
                padding: 4px 10px;
            }
            QPushButton:hover { background: $hover; border-color: $accent; }
            QPushButton:checked { background: $accent; color: $on_accent; border-color: $accent; }
            QPushButton:default { border-color: $accent; }
            QPushButton:disabled { background: $panel; color: $disabled; border-color: $raised; }
            QSpinBox {
                background: $raised;
                color: $text;
                border: 1px solid $border;
                border-radius: 3px;
                padding: 3px 22px 3px 7px;
                selection-background-color: $accent;
                selection-color: $on_accent;
            }
            QSpinBox:hover, QSpinBox:focus { border-color: $accent; }
            QSpinBox:disabled { background: $panel; color: $muted; border-color: $hover; }
            QComboBox {
                background: $raised;
                color: $text;
                border: 1px solid $border;
                border-radius: 3px;
                padding: 3px 22px 3px 7px;
                selection-background-color: $accent;
                selection-color: $on_accent;
            }
            QComboBox:hover, QComboBox:focus { border-color: $accent; }
            QComboBox::drop-down { border: 0; width: 22px; }
            QComboBox QAbstractItemView {
                background: $raised;
                color: $text;
                border: 1px solid $border;
                selection-background-color: $accent;
                selection-color: $on_accent;
                outline: 0;
            }
            QSpinBox QToolButton[spinArrow="true"] {
                background: $hover;
                border: 0;
                border-left: 1px solid $border;
                border-radius: 0;
                padding: 0;
            }
            QSpinBox QToolButton[spinArrow="true"]:hover { background: $border; }
            QSlider::groove:horizontal { height: 4px; background: $border; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: $accent;
                border: 1px solid $border;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QToolTip { background: $raised; color: $text; border: 1px solid $border; }
            QLineEdit {
                background: $base;
                color: $text;
                border: 1px solid $border;
                border-radius: 3px;
                padding: 3px 7px;
                selection-background-color: $accent;
                selection-color: $on_accent;
            }
            QLineEdit:focus { border-color: $accent; }
        """).substitute(DARK_COLORS)
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
