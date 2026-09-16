from __future__ import annotations

import re
import subprocess
import sys
from enum import Enum

from PySide6.QtCore import QLocale, QObject, QSettings, Signal


class LanguageMode(str, Enum):
    SYSTEM = "system"
    ZH_TW = "zh_TW"
    EN = "en"


TRANSLATIONS = {
    "en": {
        "open_tabs": "Open tabs",
        "tools": "Tools",
        "pen": "Pen",
        "line": "Line",
        "line_end_settings": "Line endpoint styles",
        "line_start": "Start",
        "line_end": "End",
        "line_end_none": "None",
        "line_end_arrow": "Arrow",
        "line_end_circle": "Solid circle",
        "rectangle": "Rectangle",
        "measure": "Measure pixels",
        "text": "Text",
        "mosaic": "Mosaic",
        "line_color": "Line and color",
        "undo": "Undo",
        "rotate_clockwise": "Rotate clockwise 90°",
        "flip_horizontal": "Flip horizontally",
        "flip_vertical": "Flip vertically",
        "resize_image": "Scale image down",
        "resize_percent": "Scale (%)",
        "resize_apply": "Apply",
        "copy": "Copy",
        "paste": "Paste image",
        "save": "Save",
        "save_as": "Save As",
        "rename": "Rename file",
        "zoom_in": "Zoom in",
        "zoom_out": "Zoom out",
        "reset_zoom": "Reset zoom",
        "include_cursor": "Include cursor",
        "include_cursor_on": "Include cursor: on",
        "include_cursor_off": "Include cursor: off",
        "delay": "Delay",
        "delay_value": "Delay: {seconds:g}s",
        "capture_shortcuts": "Capture shortcuts",
        "capture_type": "Capture type",
        "ctrl": "Ctrl",
        "shift": "Shift",
        "alt": "Alt",
        "letter": "Letter",
        "use_defaults": "Use defaults",
        "capture_active_window": "Active window",
        "capture_region": "Region",
        "capture_fullscreen": "Full screen",
        "capture_window_under_cursor": "Window / control",
        "capture_repeat": "Repeat previous capture",
        "hotkey_incomplete": "All capture shortcuts must be configured.",
        "hotkey_invalid": "Shift must be combined with Ctrl or Alt.",
        "hotkey_duplicate": "Capture shortcuts cannot be duplicated.",
        "hotkey_conflict": "{shortcut} is already registered by another application.",
        "hotkey_registration_failed": "A shortcut could not be registered. Cancel and choose another combination.",
        "theme": "Theme: {mode} ({effective})",
        "theme_system": "follow system",
        "theme_light": "light",
        "theme_dark": "dark",
        "language": "Language: {mode} ({effective})",
        "language_system": "follow system",
        "language_zh_TW": "Traditional Chinese",
        "language_en": "English",
        "width": "Width",
        "custom": "Custom",
        "custom_color": "Custom...",
        "off": "Off",
        "line_color_dialog": "Line color",
        "save_screenshot": "Save Screenshot",
        "close_discard_all": "Close FShot and discard unsaved screenshots?",
        "close_discard_tab": "Close {title} and discard changes?",
        "save_failed": "Could not save {path}",
        "rename_invalid": "Enter a valid file name.",
        "rename_exists": "A file named {name} already exists.",
        "rename_failed": "Could not rename {path}",
        "check_updates": "Check for updates...",
        "checking_updates": "Checking for updates...",
        "automatic_update_checks": "Automatically check for updates",
        "update_available_title": "FShot Update",
        "update_available": "FShot {latest} is available. You are using {current}.",
        "update_now": "Update and restart",
        "update_download": "Open download page",
        "update_later": "Later",
        "update_skip": "Skip this version",
        "update_up_to_date": "FShot {version} is up to date.",
        "update_unsupported": "Automatic updates require FShot to be installed with uv tool. Update manually with: uv tool upgrade fshot",
        "update_check_failed": "Could not check for updates: {error}",
        "update_capture_in_progress": "Wait for the current capture to finish before updating.",
        "update_discard_all": "Update FShot and discard unsaved screenshots?",
        "update_start_failed": "Could not start the update: {error}",
        "update_result_invalid": "Could not read the previous update result: {error}",
        "update_result_succeeded": "FShot was updated successfully to {version}.",
        "update_result_no_change": "The update completed, but FShot is still version {version}.",
        "update_result_timeout": "The update was cancelled because FShot did not exit in time.",
        "update_result_restart_failed": "FShot was updated, but could not be restarted automatically.",
        "update_result_failed": "The update failed: {error}",
        "exit": "Exit",
        "capture_failed": "Capture failed: {error}",
        "open_image_failed": "Could not open image: {path}",
        "tooltip_shortcut": "{label} ({shortcut})",
    },
    "zh_TW": {
        "open_tabs": "開啟的頁籤",
        "tools": "工具",
        "pen": "畫筆",
        "line": "線條",
        "line_end_settings": "線條端點樣式",
        "line_start": "起點",
        "line_end": "終點",
        "line_end_none": "無箭頭",
        "line_end_arrow": "箭頭",
        "line_end_circle": "實心圓",
        "rectangle": "矩形",
        "measure": "丈量像素",
        "text": "文字",
        "mosaic": "馬賽克",
        "line_color": "線條與顏色",
        "undo": "復原",
        "rotate_clockwise": "順時針旋轉 90°",
        "flip_horizontal": "水平鏡射",
        "flip_vertical": "垂直鏡射",
        "resize_image": "依比例縮小圖片",
        "resize_percent": "縮小比例（%）",
        "resize_apply": "套用",
        "copy": "複製",
        "paste": "貼上影像",
        "save": "儲存",
        "save_as": "另存新檔",
        "rename": "重新命名檔案",
        "zoom_in": "放大",
        "zoom_out": "縮小",
        "reset_zoom": "重設縮放",
        "include_cursor": "包含滑鼠游標",
        "include_cursor_on": "包含滑鼠游標：開啟",
        "include_cursor_off": "包含滑鼠游標：關閉",
        "delay": "延遲",
        "delay_value": "延遲：{seconds:g} 秒",
        "capture_shortcuts": "設定截圖快捷鍵",
        "capture_type": "截圖方式",
        "ctrl": "Ctrl",
        "shift": "Shift",
        "alt": "Alt",
        "letter": "字母",
        "use_defaults": "使用預設",
        "capture_active_window": "目前焦點視窗",
        "capture_region": "矩形區域",
        "capture_fullscreen": "全螢幕",
        "capture_window_under_cursor": "視窗／控制項",
        "capture_repeat": "重複前一次擷取",
        "hotkey_incomplete": "必須設定所有截圖快捷鍵。",
        "hotkey_invalid": "Shift 必須搭配 Ctrl 或 Alt 使用。",
        "hotkey_duplicate": "截圖快捷鍵不可重複。",
        "hotkey_conflict": "{shortcut} 已由其他軟體註冊使用。",
        "hotkey_registration_failed": "快捷鍵無法註冊，請取消並選擇其他組合。",
        "theme": "配色主題：{mode}（{effective}）",
        "theme_system": "跟隨系統",
        "theme_light": "淺色",
        "theme_dark": "深色",
        "language": "語言：{mode}（{effective}）",
        "language_system": "跟隨系統",
        "language_zh_TW": "繁體中文",
        "language_en": "英文",
        "width": "粗細",
        "custom": "自訂",
        "custom_color": "自訂顏色...",
        "off": "關閉",
        "line_color_dialog": "線條顏色",
        "save_screenshot": "儲存截圖",
        "close_discard_all": "關閉 FShot 並捨棄尚未儲存的截圖？",
        "close_discard_tab": "關閉 {title} 並捨棄變更？",
        "save_failed": "無法儲存至 {path}",
        "rename_invalid": "請輸入有效的檔案名稱。",
        "rename_exists": "已有名為 {name} 的檔案。",
        "rename_failed": "無法重新命名 {path}",
        "check_updates": "檢查更新…",
        "checking_updates": "正在檢查更新…",
        "automatic_update_checks": "自動檢查更新",
        "update_available_title": "FShot 更新",
        "update_available": "FShot {latest} 已可使用，目前版本為 {current}。",
        "update_now": "更新並重新啟動",
        "update_download": "開啟下載頁面",
        "update_later": "稍後",
        "update_skip": "略過這個版本",
        "update_up_to_date": "FShot {version} 已是最新版本。",
        "update_unsupported": "自動更新需要透過 uv tool 安裝 FShot。請手動執行：uv tool upgrade fshot",
        "update_check_failed": "無法檢查更新：{error}",
        "update_capture_in_progress": "請等待目前的擷取完成後再更新。",
        "update_discard_all": "更新 FShot 並捨棄尚未儲存的截圖？",
        "update_start_failed": "無法啟動更新：{error}",
        "update_result_invalid": "無法讀取前一次更新結果：{error}",
        "update_result_succeeded": "FShot 已成功更新至 {version}。",
        "update_result_no_change": "更新程序已完成，但 FShot 仍為 {version}。",
        "update_result_timeout": "FShot 未在期限內結束，更新已取消。",
        "update_result_restart_failed": "FShot 已更新，但無法自動重新啟動。",
        "update_result_failed": "更新失敗：{error}",
        "exit": "結束",
        "capture_failed": "擷取失敗：{error}",
        "open_image_failed": "無法開啟影像：{path}",
        "tooltip_shortcut": "{label} ({shortcut})",
    },
}


class LanguageManager(QObject):
    changed = Signal(LanguageMode, LanguageMode)

    def __init__(self, settings: QSettings | None = None, system_locale: QLocale | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings()
        self.system_locale = system_locale or QLocale.system()
        self.system_languages = (
            (self.system_locale.uiLanguages() or [self.system_locale.name()])
            if system_locale is not None
            else _system_language_names(self.system_locale)
        )
        self.mode = self._stored_mode()

    @property
    def effective_mode(self) -> LanguageMode:
        if self.mode != LanguageMode.SYSTEM:
            return self.mode
        return (
            LanguageMode.ZH_TW
            if any(_is_traditional_chinese(name) for name in self.system_languages)
            else LanguageMode.EN
        )

    def set_mode(self, mode: LanguageMode) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self.settings.setValue("appearance/language", mode.value)
        self.changed.emit(mode, self.effective_mode)

    def text(self, key: str, **values) -> str:
        language = self.effective_mode.value
        template = TRANSLATIONS[language].get(key, TRANSLATIONS["en"].get(key, key))
        return template.format(**values)

    def _stored_mode(self) -> LanguageMode:
        value = self.settings.value("appearance/language", LanguageMode.SYSTEM.value)
        try:
            return LanguageMode(str(value))
        except ValueError:
            return LanguageMode.SYSTEM


def _system_language_names(fallback: QLocale) -> list[str]:
    if sys.platform == "darwin":
        languages = _read_macos_user_languages()
        if languages:
            return languages
    return fallback.uiLanguages() or [fallback.name()]


def _read_macos_user_languages() -> list[str]:
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return re.findall(r'"([^\"]+)"', result.stdout)


def _is_traditional_chinese(language: str) -> bool:
    normalized = language.replace("-", "_").lower()
    return normalized.startswith(("zh_tw", "zh_hk", "zh_mo", "zh_hant"))
