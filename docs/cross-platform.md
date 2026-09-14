# Cross-Platform Notes

[繁體中文](cross-platform.md) | [English](cross-platform.en.md)

FShot 的 UI 大部分使用 PySide6，可跨平台重用；但截圖、全域快捷鍵、游標、視窗選取與剪貼簿都是平台相依區域。macOS 實作時請優先處理本文件列出的邊界。

配色主題屬於跨平台共用 UI：`ThemeManager` 使用 Qt 系統配色提示與 `QSettings`，支援跟隨系統、淺色及深色模式。修改主題樣式或圖示時，應同時在 Windows 與 macOS 驗證系統配色偵測、即時切換與持久化。
介面語言同樣屬於跨平台共用 UI：`LanguageManager` 在 macOS 優先讀取使用者的 `AppleLanguages`，其他平台使用 Qt locale；繁體中文系統環境顯示繁中，其餘預設英文，並允許使用者手動覆寫。
頁籤關閉按鈕遵循平台位置：macOS 位於左側、Windows 位於右側，但使用 FShot 自繪高對比圖示以確保淺色與深色主題皆清楚可見。Windows 的未存檔狀態方塊位於標題左側；其他平台依原生頁籤配置安排。
圖片拖放與剪貼簿貼上使用 Qt `QMimeData`／`QUrl`／clipboard API，核心流程可跨平台共用。macOS 驗收時需額外確認 Finder 複製檔案可取得 local file URL、HEIC/HEIF 解碼器是否可用，以及 App Sandbox 打包後是否仍有權限寫回使用者拖入的原始檔案。

## Current Platform State

### Windows

Windows 是目前主要實作平台。

已實作：

- 全域快捷鍵：`RegisterHotKey` 接收 `WM_HOTKEY`，避免快捷鍵送到焦點視窗。
- 預設使用 `Ctrl+Shift+Q` 重複前一次成功擷取（可自訂），並保留前次矩形或選取的視窗／控制項目標。
- 可由工具列鍵盤圖示設定四種截圖方式與重複擷取動作的快捷鍵；Windows 在套用前以 `RegisterHotKey` 探測是否被其他程式占用。
- 全螢幕/矩形擷取：`mss`，失敗時 fallback 到 Pillow `ImageGrab`。
- 矩形區域與視窗／控制項選取會先凍結虛擬桌面，再從凍結畫面裁切，以保留功能表等失去焦點即消失的暫態內容。
- 焦點視窗及選取到的頂層視窗：使用 DWM `DWMWA_EXTENDED_FRAME_BOUNDS`，避免截到不可見 resize frame；視窗內控制項則使用 UI Automation 邊界。
- 選取視窗/控制項：UI Automation 優先，傳統 HWND hit-test fallback。
- snapshot 時會一併保存前景執行緒的暫態視窗及 UI Automation 功能表控制項邊界。之後向原生 menu owner 傳送 `WM_CANCELMODE` 關閉 live popup menu，選取時優先命中保存的控制項，因此凍結畫面上的功能表仍可選取。全螢幕 selector 本身接收並吞掉滑鼠事件；一般視窗則依游標所在 HWND 延遲建立並快取該視窗的 UI Automation target map，不需要 input-transparent overlay、畫面外 mouse catcher 或全域 mouse grab。
- 真實游標貼圖：Win32 cursor handle best-effort 轉 RGBA bitmap，失敗不阻斷截圖。
- 系統匣、編輯器、剪貼簿、存檔、裁切與繪圖工具。

### macOS

已實作：

- Quartz event tap 全域快捷鍵，攔截並 consume `Ctrl+Shift+A/R/F/W`。
- 快捷鍵 listener 支援使用者設定的 Ctrl／Shift／Option 與 A–Z 字母組合，設定以 `QSettings` 保留。
- 透過 Screen Recording API 檢查並要求螢幕錄製權限。
- 優先使用 Accessibility `AXFocusedWindow` 擷取焦點視窗；失敗時才從前景程序的 Core Graphics 視窗選擇最大正常視窗，避免 Chrome 連結網址等 transient popup 被誤判為焦點視窗。
- 使用 Accessibility API hit-test 最小控制項，並將 bounds 限制在游標下視窗內；無效或未包含游標的結果會 fallback 至游標下視窗。
- 無延遲矩形區域及視窗／控制項選取會在 selector 取得焦點前凍結桌面，保留原應用程式中失去焦點即消失的功能表。
- 使用目前 `NSCursor` 圖像、hotspot 與游標座標貼入截圖。
- 共用 Qt 剪貼簿、系統匣、編輯器與存檔流程。

首次啟動會要求輔助使用權限，首次截圖會要求螢幕錄製權限。從 DMG 安裝時，請在「系統設定 → 隱私權與安全性 → 輔助使用／螢幕錄製」授權 `FShot.app`；透過 `uv`／`uvx` 執行時，授權對象通常是啟動指令的「終端機」、iTerm2、Warp 或 IDE 宿主程式。變更後需完全結束並重新開啟 FShot 或宿主 App。未授予輔助使用權限時，控制項選取與全域快捷鍵不可用；視窗 hit-test 仍會 best-effort fallback。

### Linux

Linux 尚未作為主要目標。Wayland/X11 差異很大，尤其是全域快捷鍵、截圖權限與視窗查詢。

## Platform Boundaries

跨平台工作應優先把以下能力抽象化，避免把平台分支散落在 UI 層：

- Global hotkeys
  - 目前在 `app.py`。
  - 建議後續抽出 `hotkeys.py`，依平台實作 Windows/macOS/Linux backend。

- Capture backend
  - 目前集中在 `capture.py`。
  - 建議拆成通用 `CaptureService` 加平台 backend，例如 `platforms/windows.py`、`platforms/macos.py`。

- Window/control selection
  - Windows 目前使用 UI Automation + HWND fallback。
  - macOS 應用 Accessibility API 提供同等的 `rect_at_point()`。

- Cursor image
  - Windows 目前 best-effort 轉 RGBA。
  - macOS 需要回傳 `(image, hotspot_x, hotspot_y, screen_x, screen_y)` 等同資料。

- Permissions
  - Windows 目前沒有集中 permission flow。
  - macOS 應在啟動或首次使用時檢查 Screen Recording/Accessibility，並提示使用者。

## macOS Implementation Layout

- `platforms/macos.py`: 權限、Core Graphics/Accessibility 視窗查詢、游標與全域快捷鍵。
- `capture.py`: 保留跨平台擷取流程，僅在平台能力入口委派給 macOS backend。
- `app.py`: Windows native filter、macOS event tap 與其他平台 fallback 的生命週期管理。

## Automatic Updates

- 僅 `uv tool install fshot` 安裝可自動更新；`uvx`、原始碼 checkout 與一般 virtualenv 會保守地顯示為不支援。
- Frozen Windows EXE 與 macOS App 每日檢查 GitHub 最新 Release；發現新版時開啟下載頁面，由使用者驗證後手動替換，不自動覆寫未簽章程式。
- Windows 使用隱藏的 Windows PowerShell helper，macOS/Linux 使用獨立的 `/bin/sh` helper。Helper 只等待 FShot 正常退出，逾時會取消，不會強制終止程式。
- 實際安裝由 uv 執行帶有已驗證目標版本的 `uv tool upgrade`；FShot 不直接修改 tool environment。
- 更新前必須先完成目前的擷取，且有未儲存頁籤時會要求確認。更新後重新啟動的 FShot 會從套件 metadata 驗證實際版本並顯示結果。

## Packaged Applications

- Windows 只發布 x64 單一 EXE；macOS 只發布 Apple Silicon arm64 DMG，不支援 Intel Mac。
- 兩平台皆不套用可信任發行者簽章。Windows 可能顯示 SmartScreen，macOS 需要 Gatekeeper「仍要打開」，詳細流程見各平台安裝文件。
- macOS DMG 內含 `FShot.app` 與 Applications 捷徑。因 App 沒有 Developer ID 簽章或 notarization，更新後可能需要重新確認 Gatekeeper、螢幕錄製與輔助使用權限。

## Manual Acceptance Checklist

每個平台至少要手動驗收：

- 快捷鍵可觸發，且不把按鍵送給焦點 app。
- 快捷鍵設定面板會顯示目前值；「使用預設」只改變面板暫存值，OK 套用並保留，Cancel 不改變目前設定。
- macOS 自訂 Ctrl／Shift／Option 與字母組合可觸發正確的截圖方式，重新啟動後設定仍保留。
- 無延遲和有延遲流程都符合：Windows 矩形區域與視窗／控制項選取於倒數後凍結桌面，其他模式則先決定目標再倒數擷取。
- 全螢幕、矩形、焦點視窗、選取視窗/控制項都可用。
- 擷取成功後 FShot 編輯器會恢復並要求成為 Windows 前景視窗；若一般 `SetForegroundWindow` 被前景鎖定拒絕，會以短暫 topmost／not-topmost 的 Z-order 提升作為 fallback。擷取完成 200ms 後會再確認一次編輯器位於前景。
- Chrome 等具有 transient popup 的應用程式，焦點視窗擷取不會誤截連結網址或 tooltip。
- ESC 可取消延遲倒數及矩形／視窗選取。
- 包含游標時顯示當下真實游標。
- 截圖後影像出現在編輯區左上角。
- 複製到剪貼簿可貼到常見 app。
- 存檔 PNG/JPG 正常。
- 拖放圖片以原始檔名開啟、初始不標為 dirty，編輯並儲存後可寫回來源檔。
- 已存檔頁籤可用 Windows/Linux `F2`、macOS `Return` 或雙擊標籤名稱直接重新命名原始檔案；不覆寫同名檔案且保留副檔名。
- 直接貼上影像與從檔案管理器複製圖片後貼上，會建立使用截圖命名規範的新頁籤。
- 像素丈量拖曳時會即時顯示水平與垂直差值，縮放後讀值仍以原圖像素計算，且不會修改輸出影像。
- 最小化隱藏、系統匣雙擊顯示、右鍵退出正常。
