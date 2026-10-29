# FShot

[繁體中文](https://github.com/codemee/fshot/blob/main/README.md) | [English](https://github.com/codemee/fshot/blob/main/README.en.md)

FShot is a desktop screenshot utility with global shortcuts, a persistent system tray, tabbed editing, and fast copy/save workflows for Windows and macOS.

## Supported platforms

- Windows 10/11 x64.
- macOS Apple Silicon; Intel Macs are not supported.
- Linux is not yet officially supported.

## Quick Start

### Desktop app

For regular use, download a build from [GitHub Releases](https://github.com/codemee/fshot/releases):

- Windows 10/11 x64: a portable `FShot-<version>-windows-x64.exe` that does not require Python.
- Apple Silicon Mac: `FShot-<version>-macos-arm64.dmg`; open it and drag `FShot.app` to Applications. Intel Macs are not supported.

Windows may show a SmartScreen prompt on first launch. On macOS, you may need **Open Anyway** under System Settings → Privacy & Security, followed by Screen Recording and Accessibility permissions. See the [Windows installation guide](docs/install-windows.en.md) or [macOS installation guide](docs/install-macos.en.md) for setup, permissions, and download verification.

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

When installed with `uv tool install`, FShot checks PyPI in the background at most once per day. The tray menu can check manually or disable automatic checks. When an update is available, you can update and restart, postpone it, or skip that release. FShot asks before discarding any unsaved screenshots. Desktop builds check GitHub Releases and open the download page for manual updates. `uvx` users receive manual update guidance.

FShot starts with its editor hidden and remains in the system tray. Double-click the tray icon to show the editor; use the tray context menu to exit.

Shortcut settings, theme, and language form a group at the right edge of the toolbar, separated from the other tools. They remain available through the overflow menu in narrow windows.

Below the toolbar, a flat tab row and a thin content frame share aligned horizontal edges. Native Qt arrow buttons scroll overflowing tabs; small squares continue to mark unsaved changes.

The theme button cycles through Follow System, Light, and Dark. Dark mode uses an Evangelion Unit-01-inspired purple and lime palette. The language button cycles through Follow System, Traditional Chinese, and English. Both choices are persisted. Toolbar tooltips follow the selected language and include shortcuts where available.

Selected state buttons use the hover background and accent-colored icons: blue in light mode and lime in dark mode, making active tools and options easy to identify.

The zoom group provides zoom in, zoom out, Fit to window, and the current percentage. Click the percentage to enter 1%–800%, then press Enter or Apply. Each tab retains its own scale; `Ctrl+0` resets it to 100%. Zoom only changes the display, leaving image content unchanged. A separator divides zoom tools from capture options such as Include cursor.

The keyboard icon opens the global shortcut settings for all four capture modes plus Repeat Previous Capture. Each shortcut can use <kbd>Ctrl</kbd>, <kbd>Shift</kbd>, <kbd>Option</kbd>/<kbd>Alt</kbd>, and an <kbd>A</kbd>–<kbd>Z</kbd> letter; <kbd>Shift</kbd> must be combined with <kbd>Ctrl</kbd> or <kbd>Option</kbd>/<kbd>Alt</kbd>. **Use defaults** restores the five default combinations in the panel. Changes are persisted only after OK successfully registers every shortcut; Cancel keeps the active settings unchanged.

Images can also be added by drag-and-drop or clipboard paste. A dropped image opens under its full file name, retains its source path, and is saved back after editing. Pasted images create new unsaved tabs using the screenshot timestamp naming format. After a successful save, FShot remembers the containing directory and uses it when opening the Save dialog for other unsaved tabs. Paste uses <kbd>Ctrl</kbd>+<kbd>V</kbd> on Windows/Linux and <kbd>⌘</kbd>+<kbd>V</kbd> on macOS.

## Virtual screen capture (experimental)

For higher-resolution window captures, switch the toolbar monitor button to virtual mode; the choice is remembered. This feature needs a virtual display and the relevant system permissions.

See the [Virtual Screen Capture Guide](docs/virtual-screen.en.md) for Windows/macOS setup, delayed interaction previews, and limitations.

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

### Tab shortcuts

These Windows/Linux shortcuts work within the editor window:

| Shortcut | Action |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>Tab</kbd> / <kbd>Ctrl</kbd>+<kbd>Page Down</kbd> | Next tab, wrapping to the first |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Tab</kbd> / <kbd>Ctrl</kbd>+<kbd>Page Up</kbd> | Previous tab, wrapping to the last |
| <kbd>Ctrl</kbd>+<kbd>1</kbd>–<kbd>8</kbd> | Select the first through eighth tab from the left |
| <kbd>Ctrl</kbd>+<kbd>9</kbd> | Select the last tab |
| <kbd>Ctrl</kbd>+<kbd>W</kbd> / <kbd>Ctrl</kbd>+<kbd>F4</kbd> | Close the current tab, confirming unsaved changes first |

On macOS, closing and numbered selection use <kbd>⌘</kbd>; previous/next use Qt's platform-standard bindings. Closing the last tab leaves the editor window open.

Before closing tabs, closing the editor, quitting, or updating, unsaved screenshots can be saved, discarded, or kept by cancelling. Save all processes each document separately; cancelling a save or encountering a write error preserves the tabs and stops the close/update. Closing the editor leaves FShot in the system tray.

## More help

- [Windows installation and permissions](docs/install-windows.en.md)
- [macOS installation and permissions](docs/install-macos.en.md)
- [Virtual Screen Capture Guide](docs/virtual-screen.en.md)

For contributions, see the [Development Guide](docs/development.en.md), including links to architecture, platform notes, and packaging documentation.

## License

FShot is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See [LICENSE](LICENSE) for the full terms. Third-party components retain their respective licenses.

View version and license information in About FShot: open the title-bar icon's system menu on Windows, or choose FShot → About FShot in the macOS menu bar.
