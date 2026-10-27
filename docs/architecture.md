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
  - Windows 恢復編輯器時，原生前景切換採 best-effort；拖放尚未放開等情況若被系統拒絕，仍保留視窗顯示、Z-order fallback 與延遲重試，不讓例外中斷截圖流程。
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
  - Windows 全螢幕模式只擷取原生游標所在的單一螢幕；工具列實體／虛擬切換不影響此模式。完整虛擬桌面範圍仍供凍結快照、跨螢幕選取與擷取邊界裁切使用。
  - Windows 區域及視窗／控制項選取共用每個螢幕獨立的遮罩及快照裁切，分別套用該螢幕 Qt 縮放；以螢幕原點及 Qt 邏輯尺寸乘 DPR 配對 Win32 原生螢幕，不依賴可能為 EDID 名稱的 QScreen.name。原生游標及 UIA 邊界轉換為各遮罩的邏輯座標繪製；跨螢幕框選／目標標示同步，點擊或取消時一併關閉所有遮罩，避免不同 DPI 下畫面與選取邊界錯位。
  - 每次選取以 finally 清除遮罩間的循環參照、UIA 快取與快照，再 deleteLater；凍結的控制項也保留所屬視窗身分。UIA resolver 優先讀取現存元件，只有邊界失效才以識別條件查詢，限制候選數量及迭代時間，避免重複掃描完整控制項樹。
  - 快照同步保存原視窗 HWND 及前後順序；選取不因原視窗消失而重新命中下層視窗。UIA live resolver 驗證 RuntimeId／識別資料及所屬視窗，重新建立的元件只允許唯一 AutomationId 配對；虛擬擷取前檢查目標位置仍屬於原 HWND，隱藏或遮擋時停止擷取。
  - 管理所有截圖模式：全螢幕、矩形區域、焦點視窗、選取視窗/控制項。
  - Windows 特有能力集中於此：焦點視窗與選取頂層視窗的 DWM frame bounds、UI Automation 控制項 hit-test、真實游標 bitmap、`mss`/`ImageGrab` fallback。
  - macOS 平台能力委派至 `platforms/macos.py`，包含權限、`AXFocusedWindow`、控制項 hit-test、游標與 Quartz event tap。
  - 延遲截圖流程也在此：Windows 互動式選取於倒數後凍結桌面，其他模式則先決定目標矩形，再倒數並擷取即時畫面。

- `platforms/macos.py`
  - 使用 Accessibility 的 focused window，避免把同程序的 transient popup 當成焦點視窗。
  - 控制項 hit-test 結果必須落在游標下視窗內並包含游標座標，否則 fallback 至該視窗。
  - 管理 Screen Recording／Accessibility 權限、真實游標與可 consume 的全域快捷鍵。

- `platforms/macos_virtual.py`
  - 切換時自動選用固定名稱 FShot-4K 的 4K 延伸螢幕並保存 UUID，名稱重複或作為主螢幕時拒絕使用；使用 AX 元件、PID 與 CGWindowID 追蹤作用中視窗。
  - 比例換算及 AX 移動使用 Quartz points，ScreenCaptureKit 輸出使用 display mode pixels。context manager 在部分搬移失敗、倒數取消與擷取錯誤後還原幾何。
  - 擷取前檢查螢幕配置、視窗幾何及中心遮擋；非同步擷取有十秒逾時，等待時保持 Qt 事件處理。需要 macOS 14 以上。
  - 指定視窗／控制項保留 `WindowCaptureTarget.native_target` 的 `MacCaptureTarget`；以 PID／CGWindowID 配對唯一 AXWindow，驗證 AX 所屬視窗。選取標題列／外框擷取全視窗，控制項移動後重新讀取 AX 邊界並裁切至所屬視窗；失效不重新 hit-test 或按舊座標猜測。AX hit-test 直接指定底下應用程式，避免 FShot 遮罩阻擋。

- `platforms/macos_virtual_setup.py`
  - 使用 BetterDisplay CLI 自動建立／連接固定名稱 FShot-4K 的 1920 × 1080 HiDPI（3840 × 2160 pixels）螢幕，首次可採用同名既有 VirtualScreen 定義。
  - QProcess 使用參數陣列與 35 秒上限，等待時保持 Qt 事件處理。建立前保存固定名稱，建立後保存 tagID／serial／model／vendor 指紋；重試時驗證身分，不設定其他名稱的螢幕。定義與連線跨 FShot 退出保留，不使用全域 discard／disconnect。

- `platforms/macos_virtual_install.py`
  - 偵測 BetterDisplay bundle／CLI；缺少時詢問是否使用 brew，缺少 brew 再另行詢問官方 Homebrew 安裝。拒絕不啟動安裝；已存在有效 FShot-4K 時略過安裝檢查與詢問。
  - 搜尋 PATH、標準 prefix 與使用者 homebrew prefix，支援 Finder 啟動的環境。經同意後由 Terminal 執行官方 Homebrew installer 或 brew cask install；不以 root 執行 brew、不收集密碼。私有暫存 shell wrapper 記錄 exit status，Qt event loop 輪詢完成，成功再驗證安裝存在；30 分鐘逾時不接續建立，提醒 Terminal 程序可能仍在運行。

- `platforms/macos_interactive.py`
  - 僅虛擬作用中視窗且延遲大於 0 時啟用。ScreenCaptureKit 的 30 fps stream 在 libdispatch serial queue 回呼，CVPixelBuffer 鎖定期間複製為 QImage；跳過非完整 frame，信箱只保留最新影像，Qt queued signal 更新非啟用預覽。首張畫面就緒後才開始倒數。
  - 背景 Quartz event tap 攔截預覽內的滑鼠與 Esc；以顯示後的預覽全域 points 邊界映射實體游標絕對位置，保留原事件 flags／滾輪／點擊資料。由 `GetProcessForPID` 解析原生程序佇列，再以 `CGEventPostToPSN` 派送視窗綁定事件；保留實體游標移動事件，不 warp 全域游標。離開預覽停止轉送，拖曳維持捕捉至放開。鍵盤其他事件不攔截，焦點保留目標程式。點擊紀錄包含映射座標、命中視窗與派送進度；API 無接收確認，實際處理仍需手動驗收。
  - 每 200ms 驗證目標及焦點，每秒檢查螢幕配置，最終擷取前再檢查。倒數到期先停止 timer（避免原生等待重新進入 final capture）、凍結滑鼠輸入及停止 stream，再擷取原生像素與可辨識的新 popup 聯集。
  - finally 關閉 stream、停用／invalidate event tap、釋放按鍵；外層 moved_window 還原視窗。Qt 預覽位於實體螢幕，與擷取螢幕分離。最終游標以映射位置與 HiDPI 比例合成至輸出，實際游標不搬移。
  - 合成事件使用獨立 private source，關閉本機輸入抑制並允許滑鼠／鍵盤／系統事件；轉送後的 delta 與縮放後座標一致。焦點恢復使用獨立的 NSRunningApplication 參照，不覆蓋 QApplication；退出訊號的解除連接置於輸入清理之後。
  - 指定程序事件需先以 NSEvent mouse factory 綁定真正的 `windowNumber` 再轉成 CGEvent；只改 Quartz hit-test annotation 仍會得到 windowNumber=0。轉送前驗證目標視窗編號，保留點擊次數、按鍵、修飾鍵及滾輪 delta／phase；macOS 原生記憶體 roundtrip 測試驗證此差異，不發送測試事件。
  - `CGEventSetLocation` 不會更新獨立儲存的視窗內座標，factory 事件可能保留 `(-1,-1)`。派送前重新驗證同 PID 的 CGWindowID 與即時邊界，使用未公開 `CGEventSetWindowLocation` 補上相對視窗左上角的 points，並由 `CGEventGetWindowLocation` 讀回驗證。符號檢查於攔截輸入前執行，不支援時明確中止；此實驗路徑有 macOS 版本相容性風險。

- `virtual_screen.py`
  - 延遲操作預覽使用獨立背景執行緒，依 Win32 顯示器名稱選用 DXGI output；初始化失敗時回退至執行緒專屬 MSS context。BGRA 轉為 QImage 並縮小至預覽像素尺寸；有鎖的單張信箱只保留最新影像，並以最多一個待處理的 queued signal 通知介面更新，避免累積舊畫面及額外輪詢等待。滑鼠移動以 4ms precise timer 合併轉送，按鍵／滾輪在下一輪事件迴圈處理；游標只更新新舊位置附近區域，預覽繪圖略過未變更的標題。目標邊界每 200ms、螢幕配置每秒及最終擷取前驗證。輸出前停止背景預覽，再由原擷取流程取得完整解析度。
  - `virtual_interactive.py` 僅在虛擬作用中視窗擷取且延遲大於 0 時啟用。實體螢幕的非啟用預覽顯示完整虛擬螢幕；倒數期間以暫時 WH_MOUSE_LL hook 與 SendInput 轉送滑鼠，排除注入事件避免迴圈，鍵盤保留目標視窗焦點。finally 解除 hook、釋放按鍵及還原游標；先擷取原生功能表及新開啟的同程序 owned popup，再關閉預覽。
  - 工具列切換透過 application validator 檢查啟用中的虛擬螢幕；`virtual_display_setup.py` 檢查 VDD 驅動檔／裝置，使用者同意後以 QProcess 啟動 UAC helper，備份設定並建立一個 4K 延伸螢幕。主程式維持事件迴圈，失敗或取消會回到實體模式。
  - `VirtualCaptureSession` 提供快捷鍵模式的直接擷取與獨立 repeat 紀錄：前景視窗在事件處理前保存原生身分；選取控制項保留所屬 HWND，跨 DPI 移動後以 UIA RuntimeId 或唯一的 AutomationId／類型／class／名稱重新尋找元件，不按舊座標猜測。忽略部分 provider 在虛擬螢幕上的 offscreen 標記，但仍要求與所屬視窗相交並裁切其可見部分。區域擷取暫不支援。
  - 依 Windows 顯示卡驅動名稱辨識已啟用的虛擬螢幕，自動選擇像素面積最大的目標；工具列切換統一處理安裝及建立確認，系統匣不提供額外入口。
  - 使用 Win32 螢幕與視窗識別及原生像素座標，不以 Qt 的邏輯座標決定擷取區域。
  - 保存原生 window rect 與 placement，使用 `MonitorFromWindow` 取得來源螢幕；寬、高分別依「原視窗可見尺寸 ÷ 來源螢幕完整尺寸 × 目標螢幕完整尺寸」換算。移動至目標 Work area 左上角後校正不同 DPI 的 DWM 邊框；預覽及擷取使用實際可見邊界。一般視窗還原 placement 後再依保存的原生座標還原位置、長寬；原本最大化者還原原 placement。桌面模式仍擷取整個螢幕。
  - 保存原視窗 placement 並在 finally 還原；螢幕斷線或座標／尺寸改變會停止流程。缺少支援的 VDD 時，使用者同意後以 WinGet 安裝官方套件，再接續建立 4K 延伸螢幕；已有驅動則只詢問建立。
  - 跨 DPI 校正以原生邊界連續穩定樣本提早結束等待，達到目標尺寸即停止重複 SetWindowPos；一般視窗不額外執行 SW_RESTORE。移動後保留重繪緩衝，僅桌面擷取跳過此等待；子元件擷取合併身分驗證與邊界查詢，紀錄移動及影像就緒時間供手動效能驗收。

- `main_window.py`
  - 編輯主視窗、toolbar、多頁籤、存檔/另存、縮放、設定面板。
  - 縮放工具群提供放大、縮小、符合視窗與可輸入的比例顯示，並以分隔線區隔擷取設定。符合視窗依最大可用 viewport 扣除 Canvas 留白計算；各頁籤以 `zoomChanged` 同步比例文字，不修改影像與 dirty 狀態。比例按鈕寬度為三位數字加百分號與左右各 7px，顯示整數比例；輸入面板提供 1%–800%，欄位最小寬度為 110px，預留自訂增減按鈕空間。
  - 視窗標題會從已安裝套件 metadata 顯示目前版本，並在有文件時附加目前頁籤名稱。
  - 工具列使用 20px 圖示與 34px 固定按鈕，高度固定為 42px，讓按鈕上下各保留 4px 留白，避免 hover 底色貼住標籤頁；畫線按鈕旁另有 20px 寬的端點樣式下拉按鈕。
  - 工具列左右各保留 4px，與按鈕間距一致；窄視窗的三點按鈕也距右側 4px。三點功能表左右各增加 8px 留白，避免工具圖示貼近邊緣。
  - 彈性空白將快捷鍵設定、配色與語言群組推至右側，群組前保留分隔線；功能表略過空白 widget。淺深色分隔線皆為 1px 寬，上下 margin 為 8px、左右為 2px。
  - 一般工具按鈕的圖示畫布四邊至按鈕外緣各為 7px，包含 6px padding 與 1px 邊框；20px 寬的端點下拉按鈕使用獨立水平內距。
  - 窄視窗下三點按鈕垂直置中，以彈出選單提供被隱藏的工具，維持原動作及勾選狀態；畫線群組另提供端點設定子選單。隱藏工具的設定面板以三點按鈕為定位基準，不採用增加工具列高度的展開方式。
  - 選用工具由編輯器共用；新增或切換標籤頁時，畫布會套用工具列當前選取的工具。
  - 頁籤快捷鍵以視窗範圍的 QAction 註冊：上一頁／下一頁與關閉使用 Qt 平台標準按鍵，另支援 Ctrl+Page Up／Page Down 與 Ctrl+1–8／9（macOS 的 Ctrl 由 Qt 對應為 Command）。切換首尾循環，9 選取最後一頁；關閉沿用未儲存確認流程，沒有頁籤時停用相關動作。
  - 畫線與箭頭整合成單一工具，端點面板可獨立設定起點與終點為無、箭頭或實心圓。
  - 每個截圖頁籤持有一個 `ImageCanvas`。
  - 關閉頁籤、關閉編輯視窗、結束程式與更新前共用未儲存處理：可儲存／儲存全部、不儲存或取消。逐張儲存使用該文件自己的 Canvas，任何取消或失敗都會中止後續關閉／更新，保留所有頁籤與尚未儲存的變更。
  - 已存檔頁籤可用 Windows/Linux <kbd>F2</kbd> 或 macOS <kbd>Return</kbd>，以及雙擊標籤名稱，直接在頁籤內重新命名原始檔案；重新命名保留影像副檔名。
  - 截圖、拖放檔案與剪貼簿影像共用頁籤建立流程；拖放保留來源 `Path` 並以 clean document 開啟，剪貼簿則建立新的 unsaved document。
  - Windows 將 dirty 狀態方塊放在頁籤標題左側、關閉按鈕放在右側；其他平台依 Qt 原生關閉按鈕位置安排。

- `dialogs.py`
  - 顯示前依完成樣式套用後的版面與文字換行需求計算高度，固定交談窗高度並限制標題垂直延展，避免快捷鍵衝突等提示沿用過大的初始尺寸；確認、警告、儲存與更新提示共用此尺寸處理。
  - 以共用 `MessageDialog(QDialog)` 呈現確認、警告、錯誤與更新提示，提供標題、說明、小型提示圖示與明確操作按鈕；使用純文字顯示檔名及錯誤內容。
  - 淺色採白底、藍色主按鈕；深色採紫底、螢光綠主按鈕。兩者共用 24px 留白及版面，具焦點與滑鼠狀態；未儲存確認的 Enter／Esc／關閉皆預設取消。訊息可選取及複製，較長內容在最高 240px 的文字區內捲動。

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
  - 工具圖示提供 `QIcon.State.On` 強調色版本，隨 QAction 選取狀態自動切換；淺色為藍色，深色為螢光綠。沿用原圖的透明度遮罩，保留 1px 筆畫與 DPI 幾何。工具列按鈕使用 8px 圓角，選取時沿用 hover 底色，不繪製選取外框。
  - 程式內自繪 toolbar/system tray icon。
  - `scripts/export_toolbar_icons.py` 同時匯出文件用的淺色圖示（`docs/images/toolbar/`）與深色圖示（`docs/images/toolbar/dark/`）；README 以 `<picture>` 的 `prefers-color-scheme` 選擇版本，並保留帶底色的 `<img>` 備用圖片，兼顧不支援主題切換的 Markdown viewer。
  - 圖示畫布維持 20 × 20px，一般圖案以 16 × 16px 範圍等比例繪製並置中，四邊各保留 2px；非正方形圖案保留原比例。細節較多的鍵盤與另存新檔圖案使用 20px 範圍。畫布外由 34px 按鈕提供各 7px（含邊框）間距；鉛筆圖示另校正其斜向外形造成的垂直偏移。
  - 工具列圖示依目標 DPI 直接繪製對應像素尺寸，支援 100%、125%、150%、175%、200%、250% 與 300%。筆畫寬度與基本幾何對齊實體像素，避免橫直線分散成半透明灰線；圓弧與斜線保留抗鋸齒，文字以輸出尺寸交由字型引擎繪製。
  - 工作列與系統匣相機圖示分別調整透明邊距，並提供 16–64px 多解析度 pixmap；macOS 選單列另使用接近正方形的相機配置填滿有限高度，讓各平台顯示槽位維持清楚且一致的視覺占比。

- `settings.py`
  - `CaptureMode`、`Tool`、`LineEndStyle`、`CaptureSettings`、`DrawingSettings`。

- `hotkeys.py`
  - 定義四種截圖方式及重複擷取動作的可設定組合鍵、格式驗證與 `QSettings` 持久化。
  - UI 只編輯暫存副本；Windows 透過 `RegisterHotKey` 探測衝突，確認成功後才替換目前註冊。

- `theme.py`
  - 管理跟隨系統、淺色與深色三種模式，透過 `QSettings` 持久化，並在系統配色變更時即時套用。
  - 深色採初號機風格：深紫底色、紫色面板、螢光綠選取與焦點、橘色提示。`DARK_COLORS` 共用於 palette、stylesheet、圖示遮罩與文件圖片；螢光綠底上的文字使用深色，維持選取狀態的對比。
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
5. 若有延遲，顯示右下角倒數 overlay，期間可按 <kbd>Esc</kbd> 取消；矩形區域與視窗／控制項選取會在倒數後凍結畫面，其他模式則在決定矩形後倒數。
6. 凍結的矩形區域與視窗／控制項直接從保存畫面裁切；其他模式在 overlay 隱藏後呼叫 `_grab_rect()` 擷取畫面。
7. 若啟用包含游標，best-effort 貼上凍結或即時擷取當下的真實游標。
8. `EditorWindow.add_shot()` 建立新頁籤並顯示於左上角。
9. `EditorWindow.copy_current()` 複製目前影像到剪貼簿。

<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Q</kbd> 預設會重複前一次成功的擷取，並可在快捷鍵設定面板自訂。矩形模式保存固定座標；視窗／控制項模式保存原生目標身分並在重複時重新取得目前邊界，目標已消失時不顯示錯誤也不建立頁籤。

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
