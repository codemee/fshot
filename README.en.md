# FShot

[繁體中文](https://github.com/codemee/fshot/blob/main/README.md) | [English](https://github.com/codemee/fshot/blob/main/README.en.md)

FShot is a Python desktop screenshot utility focused on global shortcuts, a persistent system tray, tabbed editing, and fast copy/save workflows. Windows and macOS are currently supported. See [Cross-Platform Notes](https://github.com/codemee/fshot/blob/main/docs/cross-platform.en.md) for platform permissions and acceptance guidance.

## Current Status

- Windows: Core features are implemented and have been manually tested and refined.
- macOS: Quartz global shortcuts, screen capture, focused-window capture, window/control selection, and cursor capture are implemented.
- Linux: Only the base architecture and some shared capabilities exist; Linux is not currently a primary target.

## Quick Start

### Desktop app

For regular use, download a build from [GitHub Releases](https://github.com/codemee/fshot/releases):

- Windows 10/11 x64: a portable `FShot-<version>-windows-x64.exe` that does not require Python.
- Apple Silicon Mac: `FShot-<version>-macos-arm64.dmg`; open it and drag `FShot.app` to Applications. Intel Macs are not supported.

These personal-project builds have no trusted Authenticode or Apple Developer ID signature and are not notarized by Apple. Windows may show SmartScreen; on first launch, macOS requires **Open Anyway** under System Settings → Privacy & Security, followed by Screen Recording and Accessibility permissions. Use `SHA256SUMS.txt` from the same release to verify the download. See the [Windows installation guide](docs/install-windows.en.md) or [macOS installation guide](docs/install-macos.en.md) for complete steps.

### Run from PyPI

FShot is available from [PyPI](https://pypi.org/project/fshot/). Run the latest stable release without installing it:

```powershell
uvx fshot
```

The first run downloads the package from PyPI and creates a uv cache environment. Later runs reuse that cache. Use `uvx` for evaluation and `uv tool install` for regular use.

Install from PyPI with uv:

```powershell
uv tool install fshot
fshot
```

After installation, run the app with `fshot`. Upgrade to the latest PyPI release with:

```powershell
uv tool upgrade fshot
```

When installed with `uv tool install`, FShot checks PyPI in the background at most once per day. The tray menu can check manually or disable automatic checks. When an update is available, you can update and restart, postpone it, or skip that release. FShot asks before discarding any unsaved screenshots. Packaged apps check GitHub Releases and open the download page instead of replacing an unsigned EXE or App. `uvx` and source checkouts receive manual update guidance.

Install the latest development version directly from GitHub's `main` branch:

```powershell
uv tool install --force "fshot @ git+https://github.com/codemee/fshot.git@main"
```

Run from a source checkout:

```powershell
uv sync
uv run fshot
```

FShot starts with its editor hidden and remains in the system tray. Double-click the tray icon to show the editor; use the tray context menu to exit.

The theme button cycles through Follow System, Light, and Dark. The language button cycles through Follow System, Traditional Chinese, and English. Both choices are persisted. Toolbar tooltips follow the selected language and include shortcuts where available.
The keyboard icon opens the global shortcut settings for all four capture modes plus Repeat Previous Capture. Each shortcut can use <kbd>Ctrl</kbd>, <kbd>Shift</kbd>, <kbd>Option</kbd>/<kbd>Alt</kbd>, and an <kbd>A</kbd>–<kbd>Z</kbd> letter; <kbd>Shift</kbd> must be combined with <kbd>Ctrl</kbd> or <kbd>Option</kbd>/<kbd>Alt</kbd>. **Use defaults** restores the five default combinations in the panel. Changes are persisted only after OK successfully registers every shortcut; Cancel keeps the active settings unchanged.

Images can also be added by drag-and-drop or clipboard paste. A dropped image opens under its full file name, retains its source path, and is saved back after editing. Pasted images create new unsaved tabs using the screenshot timestamp naming format. After a successful save, FShot remembers the containing directory and uses it when opening the Save dialog for other unsaved tabs. Paste uses <kbd>Ctrl</kbd>+<kbd>V</kbd> on Windows/Linux and <kbd>⌘</kbd>+<kbd>V</kbd> on macOS.

## Virtual 4K Capture (Windows experimental feature)

The toolbar monitor button switches between physical (solid outline) and virtual (dashed outline) capture and remembers the choice. Virtual mode uses the same shortcuts:

- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>: move and resize the active window to the virtual monitor, capture it, then restore its original position, size, and window state.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>W</kbd>: select a window/control on the original monitor, move its owning window, and capture the tracked target. An unavailable or unstable target produces an error.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd>: capture the monitor containing the cursor directly, in either mode.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Q</kbd>: repeat the previous successful capture; physical and virtual modes maintain separate histories.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>: unavailable in virtual mode; switch to physical mode for region capture.

FShot chooses the active virtual monitor with the largest pixel area. Window width and height are scaled independently according to their original proportions of the source monitor. Windows display scaling is left to the user. Minimized windows must be restored first; windows that cannot fit the destination work area are rejected. The original placement is restored after capture, cancellation, or failure. Layout and image detail depend on the target application's DPI support.

Switching to virtual mode checks for an existing virtual monitor and supported driver. If neither is available, FShot asks to install the official VirtualDrivers/MikeTheTech Virtual Display Driver through WinGet and create a 3840 × 2160 extended monitor. If the driver is already present, it asks only to create the monitor. UAC approval remains manual; cancellation or failure keeps physical mode. Setup backs up `C:\\VirtualDisplayDriver\\vdd_settings.xml` and preserves existing configuration on reinstall. Other drivers can be used with an already active virtual monitor. There is no separate virtual-capture tray entry. This workflow is currently Windows-only.

### Delayed active-window interaction

Enable virtual mode and a delay greater than zero (try 5 or 10 seconds), leave the cursor on a physical monitor, focus the target app, and press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>. After moving the target, FShot shows a non-activating mirror on the physical monitor. The countdown begins when the first frame is ready.

During the countdown, mouse input is forwarded to the virtual display and shown as a crosshair; keyboard input stays with the target. Click, drag, scroll, or open menus before capture. <kbd>Esc</kbd> cancels and restores the window and cursor. Losing target focus, disappearing targets, or input-forwarding failures stop the session. Elevated apps may reject forwarded input.

Preview capture runs in the background with a 30 fps target, scales to the physical preview size, and retains only the latest frame. Frame-ready notifications and local cursor repainting reduce waiting; actual responsiveness depends on the system and display driver. The final image still uses the virtual monitor's original pixels and includes native menus/new owned popups before closing the mirror. Custom-drawn menus need manual acceptance testing. Zero-delay, selected-control, and full-screen capture keep their existing flows.

## Capture Shortcuts

- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Q</kbd>: Repeat the previous capture (reuses the previous region or selected window/control target; configurable in the shortcut panel)
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>: Capture the focused window
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>: Capture a rectangular region
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd>: Capture the full screen
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>W</kbd>: Select and capture a window or control

macOS uses the same <kbd>Ctrl</kbd>+<kbd>Shift</kbd> letter combinations. Grant the packaged `FShot.app` both Screen Recording and Accessibility access. When running through `uv`/`uvx`, the permission entry usually belongs to the host that launched the command, such as Terminal, iTerm2, or an IDE. After granting access, fully quit and reopen FShot or that host app.

Editor shortcuts:

The line tool also creates arrows and endpoint markers, with a solid circle at the start and an arrow at the end by default. Use the dropdown beside the line button to set the start and end independently to none, an arrow, or a solid circle.
The pixel measurement tool uses the same press-and-drag interaction as a rectangle and shows live horizontal and vertical deltas from the starting point. The reading remains after release until you measure again or switch tools. It is an editor-only overlay and never changes the image or adds an undo entry.
The leading editor-tool group can also rotate the current image 90° clockwise or flip it horizontally or vertically. The downscale button opens a panel matching the line-style controls and accepts a 1–99% physical image size. These operations mark the document as modified and can be undone.

- <kbd>Alt</kbd>+<kbd>P</kbd>: Freehand pen
- <kbd>Alt</kbd>+<kbd>L</kbd>: Line
- <kbd>Alt</kbd>+<kbd>R</kbd>: Rectangle
- <kbd>Alt</kbd>+<kbd>D</kbd>: Measure pixels
- <kbd>Alt</kbd>+<kbd>T</kbd>: Text
- <kbd>Alt</kbd>+<kbd>M</kbd>: Mosaic
- <kbd>Alt</kbd>+<kbd>C</kbd>: Rotate clockwise 90°
- <kbd>Alt</kbd>+<kbd>S</kbd>: Scale image down
- <kbd>Alt</kbd>+<kbd>H</kbd>: Flip horizontally
- <kbd>Alt</kbd>+<kbd>V</kbd>: Flip vertically
- <kbd>Ctrl</kbd>+<kbd>+</kbd> / <kbd>Ctrl</kbd>+<kbd>=</kbd>: Zoom in
- <kbd>Ctrl</kbd>+<kbd>-</kbd>: Zoom out
- <kbd>Ctrl</kbd>+<kbd>0</kbd>: Reset zoom
- <kbd>F2</kbd>: Rename the current saved file directly in its tab (<kbd>Return</kbd> on macOS)

You can also double-click the name of a saved tab to rename it. The original file extension is preserved.

## Project Docs

- [PRD](https://github.com/codemee/fshot/blob/main/PRD.en.md): Original product requirements.
- [Architecture](https://github.com/codemee/fshot/blob/main/docs/architecture.en.md): Project structure, modules, and data flow.
- [uv-tool-updater design draft](docs/uv-tool-updater-spec.md) (Traditional Chinese): updater design background and current FShot integration status.
- [Cross-Platform Notes](https://github.com/codemee/fshot/blob/main/docs/cross-platform.en.md): Windows/macOS/Linux differences and platform acceptance guidance.

## Development

```shell
uv sync
uv run pytest -q
uv run python -m compileall src tests
```

If FShot is running, `compileall` may occasionally fail because an executable or `__pycache__` file is locked. Stop FShot and rerun the command.

## Desktop Packaging

FShot uses PyInstaller and must be built on the target operating system. A Windows runner produces the single x64 EXE; an Apple Silicon macOS runner produces an arm64 DMG containing `FShot.app` and an Applications shortcut. Intel Mac builds are not produced.

Build locally:

```powershell
uv sync
uv run python scripts/build_app.py
```

Outputs are written to `dist/`. Publishing a GitHub Release automatically runs tests and packaging on native Windows and macOS runners, then attaches the EXE, DMG, and `SHA256SUMS.txt` through the `Package desktop apps` workflow. The workflow uses no Authenticode, Apple Developer ID, or notarization credentials, so the resulting files retain the SmartScreen and Gatekeeper behavior described above. See [Desktop Packaging](docs/packaging.md) for development and manual recovery details.
