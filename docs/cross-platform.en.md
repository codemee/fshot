# Cross-Platform Notes

[繁體中文](cross-platform.md) | [English](cross-platform.en.md)

Most FShot UI code uses reusable PySide6 components. Capture, global shortcuts, cursor extraction, window selection, permissions, and some clipboard behavior remain platform-specific.

Themes are shared through `ThemeManager` and Qt system color hints. Language is shared through `LanguageManager`; macOS prioritizes `AppleLanguages`, while other platforms use the Qt locale. Tab close buttons follow platform placement and use FShot's high-contrast icon. Windows places the dirty marker left of the title.

Image drag/drop and paste use Qt `QMimeData`, `QUrl`, and clipboard APIs. On macOS, verify Finder local-file URLs, HEIC/HEIF decoder availability, and source-file write access in sandboxed builds.

## Current Platform State

### Windows

- Global shortcuts use `RegisterHotKey` and consume `WM_HOTKEY`.
- The toolbar keyboard icon configures the four capture shortcuts and the repeat action; Windows probes `RegisterHotKey` conflicts before applying them.
- Repeat Previous Capture defaults to `Ctrl+Shift+Q`, is configurable, and preserves the previous region or selected window/control target.
- Full-screen/region capture uses `mss` with Pillow `ImageGrab` fallback.
- Region and window/control selection freeze the virtual desktop before showing the selector, preserving transient menus that disappear on focus loss.
- Focused windows and selected top-level windows use DWM extended frame bounds to exclude invisible resize frames; controls inside a window retain their UI Automation bounds.
- Window/control selection prefers UI Automation with HWND fallback.
- The snapshot also saves transient windows and UI Automation menu-control bounds from the foreground thread. FShot then sends `WM_CANCELMODE` to close the live popup; selection prefers the saved controls, so menus in the frozen image remain selectable. The full-screen selector receives and consumes mouse input itself. For ordinary windows it lazily builds and caches a UI Automation target map for the HWND under the pointer, eliminating the input-transparent overlay, off-screen mouse catcher, and global mouse grab.
- Real cursor images are converted from Win32 handles best-effort.
- Tray, editor, clipboard, save, crop, and drawing workflows are implemented.

### macOS

- Quartz event taps consume `Ctrl+Shift+A/R/F/W`.
- The shortcut listener supports user-configured Ctrl/Shift/Option plus A–Z combinations, persisted with `QSettings`.
- Screen Recording permission is checked/requested.
- Accessibility `AXFocusedWindow` is preferred; Core Graphics window fallback avoids transient browser popups.
- Accessibility hit testing finds the smallest valid element under the pointer and clamps results to the owning window.
- Current `NSCursor` image, hotspot, and position are included best-effort.
- Shared Qt tray, editor, clipboard, and save workflows are used.

First launch requests Accessibility permission; first capture requests Screen Recording permission. For a DMG installation, enable both permissions for `FShot.app` under **System Settings → Privacy & Security → Accessibility / Screen Recording**. When running through `uv`/`uvx`, the entries usually belong to Terminal, iTerm2, Warp, or the IDE host that launched the command. After changing access, fully quit and reopen FShot or that host app. Without Accessibility permission, global shortcuts and control selection may be unavailable, while window hit testing falls back best-effort.

### Linux

Linux is not currently a primary target. X11 and Wayland differ substantially in global shortcuts, capture permissions, and window discovery.

## Platform Boundaries

- Global hotkeys currently live in `app.py`; a future `hotkeys.py` could expose per-platform backends.
- Capture orchestration currently lives in `capture.py`; future work can split shared flow from `platforms/windows.py` and `platforms/macos.py`.
- Window/control selection uses UI Automation on Windows and Accessibility on macOS.
- Cursor backends should return equivalent image, hotspot, and screen-position data.
- macOS permission checks must remain explicit; Windows currently has no centralized permission flow.

## macOS Implementation Layout

- `platforms/macos.py`: permissions, Core Graphics/Accessibility window queries, cursor, and shortcuts.
- `capture.py`: shared capture flow and platform delegation.
- `app.py`: Windows native filter, macOS event tap, and fallback lifecycle.

## Automatic Updates

- Automatic installation is available only for `uv tool install fshot`; `uvx`, source checkouts, and ordinary virtual environments are conservatively reported as unsupported.
- Frozen Windows EXE and macOS App builds check the latest GitHub Release daily. When a new version is available they open the download page for manual verification and replacement; they never overwrite an unsigned app automatically.
- Windows uses a hidden Windows PowerShell helper, while macOS/Linux use a detached `/bin/sh` helper. The helper only waits for FShot to exit normally; it cancels on timeout and never force-terminates the app.
- uv performs the actual version-qualified `uv tool upgrade`; FShot never mutates the tool environment directly.
- The current capture must finish first, and unsaved tabs require confirmation. After restart, FShot verifies the installed package metadata and reports the actual result.

## Packaged Applications

- Releases provide a single Windows x64 EXE and an Apple Silicon arm64 DMG only. Intel Macs are not supported.
- Neither platform receives a trusted publisher signature. Windows can show SmartScreen, while macOS requires a Gatekeeper Open Anyway approval; see the platform installation guides.
- The macOS DMG contains `FShot.app` and an Applications shortcut. Without Developer ID signing or notarization, replacement builds can require another Gatekeeper approval and renewed Screen Recording or Accessibility permissions.

## Manual Acceptance Checklist

- Shortcuts trigger capture and are not forwarded to the focused application.
- The shortcut panel opens with the active values; **Use defaults** changes only the pending panel values, OK applies and persists them, and Cancel leaves the active settings unchanged.
- On macOS, custom Ctrl/Shift/Option plus letter combinations trigger the intended capture mode and remain configured after restart.
- Immediate and delayed capture behave consistently: Windows region and window/control selection freeze the desktop after the countdown, while other modes resolve the target before counting down and capturing the live image.
- Full-screen, region, focused-window, and selected window/control capture work.
- After a successful capture, the FShot editor is restored and requests foreground activation. If the foreground lock rejects the ordinary `SetForegroundWindow` call, a brief topmost/not-topmost Z-order raise is used as a fallback. FShot checks and reasserts the editor foreground state 200ms after capture completes.
- Browser transient URLs/tooltips are not mistaken for the focused window.
- Escape cancels delayed countdowns and region/window selection.
- Include Cursor captures the current real pointer.
- New captures appear at the editor's top-left.
- Clipboard content pastes into common applications.
- PNG/JPG save works.
- Dropped images open under their original name, start clean, and save edits back to the source.
- Saved tabs rename their source file inline with Windows/Linux `F2`, macOS `Return`, or a double-click; existing files are not overwritten and the extension is preserved.
- Pasted images and pasted file-manager images create new timestamp-named tabs.
- Pixel measurement shows live horizontal and vertical deltas while dragging, remains based on source-image pixels at every zoom level, and does not modify exported images.
- Minimize/hide, tray double-click, and tray Exit work.
