from types import SimpleNamespace

from fshot import __version__
from fshot.app import _activate_window, main


def test_version_flag_exits_without_starting_gui(monkeypatch, capsys):
    monkeypatch.setattr("fshot.app.sys.argv", ["fshot", "--version"])

    assert main() == 0
    assert capsys.readouterr().out.strip() == f"FShot {__version__}"


def test_activate_window_uses_native_foreground_calls_on_windows(qt_app, monkeypatch):
    qt_calls = []
    native_calls = []
    foreground = [999]
    window = SimpleNamespace(
        showNormal=lambda: qt_calls.append("show"),
        raise_=lambda: qt_calls.append("raise"),
        activateWindow=lambda: qt_calls.append("activate"),
        winId=lambda: 123,
    )
    gui = SimpleNamespace(
        ShowWindow=lambda hwnd, command: native_calls.append(("show", hwnd, command)),
        BringWindowToTop=lambda hwnd: native_calls.append(("top", hwnd)),
        SetForegroundWindow=lambda hwnd: (
            native_calls.append(("foreground", hwnd)), foreground.__setitem__(0, hwnd)
        ),
        GetForegroundWindow=lambda: foreground[0],
    )
    monkeypatch.setattr("fshot.app.sys.platform", "win32")
    monkeypatch.setattr("fshot.app.win32gui", gui)
    monkeypatch.setattr("fshot.app.win32con", SimpleNamespace(SW_RESTORE=9))

    _activate_window(window)

    assert qt_calls == ["show", "raise", "activate"]
    assert native_calls == [
        ("show", 123, 9), ("top", 123), ("foreground", 123)
    ]


def test_activate_window_raises_z_order_when_initial_request_is_denied(qt_app, monkeypatch):
    foreground = [999]
    attempts = []
    positions = []

    def set_foreground(hwnd):
        attempts.append(hwnd)

    window = SimpleNamespace(
        showNormal=lambda: None,
        raise_=lambda: None,
        activateWindow=lambda: None,
        winId=lambda: 123,
    )
    monkeypatch.setattr("fshot.app.sys.platform", "win32")
    monkeypatch.setattr(
        "fshot.app.win32gui",
        SimpleNamespace(
            ShowWindow=lambda *_args: None,
            BringWindowToTop=lambda _hwnd: None,
            SetForegroundWindow=set_foreground,
            GetForegroundWindow=lambda: foreground[0],
            SetWindowPos=lambda *args: positions.append(args),
        ),
    )
    monkeypatch.setattr(
        "fshot.app.win32con",
        SimpleNamespace(
            SW_RESTORE=9,
            SWP_NOMOVE=1,
            SWP_NOSIZE=2,
            SWP_SHOWWINDOW=4,
            HWND_TOPMOST=-1,
            HWND_NOTOPMOST=-2,
        ),
    )

    _activate_window(window)

    assert attempts == [123, 123]
    assert [call[1] for call in positions] == [-1, -2]


def test_activate_window_tolerates_foreground_errors_during_drag(qt_app, monkeypatch):
    attempts = []
    positions = []

    def set_foreground(hwnd):
        attempts.append(hwnd)
        raise RuntimeError("foreground activation denied while dragging")

    window = SimpleNamespace(
        showNormal=lambda: None,
        raise_=lambda: None,
        activateWindow=lambda: None,
        winId=lambda: 123,
    )
    monkeypatch.setattr("fshot.app.sys.platform", "win32")
    monkeypatch.setattr(
        "fshot.app.win32gui",
        SimpleNamespace(
            ShowWindow=lambda *_args: None,
            BringWindowToTop=lambda _hwnd: None,
            SetForegroundWindow=set_foreground,
            GetForegroundWindow=lambda: 999,
            SetWindowPos=lambda *args: positions.append(args),
        ),
    )
    monkeypatch.setattr(
        "fshot.app.win32con",
        SimpleNamespace(
            SW_RESTORE=9,
            SWP_NOMOVE=1,
            SWP_NOSIZE=2,
            SWP_SHOWWINDOW=4,
            HWND_TOPMOST=-1,
            HWND_NOTOPMOST=-2,
        ),
    )

    _activate_window(window)

    assert attempts == [123, 123]
    assert [call[1] for call in positions] == [-1, -2]
