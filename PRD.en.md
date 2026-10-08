# Simple Screenshot Utility: FShot

[繁體中文](PRD.md) | [English](PRD.en.md)

FShot is a keyboard-first, cross-platform screenshot utility implemented in Python. Its command name is `fshot`.

## User Interface

- Start with the editor hidden and show only a camera-shaped system tray icon.
- Right-clicking the tray icon opens a menu containing only Exit.
- Double-clicking the tray icon shows the editor.

## Capture Shortcuts

On macOS, replace <kbd>Alt</kbd> with <kbd>Option</kbd>:

- <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>: capture the currently focused window.
- <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>: capture a selected rectangular region.
- <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd>: capture the full screen.
- <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>W</kbd>: capture a selected window or a control inside it, targeting the smallest window/control under the pointer.

## Capture Flow

1. Hide the editor when a capture shortcut is pressed.
2. Capture according to the shortcut; <kbd>Escape</kbd> cancels selection.
3. Copy the captured image directly to the system clipboard.
4. Show the image in a new editor tab named with the `yy-mm-dd-hhmmss` format.
5. Mark screenshots that are unsaved or have been edited as pending save.

## Editor Window

- Use a modern, flat, tabbed interface.
- Show `FShot-<current tab title>` in the window title, or `FShot` when no tabs exist.
- When tabs overflow, provide a menu at the right side of the tab bar. Selecting an edge tab should scroll neighboring tabs into view.
- Hiding/minimizing the editor leaves the application available from the system tray.
- Place an icon-only toolbar above the tabs with these tools:
  - Pen (<kbd>Alt</kbd>+<kbd>P</kbd>): draw freehand strokes.
  - Line (<kbd>Alt</kbd>+<kbd>L</kbd>): draw straight lines.
  - Rectangle (<kbd>Alt</kbd>+<kbd>R</kbd>): draw rectangles.
  - Text (<kbd>Alt</kbd>+<kbd>T</kbd>): click a placement point, enter text, choose a font, and press <kbd>Enter</kbd> to place it.
  - Mosaic (<kbd>Alt</kbd>+<kbd>M</kbd>): pixelate a selected region to hide sensitive content.
  - Line width and color (<kbd>Alt</kbd>+<kbd>C</kbd>): open a panel that controls drawing width/color and text appearance; the icon reflects current settings.
  - Undo: use the platform-standard undo shortcut and undo editing operations.
  - Copy: use the platform-standard shortcut and copy the current editor image.
  - Save: save a new tab through Save As, save modified existing files directly, and disable when no changes exist.
  - Save As: choose a file name/location, default to the tab title or current path, and support PNG/JPG.
- Zoom in/out using platform-standard shortcuts, with 100% as the default.
- Include Cursor: choose whether captures include the pointer.
- Delay: provide Off, 1, 3, 5 seconds, and a custom value.

## Notes

- Capture shortcuts must be consumed and must not be forwarded to the focused application, where they could cause unintended input or close FShot's own preview.
