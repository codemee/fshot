# Desktop Packaging

[繁體中文](packaging.md) | [English](packaging.en.md) · [Development Guide](development.en.md)

FShot uses PyInstaller for desktop packages. Builds must run on the target operating system.

The installed `fshot` command uses a console entry point (`project.scripts`) so it inherits the invoking terminal. Desktop packages use PyInstaller's windowed launcher.

## Local build

```powershell
uv sync
uv run python scripts/build_app.py
```

Windows produces `dist/FShot-<version>-windows-x64.exe`. Apple Silicon macOS produces `dist/FShot-<version>-macos-arm64.dmg` containing `FShot.app` and an Applications shortcut. Intel macOS is not supported.

Generated icons and Windows version resources live under `build/package-assets` and are not source files. The PyInstaller spec copies FShot package metadata so the frozen application title and update checker retain the installed version.

## GitHub Actions

Publishing a GitHub Release automatically builds Windows x64 and macOS arm64 packages, attaches them to that release, and uploads `SHA256SUMS.txt`. **Package desktop apps** can also be run manually: **ref** selects the source commit, while the optional **release_tag** selects an existing GitHub Release that receives the files. Enable **attach_to_release** only when that release exists; if **release_tag** is omitted, it defaults to **ref**.

The workflow does not use Authenticode, Apple Developer ID, or notarization credentials. See the platform installation guides for the resulting SmartScreen and Gatekeeper experience.
