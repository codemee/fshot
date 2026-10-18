# Virtual Screen Capture Guide

[繁體中文](virtual-screen.md) | [English](virtual-screen.en.md) · [Back to README](../README.en.md)

This guide covers experimental virtual-screen setup, interactive previews, and limitations. See the [README](../README.en.md) for ordinary capture and shortcuts, or [Cross-Platform Notes](cross-platform.en.md) for implementation and acceptance details.

## Windows virtual 4K capture


The toolbar monitor button switches between physical (solid outline) and virtual (dashed outline) capture and remembers the choice. Virtual mode uses the same shortcuts:

- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>: move and resize the active window to the virtual monitor, capture it, then restore its original position, size, and window state.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>W</kbd>: select a window/control on the original monitor, move its owning window, and capture the tracked target. An unavailable or unstable target produces an error.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd>: capture the monitor containing the cursor directly, in either mode.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Q</kbd>: repeat the previous successful capture; physical and virtual modes maintain separate histories.
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>: unavailable in virtual mode; switch to physical mode for region capture.

FShot chooses the active virtual monitor with the largest pixel area. Window width and height are scaled independently according to their original proportions of the source monitor. Windows display scaling is left to the user. Minimized windows must be restored first; windows that cannot fit the destination work area are rejected. The original placement is restored after capture, cancellation, or failure. Layout and image detail depend on the target application's DPI support.

Switching to virtual mode checks for an existing virtual monitor and supported driver. If neither is available, FShot asks to install the official VirtualDrivers/MikeTheTech Virtual Display Driver through WinGet and create a 3840 × 2160 extended monitor. If the driver is already present, it asks only to create the monitor. UAC approval remains manual; cancellation or failure keeps physical mode. Setup backs up `C:\VirtualDisplayDriver\vdd_settings.xml` and preserves existing configuration on reinstall. Other drivers can be used with an already active virtual monitor. There is no separate virtual-capture tray entry. This workflow is currently Windows-only.

### Delayed active-window interaction

Enable virtual mode and a delay greater than zero (try 5 or 10 seconds), leave the cursor on a physical monitor, focus the target app, and press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>. After moving the target, FShot shows a non-activating mirror on the physical monitor. The countdown begins when the first frame is ready.

During the countdown, mouse input is forwarded to the virtual display and shown as a crosshair; keyboard input stays with the target. Click, drag, scroll, or open menus before capture. <kbd>Esc</kbd> cancels and restores the window and cursor. Losing target focus, disappearing targets, or input-forwarding failures stop the session. Elevated apps may reject forwarded input.

Preview capture runs in the background with a 30 fps target, scales to the physical preview size, and retains only the latest frame. On Windows it uses DXGI for the virtual display when available and falls back to `mss` if DXGI cannot start. Run `uv run python scripts/benchmark_windows_preview.py` to compare both paths on your computer. Frame-ready notifications and local cursor repainting reduce waiting; actual responsiveness depends on the system and display driver. The final image still uses the virtual monitor's original pixels and includes native menus/new owned popups before closing the mirror. Custom-drawn menus need manual acceptance testing. Zero-delay, selected-control, and full-screen capture keep their existing flows.


## macOS virtual capture (experimental)

Virtual capture requires macOS 14 or later, Screen Recording and Accessibility permissions, and a 4K extended display. FShot automatically selects the fixed-name `FShot-4K` display. If disconnected, it uses BetterDisplay CLI to reconnect the saved definition or create a 1920 × 1080 HiDPI display with 3840 × 2160 output pixels.

If BetterDisplay is missing, FShot asks to install it with Homebrew; if Homebrew is also missing, it asks to install Homebrew first. Approved installation runs in Terminal, where you enter passwords and confirm installation yourself. FShot does not collect passwords. After success, setup resumes automatically. Cancellation or failure keeps physical mode. A timed-out installer may still be running in Terminal; finish or stop it before retrying. BetterDisplay must remain running, and its CLI integration or licensed features may need manual setup.

### Capture and restore

1. Switch the toolbar monitor button to virtual mode and complete any setup prompts.
2. Keep the target application on another display and press `Ctrl+Shift+A`.
3. FShot scales the window according to its original proportions of the source display, moves it to the virtual display, and captures native pixels with ScreenCaptureKit.
4. Completion, cancellation, or failure restores the window's original position and size. `Ctrl+Shift+Q` repeats the last successful virtual capture.

`Ctrl+Shift+W` can select a window or control on the original display. Selecting a title bar or frame captures the whole window; selecting a control captures its updated Accessibility bounds after moving the owning window. If the target disappears or cannot be uniquely identified, capture stops and restores the window. It does not choose a different control at the old coordinates.

Full-screen capture follows the ordinary macOS behavior. Region capture is unavailable in virtual mode. Minimized, full-screen, or immovable/unresizable windows are rejected. Display disconnection, configuration changes, rejected dimensions, or an obstructed target center also stop capture and attempt restoration; the center check cannot guarantee that every corner is unobstructed.

### Delayed interaction preview

1. Enable virtual mode and set a 5- or 10-second delay. Leave the cursor on the physical display and release all mouse buttons.
2. Focus the target app and press `Ctrl+Shift+A`. After the window moves, a scaled preview of the whole virtual display appears on the physical display. The countdown begins after the first valid frame.
3. Move into the preview to interact. Clicks, dragging, and scrolling are mapped to the target while keyboard focus remains with that app. Moving outside stops forwarding, except that an active drag continues until release with coordinates clamped to the display bounds.
4. At the end, FShot captures native pixels, including recognizable new same-process popups intersecting the target window or the destination display's menu-bar area. The preview itself is excluded.
5. `Esc`, focus changes, target closure, display removal/configuration changes, or stream/input errors cancel the session. Cleanup releases forwarded buttons, removes the event tap, and restores the target window without moving the physical cursor.

The preview uses ScreenCaptureKit with a 30 fps target and retains only the latest frame. Responsiveness depends on the system; final output does not reuse the scaled preview. Delayed selected-control capture uses the ordinary countdown instead.

If forwarding is rejected, check Accessibility/Input Monitoring permissions for FShot or its launching host. Events are sent to the target process with `CGEventPostToPSN`; delivery diagnostics do not prove that the app handled an event. Custom popups, cross-display menus, and same-process window relationships need manual verification. Only popups inside the virtual display are included. When cursor inclusion is enabled, the mapped preview cursor is composited into the native-resolution output.

### Display identity and cleanup

FShot uses the fixed name `FShot-4K` and may adopt an existing same-name VirtualScreen definition on first use. It saves tagID/serial/vendor/model identity for retries and refuses ambiguous names or identity changes. It does not reconfigure other display names or delete older randomly named definitions. The destination UUID is saved and resolved again when switching modes.

Switching to physical mode, quitting FShot, or a failed creation attempt leaves the BetterDisplay definition in place. Disconnect or remove it manually in BetterDisplay when no longer needed. See the [macOS implementation history](macos-virtual-screen.md) (Traditional Chinese) for development details.
