"""Export the application's actual toolbar glyphs for the README.

Run with: uv run python scripts/export_toolbar_icons.py
This only renders documentation assets; it does not start FShot or capture screens.
"""
from __future__ import annotations

import os
from pathlib import Path

# Windows' offscreen plugin lacks its native font database (Chinese becomes boxes).
# QApplication alone opens no windows; use the native plugin for faithful glyphs.
if os.name != "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QStyle, QStyleOption

from fshot.icons import tool_icon
from fshot.settings import DrawingSettings


def main() -> None:
    app = QApplication([])
    destination = Path(__file__).resolve().parents[1] / "docs" / "images" / "toolbar"
    destination.mkdir(parents=True, exist_ok=True)
    icons = {name: tool_icon(name) for name in (
        "pen", "rectangle", "measure", "text", "mosaic", "rotate_clockwise",
        "flip_horizontal", "flip_vertical", "resize_down", "undo", "copy",
        "save", "save_as", "zoom_in", "zoom_out", "keyboard",
    )}
    icons["line"] = tool_icon("line", line_start="circle", line_end="arrow")
    drawing = DrawingSettings.default()
    icons["style"] = tool_icon("style", drawing.color, drawing.line_width)
    for suffix, checked in (("off", False), ("on", True)):
        icons[f"cursor_{suffix}"] = tool_icon("cursor", checked=checked)
    for suffix, checked in (("physical", False), ("virtual", True)):
        icons[f"screen_{suffix}"] = tool_icon("screen_mode", checked=checked)
    for badge in ("off", "5"):
        icons[f"delay_{badge}"] = tool_icon("delay", badge=badge)
    for badge in ("system", "light", "dark"):
        icons[f"theme_{badge}"] = tool_icon("theme", badge=badge)
    for badge in ("system", "zh_TW", "en"):
        icons[f"language_{badge}"] = tool_icon("language", badge=badge)

    for name, icon in icons.items():
        # A light tile keeps the real light-theme glyph legible on either GitHub theme.
        tile = QPixmap(40, 40)
        tile.fill(QColor("#f8f9fa"))
        painter = QPainter(tile)
        icon.paint(painter, QRect(4, 4, 32, 32))
        painter.end()
        if not tile.save(str(destination / f"{name}.png")):
            raise RuntimeError(f"Could not export {name}")

    tile = QPixmap(40, 40)
    tile.fill(QColor("#f8f9fa"))
    painter = QPainter(tile)
    option = QStyleOption()
    option.rect = QRect(10, 10, 20, 20)
    option.state = QStyle.StateFlag.State_Enabled
    app.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorArrowDown, option, painter)
    painter.end()
    if not tile.save(str(destination / "line_dropdown.png")):
        raise RuntimeError("Could not export line dropdown")
    print(f"Exported {len(icons)+1} toolbar icons to {destination}")


if __name__ == "__main__":
    main()
