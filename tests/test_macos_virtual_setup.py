import json
from types import SimpleNamespace

import pytest

from fshot.platforms import macos_virtual as virtual
from fshot.platforms import macos_virtual_setup as setup
from fshot.capture import CaptureRect


class Settings:
    def __init__(self):
        self.values = {}

    def value(self, key, default=""):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)


def test_cli_parses_comma_separated_objects_and_arrays():
    a = {"name": "FShot", "deviceType": "VirtualScreen"}
    b = {"name": "Other"}
    assert setup.parse_identifiers(json.dumps(a) + "," + json.dumps(b)) == [a, b]
    assert setup.parse_identifiers(json.dumps([a, b])) == [a, b]
    assert setup.parse_identifiers("") == []
    with pytest.raises(RuntimeError, match="invalid"):
        setup.parse_identifiers("Failed: CLI disabled")


def test_provisioning_creates_once_and_only_reconfigures_owned_screen(qt_app, monkeypatch):
    settings = Settings()
    user_screen = {"name": "Other-4K", "deviceType": "VirtualScreen", "tagID": "3",
                   "serial": "user-serial", "vendor": "2198", "model": "55"}
    entries = [user_screen]
    commands = []
    monkeypatch.setattr(setup, "cli_path", lambda: "/mock/betterdisplaycli")

    def run(parent, arguments, **kwargs):
        commands.append(arguments)
        if arguments[0] == "get":
            return json.dumps(entries)
        if arguments[0] == "create":
            name = next(arg.split("=", 1)[1] for arg in arguments if arg.startswith("--virtualScreenName="))
            entries.append({"name": name, "deviceType": "VirtualScreen", "tagID": "4",
                            "serial": "new-serial", "vendor": "2198", "model": "77"})
        return ""

    monkeypatch.setattr(setup, "run_cli", run)
    rect = CaptureRect(1920, 0, 1920, 1080)
    monkeypatch.setattr(virtual, "displays", lambda: [virtual.Display(
        "new-uuid", 70, settings.value(setup.NAME_KEY), rect, rect, 3840, 2160
    )])
    display = setup.ensure_display(None, settings, lambda key: key)
    assert display.identifier == "new-uuid"
    setup.ensure_display(None, settings, lambda key: key)
    assert len([args for args in commands if args[0] == "create"]) == 1
    assert settings.value(setup.NAME_KEY) == setup.DISPLAY_NAME
    mutations = [args for args in commands if args[0] == "set"]
    assert all("--tagID=4" in args for args in mutations)
    assert user_screen == entries[0]
    assert not any(args[0] == "discard" for args in commands)


def test_changed_managed_identity_refuses_all_mutations(monkeypatch):
    settings = Settings()
    settings.setValue(setup.NAME_KEY, setup.DISPLAY_NAME)
    original = {"tagID": "4", "serial": "old", "vendor": "2198", "model": "77"}
    settings.setValue(setup.IDENTITY_KEY, json.dumps(original))
    changed = dict(original, serial="different", name=setup.DISPLAY_NAME, deviceType="VirtualScreen")
    commands = []
    monkeypatch.setattr(setup, "cli_path", lambda: "/mock/betterdisplaycli")
    monkeypatch.setattr(setup, "run_cli", lambda parent, args, **kwargs:
                        (commands.append(args) or json.dumps([changed])))
    with pytest.raises(RuntimeError, match="identity has changed"):
        setup.ensure_display(None, settings, lambda key: key)
    assert [args[0] for args in commands] == ["get"]


def test_retry_after_ambiguous_create_response_reuses_saved_definition(qt_app, monkeypatch):
    settings = Settings()
    entries = []
    creates = []
    monkeypatch.setattr(setup, "cli_path", lambda: "/mock/betterdisplaycli")

    def run(parent, args, **kwargs):
        if args[0] == "get":
            return json.dumps(entries)
        if args[0] == "create":
            creates.append(args)
            name = settings.value(setup.NAME_KEY)
            entries.append({"name": name, "deviceType": "VirtualScreen", "tagID": "8",
                            "serial": "8", "vendor": "2198", "model": "88"})
            raise RuntimeError("timed out")
        return ""

    monkeypatch.setattr(setup, "run_cli", run)
    with pytest.raises(RuntimeError, match="timed out"):
        setup.ensure_display(None, settings, lambda key: key)
    rect = CaptureRect(0, 0, 1920, 1080)
    monkeypatch.setattr(virtual, "displays", lambda: [virtual.Display(
        "recovered", 70, settings.value(setup.NAME_KEY), rect, rect, 3840, 2160
    )])
    assert setup.ensure_display(None, settings, lambda key: key).identifier == "recovered"
    assert len(creates) == 1
