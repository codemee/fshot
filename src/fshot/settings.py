from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QColor


class CaptureMode(str, Enum):
    ACTIVE_WINDOW = "active_window"
    REGION = "region"
    FULLSCREEN = "fullscreen"
    WINDOW_UNDER_CURSOR = "window_under_cursor"


class Tool(str, Enum):
    PEN = "pen"
    LINE = "line"
    RECTANGLE = "rectangle"
    MEASURE = "measure"
    TEXT = "text"
    MOSAIC = "mosaic"


class LineEndStyle(str, Enum):
    NONE = "none"
    ARROW = "arrow"
    CIRCLE = "circle"


@dataclass
class CaptureSettings:
    include_cursor: bool = False
    delay_seconds: float = 0


@dataclass
class DrawingSettings:
    color: QColor
    line_width: int = 3
    line_start_style: LineEndStyle = LineEndStyle.NONE
    line_end_style: LineEndStyle = LineEndStyle.NONE
    font_family: str = "Segoe UI"
    font_size: int = 24

    @classmethod
    def default(cls) -> "DrawingSettings":
        return cls(color=QColor("#e03131"))
