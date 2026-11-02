import plistlib
import sys
from pathlib import Path
from types import SimpleNamespace

from fshot import autostart


def test_windows_registration_quotes_paths_and_can_be_removed(monkeypatch):
    values = {}
    class Key:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def read(key, name):
        if name not in values: raise FileNotFoundError(name)
        return values[name], 1
    def delete(key, name):
        if name not in values: raise FileNotFoundError(name)
        del values[name]
    registry = SimpleNamespace(HKEY_CURRENT_USER=1, REG_SZ=1,
        OpenKey=lambda *a: Key(), CreateKey=lambda *a: Key(), QueryValueEx=read,
        SetValueEx=lambda key, name, reserved, kind, value: values.update({name: value}),
        DeleteValue=delete)
    monkeypatch.setitem(sys.modules, 'winreg', registry)
    monkeypatch.setattr(autostart.sys, 'platform', 'win32')
    monkeypatch.setattr(autostart, 'launch_command', lambda: [r'C:\Program Files\FShot.exe'])
    manager = autostart.Autostart()
    assert not manager.enabled()
    manager.set_enabled(True)
    assert values['FShot'] == '"C:\\Program Files\\FShot.exe"'
    assert manager.enabled()
    manager.set_enabled(False)
    manager.set_enabled(False)
    assert not manager.enabled()


def test_macos_agent_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart.sys, 'platform', 'darwin')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    command = ['/Applications/FShot.app/Contents/MacOS/FShot']
    monkeypatch.setattr(autostart, 'launch_command', lambda: command)
    manager = autostart.Autostart()
    assert not manager.enabled()
    manager.set_enabled(True)
    payload = plistlib.loads(manager.agent_path.read_bytes())
    assert payload['ProgramArguments'] == command
    assert payload['RunAtLoad'] is True
    assert manager.enabled()
    manager.set_enabled(False)
    assert not manager.enabled()


def test_frozen_launch_command_uses_current_executable(monkeypatch):
    monkeypatch.setattr(autostart.sys, 'frozen', True, raising=False)
    assert autostart.launch_command() == [str(Path(sys.executable).resolve())]
