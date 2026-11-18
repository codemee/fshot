from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

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


class ShapeStyle(str, Enum):
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"


class LineEndStyle(str, Enum):
    NONE = "none"
    ARROW = "arrow"
    CIRCLE = "circle"


@dataclass
class CaptureSettings:
    include_cursor: bool = False
    delay_seconds: float = 0
    virtual_screen: bool = False
    virtual_repaint_seconds: float = 1.5


def virtual_repaint_seconds(value) -> float:
    """Read persisted repaint timing without allowing invalid or unbounded waits."""
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        return 1.5
    return min(10.0, max(0.0, seconds)) if math.isfinite(seconds) else 1.5


@dataclass
class DrawingSettings:
    color: QColor
    line_width: int = 3
    shape_style: ShapeStyle = ShapeStyle.RECTANGLE
    line_start_style: LineEndStyle = LineEndStyle.CIRCLE
    line_end_style: LineEndStyle = LineEndStyle.ARROW
    font_family: str = "Segoe UI"
    font_size: int = 24

    @classmethod
    def default(cls) -> "DrawingSettings":
        return cls(color=QColor("#e03131"))
