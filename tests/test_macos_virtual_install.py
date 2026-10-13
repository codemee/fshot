import sys
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from fshot.capture import CaptureRect
from fshot.platforms import macos_virtual as virtual
from fshot.platforms import macos_virtual_setup as setup
from fshot.platforms import macos_virtual_install as install
from test_macos_virtual_setup import Settings


def missing():
    raise RuntimeError("missing")


@pytest.mark.parametrize("brew_present", [True, False])
def test_missing_app_installation_continues_after_consent(monkeypatch, brew_present):
    calls = []
    installed = []
    brew = ["/mock path/bin/brew" if brew_present else None]
    monkeypatch.setattr(setup, "cli_path", lambda: "/app" if installed else missing())
    monkeypatch.setattr(install, "brew_path", lambda: brew[0])
    monkeypatch.setattr(install, "ask", lambda parent, tr, key: calls.append(key) or True)
    monkeypatch.setattr(install, "install_homebrew", lambda *args: brew.__setitem__(0, "/mock path/bin/brew"))
    monkeypatch.setattr(install, "terminal_install", lambda parent, tr, command: installed.append(command))
    assert install.ensure_application(None, lambda key: key)
    assert calls == ["mac_virtual_install_question"] + ([] if brew_present else ["mac_virtual_brew_question"])
    assert "'/mock path/bin/brew' install --cask betterdisplay" in installed[0]


@pytest.mark.parametrize("declined", ["mac_virtual_install_question", "mac_virtual_brew_question"])
def test_declining_installation_does_not_launch_any_installer(monkeypatch, declined):
    monkeypatch.setattr(setup, "cli_path", missing)
    monkeypatch.setattr(install, "brew_path", lambda: None)
    monkeypatch.setattr(install, "ask", lambda parent, tr, key: key != declined)
    monkeypatch.setattr(install, "terminal_install", lambda *args: pytest.fail("must not install"))
    assert not install.ensure_application(None, lambda key: key)


def test_existing_app_does_not_require_brew_or_prompt(monkeypatch):
    monkeypatch.setattr(setup, "cli_path", lambda: "/app")
    monkeypatch.setattr(install, "brew_path", lambda: pytest.fail("brew not needed"))
    monkeypatch.setattr(install, "ask", lambda *args: pytest.fail("prompt not needed"))
    assert install.ensure_application(None, lambda key: key)


def test_installer_success_requires_app_to_actually_exist(monkeypatch):
    monkeypatch.setattr(setup, "cli_path", missing)
    monkeypatch.setattr(install, "brew_path", lambda: "/brew")
    monkeypatch.setattr(install, "ask", lambda *args: True)
    monkeypatch.setattr(install, "terminal_install", lambda *args: None)
    with pytest.raises(RuntimeError, match="missing"):
        install.ensure_application(None, lambda key: key)


def test_terminal_wrapper_quotes_paths_and_records_exit_code(tmp_path):
    result = tmp_path / "it's a result"
    script = install.terminal_script("exit 7", result)
    assert "(\nexit 7\n)" in script
    assert "fshot_status=$?" in script
    assert "'\"'\"'" in script


def choose_fixture(monkeypatch, connected):
    monkeypatch.setitem(sys.modules, "ScreenCaptureKit", SimpleNamespace(SCScreenshotManager=object))
    monkeypatch.setattr(virtual.macos, "accessibility_allowed", lambda: True)
    monkeypatch.setattr(virtual.macos, "screen_recording_allowed", lambda: True)
    monkeypatch.setattr(virtual.macos, "_frameworks", lambda: (None, SimpleNamespace(CGMainDisplayID=lambda: 2)))
    monkeypatch.setattr(virtual, "displays", lambda: connected)


def display(name=setup.DISPLAY_NAME):
    rect = CaptureRect(1920, 0, 1920, 1080)
    return virtual.Display("fixed-uuid", 70, name, rect, rect, 3840, 2160)


def test_connected_fixed_display_is_selected_without_any_prompt(monkeypatch):
    choose_fixture(monkeypatch, [display(), display("Other")])
    monkeypatch.setattr(install, "ensure_application", lambda *args: pytest.fail("not needed"))
    monkeypatch.setattr(setup, "ensure_display", lambda *args: pytest.fail("not needed"))
    settings = Settings()
    assert virtual.choose_display(None, settings, lambda key: key)
    assert settings.value(virtual.DISPLAY_KEY) == "fixed-uuid"


@pytest.mark.parametrize("approved", [True, False])
def test_prepare_then_select_fixed_display_or_leave_previous_setting(monkeypatch, approved):
    choose_fixture(monkeypatch, [display("Other")])
    monkeypatch.setattr(install, "ensure_application", lambda *args: approved)
    monkeypatch.setattr(setup, "ensure_display", lambda *args: display() if approved else pytest.fail("not approved"))
    settings = Settings()
    settings.setValue(virtual.DISPLAY_KEY, "previous")
    assert virtual.choose_display(None, settings, lambda key: key) == approved
    assert settings.value(virtual.DISPLAY_KEY) == ("fixed-uuid" if approved else "previous")


def test_duplicate_fixed_display_names_are_rejected(monkeypatch):
    choose_fixture(monkeypatch, [display(), display()])
    with pytest.raises(RuntimeError, match="ambiguous"):
        virtual.choose_display(None, Settings(), lambda key: key)


@pytest.mark.parametrize("status", ["0", "7", ""])
def test_terminal_completion_failure_and_timeout_without_launching_terminal(qt_app, tmp_path, monkeypatch, status):
    monkeypatch.setattr(install.tempfile, "TemporaryDirectory", lambda **kwargs: nullcontext(str(tmp_path)))
    launches = []

    def launch(parent, arguments, **kwargs):
        launches.append((arguments, kwargs))
        (tmp_path / "result").write_text(status, encoding="utf-8")

    monkeypatch.setattr(setup, "run_cli", launch)
    if status == "0":
        install.terminal_install(None, lambda key: key, "exit 0", timeout=0)
    else:
        expected = "mac_virtual_install_failed" if status else "mac_virtual_install_timeout"
        with pytest.raises(RuntimeError, match=expected):
            install.terminal_install(None, lambda key: key, "exit 0", timeout=0)
    assert launches[0][1]["executable"] == "/usr/bin/osascript"
    assert "do script" in launches[0][0][1]
