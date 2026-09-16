# Architecture

[繁體中文](architecture.md) | [English](architecture.en.md)

本文是給初次接觸 FShot 專案的導覽。若要做 macOS 跨平台實作，請同時閱讀 [cross-platform.md](cross-platform.md)。

## Entry Points

- `pyproject.toml`: 專案 metadata、依賴與 `fshot` command。
- `src/fshot/__main__.py`: `python -m fshot` 入口。
- `src/fshot/app.py`: Qt application、系統匣、全域快捷鍵與截圖流程 orchestration。

## Main Modules

- `app.py`
  - 建立 `QApplication`、`FShotApplication`、系統匣圖示。
  - Windows 使用 `RegisterHotKey` 接收全域快捷鍵，避免快捷鍵送到焦點視窗。
  - 收到快捷鍵後隱藏編輯視窗，呼叫 `CaptureService`，截圖完成後加入編輯頁籤並複製到剪貼簿。
  - 系統匣提供手動及每日自動更新檢查；確認更新後先處理未儲存資料，再啟動外部 helper 並正常結束程式，重啟時顯示實際更新結果。

- `updates.py`
  - 在 Qt thread pool 執行 `uv-tool-updater` 的同步網路檢查，避免阻塞 UI thread。
  - 使用 `QSettings` 保存自動檢查開關、上次檢查時間及略過版本；背景檢查最多每日一次，手動檢查不受間隔限制。
  - 不直接修改 uv tool environment；安裝、等待程序退出與重新啟動由 `uv-tool-updater` 協調。
  - Frozen EXE／App 改查 GitHub 最新 Release；發現新版時只開啟下載頁面，不自動覆寫未簽章應用程式。

- `packaging/fshot.spec`、`scripts/build_app.py`
  - 使用 PyInstaller 產生 Windows x64 單一 EXE，以及 Apple Silicon macOS App。
  - macOS App 會放入含 Applications 捷徑的 arm64 DMG；Windows 版本資訊、ICO 與 macOS ICNS 在建置時由程式 metadata 及現有相機圖示產生。
  - GitHub Release 發布後，由 `package-apps.yml` 自動在原生 runner 建置、驗證並附加 EXE、DMG 與 SHA-256；不支援 Intel Mac。

- `capture.py`
  - 管理所有截圖模式：全螢幕、矩形區域、焦點視窗、選取視窗/控制項。
  - Windows 特有能力集中於此：焦點視窗與選取頂層視窗的 DWM frame bounds、UI Automation 控制項 hit-test、真實游標 bitmap、`mss`/`ImageGrab` fallback。
  - macOS 平台能力委派至 `platforms/macos.py`，包含權限、`AXFocusedWindow`、控制項 hit-test、游標與 Quartz event tap。
  - 延遲截圖流程也在此：Windows 互動式選取於倒數後凍結桌面，其他模式則先決定目標矩形，再倒數並擷取即時畫面。

- `platforms/macos.py`
  - 使用 Accessibility 的 focused window，避免把同程序的 transient popup 當成焦點視窗。
  - 控制項 hit-test 結果必須落在游標下視窗內並包含游標座標，否則 fallback 至該視窗。
  - 管理 Screen Recording／Accessibility 權限、真實游標與可 consume 的全域快捷鍵。

- `main_window.py`
  - 編輯主視窗、toolbar、多頁籤、存檔/另存、縮放、設定面板。
  - 視窗標題會從已安裝套件 metadata 顯示目前版本，並在有文件時附加目前頁籤名稱。
  - 工具列使用 20px 圖示與 34px 固定按鈕，讓各平台的工具列維持緊湊且一致的點擊區域；畫線按鈕旁另有 20px 寬的端點樣式下拉按鈕。
  - 畫線與箭頭整合成單一工具，端點面板可獨立設定起點與終點為無、箭頭或實心圓。
  - 每個截圖頁籤持有一個 `ImageCanvas`。
  - 已存檔頁籤可用 Windows/Linux `F2` 或 macOS `Return`，以及雙擊標籤名稱，直接在頁籤內重新命名原始檔案；重新命名保留影像副檔名。
  - 截圖、拖放檔案與剪貼簿影像共用頁籤建立流程；拖放保留來源 `Path` 並以 clean document 開啟，剪貼簿則建立新的 unsaved document。
  - Windows 將 dirty 狀態方塊放在頁籤標題左側、關閉按鈕放在右側；其他平台依 Qt 原生關閉按鈕位置安排。

- `canvas.py`
  - 編輯區與影像操作。
  - 支援自由畫筆、具可組合端點樣式的線條、矩形、非破壞性像素丈量、文字、馬賽克、裁切控制方塊、圖片旋轉／鏡射／重採樣、顯示縮放與 undo。
  - 像素丈量使用圖片座標計算起點至游標的水平／垂直差值，縮放不影響讀值；丈量框與讀值只在 Canvas overlay 繪製，不會進入輸出影像或 undo stack。
  - 順時針旋轉 90°、水平／垂直鏡射與依 1–99% 比例縮小會直接更新 `QImage`、重設裁切／丈量暫態、同步 Canvas 尺寸並進入 undo stack；比例縮小使用平滑重採樣，其展開面板沿用線條粗細控制的 `ArrowSpinBox`。
  - Canvas 會在圖片外圍預留 padding，讓裁切控制方塊不覆蓋圖片內容。
  - 捲軸只對齊圖片區域，不延伸到裁切控制方塊的 padding；兩端與右下角交會區使用 Canvas 補白色。
  - 淺色與深色主題使用相同尺寸的自訂捲軸，並以各自主題的高對比軌道、滑塊及 hover 色呈現。

- `document.py`
  - `ShotDocument` 管理頁籤標題、存檔路徑、dirty/unsaved 狀態。

- `icons.py`
  - 程式內自繪 toolbar/system tray icon。
  - 各工具圖示在共同畫布內做視覺置中；鉛筆圖示另校正其斜向外形造成的垂直偏移。
  - 工作列與系統匣相機圖示分別調整透明邊距，並提供 16–64px 多解析度 pixmap；macOS 選單列另使用接近正方形的相機配置填滿有限高度，讓各平台顯示槽位維持清楚且一致的視覺占比。

- `settings.py`
  - `CaptureMode`、`Tool`、`LineEndStyle`、`CaptureSettings`、`DrawingSettings`。

- `hotkeys.py`
  - 定義四種截圖方式及重複擷取動作的可設定組合鍵、格式驗證與 `QSettings` 持久化。
  - UI 只編輯暫存副本；Windows 透過 `RegisterHotKey` 探測衝突，確認成功後才替換目前註冊。

- `theme.py`
  - 管理跟隨系統、淺色與深色三種模式，透過 `QSettings` 持久化，並在系統配色變更時即時套用。
  - `ThemeManager` 在 application 層建立並注入 `EditorWindow`，統一管理 palette、stylesheet 與依主題重繪的工具列圖示。
  - 淺色與深色面板使用對應色票但維持相同控制項結構；數值欄位由 `ArrowSpinBox` 提供跨平台一致且可連續操作的上下按鈕。

- `i18n.py`
  - 管理跟隨系統、繁體中文與英文三種語言模式，使用 `QLocale` 判斷系統語言並透過 `QSettings` 持久化。
  - 可見字串集中在翻譯表，`LanguageManager.changed` 會觸發主視窗與系統匣即時更新。
  - 工具列 tooltip 由翻譯文字與 `QAction` 快捷鍵動態組合，避免翻譯表重複維護按鍵名稱。

- `qt_image.py`
  - Pillow 與 Qt image/pixmap 轉換 helper。

## Capture Flow

1. `app.py` 收到全域快捷鍵。
2. 編輯視窗先隱藏，避免被截入畫面。
3. Windows 與 macOS 的無延遲矩形區域及視窗／控制項選取會在 selector 取得焦點前擷取整個虛擬桌面，保留原應用程式中失去焦點即消失的功能表；Windows 的視窗／控制項模式還會在 `WM_HOTKEY` 返回前保存暫態視窗及 UI Automation 功能表控制項邊界。即使目標程式隨後關閉 live menu，overlay 仍能從凍結畫面選取及裁切。
4. 其他模式由 `CaptureService._rect_for_mode()` 決定擷取矩形。
5. 若有延遲，顯示右下角倒數 overlay，期間可按 `Esc` 取消；矩形區域與視窗／控制項選取會在倒數後凍結畫面，其他模式則在決定矩形後倒數。
6. 凍結的矩形區域與視窗／控制項直接從保存畫面裁切；其他模式在 overlay 隱藏後呼叫 `_grab_rect()` 擷取畫面。
7. 若啟用包含游標，best-effort 貼上凍結或即時擷取當下的真實游標。
8. `EditorWindow.add_shot()` 建立新頁籤並顯示於左上角。
9. `EditorWindow.copy_current()` 複製目前影像到剪貼簿。

`Ctrl+Shift+Q` 預設會重複前一次成功的擷取，並可在快捷鍵設定面板自訂。矩形模式保存固定座標；視窗／控制項模式保存原生目標身分並在重複時重新取得目前邊界，目標已消失時不顯示錯誤也不建立頁籤。

## Editing Model

目前編輯是直接修改 `QImage`，每次操作前把當前影像複製進 undo stack。這讓實作簡單，但不是向量化/物件化模型；未來若要支援重新選取已畫物件、調整文字內容或匯出可編輯圖層，需要重構 canvas model。

拖放開啟的圖片會保留來源路徑，初始狀態為已儲存；首次編輯後才標為 dirty，`Save` 直接寫回來源。剪貼簿貼上的圖片沒有來源路徑，標題使用 `YY-MM-DD-HHMMSS`，首次儲存會進入另存新檔流程。每次成功存檔後，檔案所在資料夾會透過 `QSettings` 保留；其他尚無自身路徑的頁籤會以該資料夾作為存檔交談窗的預設位置，並沿用自己的頁籤標題作為預設檔名。

裁切也是影像操作：拖曳圖片外圍控制方塊後，滑鼠放開即裁切並進入 undo stack。

## Testing

目前測試以輕量單元測試和 Qt offscreen smoke 為主：

- `tests/test_document.py`: tab title、dirty/save 狀態、文件 reindex。
- `tests/test_icons.py`: 工作列與系統匣圖示在原生槽位尺寸中的不透明圖案占比，以及工具圖示的視覺置中。
- `tests/test_main_window.py`: 工具列按鈕尺寸、圖片捲軸排除 Canvas padding 的幾何與補白元件。
- `tests/test_version.py`: 執行時版本與已安裝套件 metadata 保持一致。
- `tests/test_updates.py`: 自動檢查間隔、略過版本、背景執行與錯誤回報。
- 以 `uv run pytest -q` 與 `uv run python -m compileall src tests` 執行跨平台檢查。

重要的 GUI/OS 行為仍需手動驗收，尤其是全域快捷鍵、視窗選取、游標擷取與剪貼簿。
