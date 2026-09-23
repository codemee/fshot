from __future__ import annotations

import ctypes
import os
import sys
import traceback
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QObject,
    QSettings,
    QStandardPaths,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
from uv_tool_updater import (
    InstallStatus,
    ReleaseInfo,
    UpdateCheck,
    UpdateStatus,
    Updater,
)

from fshot.capture import CaptureService
from fshot.icons import tray_icon
from fshot.hotkeys import HotkeyAction, HotkeyCombination, HotkeyStore, validate_hotkeys
from fshot.i18n import LanguageManager
from fshot.main_window import EditorWindow
from fshot.settings import CaptureMode
from fshot.theme import ThemeManager
from fshot.updates import GITHUB_RELEASES_URL, GitHubReleaseUpdater, UpdateManager

if sys.platform == "win32":
    import win32con
    import win32gui
else:  # pragma: no cover - platform branch
    win32con = None
    win32gui = None


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class HotkeyBridge(QObject):
    captureRequested = Signal(CaptureMode)
    repeatRequested = Signal()


def _activate_window(window) -> None:
    window.showNormal()
    window.raise_()
    window.activateWindow()
    QApplication.processEvents()
    if sys.platform == "win32":
        hwnd = int(window.winId())
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # Windows can reject foreground activation while another process
            # owns mouse capture, notably during an in-progress drag-and-drop.
            pass
        try:
            is_foreground = win32gui.GetForegroundWindow() == hwnd
        except Exception:
            is_foreground = False
        if is_foreground:
            return
        flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
        try:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # Showing the editor is sufficient; the delayed activation retry
            # can request focus again after the input transaction settles.
            pass


class WindowsHotkeyFilter(QAbstractNativeEventFilter):
    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000

    def __init__(self, hwnd: int | None, bridge: HotkeyBridge, bindings) -> None:
        super().__init__()
        self.hwnd = hwnd
        self.bridge = bridge
        self.bindings = {
            1001 + index: (combination, mode)
            for index, (mode, combination) in enumerate(bindings.items())
        }
        self.registered_ids: list[int] = []

    def register(self) -> None:
        ctypes.windll.user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
        ctypes.windll.user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
        for hotkey_id, (combination, _mode) in self.bindings.items():
            modifiers = self.modifiers(combination) | self.MOD_NOREPEAT
            ok = ctypes.windll.user32.RegisterHotKey(
                ctypes.c_void_p(self.hwnd or 0),
                hotkey_id,
                modifiers,
                ord(combination.letter),
            )
            if not ok:
                self.unregister()
                raise ctypes.WinError()
            self.registered_ids.append(hotkey_id)

    def unregister(self) -> None:
        for hotkey_id in self.registered_ids:
            ctypes.windll.user32.UnregisterHotKey(ctypes.c_void_p(self.hwnd or 0), hotkey_id)
        self.registered_ids.clear()

    def nativeEventFilter(self, event_type, message):
        event_name = bytes(event_type).decode(errors="ignore") if not isinstance(event_type, str) else event_type
        if event_name not in {"windows_generic_MSG", "windows_dispatcher_MSG"}:
            return False, 0
        msg = MSG.from_address(int(message))
        if msg.message != self.WM_HOTKEY:
            return False, 0
        binding = self.bindings.get(int(msg.wParam))
        if binding is None:
            return False, 0
        _combination, mode = binding
        if mode == HotkeyAction.REPEAT:
            self.bridge.repeatRequested.emit()
        else:
            self.bridge.captureRequested.emit(mode)
        return True, 0

    @classmethod
    def modifiers(cls, combination: HotkeyCombination) -> int:
        return (
            (cls.MOD_CONTROL if combination.ctrl else 0)
            | (cls.MOD_SHIFT if combination.shift else 0)
            | (cls.MOD_ALT if combination.alt else 0)
        )


class FShotApplication(QObject):
    def __init__(
        self,
        app: QApplication,
        *,
        updater: Updater | None = None,
        update_settings: QSettings | None = None,
        packaged: bool | None = None,
    ) -> None:
        super().__init__()
        self.app = app
        self.app.setApplicationName("FShot")
        self.app.setOrganizationName("FShot")
        self.app.setQuitOnLastWindowClosed(False)
        self.packaged = bool(getattr(sys, "frozen", False)) if packaged is None else packaged
        self.update_settings = update_settings if update_settings is not None else QSettings()
        self.updater = updater or self._default_updater()
        self.update_manager = UpdateManager(self.updater, self.update_settings)
        self.update_manager.checkFinished.connect(self._update_check_finished)
        self.update_manager.checkFailed.connect(self._update_check_failed)
        self.update_manager.checkingChanged.connect(self._update_checking_changed)
        self.theme_manager = ThemeManager(self.app)
        self.language_manager = LanguageManager()
        self.capture = CaptureService()
        self.window = EditorWindow(self.theme_manager, self.language_manager)
        self.hotkey_store = HotkeyStore()
        self.hotkeys = self.hotkey_store.load()
        self.bridge = HotkeyBridge()
        self.bridge.captureRequested.connect(self.capture_mode)
        self.bridge.repeatRequested.connect(self.repeat_capture)
        self.tray = self._build_tray()
        self.language_manager.changed.connect(self._language_changed)
        self._hotkey_handles: list[object] = []
        self._native_hotkey_filter: WindowsHotkeyFilter | None = None
        self._mac_hotkey_listener = None
        self._capture_in_progress = False
        self.window.configure_hotkeys(self.hotkeys, self._validate_hotkeys, self._apply_hotkeys)
        self._register_hotkeys()

    def run(self) -> int:
        self.tray.show()
        self.window.hide()
        if not self.packaged:
            QTimer.singleShot(0, self._show_pending_update_result)
        QTimer.singleShot(5000, self._start_automatic_update_check)
        return self.app.exec()

    def _default_updater(self):
        if self.packaged:
            return GitHubReleaseUpdater()
        return Updater(
            package_name="fshot",
            command_name="fshot",
            state_dir=Path(
                QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
            )
            / "updates",
        )

    def show_window(self) -> None:
        _activate_window(self.window)

    def quit(self) -> None:
        self._shutdown()

    def _shutdown(self) -> None:
        self._unregister_hotkeys()
        self.tray.hide()
        self.app.quit()

    def capture_mode(self, mode: CaptureMode) -> None:
        settings = self.window.capture_settings
        frozen_selection = None

        def freeze_before_hotkey_returns() -> None:
            nonlocal frozen_selection
            frozen_selection = self.capture.prepare_frozen_selection(mode, settings)

        self._start_capture(
            lambda: self.capture.capture(mode, settings, frozen_selection),
            before_event_flush=freeze_before_hotkey_returns,
        )

    def repeat_capture(self) -> None:
        self._start_capture(lambda: self.capture.repeat(self.window.capture_settings))

    def _start_capture(self, capture, before_event_flush=None) -> None:
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        self.window.hide()
        if before_event_flush is not None:
            try:
                before_event_flush()
            except Exception as exc:  # pragma: no cover - UI guard
                traceback.print_exc()
                QMessageBox.warning(
                    self.window,
                    "FShot",
                    self.language_manager.text("capture_failed", error=exc),
                )
                self._capture_in_progress = False
                return
        QApplication.processEvents()

        def do_capture() -> None:
            try:
                image = capture()
            except Exception as exc:  # pragma: no cover - UI guard
                traceback.print_exc()
                QMessageBox.warning(
                    self.window,
                    "FShot",
                    self.language_manager.text("capture_failed", error=exc),
                )
                self._capture_in_progress = False
                return
            if image is None:
                self._capture_in_progress = False
                return
            self.window.add_shot(image)
            self.show_window()
            # Selection completion can post a delayed activation restore after
            # SetForegroundWindow initially succeeds. Reassert the editor once
            # that input transaction has fully settled.
            QTimer.singleShot(200, self.show_window)
            self.window.copy_current()
            self._capture_in_progress = False

        QTimer.singleShot(120, do_capture)

    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(tray_icon(macos=sys.platform == "darwin"), self.app)
        tray.setToolTip("FShot")
        menu = QMenu()
        self.check_updates_action = QAction(self.language_manager.text("check_updates"), menu)
        self.check_updates_action.triggered.connect(
            lambda _checked=False: self.update_manager.start_check(manual=True)
        )
        menu.addAction(self.check_updates_action)
        self.automatic_updates_action = QAction(
            self.language_manager.text("automatic_update_checks"), menu
        )
        self.automatic_updates_action.setCheckable(True)
        self.automatic_updates_action.setChecked(self.update_manager.automatic_checks_enabled)
        self.automatic_updates_action.toggled.connect(self._automatic_update_checks_toggled)
        menu.addAction(self.automatic_updates_action)
        menu.addSeparator()
        self.exit_action = QAction(self.language_manager.text("exit"), menu)
        self.exit_action.triggered.connect(self.quit)
        menu.addAction(self.exit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        return tray

    def _language_changed(self, _mode, _effective) -> None:
        self.check_updates_action.setText(
            self.language_manager.text(
                "checking_updates" if self.update_manager.is_checking else "check_updates"
            )
        )
        self.automatic_updates_action.setText(
            self.language_manager.text("automatic_update_checks")
        )
        self.exit_action.setText(self.language_manager.text("exit"))

    def _automatic_update_checks_toggled(self, enabled: bool) -> None:
        self.update_manager.set_automatic_checks_enabled(enabled)
        if enabled:
            QTimer.singleShot(0, self._start_automatic_update_check)

    def _start_automatic_update_check(self) -> None:
        self.update_manager.start_check(manual=False)

    def _update_checking_changed(self, checking: bool) -> None:
        self.check_updates_action.setEnabled(not checking)
        self.check_updates_action.setText(
            self.language_manager.text("checking_updates" if checking else "check_updates")
        )

    def _update_check_failed(self, message: str, manual: bool) -> None:
        if manual:
            QMessageBox.warning(
                self.window,
                "FShot",
                self.language_manager.text("update_check_failed", error=message),
            )

    def _update_check_finished(self, check: UpdateCheck, manual: bool) -> None:
        if check.status is UpdateStatus.UPDATE_AVAILABLE and check.release is not None:
            version = str(check.release.version)
            if not manual and self.update_manager.is_version_skipped(version):
                return
            self._offer_update(check)
            return
        if not manual:
            return
        if check.status is UpdateStatus.UP_TO_DATE:
            current = str(check.installed.current_version) if check.installed is not None else ""
            QMessageBox.information(
                self.window,
                "FShot",
                self.language_manager.text("update_up_to_date", version=current),
            )
        elif check.status is UpdateStatus.UNSUPPORTED_INSTALLATION:
            QMessageBox.information(
                self.window,
                "FShot",
                self.language_manager.text("update_unsupported"),
            )
        else:
            QMessageBox.warning(
                self.window,
                "FShot",
                self.language_manager.text(
                    "update_check_failed", error=check.message or check.error_code or "Unknown error"
                ),
            )

    def _offer_update(self, check: UpdateCheck) -> None:
        release = check.release
        if release is None:
            return
        current = str(check.installed.current_version) if check.installed is not None else ""
        latest = str(release.version)
        dialog = QMessageBox(self.window)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle(self.language_manager.text("update_available_title"))
        dialog.setText(
            self.language_manager.text(
                "update_available", current=current, latest=latest
            )
        )
        update_button = dialog.addButton(
            self.language_manager.text("update_download" if self.packaged else "update_now"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        later_button = dialog.addButton(
            self.language_manager.text("update_later"), QMessageBox.ButtonRole.RejectRole
        )
        skip_button = dialog.addButton(
            self.language_manager.text("update_skip"), QMessageBox.ButtonRole.DestructiveRole
        )
        dialog.setDefaultButton(update_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is skip_button:
            self.update_manager.skip_version(latest)
        elif clicked is update_button:
            if self.packaged:
                self._open_packaged_release(release)
            else:
                self._install_update(release)
        elif clicked is later_button:
            return

    def _open_packaged_release(self, release: ReleaseInfo) -> None:
        QDesktopServices.openUrl(QUrl(release.release_url or GITHUB_RELEASES_URL))

    def _install_update(self, release: ReleaseInfo) -> None:
        if self._capture_in_progress:
            QMessageBox.information(
                self.window,
                "FShot",
                self.language_manager.text("update_capture_in_progress"),
            )
            return
        if not self.window.confirm_discard_all("update_discard_all"):
            return
        try:
            session = self.updater.prepare_update(
                release,
                restart_args=[],
                restart_on_failure=True,
                wait_timeout=600,
            )
            session.start_helper(host_pid=os.getpid())
        except Exception as exc:
            QMessageBox.warning(
                self.window,
                "FShot",
                self.language_manager.text("update_start_failed", error=exc),
            )
            return
        self._shutdown()

    def _show_pending_update_result(self) -> None:
        try:
            result = self.updater.consume_latest_result()
        except Exception as exc:
            self.tray.showMessage(
                "FShot",
                self.language_manager.text("update_result_invalid", error=exc),
                QSystemTrayIcon.MessageIcon.Warning,
                10000,
            )
            return
        if result is None:
            return
        icon = QSystemTrayIcon.MessageIcon.Information
        if result.status is InstallStatus.SUCCEEDED:
            message = self.language_manager.text(
                "update_result_succeeded",
                version=result.actual_version or result.requested_version or "",
            )
        elif result.status is InstallStatus.NO_CHANGE:
            icon = QSystemTrayIcon.MessageIcon.Warning
            message = self.language_manager.text(
                "update_result_no_change", version=result.actual_version or result.previous_version
            )
        elif result.status is InstallStatus.APP_EXIT_TIMEOUT:
            icon = QSystemTrayIcon.MessageIcon.Warning
            message = self.language_manager.text("update_result_timeout")
        elif result.status is InstallStatus.RESTART_FAILED:
            icon = QSystemTrayIcon.MessageIcon.Warning
            message = self.language_manager.text("update_result_restart_failed")
        else:
            icon = QSystemTrayIcon.MessageIcon.Critical
            message = self.language_manager.text(
                "update_result_failed", error=result.error or "Unknown error"
            )
        self.tray.showMessage("FShot", message, icon, 10000)

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def _register_hotkeys(self, bindings=None, show_warning: bool = True) -> bool:
        bindings = bindings or self.hotkeys
        if sys.platform == "win32":
            try:
                self._native_hotkey_filter = WindowsHotkeyFilter(None, self.bridge, bindings)
                self._native_hotkey_filter.register()
                self.app.installNativeEventFilter(self._native_hotkey_filter)
                return True
            except Exception as exc:
                self._native_hotkey_filter = None
                if show_warning:
                    QMessageBox.warning(self.window, "FShot", f"Native global hotkeys unavailable: {exc}")
                return False

        if sys.platform == "darwin":
            try:
                from fshot.platforms.macos import MacHotkeyListener, accessibility_allowed

                accessibility_allowed(request=True)
                actions = {combination: action for action, combination in bindings.items()}

                def dispatch(combination) -> None:
                    action = actions[combination]
                    if action == HotkeyAction.REPEAT:
                        self.bridge.repeatRequested.emit()
                    else:
                        self.bridge.captureRequested.emit(action)

                self._mac_hotkey_listener = MacHotkeyListener(
                    dispatch,
                    tuple(actions),
                )
                self._mac_hotkey_listener.start()
                return True
            except Exception as exc:
                if show_warning:
                    QMessageBox.warning(self.window, "FShot", f"macOS global hotkeys unavailable: {exc}")
                return False

        try:
            import keyboard
        except Exception as exc:  # pragma: no cover - optional dependency guard
            if show_warning:
                QMessageBox.warning(self.window, "FShot", f"Global hotkeys unavailable: {exc}")
            return False

        for action, combination in bindings.items():
            shortcut = combination.display().lower()
            try:
                if action == HotkeyAction.REPEAT:
                    callback = lambda: self.bridge.repeatRequested.emit()
                else:
                    callback = lambda capture_mode=action: self.bridge.captureRequested.emit(capture_mode)
                handle = keyboard.add_hotkey(shortcut, callback, suppress=True)
                self._hotkey_handles.append(handle)
            except Exception as exc:
                self._unregister_hotkeys()
                if show_warning:
                    QMessageBox.warning(self.window, "FShot", f"Could not register {shortcut}: {exc}")
                return False
        return True

    def _validate_hotkeys(self, bindings) -> tuple[bool, str]:
        problem = validate_hotkeys(bindings)
        if problem:
            return False, self.language_manager.text(f"hotkey_{problem}")
        if sys.platform != "win32" or self._native_hotkey_filter is None:
            return True, ""
        owned = {combination for combination, _mode in self._native_hotkey_filter.bindings.values()}
        registered: list[int] = []
        try:
            for index, combination in enumerate(bindings.values()):
                if combination in owned:
                    continue
                hotkey_id = 2101 + index
                ok = ctypes.windll.user32.RegisterHotKey(
                    ctypes.c_void_p(0),
                    hotkey_id,
                    WindowsHotkeyFilter.modifiers(combination)
                    | WindowsHotkeyFilter.MOD_NOREPEAT,
                    ord(combination.letter),
                )
                if not ok:
                    return False, self.language_manager.text(
                        "hotkey_conflict", shortcut=combination.display()
                    )
                registered.append(hotkey_id)
        finally:
            for hotkey_id in registered:
                ctypes.windll.user32.UnregisterHotKey(ctypes.c_void_p(0), hotkey_id)
        return True, ""

    def _apply_hotkeys(self, bindings) -> tuple[bool, str]:
        valid, message = self._validate_hotkeys(bindings)
        if not valid:
            return valid, message
        previous = self.hotkeys
        self._unregister_hotkeys()
        if not self._register_hotkeys(bindings, show_warning=False):
            self._register_hotkeys(previous, show_warning=False)
            return False, self.language_manager.text("hotkey_registration_failed")
        self.hotkeys = dict(bindings)
        self.hotkey_store.save(self.hotkeys)
        self.window.configure_hotkeys(self.hotkeys, self._validate_hotkeys, self._apply_hotkeys)
        return True, ""

    def _unregister_hotkeys(self) -> None:
        if self._mac_hotkey_listener is not None:
            self._mac_hotkey_listener.stop()
            self._mac_hotkey_listener = None
        if self._native_hotkey_filter is not None:
            self.app.removeNativeEventFilter(self._native_hotkey_filter)
            self._native_hotkey_filter.unregister()
            self._native_hotkey_filter = None
        try:
            import keyboard
        except Exception:
            return
        for handle in self._hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._hotkey_handles.clear()


def main() -> int:
    if "--version" in sys.argv:
        from fshot import __version__

        print(f"FShot {__version__}")
        return 0
    app = QApplication(sys.argv)
    controller = FShotApplication(app)
    return controller.run()
