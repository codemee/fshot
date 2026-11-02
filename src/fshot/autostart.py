from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'FShot'


def launch_command() -> list[str]:
    executable = Path(sys.executable).resolve()
    if getattr(sys, 'frozen', False):
        return [str(executable)]
    if sys.platform == 'win32' and executable.with_name('pythonw.exe').exists():
        executable = executable.with_name('pythonw.exe')
    return [str(executable), '-m', 'fshot']


class Autostart:
    @property
    def supported(self) -> bool:
        return sys.platform in {'win32', 'darwin'}

    @property
    def agent_path(self) -> Path:
        return Path.home() / 'Library/LaunchAgents/io.github.codemee.fshot.plist'

    def enabled(self) -> bool:
        if sys.platform == 'win32':
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                    winreg.QueryValueEx(key, VALUE_NAME)
                return True
            except FileNotFoundError:
                return False
        return sys.platform == 'darwin' and self.agent_path.is_file()

    def set_enabled(self, enabled: bool) -> None:
        if sys.platform == 'win32':
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                if enabled:
                    winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ,
                                     subprocess.list2cmdline(launch_command()))
                else:
                    try:
                        winreg.DeleteValue(key, VALUE_NAME)
                    except FileNotFoundError:
                        pass
        elif sys.platform == 'darwin':
            path = self.agent_path
            if enabled:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.tmp')
                temporary.write_bytes(plistlib.dumps({
                    'Label': 'io.github.codemee.fshot',
                    'ProgramArguments': launch_command(), 'RunAtLoad': True,
                }))
                temporary.replace(path)
            else:
                path.unlink(missing_ok=True)
        else:
            raise OSError('Autostart is unavailable on this platform')
