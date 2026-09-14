# Architecture

[繁體中文](architecture.md) | [English](architecture.en.md)

This document introduces the FShot codebase. Read [cross-platform.en.md](cross-platform.en.md) before changing capture, hotkey, or platform-specific behavior.

## Entry Points

- `pyproject.toml`: package metadata, dependencies, and the `fshot` command.
- `src/fshot/__main__.py`: entry point for `python -m fshot`.
- `src/fshot/app.py`: Qt application, system tray, global shortcuts, and capture orchestration.

## Main Modules

- `app.py`: creates the application and tray; registers Windows/macOS global shortcuts; hides the editor before capture and adds successful captures to the editor and clipboard. The tray exposes manual and daily automatic update checks. After user confirmation and unsaved-data handling, it starts the external updater helper, exits normally, and reports the metadata-confirmed result after restart.
- `updates.py`: runs synchronous update checks in a Qt thread pool, keeping them off the UI thread. It persists the automatic-check toggle, last check time, and skipped version with `QSettings`; background checks run at most daily while manual checks bypass the interval. uv tool installations delegate installation changes, process waiting, and restart to `uv-tool-updater`. Frozen EXE/App builds check the latest GitHub Release and only open its download page, never replacing an unsigned app automatically.
- `packaging/fshot.spec`, `scripts/build_app.py`: use PyInstaller to create a single Windows x64 EXE and an Apple Silicon macOS App. The App is placed in an arm64 DMG with an Applications shortcut. Build-time code derives Windows version resources, ICO, and ICNS assets from project metadata and the existing camera artwork. Publishing a GitHub Release automatically builds and attaches the EXE, DMG, and SHA-256 checksums through `package-apps.yml`. Intel Macs are not supported.
- `capture.py`: coordinates full-screen, region, focused-window, and selected window/control capture. Windows-specific DWM, UI Automation, cursor, and fallback logic lives here; macOS capabilities are delegated to `platforms/macos.py`. Delayed capture also lives here.
- `platforms/macos.py`: handles permissions, Accessibility focused-window/control hit testing, cursor capture, and consumable Quartz global shortcuts.
- `main_window.py`: owns the editor, toolbar, tabs, save/save-as, zoom, and settings panels. The window title shows the current version from installed package metadata and appends the active tab name when a document is open. The toolbar uses 20 px icons and fixed 34 px buttons for a compact, consistent target across platforms; a 20 px dropdown beside the line button configures the start and end independently as none, an arrow, or a solid circle. Saved tabs can rename their source file inline with Windows/Linux `F2`, macOS `Return`, or a double-click; the image extension is preserved. Screenshots, dropped files, and clipboard images share one tab creation path. Dropped files retain their source `Path` and open clean; clipboard images are new unsaved documents. Windows puts the dirty marker left of the title and close button on the right; other platforms follow native tab placement.
- `canvas.py`: implements pen, lines with independently configurable endpoint styles, rectangle, non-destructive pixel measurement, text, mosaic, crop handles, zoom, and undo. Measurement uses image coordinates for zoom-independent horizontal and vertical deltas; its rectangle and reading are Canvas overlays that never enter exports or the undo stack. Padding keeps crop handles outside image content. Scrollbars align only with the image instead of extending into this padding; their end spacers and lower-right corner use the canvas padding color. Light and dark themes use matching scrollbar dimensions with theme-specific high-contrast tracks, handles, and hover colors.
- `document.py`: tracks title, path, and dirty/unsaved state through `ShotDocument`.
- `icons.py`: draws toolbar and tray icons in code. Tool glyphs are visually centered within a shared canvas, including a vertical correction for the pencil's diagonal silhouette. The taskbar and system-tray camera icons use separately tuned transparent margins and 16–64 px pixmaps; the macOS menu bar uses a squarer camera layout that fills its limited height so the visual weight stays clear and consistent across platforms.
- `settings.py`: defines `CaptureMode`, `Tool`, `LineEndStyle`, `CaptureSettings`, and `DrawingSettings`.
- `hotkeys.py`: defines configurable combinations for the four capture modes and the repeat action, validates them, and persists them with `QSettings`. The UI edits a temporary copy; Windows probes conflicts with `RegisterHotKey` and replaces active registrations only after every new shortcut succeeds.
- `theme.py`: manages System, Light, and Dark modes through `QSettings`, application palettes/stylesheets, and theme-aware icon redraw. `ArrowSpinBox` provides consistent cross-platform numeric controls.
- `i18n.py`: manages System, Traditional Chinese, and English modes. It detects the system language, persists overrides, and emits changes that retranslate the editor/tray. Tooltips combine translated labels with `QAction` shortcuts.
- `qt_image.py`: converts between Pillow and Qt image types.

## Capture Flow

1. `app.py` receives a global shortcut.
2. The editor hides so it is not captured.
3. On Windows, zero-delay region and window/control selection save the virtual desktop before `WM_HOTKEY` returns. Window/control mode also saves transient-window and UI Automation menu-control bounds, so the overlay can select and crop a menu from the frozen image after its live counterpart closes.
4. Other modes use `CaptureService._rect_for_mode()` to resolve the target rectangle. Selected top-level UIA windows are normalized through HWND/DWM visible frame bounds, while child controls retain their UIA bounds.
5. A delayed capture displays a bottom-right countdown that can be cancelled with `Esc`; region and window/control selection freeze the desktop after the countdown, while other modes count down after resolving the rectangle.
6. Frozen regions and selected windows/controls are cropped from the saved desktop image; other modes hide the overlay and capture through `_grab_rect()`.
7. If enabled, the native pointer at freeze or capture time is composited best-effort.
8. `EditorWindow.add_shot()` creates a tab aligned to the editor's top-left.
9. `EditorWindow.copy_current()` copies the image to the clipboard.

`Ctrl+Shift+Q` repeats the previous successful capture by default and can be customized in the shortcut panel. Region capture preserves fixed coordinates; window/control capture preserves the native target identity and resolves its current bounds when repeated. If that target no longer exists, no error or new tab is shown.

## Editing Model

Editing directly mutates a `QImage`; the previous image is copied to an undo stack before each operation. This is intentionally simple and is not a vector/object model. Re-selectable objects, editable text, or layered exports would require a redesigned canvas model.

Dropped images retain their source path and start clean. The first edit marks the document dirty; Save writes to the source. Clipboard images have no source path, use `YY-MM-DD-HHMMSS`, and open Save As on first save. After each successful save, the containing directory is persisted through `QSettings`; other tabs without their own paths use that directory as the Save dialog's default location while retaining their own tab titles as the default file names.

Cropping is also an image operation: releasing a dragged outer crop handle applies the crop and records an undo entry.

## Testing

- `tests/test_document.py`: tab names, dirty/save state, document reindexing, and image import.
- `tests/test_icons.py`: opaque artwork coverage at native taskbar and system-tray icon sizes, plus visual centering for tool glyphs.
- `tests/test_main_window.py`: toolbar button sizing, image scrollbar geometry, and padding widgets that exclude canvas padding.
- `tests/test_version.py`: runtime version consistency with installed package metadata.
- `tests/test_updates.py`: automatic-check scheduling, skipped versions, background execution, and error reporting.
- Run `uv run pytest -q` and `uv run python -m compileall src tests` for cross-platform checks.

Global shortcuts, window selection, cursor capture, drag/drop, and clipboard behavior still require manual OS-level acceptance testing.
