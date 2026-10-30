# Installing the Windows app

[繁體中文](install-windows.md) | [English](install-windows.en.md)

The Windows build is a portable single EXE. This personal-project build has no Authenticode publisher signature, so Windows may report an unknown publisher or show a Microsoft Defender SmartScreen warning.

Code signing policy: [signing scope, team roles, and privacy](code-signing-policy.md).

## Download and verify

1. Download `FShot-<version>-windows-x64.exe` only from [FShot GitHub Releases](https://github.com/codemee/fshot/releases).
2. Download `SHA256SUMS.txt` from the same release.
3. Run this in PowerShell:

```powershell
Get-FileHash .\FShot-*-windows-x64.exe -Algorithm SHA256
```

Compare the result with `SHA256SUMS.txt`. A checksum verifies file integrity but does not replace a publisher signature; also verify that the file came from the official GitHub repository.

## First launch

Run the EXE directly. If SmartScreen says that Windows protected your PC:

1. Confirm the filename, download source, and SHA-256.
2. Select **More info**.
3. Confirm that the app is FShot, then select **Run anyway**.

The single-file build extracts required components into the user's temporary directory on each launch. Its first launch may be slower, and heuristic antivirus scanners can be more suspicious of this layout. If the file is quarantined, verify its source and checksum before reviewing it in Windows Security. Do not disable protection for an entire directory.

## Updates

The packaged app checks GitHub Releases. When a new version is available it opens the download page; it never replaces the current unsigned EXE automatically. Download, verify, and replace the old file manually.
