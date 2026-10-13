"""Compare MSS and DXGI on the active Windows virtual display.

Run with: uv run python scripts/benchmark_windows_preview.py
"""
from __future__ import annotations

import statistics
import time

import mss
from PySide6.QtCore import QSize

from fshot.virtual_interactive import PreviewFrames, _dxgi_camera
from fshot.virtual_screen import displays


def summarize(label: str, samples: list[float]) -> None:
    samples.sort()
    print(f"{label}: mean={statistics.mean(samples):.1f} ms, "
          f"p95={samples[int(0.95 * (len(samples) - 1))]:.1f} ms")


def main() -> None:
    display = next((item for item in displays() if item.is_virtual), None)
    if display is None:
        raise SystemExit("No active virtual display")
    rect = display.rect
    preview = QSize(round(rect.width * min(1, 940 / rect.height)),
                    round(rect.height * min(1, 940 / rect.height)))
    frames = PreviewFrames(rect, preview, 1, display.device)
    print(f"Display: {display.device} {rect.width}x{rect.height}; "
          f"preview: {preview.width()}x{preview.height()}")

    mss_samples, dxgi_samples = [], []
    with mss.MSS() as old, _dxgi_camera(display.device) as new:
        print(f"DXGI source: {new.width}x{new.height}")
        for index in range(50):
            started = time.perf_counter()
            old_image = frames._frame(old)
            middle = time.perf_counter()
            new_image = frames._dxgi_frame(new)
            finished = time.perf_counter()
            if index >= 5:
                assert new_image is not None and old_image.size() == new_image.size()
                mss_samples.append((middle - started) * 1000)
                dxgi_samples.append((finished - middle) * 1000)

    summarize("MSS grab and resize", mss_samples)
    summarize("DXGI grab and resize", dxgi_samples)


if __name__ == "__main__":
    main()
