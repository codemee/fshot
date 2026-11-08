# Installing the Windows app

[繁體中文](install-windows.md) | [English](install-windows.en.md)

The Windows build is a portable folder distributed as a ZIP. This personal-project build has no Authenticode publisher signature, so Windows may report an unknown publisher or show a Microsoft Defender SmartScreen warning.

Code signing status: [download verification and current signing status](code-signing-policy.md).

## Download and verify

1. Download `FShot-<version>-windows-x64.zip` only from [FShot GitHub Releases](https://github.com/codemee/fshot/releases).
2. Download `SHA256SUMS.txt` from the same release.
3. Run this in PowerShell:

```powershell
Get-FileHash .\FShot-*-windows-x64.zip -Algorithm SHA256
```

Compare the result with `SHA256SUMS.txt`. A checksum verifies file integrity but does not replace a publisher signature; also verify that the file came from the official GitHub repository.

## First launch

Extract the whole ZIP to a stable location and run `FShot.exe` inside it. Keep `_internal` and `LICENSE` with the executable. Do not run inside the ZIP or move only the EXE. If SmartScreen says that Windows protected your PC:

1. Confirm the filename, download source, and SHA-256.
2. Select **More info**.
3. Confirm that the app is FShot, then select **Run anyway**.

The folder build pays the extraction cost when you unzip the download, then loads dependencies directly from that folder. Antivirus scanning and file caching can still affect first launch. If the file is quarantined, verify its source and checksum before reviewing it in Windows Security. Do not disable protection for an entire directory.

## Updates

The packaged app checks GitHub Releases. When a new version is available it opens the download page; it never replaces the current unsigned EXE automatically. Download and verify the ZIP, quit FShot, and replace the complete folder to avoid mixing DLL versions. Disable Start at login before moving it, then enable it again from the new location and update shortcuts.
