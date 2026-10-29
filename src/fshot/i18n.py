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
        "about_fshot": "About FShot…",
        "help_menu": "Help",
        "about_details": "FShot {version}\nCross-platform screenshot and image annotation tool.\n\nLicense: GNU General Public License v3.0 or later (GPL-3.0-or-later).\nThird-party components retain their respective licenses.\n\nProject and source code:\nhttps://github.com/codemee/fshot\n\nFull license:\nhttps://www.gnu.org/licenses/gpl-3.0.html",
        "message_question": "Confirm action",
        "message_warning": "Please check",
        "message_error": "Unable to complete",
        "message_information": "Information",
        "continue": "Continue",
        "ok": "OK",
        "cancel": "Cancel",
        "dont_save": "Don't save",
        "save_all": "Save all",
        "unsaved_title": "Unsaved screenshots",
        "unsaved_single": "“{title}” has unsaved changes.",
        "unsaved_many": "{count} screenshots have unsaved changes.",
        "unsaved_close_help": "Save before closing, or close without saving.",
        "unsaved_update_help": "Save before updating, or continue without saving.",
        "unsaved_quit_help": "Save before quitting, or quit without saving.",
        "mac_virtual_install_question": "BetterDisplay was not found. Install it using Homebrew, then automatically create and select FShot-4K? BetterDisplay will stay running. Its CLI integration or licensed features may require setup. Terminal will open for installation and any administrator confirmation.",
        "mac_virtual_brew_question": "Homebrew was not found. Install it using Homebrew's official installer, then continue installing BetterDisplay? Terminal will open; review the installer and enter your password there if requested. FShot does not collect your password.",
        "mac_virtual_install_progress": "Installing in Terminal… Complete any installer/password prompts there. FShot will continue automatically after successful installation.",
        "mac_virtual_install_failed": "Installation failed or the installed application could not be found. Check the Terminal output, then switch to virtual mode again. Physical mode is retained.",
        "mac_virtual_install_timeout": "Installation did not finish within 30 minutes. Physical mode is retained. The installer may still be running in Terminal; finish or stop it there, then try again.",
        "mac_virtual_permissions": "Grant FShot Accessibility and Screen Recording permissions before using virtual capture.",
        "mac_virtual_version": "Virtual display capture requires macOS 14 or later.",
        "mac_virtual_missing": "FShot-4K is unavailable. Switch virtual mode off and on to automatically prepare and select it again.",
        "mac_virtual_choose": "Select an existing extended display for capture. Choose your virtual display; physical external displays are also listed. No display configuration will be changed.",
        "mac_virtual_create_question": "No 4K extended display is active. Create or reconnect a dedicated FShot virtual screen using BetterDisplay? BetterDisplay must be installed; it will remain running to keep the screen connected.",
        "mac_virtual_create_option": "Create/reconnect an FShot 4K virtual screen with BetterDisplay…",
        "mac_virtual_setup_failed": "The FShot virtual screen could not be enabled at 4K HiDPI. Check BetterDisplay's integration settings, license requirements and display mode. Its saved definition is kept for retry.",
        "mac_virtual_help": "Experimental macOS virtual capture: automatically prepare and select FShot-4K. Missing BetterDisplay/Homebrew installations require your consent. Active or selected windows/controls are moved, captured and restored. Delayed active-window capture opens an interactive preview. Region capture is not available. Requires macOS 14 or later.",
        "mac_interactive_input": "Mouse forwarding stopped. Check Accessibility and Input Monitoring permissions for FShot (or its terminal/IDE host).",
        "mac_interactive_hint": "Interactive virtual display — capture in {seconds}s\nMove the pointer into the preview to click, drag or scroll. Keyboard controls the target app. Esc cancels.",
        "virtual_interactive_hint": "Interactive virtual display — capture in {seconds}s\nMouse and keyboard control the target app. Esc cancels and restores the window.",
        "virtual_interactive_screen": "Keep the cursor on a physical monitor before starting interactive virtual capture. The preview must be on a different display.",
        "virtual_interactive_focus": "The target app could not keep keyboard focus. Interactive capture was stopped and the window will be restored.",
        "virtual_interactive_input": "Mouse input could not be forwarded. The target app may have higher administrator privileges. Interactive capture was stopped.",
        "virtual_install_question": "No supported virtual display driver was found. Install VirtualDrivers Virtual Display Driver and then create a 3840 × 2160 virtual display?\n\nThe official package will be downloaded through WinGet. Installation will accept the package/source agreements and may require Windows administrator approval.",
        "virtual_install_progress": "Downloading and installing Virtual Display Driver…",
        "virtual_install_failed": "Virtual Display Driver could not be installed. You can install it manually with: winget install --id=VirtualDrivers.Virtual-Display-Driver -e",
        "virtual_winget_missing": "WinGet is unavailable. Install or update Microsoft's App Installer, or download Virtual Driver Control from https://github.com/VirtualDrivers/Virtual-Display-Driver/releases, then switch to virtual mode again.",
        "virtual_driver_missing": "No active virtual display or supported Virtual Display Driver installation was found.\n\nInstall Virtual Driver Control using PowerShell:\nwinget install --id=VirtualDrivers.Virtual-Display-Driver -e\n\nThen switch to virtual mode again. Official downloads:\nhttps://github.com/VirtualDrivers/Virtual-Display-Driver/releases",
        "virtual_create_question": "A supported virtual display driver was found, but no virtual display is active. Create one 3840 × 2160 virtual display and enable extended desktop?\n\nWindows may ask for administrator approval. The current driver configuration will be backed up before updating it.",
        "virtual_setup_progress": "Creating the 4K virtual display… Please approve the Windows administrator prompt if shown.",
        "virtual_setup_cancelled": "Creation was cancelled or Windows administrator approval was not granted.",
        "virtual_setup_failed": "The virtual display could not be enabled at 3840 × 2160. Check Windows Display Settings or Virtual Driver Control, then try again.",
        "capture_screen_physical": "Capture screen: physical (click to switch)",
        "capture_screen_virtual": "Capture screen: virtual (click to switch)",
        "capture_screen_help": "Virtual mode moves the active window or selected window/control. A delayed active-window capture opens an interactive preview. Full-screen capture uses the monitor containing the cursor. Region capture is not available in virtual mode.",
        "virtual_region_unsupported": "Region capture is not available in virtual mode yet. Switch to physical mode to capture a region.",
        "virtual_target_unavailable": "The selected window or control cannot be tracked on the virtual display. It may have closed, been recreated or disappeared after losing focus. Select a stable window/control and try again.",
        "virtual_owner_unavailable": "The selected control has no movable owning window. Popup menus and system panels cannot be moved using this mode.",
        "virtual_control_unavailable": "The selected control could not be located again in its owning window after selection or moving. The app may have removed it or changed its identity. Please select it again.",
        "virtual_target_obscured": "The selected target is hidden, covered or has disappeared on the virtual display. Capture was stopped to avoid capturing a different window.",
        "virtual_screen_capture": "Virtual display capture…",
        "virtual_screen_help": "The active virtual display is selected automatically. Select a capture target below.",
        "virtual_screen_missing": "No active supported virtual display was found. Enable your virtual display and set Windows to extend the desktop, then try again.",
        "virtual_screen_desktop": "Capture desktop without moving a window",
        "virtual_screen_display": "Display",
        "virtual_screen_window": "Select capture target",
        "virtual_screen_preview": "Display preview",
        "virtual_screen_preview_help": "View-only preview. Window width and height keep their original fractions of the source screen on the destination screen. Only the window is captured. Wait for rendering to finish. Original position, size and state are restored after capture or cancellation.",
        "virtual_screen_take": "Capture",
        "virtual_screen_separate": "Select a different extended display so the preview does not cover the captured screen. Add a virtual display or move FShot to another screen first.",
        "open_tabs": "Open tabs",
        "next_tab": "Next tab",
        "previous_tab": "Previous tab",
        "close_tab": "Close tab",
        "select_tab": "Select tab {number}",
        "last_tab": "Last tab",
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
        "zoom_fit": "Fit to window",
        "zoom_percent": "Display scale: {percent}% — click to enter a scale",
        "zoom_value": "Display scale",
        "zoom_apply": "Apply",
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
        "about_fshot": "關於 FShot…",
        "help_menu": "說明",
        "about_details": "FShot {version}\n跨平台截圖與圖片標註工具。\n\n授權：GNU General Public License 第三版或更新版本（GPL-3.0-or-later）。\n第三方元件維持各自的授權。\n\n專案與原始碼：\nhttps://github.com/codemee/fshot\n\n完整授權條款：\nhttps://www.gnu.org/licenses/gpl-3.0.html",
        "message_question": "確認操作",
        "message_warning": "請注意",
        "message_error": "操作未完成",
        "message_information": "提示",
        "continue": "繼續",
        "ok": "確定",
        "cancel": "取消",
        "dont_save": "不儲存",
        "save_all": "儲存全部",
        "unsaved_title": "有尚未儲存的截圖",
        "unsaved_single": "「{title}」尚未儲存。",
        "unsaved_many": "共 {count} 張截圖尚未儲存。",
        "unsaved_close_help": "請先儲存，或選擇不儲存並關閉；未儲存的變更將會捨棄。",
        "unsaved_update_help": "請先儲存，或選擇不儲存並更新；未儲存的變更將會捨棄。",
        "unsaved_quit_help": "請先儲存，或選擇不儲存並結束；未儲存的變更將會捨棄。",
        "mac_virtual_install_question": "找不到 BetterDisplay。是否透過 Homebrew 安裝，並自動建立及選用 FShot-4K？BetterDisplay 會保持運行；CLI 整合或授權功能可能需要設定。安裝會開啟「終端機」，請在其中完成安裝與管理員確認。",
        "mac_virtual_brew_question": "找不到 Homebrew。是否使用 Homebrew 官方安裝程式安裝，完成後接續安裝 BetterDisplay？會開啟「終端機」，請閱讀安裝內容，並在需要時於終端機輸入密碼；FShot 不會收集密碼。",
        "mac_virtual_install_progress": "正在終端機安裝… 請在終端機完成安裝／密碼提示。成功後 FShot 會自動接續準備虛擬螢幕。",
        "mac_virtual_install_failed": "安裝失敗或找不到安裝完成的程式。請檢查終端機輸出，再切換虛擬模式重試；目前維持實體模式。",
        "mac_virtual_install_timeout": "安裝未在 30 分鐘內完成，目前維持實體模式。終端機內的安裝程式可能仍在運行，請在其中完成或停止後再重試。",
        "mac_virtual_permissions": "使用虛擬擷取前，請授予 FShot「輔助使用」與「螢幕錄製」權限。",
        "mac_virtual_version": "虛擬螢幕擷取需要 macOS 14 或更新版本。",
        "mac_virtual_missing": "FShot-4K 目前不可用。請關閉及重新開啟虛擬模式，自動準備並選用此螢幕。",
        "mac_virtual_choose": "選擇既有的延伸螢幕作為擷取目標。請選取你的虛擬螢幕；清單也會列出實體外接螢幕。不會變更螢幕設定。",
        "mac_virtual_create_question": "目前沒有啟用中的 4K 延伸螢幕。要透過 BetterDisplay 建立或重新連接 FShot 專用虛擬螢幕嗎？需先安裝 BetterDisplay，並保持運行以維持螢幕連線。",
        "mac_virtual_create_option": "透過 BetterDisplay 建立／重新連接 FShot 4K 虛擬螢幕…",
        "mac_virtual_setup_failed": "FShot 虛擬螢幕無法啟用為 4K HiDPI。請檢查 BetterDisplay 的整合設定、授權需求與顯示模式。螢幕定義會保留供重試。",
        "mac_virtual_help": "macOS 實驗功能：自動準備並選用 FShot-4K，缺少 BetterDisplay／Homebrew 時先詢問是否安裝。將作用中或指定的視窗／控制項移動、擷取後還原。作用中視窗的延遲擷取會開啟操作預覽。不支援區域擷取。需要 macOS 14 以上。",
        "mac_interactive_input": "滑鼠轉送已停止。請檢查 FShot（或啟動它的終端機／IDE）是否有「輔助使用」與「輸入監控」權限。",
        "mac_interactive_hint": "虛擬螢幕操作預覽 — {seconds} 秒後擷取\n將滑鼠移入預覽即可點擊、拖曳或捲動。鍵盤操作目標程式；Esc 取消。",
        "virtual_interactive_hint": "虛擬螢幕操作預覽 — {seconds} 秒後擷取\n滑鼠與鍵盤操作目標程式；Esc 取消並還原視窗。",
        "virtual_interactive_screen": "請先將游標放在實體螢幕再啟動互動式虛擬擷取。預覽必須位於另一個螢幕。",
        "virtual_interactive_focus": "目標程式無法維持鍵盤焦點，已停止互動式擷取並還原視窗。",
        "virtual_interactive_input": "無法轉送滑鼠操作，目標程式可能使用較高的系統管理員權限。已停止互動式擷取。",
        "virtual_install_question": "找不到支援的虛擬螢幕驅動程式。是否安裝 VirtualDrivers Virtual Display Driver，並接著建立 3840 × 2160 虛擬螢幕？\n\n會透過 WinGet 下載官方套件並接受套件／來源授權條款；Windows 可能要求系統管理員確認。",
        "virtual_install_progress": "正在下載並安裝 Virtual Display Driver…",
        "virtual_install_failed": "Virtual Display Driver 安裝失敗。可手動執行：winget install --id=VirtualDrivers.Virtual-Display-Driver -e",
        "virtual_winget_missing": "系統找不到 WinGet。請安裝或更新 Microsoft 的 App Installer，或從 https://github.com/VirtualDrivers/Virtual-Display-Driver/releases 下載 Virtual Driver Control，安裝後再切換虛擬模式。",
        "virtual_driver_missing": "找不到已啟用的虛擬螢幕或支援的 Virtual Display Driver 安裝。\n\n請在 PowerShell 安裝 Virtual Driver Control：\nwinget install --id=VirtualDrivers.Virtual-Display-Driver -e\n\n安裝後再切換為虛擬模式。官方下載：\nhttps://github.com/VirtualDrivers/Virtual-Display-Driver/releases",
        "virtual_create_question": "已找到支援的虛擬螢幕驅動程式，但目前沒有啟用的虛擬螢幕。是否建立一個 3840 × 2160 虛擬螢幕並啟用延伸桌面？\n\nWindows 可能要求系統管理員確認。更新前會備份原本的驅動設定。",
        "virtual_setup_progress": "正在建立 4K 虛擬螢幕… 若 Windows 顯示系統管理員提示，請手動確認。",
        "virtual_setup_cancelled": "建立已取消，或未取得 Windows 系統管理員同意。",
        "virtual_setup_failed": "無法啟用 3840 × 2160 虛擬螢幕。請檢查 Windows 顯示設定或 Virtual Driver Control 後再試。",
        "capture_screen_physical": "擷取螢幕：實體（點擊切換）",
        "capture_screen_virtual": "擷取螢幕：虛擬（點擊切換）",
        "capture_screen_help": "虛擬模式會移動作用中視窗或選取的視窗／控制項。作用中視窗設定延遲後可開啟操作預覽。全螢幕擷取游標所在螢幕；虛擬模式暫不支援區域擷取。",
        "virtual_region_unsupported": "虛擬模式暫不支援區域擷取。請切換為實體模式後擷取區域。",
        "virtual_target_unavailable": "無法在虛擬螢幕追蹤選取的視窗或控制項。目標可能已關閉、重新建立，或因失去焦點而消失。請重新選取穩定的視窗／控制項。",
        "virtual_owner_unavailable": "選取的子元件沒有可移動的所屬視窗。彈出功能表或系統面板無法使用此模式搬移。",
        "virtual_control_unavailable": "選取或移動後，無法在所屬視窗中重新找到該子元件。程式可能已移除它或改變其識別資料，請重新選取。",
        "virtual_target_obscured": "原選取標的在虛擬螢幕上已隱藏、被遮住或消失。已停止擷取，避免截到其他視窗。",
        "virtual_screen_capture": "虛擬螢幕擷取…",
        "virtual_screen_help": "自動使用已啟用的虛擬螢幕，請選取下方的擷取標的。",
        "virtual_screen_missing": "找不到已啟用且支援的虛擬螢幕。請先啟用虛擬螢幕並在 Windows 設定為延伸桌面，再重新擷取。",
        "virtual_screen_desktop": "擷取桌面，不移動視窗",
        "virtual_screen_display": "螢幕",
        "virtual_screen_window": "選取擷取標的",
        "virtual_screen_preview": "螢幕預覽",
        "virtual_screen_preview_help": "此預覽僅供查看。視窗寬、高依原本佔來源螢幕的比例，換算為目標螢幕尺寸。只擷取視窗範圍。請等待畫面完成繪製；擷取或取消後還原原位置、長寬與視窗狀態。",
        "virtual_screen_take": "擷取",
        "virtual_screen_separate": "請選擇另一個延伸螢幕，避免預覽遮住擷取畫面。請先建立虛擬螢幕，或把 FShot 移到另一個螢幕。",
        "open_tabs": "開啟的頁籤",
        "next_tab": "下一個頁籤",
        "previous_tab": "上一個頁籤",
        "close_tab": "關閉頁籤",
        "select_tab": "切換至第 {number} 個頁籤",
        "last_tab": "最後一個頁籤",
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
        "zoom_fit": "符合視窗",
        "zoom_percent": "顯示比例：{percent}% — 按一下輸入比例",
        "zoom_value": "顯示比例",
        "zoom_apply": "套用",
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
