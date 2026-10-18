# Development Guide

[繁體中文](development.md) | [English](development.en.md) · [Back to README](../README.en.md)

This guide covers development setup, testing, and documentation maintenance. See the [README](../README.en.md) for stable installation and everyday use.

## Run from source

Use uv from the repository root:

```powershell
uv sync
uv run fshot
```

To install the latest development version from GitHub's `main` branch:

```powershell
uv tool install --force "fshot @ git+https://github.com/codemee/fshot.git@main"
```

## Tests

```powershell
uv run pytest -q
uv run python -m compileall src tests
```

On Windows, a running FShot may lock an executable or `__pycache__` file and prevent environment updates or `compileall`. Stop FShot and rerun the command.

## Documentation icons

```powershell
uv run python scripts/export_toolbar_icons.py
```

The exporter uses the application's renderer to generate 31 light and 31 dark icons:

- `docs/images/toolbar/`: light assets, also used as fallbacks.
- `docs/images/toolbar/dark/`: dark assets.

README pictures use `<picture>` and `prefers-color-scheme` to select a version. Viewers without theme switching display an `<img>` fallback with an opaque light background to preserve contrast. Check both themes, fallback images, and README references when changing icons.

## Windows preview benchmark

```powershell
uv run python scripts/benchmark_windows_preview.py
```

Compare the local DXGI and MSS preview paths. Speed depends on the system and display driver. See the [Virtual Screen Capture Guide](virtual-screen.en.md) for setup and operation.

## Technical documentation

- [Architecture](architecture.en.md): modules and data flow.
- [Cross-Platform Notes](cross-platform.en.md): platform differences, permissions, and manual acceptance.
- [Desktop Packaging](packaging.en.md): local builds and GitHub Release workflows.
- [PRD](../PRD.en.md): original product requirements.
- [uv-tool-updater design draft](uv-tool-updater-spec.md) (Traditional Chinese): updater design and integration status.
- [macOS virtual-screen implementation history](macos-virtual-screen.md) (Traditional Chinese): development stages and acceptance records.
