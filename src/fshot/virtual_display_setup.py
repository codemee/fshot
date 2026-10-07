"""Opt-in provisioning of the supported VirtualDrivers Windows display driver."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import shutil

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import QProgressDialog


def installed_driver() -> bool:
    """Include disabled devices and the retained signed driver installation files."""
    query = r"""$device = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object FriendlyName -eq 'Virtual Display Driver'
$package = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter 'VirtualDrivers.Virtual-Display-Driver_*' -ErrorAction SilentlyContinue | Select-Object -First 1
$files = (Test-Path 'C:\VirtualDisplayDriver\MttVDD.inf') -or ($package -and (Test-Path (Join-Path $package.FullName 'SignedDrivers\x86\VDD\MttVDD.inf')))
[bool]($device -or $files) | ConvertTo-Json
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", query],
        capture_output=True, text=True, timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to inspect virtual display drivers.")
    return json.loads(result.stdout.strip())


def install_driver(parent, tr) -> None:
    """Download the official signed bundle through WinGet after explicit consent."""
    winget = shutil.which("winget")
    if winget is None:
        raise RuntimeError(tr("virtual_winget_missing"))
    process = QProcess(parent)

    class InstallProgress(QProgressDialog):
        def reject(self):
            if process.state() == QProcess.ProcessState.NotRunning:
                super().reject()

    progress = InstallProgress(tr("virtual_install_progress"), "", 0, 0, parent)
    progress.setCancelButton(None)
    progress.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
    progress.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    process.finished.connect(lambda *_: progress.accept())
    process.errorOccurred.connect(lambda *_: progress.reject())
    process.start(winget, [
        "install", "--id=VirtualDrivers.Virtual-Display-Driver", "-e", "--source", "winget",
        "--silent", "--disable-interactivity", "--accept-source-agreements", "--accept-package-agreements",
    ])
    progress.exec()
    if process.exitCode() != 0 or process.exitStatus() != QProcess.ExitStatus.NormalExit or process.error() == QProcess.ProcessError.FailedToStart:
        output = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        raise RuntimeError(tr("virtual_install_failed") + "\n" + output[-1200:])
    if not installed_driver():
        raise RuntimeError(tr("virtual_install_failed"))


INSTALL_SCRIPT = r"""param([string]$ResultPath)
$ErrorActionPreference = 'Stop'
try {
    $package = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter 'VirtualDrivers.Virtual-Display-Driver_*' -ErrorAction SilentlyContinue | Select-Object -First 1
    $device = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object FriendlyName -eq 'Virtual Display Driver' | Select-Object -First 1
    $config = 'C:\VirtualDisplayDriver\vdd_settings.xml'
    # A previous uninstall may preserve settings while removing the driver files.
    # Reinstall the signed binaries without overwriting that saved configuration.
    if (-not $device -and $package) {
        $source = Join-Path $package.FullName 'SignedDrivers\x86\VDD'
        if ((Get-AuthenticodeSignature -LiteralPath (Join-Path $source 'mttvdd.cat')).Status -ne 'Valid') { throw 'Invalid driver signature' }
        New-Item -ItemType Directory -Path 'C:\VirtualDisplayDriver' -Force | Out-Null
        foreach ($name in @('MttVDD.inf','MttVDD.dll','mttvdd.cat')) {
            Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path 'C:\VirtualDisplayDriver' $name) -Force
        }
    }
    if (-not (Test-Path -LiteralPath $config)) {
        if (-not $package) { throw 'Virtual Driver Control package is required to create the display.' }
        $source = Join-Path $package.FullName 'SignedDrivers\x86\VDD'
        if ((Get-AuthenticodeSignature -LiteralPath (Join-Path $source 'mttvdd.cat')).Status -ne 'Valid') { throw 'Invalid driver signature' }
        New-Item -ItemType Directory -Path 'C:\VirtualDisplayDriver' -Force | Out-Null
        Copy-Item -Path (Join-Path $source '*') -Destination 'C:\VirtualDisplayDriver'
    }
    Copy-Item -LiteralPath $config -Destination ($config + '.fshot-' + (Get-Date -Format 'yyyyMMddHHmmss') + '.bak')
    [xml]$xml = Get-Content -LiteralPath $config
    $xml.vdd_settings.monitors.count = '1'
    $mode = $xml.SelectSingleNode('/vdd_settings/resolutions/resolution[width="3840" and height="2160"]')
    if (-not $mode) {
        $mode = $xml.CreateElement('resolution')
        foreach ($pair in @(@('width','3840'), @('height','2160'), @('refresh_rate','60'))) {
            $node = $xml.CreateElement($pair[0]); $node.InnerText = $pair[1]; [void]$mode.AppendChild($node)
        }
        [void]$xml.vdd_settings.resolutions.AppendChild($mode)
    }
    $xml.Save($config)
    if ($device) {
        pnputil.exe /restart-device $device.InstanceId | Out-Null
        Enable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false -ErrorAction SilentlyContinue
    } else {
        if (-not $package) { throw 'Virtual Driver Control package is required to create the display.' }
        $devcon = Join-Path $package.FullName 'Dependencies\devcon.exe'
        if ((Get-AuthenticodeSignature -LiteralPath $devcon).Status -ne 'Valid') { throw 'Invalid installation tool signature' }
        if ((Get-AuthenticodeSignature -LiteralPath 'C:\VirtualDisplayDriver\mttvdd.cat').Status -ne 'Valid') { throw 'Invalid driver signature' }
        & $devcon install 'C:\VirtualDisplayDriver\MttVDD.inf' 'Root\MttVDD' | Out-Null
        if ($LASTEXITCODE -notin @(0,1)) { throw "Driver installation failed: $LASTEXITCODE" }
    }
    # Result text is diagnostic only. Its ACL must not change an installation's outcome.
    try { [System.IO.File]::WriteAllText($ResultPath, 'OK') } catch {}
    exit 0
} catch {
    $failure = $_.Exception.Message
    try { [System.IO.File]::WriteAllText($ResultPath, $failure) } catch {}
    exit 1
}
"""


def create_4k_display(parent, tr) -> None:
    """Run only after the user chooses Yes; UAC remains a Windows user action."""
    from fshot.virtual_screen import displays, virtual_display_devices
    import win32api
    import win32con

    with tempfile.TemporaryDirectory(prefix="fshot-vdd-", ignore_cleanup_errors=True) as folder:
        script = Path(folder) / "create.ps1"
        result_file = Path(folder) / "result.txt"
        # Create this as the normal user so the elevated helper keeps the existing
        # file ownership/ACL instead of creating a privileged result file.
        result_file.write_text("", encoding="utf-8")
        script.write_text(INSTALL_SCRIPT, encoding="utf-8-sig")
        # Pass paths through environment variables, never interpolate paths into code.
        environment = os.environ.copy()
        environment["FSHOT_VDD_SCRIPT"] = str(script)
        environment["FSHOT_VDD_RESULT"] = str(result_file)
        bootstrap = r"""try {
    $p = Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList @('-NoProfile','-File',('"' + $env:FSHOT_VDD_SCRIPT + '"'),('"' + $env:FSHOT_VDD_RESULT + '"')) -Wait -PassThru
    exit $p.ExitCode
} catch { exit 1 }
"""
        process = QProcess(parent)
        from PySide6.QtCore import QProcessEnvironment
        env = QProcessEnvironment()
        for key, value in environment.items():
            env.insert(key, value)
        process.setProcessEnvironment(env)
        class SetupProgress(QProgressDialog):
            def reject(self):
                if process.state() == QProcess.ProcessState.NotRunning:
                    super().reject()

        progress = SetupProgress(tr("virtual_setup_progress"), "", 0, 0, parent)
        progress.setCancelButton(None)
        progress.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        process.finished.connect(lambda *_: progress.accept())
        process.errorOccurred.connect(lambda *_: progress.reject())
        process.start("powershell.exe", ["-NoProfile", "-Command", bootstrap])
        progress.exec()
        if process.exitCode() != 0 or process.exitStatus() != QProcess.ExitStatus.NormalExit or process.error() == QProcess.ProcessError.FailedToStart:
            try:
                message = result_file.read_text(encoding="utf-8-sig").strip()
            except OSError:
                message = ""
            raise RuntimeError(message or tr("virtual_setup_cancelled"))
        # Exit status is authoritative; unreadable diagnostic files and temporary
        # file cleanup must not prevent display activation and 4K verification.
    subprocess.run([os.path.join(os.environ["WINDIR"], "System32", "DisplaySwitch.exe"), "/extend"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    # Allow the adapter's arrival notifications to reach Qt without blocking UI.
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()
    devices = virtual_display_devices()
    supported = set()
    index = 0
    while True:
        try:
            adapter = win32api.EnumDisplayDevices(None, index)
        except win32api.error:
            break
        index += 1
        if "virtual display driver" in adapter.DeviceString.casefold():
            supported.add(adapter.DeviceName)
    for device in devices & supported:
        try:
            mode = win32api.EnumDisplaySettings(device, win32con.ENUM_CURRENT_SETTINGS)
            mode.PelsWidth, mode.PelsHeight = 3840, 2160
            mode.DisplayFrequency = 60
            result = win32api.ChangeDisplaySettingsEx(device, mode, win32con.CDS_UPDATEREGISTRY)
            if result == win32con.DISP_CHANGE_SUCCESSFUL:
                loop = QEventLoop()
                QTimer.singleShot(500, loop.quit)
                loop.exec()
                if any(d.device == device and (d.rect.width, d.rect.height) == (3840, 2160) for d in displays()):
                    return
        except win32api.error:
            continue
    raise RuntimeError(tr("virtual_setup_failed"))
