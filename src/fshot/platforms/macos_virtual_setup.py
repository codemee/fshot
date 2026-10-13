"""Opt-in BetterDisplay provisioning; existing displays are never reconfigured."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import time
import uuid

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication


NAME_KEY = "capture/macos_managed_display_name"
IDENTITY_KEY = "capture/macos_managed_display_identity"


def cli_path() -> str:
    # An app bundle works in packaged apps whose PATH does not include Homebrew.
    bundle = Path("/Applications/BetterDisplay.app/Contents/MacOS/BetterDisplay")
    if bundle.is_file():
        return str(bundle)
    executable = shutil.which("betterdisplaycli")
    if executable:
        return executable
    raise RuntimeError("BetterDisplay is required. Install it with: brew install --cask betterdisplay")


def run_cli(parent, arguments: list[str], *, executable: str | None = None) -> str:
    process = QProcess(parent)
    try:
        process.start(executable or cli_path(), arguments)
        if not process.waitForStarted(3000):
            raise RuntimeError("Could not start BetterDisplay. Open the app and enable CLI integration.")
        deadline = time.monotonic() + 35
        while process.state() != QProcess.ProcessState.NotRunning:
            if process.waitForFinished(20):
                break
            QApplication.processEvents()
            if time.monotonic() >= deadline:
                process.kill()
                process.waitForFinished(1000)
                raise RuntimeError("BetterDisplay command timed out. Open the app and enable CLI integration.")
        output = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        error = bytes(process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if process.exitCode() != 0 or process.exitStatus() != QProcess.ExitStatus.NormalExit:
            raise RuntimeError(error or output or "BetterDisplay command failed.")
        # Some versions report CLI failure as text without a failing exit code.
        if output.casefold().startswith("failed"):
            raise RuntimeError(output)
        return output
    finally:
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(1000)
        process.deleteLater()


def parse_identifiers(output: str) -> list[dict]:
    """BetterDisplay returns comma-separated JSON objects, not always an array."""
    text = output.strip()
    if not text:
        return []
    try:
        values = json.loads(text if text.startswith("[") else "[" + text + "]")
    except (ValueError, TypeError) as exc:
        raise RuntimeError("BetterDisplay returned invalid display identifiers.") from exc
    if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
        raise RuntimeError("BetterDisplay returned invalid display identifiers.")
    return values


def identity(item: dict) -> dict:
    return {key: str(item.get(key, "")) for key in ("tagID", "serial", "model", "vendor")}


def ensure_display(parent, settings, tr):
    """Create/reconnect one persistently owned screen after user opts in.

    Keep definitions and connections across FShot exits, like the Windows
    driver workflow. Do not discard or disconnect user-owned resources.
    """
    from fshot.platforms.macos_virtual import displays

    executable = cli_path()
    if executable.startswith("/Applications/"):
        run_cli(parent, ["-a", "/Applications/BetterDisplay.app"], executable="/usr/bin/open")

    def command(*arguments):
        return run_cli(parent, list(arguments), executable=executable)

    def inventory():
        return parse_identifiers(command("get", "--type=VirtualScreen", "--identifiers"))

    entries = inventory()
    name = settings.value(NAME_KEY, "")
    recorded = settings.value(IDENTITY_KEY, "")
    matches = [item for item in entries if name and item.get("name") == name
               and item.get("deviceType") == "VirtualScreen"]
    if len(matches) > 1:
        raise RuntimeError("The managed virtual screen name is ambiguous.")
    if matches:
        item = matches[0]
        if recorded and identity(item) != json.loads(recorded):
            raise RuntimeError("The managed virtual screen identity has changed. Refusing to reconfigure it.")
    else:
        # Persist the unique name before sending create so a timed-out response
        # can be recovered on retry without creating another screen.
        name = "FShot-" + uuid.uuid4().hex[:12]
        settings.setValue(NAME_KEY, name)
        settings.remove(IDENTITY_KEY)
        command("create", "--type=VirtualScreen", f"--virtualScreenName={name}",
                "--aspectWidth=16", "--aspectHeight=9")
        matches = [item for item in inventory() if item.get("name") == name
                   and item.get("deviceType") == "VirtualScreen"]
        if len(matches) != 1:
            raise RuntimeError("Could not identify the newly created virtual screen.")
        item = matches[0]
    fingerprint = identity(item)
    if not all(fingerprint.values()) or not fingerprint["tagID"].lstrip("-").isdigit():
        raise RuntimeError("The virtual screen has no valid persistent identity.")
    settings.setValue(IDENTITY_KEY, json.dumps(fingerprint))
    selector = f"--tagID={fingerprint['tagID']}"
    command("set", selector, "--connected=on")
    command("set", selector, "--resolution=1920x1080", "--hiDPI=on", "--refreshRate=60")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        QApplication.processEvents()
        current = next((display for display in displays() if display.name == name), None)
        if current is not None and (current.pixel_width, current.pixel_height) == (3840, 2160):
            return current
        time.sleep(0.05)
    raise RuntimeError(tr("mac_virtual_setup_failed"))
