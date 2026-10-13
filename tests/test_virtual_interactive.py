"""Windows preview backend selection and frame ownership."""
from types import SimpleNamespace
import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from fshot.capture import CaptureRect
from fshot import virtual_interactive
from fshot.virtual_interactive import PreviewFrames, _dxgi_camera


def test_dxgi_camera_matches_device_name_not_resolution(monkeypatch):
    cameras = []

    def create(*, device_idx, output_idx, **_kwargs):
        name = r"\\.\DISPLAY1" if output_idx == 0 else r"\\.\DISPLAY9"
        camera = SimpleNamespace(
            _output=SimpleNamespace(desc=SimpleNamespace(DeviceName=name)),
            released=False,
        )
        camera.release = lambda: setattr(camera, "released", True)
        cameras.append(camera)
        return camera

    monkeypatch.setitem(sys.modules, "dxcam", SimpleNamespace(
        output_info=lambda: "Device[0] Output[0]: Res:(1920,1080)\n"
                            "Device[0] Output[1]: Res:(1920,1080)",
        create=create,
    ))

    chosen = _dxgi_camera(r"\\.\DISPLAY9")
    assert chosen is cameras[1]
    assert cameras[0].released
    assert not chosen.released


def test_dxgi_frame_copies_camera_buffer(qt_app):
    frames = PreviewFrames(CaptureRect(0, 0, 2, 1), QSize(2, 1), 2)
    pixels = bytearray((0, 0, 255, 255, 0, 255, 0, 255))
    frame = SimpleNamespace(data=pixels, shape=(1, 2, 4), strides=(8, 4, 1))
    camera = SimpleNamespace(grab=lambda **_kwargs: frame)

    image = frames._dxgi_frame(camera)
    pixels[:] = bytes(8)
    assert image.pixelColor(0, 0).red() == 255
    assert image.pixelColor(1, 0).green() == 255
    assert image.devicePixelRatio() == 2


def test_preview_worker_falls_back_to_mss_when_dxgi_is_unavailable(qt_app, monkeypatch):
    class MSS:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(mss=MSS))

    def unavailable(_device):
        raise RuntimeError("no DXGI output")

    monkeypatch.setattr(virtual_interactive, "_dxgi_camera", unavailable)
    frames = PreviewFrames(CaptureRect(0, 0, 2, 1), QSize(2, 1), 1, "missing")
    image = QImage(2, 1, QImage.Format.Format_RGB32)

    def frame(_capture):
        frames.stopped.set()
        return image

    monkeypatch.setattr(frames, "_frame", frame)
    frames._run()
    assert frames.take_latest().size() == QSize(2, 1)
