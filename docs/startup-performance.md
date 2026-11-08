# 啟動效能與量測

繁體中文 | [English](startup-performance.en.md)

本輪參考 rePDF 的 STARTUP_PERFORMANCE.md，將 Windows 正式封裝改為 PyInstaller onedir 資料夾包，以 ZIP 散布。使用者完整解壓一次，之後直接載入資料夾內的 Python／Qt 依賴。macOS 延用原有 App／DMG。

## 建置兩種比較產物

```powershell
uv sync
uv run python scripts/build_app.py --windows-layout onefile
uv run python scripts/build_app.py
```

- 比較基準：`dist/FShot-<version>-windows-x64-onefile.exe`。
- 資料夾執行檔：`dist/FShot/FShot.exe`。
- 正式散布檔：`dist/FShot-<version>-windows-x64.zip`，包含完整的 `FShot/`。

建置腳本會從其他工作目錄執行 `--version` 與 `--self-test`。GUI 自我檢查會建立 Qt 編輯器與測試圖片、檢查圖示及尺寸顯示，使用暫存設定，不註冊快捷鍵，也不擷取螢幕。

## 交錯量測封裝成品

先關閉正在執行的 FShot，避免全域快捷鍵衝突。使用同一份程式碼、相同 Python 與依賴建立兩種產物：

```powershell
uv run python scripts/benchmark_startup.py --exe .\dist\FShot-0.1.12-windows-x64-onefile.exe --exe .\dist\FShot\FShot.exe --runs 5
```

版本號須配合實際產物。腳本在每輪交錯交換兩種產物的順序，使用其他工作目錄啟動，記錄各次 JSONL 與 `build/startup-benchmark/results.json`，並輸出 event_loop_ready 的中位數。`--startup-probe` 執行正常初始化及快捷鍵註冊，進入事件迴圈後自動關閉並解除快捷鍵。逾時時只清理該次啟動的程序樹。

每次程序共用外部計時器的起點，量測包含封裝啟動器、解壓與 Python 初始化：

| 節點 | 定義 |
| --- | --- |
| python_entry | 輕量 Python 入口執行；包含 bootloader／解壓與入口前 Python 載入成本，不能單獨視為純解壓時間 |
| imports_ready | GUI／截圖等啟動模組載入完成 |
| application_created | QApplication 建立完成 |
| controller_ready | 編輯器、服務與全域快捷鍵初始化完成 |
| tray_ready | 已呼叫系統匣圖示 show；屬程式回報節點，不代表 Explorer 已完成畫面繪製 |
| event_loop_ready | 事件迴圈開始處理 callback，供自動比較 |
| editor_visible | 正常操作中，編輯器顯示與前景切換完成 |
| first_document_ready | 首份圖片標籤與工具狀態建立完成 |
| first_capture_ready | 首次截圖已加入編輯器並顯示 |

要量測首次截圖／編輯器，設定 `FSHOT_STARTUP_TRACE` 為可寫入的絕對路徑，再正常執行程式並操作；不加 `--startup-probe`。未設定追蹤環境變數時不產生紀錄。若要包含解壓前的外部時間，啟動器另須設定 `FSHOT_STARTUP_STARTED_NS`，其值來自同機的 `time.perf_counter_ns()`，比較腳本已處理。

結果受防毒掃描、檔案快取與系統負載影響。首次樣本不等同重新開機後冷啟動；應保留每次資料、同機交錯測量多次，不能套用 rePDF 的秒數。

## 更新與後續階段

更新時關閉 FShot 並替換完整資料夾，保留 EXE、`_internal` 與授權檔。若搬移位置，重新設定捷徑與開機自動執行。資料夾包仍需要 Python／Qt 初始化時間。

Windows 已加入單一執行個體：再次執行時，在載入 Qt 前透過目前登入工作階段的原生命名事件通知既有程序顯示編輯器，第二個程序隨即結束；原程序尚在初始化時也會保留請求。程序結束時系統自動釋放資源，不使用持久鎖檔。`--version` 與 `--self-test` 仍獨立執行；量測 `--startup-probe` 前須先退出既有程式。此功能尚未套用至 macOS／Linux，也未延後建立編輯器。

後續可依數據評估延後建立編輯器或虛擬螢幕功能，並分開量測首次啟動、重複啟動與首次功能使用。以下數據來自加入單一執行個體之前。

## 本機封裝量測結果（2026-11-08）

同一份 0.1.12 開發中程式碼、Python 3.14.6 與鎖定依賴，在同一台 Windows 電腦交錯啟動各 5 次；資料夾版使用從正式 ZIP 解壓到含空白路徑的 EXE。指標為外部啟動至 event_loop_ready，並非 Explorer 圖示繪製完成或首次截圖時間。

| 輪次 | 單檔版（秒） | 資料夾版（秒） |
| --- | ---: | ---: |
| 1 | 6.947 | 2.378 |
| 2 | 5.478 | 1.066 |
| 3 | 7.082 | 1.679 |
| 4 | 8.103 | 2.375 |
| 5 | 7.352 | 1.637 |
| 中位數 | 7.082 | 1.679 |

這組樣本的中位時間約縮短 76%。python_entry 中位數由 4.342 秒降至 0.436 秒，表示入口前成本明顯下降；此節點同時包含解壓、bootloader、Python 與早期載入，不應全數歸因於純解壓。此結果不是其他機器的效能保證，也不是重新開機後冷啟動結果。原始 JSONL 與結果保留於本機 `build/startup-benchmark/`。
