"""Application-rendered message dialogs with shared light/dark styling."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from fshot.i18n import LanguageManager


class MessageDialog(QDialog):
    # Keep Qt's familiar roles and result values at the application boundary.
    Icon = QMessageBox.Icon
    StandardButton = QMessageBox.StandardButton
    ButtonRole = QMessageBox.ButtonRole

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("messageDialog")
        self.setWindowTitle("FShot")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(420)
        self.setMaximumWidth(560)
        self._clicked: QPushButton | None = None
        self._escape: QPushButton | None = None
        self._standard: dict[QPushButton, QMessageBox.StandardButton] = {}
        self._language = getattr(parent, "language_manager", None) or LanguageManager()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        heading_row = QHBoxLayout()
        heading_row.setSpacing(12)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        self.heading = QLabel()
        self.heading.setObjectName("messageHeading")
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        self.heading.setWordWrap(True)
        self.heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        heading_row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        heading_row.addWidget(self.heading, 1)
        layout.addLayout(heading_row)
        self.body = QTextEdit()
        self.body.setObjectName("messageBody")
        self.body.setReadOnly(True)
        self.body.setFrameShape(QFrame.Shape.NoFrame)
        self.body.document().setDocumentMargin(0)
        self.body.setTabChangesFocus(True)
        layout.addWidget(self.body)
        self.footer = QHBoxLayout()
        self.footer.setContentsMargins(0, 8, 0, 0)
        self.footer.setSpacing(8)
        self.footer.addStretch()
        layout.addLayout(self.footer)
        self.setIcon(self.Icon.Information)

    def showEvent(self, event) -> None:
        # Bound the whole dialog, not just the text area. Inherited/native
        # window geometry must not stretch the header to the screen height.
        self.ensurePolished()
        layout = self.layout()
        layout.activate()
        width = max(self.minimumWidth(), min(self.maximumWidth(), self.sizeHint().width()))
        height = layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else layout.sizeHint().height()
        self.setFixedHeight(height)
        self.resize(width, height)
        super().showEvent(event)

    def setWindowTitle(self, title: str) -> None:
        super().setWindowTitle(title)
        if hasattr(self, "heading") and title != "FShot":
            self.heading.setText(title)

    def setText(self, text: str) -> None:
        self.body.ensurePolished()
        self.body.setPlainText(text)
        self.body.document().setTextWidth(self.minimumWidth() - 48)
        height = int(self.body.document().size().height()) + 4
        self.body.setFixedHeight(min(240, max(24, height)))

    def setIcon(self, icon: QMessageBox.Icon) -> None:
        self._icon = icon
        kind = {
            self.Icon.Question: "question",
            self.Icon.Warning: "warning",
            self.Icon.Critical: "error",
        }.get(icon, "information")
        self.heading.setText(self._language.text(f"message_{kind}"))
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        if kind in {"question", "warning"}:
            color = QColor("#ff9d3d" if dark else "#a94b00")
        elif kind == "error":
            color = QColor("#ff8c83" if dark else "#c92a2a")
        else:
            color = self.palette().color(QPalette.ColorRole.Highlight)
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 3))
        painter.drawEllipse(5, 5, 54, 54)
        painter.setFont(QFont(self.font().family(), 24, QFont.Weight.DemiBold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "!" if kind != "information" else "i")
        painter.end()
        pixmap.setDevicePixelRatio(2)
        self.icon_label.setPixmap(pixmap)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and hasattr(self, "_icon"):
            heading = self.heading.text()
            self.setIcon(self._icon)
            self.heading.setText(heading)

    def addButton(self, text: str, role: QMessageBox.ButtonRole) -> QPushButton:
        button = QPushButton(text, self)
        button.setMinimumSize(88, 34)
        button.setAutoDefault(False)
        if role in (self.ButtonRole.AcceptRole, self.ButtonRole.YesRole):
            style_role = "primary"
        elif role == self.ButtonRole.DestructiveRole:
            style_role = "destructive"
        else:
            style_role = "secondary"
        button.setProperty("dialogRole", style_role)
        self.footer.addWidget(button)
        button.clicked.connect(lambda _checked=False: self._choose(button))
        if role in (self.ButtonRole.RejectRole, self.ButtonRole.NoRole) and self._escape is None:
            self._escape = button
        return button

    def _choose(self, button: QPushButton) -> None:
        self._clicked = button
        self.done(QDialog.DialogCode.Accepted)

    def clickedButton(self) -> QPushButton | None:
        return self._clicked

    def setDefaultButton(self, button: QPushButton) -> None:
        for child in self.findChildren(QPushButton):
            child.setDefault(child is button)
        button.setFocus()

    def reject(self) -> None:
        self._clicked = self._escape
        super().reject()

    @classmethod
    def _message(cls, parent, title, text, icon, buttons, default):
        dialog = cls(parent)
        dialog.setIcon(icon)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        preferred = None
        for standard, label, role in (
            (cls.StandardButton.No, "cancel", cls.ButtonRole.RejectRole),
            (cls.StandardButton.Yes, "continue", cls.ButtonRole.AcceptRole),
            (cls.StandardButton.Ok, "ok", cls.ButtonRole.AcceptRole),
        ):
            if buttons & standard:
                button = dialog.addButton(dialog._language.text(label), role)
                dialog._standard[button] = standard
                if standard == default:
                    preferred = button
        if preferred is not None:
            dialog.setDefaultButton(preferred)
        dialog.exec()
        result = dialog._standard.get(dialog.clickedButton(), cls.StandardButton.No)
        dialog.deleteLater()
        return result

    @classmethod
    def unsaved(cls, parent, title: str, text: str, *, multiple: bool):
        dialog = cls(parent)
        dialog.setIcon(cls.Icon.Warning)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        for standard, label, role, name in (
            (cls.StandardButton.Cancel, "cancel", cls.ButtonRole.RejectRole, "cancel"),
            (cls.StandardButton.Discard, "dont_save", cls.ButtonRole.DestructiveRole, "discard"),
            (cls.StandardButton.Save, "save_all" if multiple else "save", cls.ButtonRole.AcceptRole, "save"),
        ):
            button = dialog.addButton(dialog._language.text(label), role)
            button.setObjectName(name)
            dialog._standard[button] = standard
            if standard == cls.StandardButton.Cancel:
                dialog.setDefaultButton(button)
        dialog.exec()
        result = dialog._standard.get(dialog.clickedButton(), cls.StandardButton.Cancel)
        dialog.deleteLater()
        return result

    @classmethod
    def question(cls, parent, title, text, buttons=None, default=None):
        return cls._message(parent, title, text, cls.Icon.Question,
                            buttons or cls.StandardButton.Yes | cls.StandardButton.No,
                            default or cls.StandardButton.No)

    @classmethod
    def warning(cls, parent, title, text):
        return cls._message(parent, title, text, cls.Icon.Warning, cls.StandardButton.Ok, cls.StandardButton.Ok)

    @classmethod
    def information(cls, parent, title, text):
        return cls._message(parent, title, text, cls.Icon.Information, cls.StandardButton.Ok, cls.StandardButton.Ok)
