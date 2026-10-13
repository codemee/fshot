"""Consent-driven Homebrew installation with interactive Terminal authentication."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import tempfile
import time

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog


def brew_path():
    found = shutil.which("brew")
    if found:
        return found
    # Finder-launched bundles do not inherit shell PATH, including custom installs.
    for path in (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew"),
                 Path.home() / "homebrew/bin/brew"):
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def ask(parent, tr, key):
    return QMessageBox.question(parent, "FShot", tr(key),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


def terminal_script(command: str, result: Path) -> str:
    # Run in a subshell so an installer failure/exit still writes completion.
    return ("#!/bin/bash\n(\n" + command + "\n)\n"
            "fshot_status=$?\n"
            f"printf '%s' \"$fshot_status\" > {shlex.quote(str(result))}\n"
            "exit \"$fshot_status\"\n")


def terminal_install(parent, tr, command: str, *, timeout=1800):
    from fshot.platforms.macos_virtual_setup import run_cli

    with tempfile.TemporaryDirectory(prefix="fshot-install-") as folder:
        result = Path(folder) / "result"
        result.touch(mode=0o600)
        script = Path(folder) / "install.sh"
        script.write_text(terminal_script(command, result), encoding="utf-8")
        shell = "/bin/bash " + shlex.quote(str(script))
        # JSON string escaping also produces an AppleScript-safe literal here.
        run_cli(parent, ["-e", 'tell application "Terminal"\nactivate\ndo script '
                         + json.dumps(shell) + '\nend tell'], executable="/usr/bin/osascript")
        progress = QProgressDialog(tr("mac_virtual_install_progress"), "", 0, 0, parent)
        progress.setCancelButton(None)
        progress.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        loop = QEventLoop()
        timer = QTimer()
        deadline = time.monotonic() + timeout
        outcome = []

        def check():
            try:
                status = result.read_text(encoding="utf-8").strip()
            except OSError:
                status = ""
            if status:
                outcome.append(status)
                loop.quit()
            elif time.monotonic() >= deadline:
                loop.quit()

        timer.timeout.connect(check)
        timer.start(250)
        progress.show()
        try:
            loop.exec()
        finally:
            timer.stop()
            progress.close()
        if not outcome:
            raise RuntimeError(tr("mac_virtual_install_timeout"))
        if outcome != ["0"]:
            raise RuntimeError(tr("mac_virtual_install_failed"))


def install_homebrew(parent, tr):
    # The official interactive installer retains its own confirmation and sudo.
    command = (
        'fshot_installer=$(mktemp -t fshot-homebrew) || exit 1\n'
        '/usr/bin/curl --fail --location --proto =https --tlsv1.2 '
        'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh '
        '-o "$fshot_installer" && /bin/bash "$fshot_installer"\n'
        'fshot_result=$?\n/bin/rm -f "$fshot_installer"\nexit "$fshot_result"'
    )
    terminal_install(parent, tr, command)
    if not brew_path():
        raise RuntimeError(tr("mac_virtual_install_failed"))


def ensure_application(parent, tr):
    from fshot.platforms.macos_virtual_setup import cli_path

    try:
        cli_path()
        return True
    except RuntimeError:
        pass
    if not ask(parent, tr, "mac_virtual_install_question"):
        return False
    brew = brew_path()
    if not brew:
        if not ask(parent, tr, "mac_virtual_brew_question"):
            return False
        install_homebrew(parent, tr)
        brew = brew_path()
    if not brew:
        raise RuntimeError(tr("mac_virtual_install_failed"))
    # PATH also needs the brew directory for helpers when launched from Finder.
    command = ("export PATH=" + shlex.quote(str(Path(brew).parent)) + ':"$PATH"\n'
               + shlex.quote(brew) + " install --cask betterdisplay")
    terminal_install(parent, tr, command)
    cli_path()  # Verify actual installation, not just a shell exit code.
    return True
