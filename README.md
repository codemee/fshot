# FShot

[繁體中文](https://github.com/codemee/fshot/blob/main/README.md) | [English](https://github.com/codemee/fshot/blob/main/README.en.md)

FShot 是以 Python 實作的桌面截圖工具，主打全域快捷鍵、系統匣常駐、多頁籤編輯與快速複製/存檔。目前支援 Windows 與 macOS；平台權限與驗收方式請閱讀 [Cross-Platform Notes](https://github.com/codemee/fshot/blob/main/docs/cross-platform.md)。

## Current Status

- Windows: 主要功能已實作並經手動測試調整。
- macOS: 已實作 Quartz 全域快捷鍵、螢幕擷取、焦點視窗、視窗/控制項選取與游標擷取。
- Linux: 僅保留基本架構與部分通用能力，尚未作為主要目標平台。

## Quick Start

### 桌面應用程式

一般使用者建議從 [GitHub Releases](https://github.com/codemee/fshot/releases) 下載：

- Windows 10/11 x64：單一可攜式 `FShot-<版本>-windows-x64.exe`，不需要 Python。
- Apple Silicon Mac：`FShot-<版本>-macos-arm64.dmg`，開啟後將 `FShot.app` 拖入 Applications；不支援 Intel Mac。

這些個人專案版本沒有 Authenticode 或 Apple Developer ID 等可信任發行者簽章，也未經 Apple notarization。Windows 可能顯示 SmartScreen 警告；macOS 第一次開啟時需到「系統設定 → 隱私權與安全性」選擇「仍要打開」，並授予「螢幕錄製」與「輔助使用」權限。下載後可用同一個 Release 內的 `SHA256SUMS.txt` 核對檔案。完整步驟請閱讀 [Windows 安裝說明](docs/install-windows.md) 或 [macOS 安裝說明](docs/install-macos.md)。

### 從 PyPI 執行

FShot 可從 [PyPI](https://pypi.org/project/fshot/) 安裝。不需安裝即可使用 `uvx` 執行最新正式版本：

```powershell
uvx fshot
```

第一次執行會從 PyPI 下載套件並建立 uv 快取環境，後續會重用快取。臨時試用建議使用 `uvx`，若要長期使用則安裝為 uv tool。

使用 uv 從 PyPI 安裝：

```powershell
uv tool install fshot
fshot
```

安裝後可直接執行 `fshot`；更新至 PyPI 最新版本：

```powershell
uv tool upgrade fshot
```

使用 `uv tool install` 安裝時，FShot 啟動後會在背景每日檢查一次 PyPI。系統匣選單可手動「檢查更新…」或停用自動檢查；發現新版時可選擇更新並重新啟動、稍後處理或略過該版本。更新前若有尚未儲存的截圖，FShot 會先要求確認。打包版則檢查 GitHub Release 並開啟下載頁面，不會自行覆寫未簽章的 EXE 或 App。`uvx` 與原始碼開發環境只提供手動更新指引。

若要直接從 GitHub 測試 `main` 的最新開發成果：

```powershell
uv tool install --force "fshot @ git+https://github.com/codemee/fshot.git@main"
```

從原始碼啟動開發環境：

```powershell
uv sync
uv run fshot
```

程式啟動後會隱藏主視窗並留在系統匣。雙擊系統匣圖示可顯示編輯視窗，右鍵選單可退出。
工具列的主題按鈕可單擊循環切換「跟隨系統 → 淺色 → 深色」；預設跟隨作業系統配色，選擇會保留至下次啟動。太陽代表淺色、月亮代表深色，分隔排列的太陽與月亮代表跟隨系統。
語言按鈕可單擊循環切換「跟隨系統 → 繁體中文 → English」，並保留使用者選擇；圖示分別為 `文/A`、`中` 與 `En`。
工具列按鈕的提示文字會依目前語言顯示，具備快捷鍵的動作也會在提示中列出對應按鍵。
畫線與箭頭共用同一個畫線工具。畫線按鈕旁的下拉面板可分別將線條起點與終點設為無箭頭、箭頭或實心圓，兩端樣式可任意組合。
丈量像素工具以拖曳矩形的方式操作，會即時顯示起點到目前位置的橫向與縱向像素差；放開後保留讀值，重新丈量或切換工具時清除。丈量結果只顯示在編輯器上，不會寫入圖片或產生復原紀錄。
前方編輯工具區也可將目前圖片順時針旋轉 90°、水平鏡射或垂直鏡射；縮小按鈕會展開與線條樣式一致的面板，可輸入 1–99% 的比例實際縮小圖片尺寸。這些操作都會標記文件已修改，並可使用復原還原。
工具列的鍵盤圖示可設定四種截圖方式及「重複前一次擷取」的全域快捷鍵。每組可選 Ctrl、Shift、Alt 與 A–Z 字母；Shift 必須搭配 Ctrl 或 Alt。「使用預設」會將面板中的五組欄位恢復為預設值；按 OK 且系統註冊成功後才會套用並保留設定，Cancel 不會變更目前快捷鍵。

圖片也可透過拖放或剪貼簿加入編輯器：拖放圖片會以完整檔名建立頁籤、保留來源路徑並在修改後寫回原檔；直接貼上影像或從檔案管理器複製圖片後貼上，會以截圖時間格式建立新的未存檔頁籤。成功存檔後會記住檔案所在資料夾，其他尚未存檔的頁籤會從該資料夾開啟儲存交談窗。Windows/Linux 使用 `Ctrl+V`，macOS 使用 `Command+V`。

## Windows Shortcuts

- `Ctrl+Shift+Q`: 重複前一次的截圖方式（矩形區域與選取的視窗／控制項會沿用前次目標，可在設定面板自訂）
- `Ctrl+Shift+A`: 擷取目前焦點視窗
- `Ctrl+Shift+R`: 擷取矩形區域
- `Ctrl+Shift+F`: 擷取全螢幕
- `Ctrl+Shift+W`: 選取視窗或控制項後擷取

macOS 使用相同的 `Ctrl+Shift` 字母組合。獨立 App 請授權 `FShot.app`；透過 `uv`／`uvx` 執行時，系統設定中的授權對象通常是啟動指令所在的 App，例如「終端機」、iTerm2 或 IDE。授權後請完全結束並重新開啟 FShot 或該宿主 App。

編輯工具快捷鍵：

- `Alt+P`: 自由畫筆
- `Alt+L`: 線條
- `Alt+R`: 矩形
- `Alt+D`: 丈量像素
- `Alt+T`: 文字
- `Alt+M`: 馬賽克
- `Alt+C`: 順時針旋轉 90°
- `Alt+S`: 依比例縮小圖片
- `Alt+H`: 水平鏡射
- `Alt+V`: 垂直鏡射
- `Ctrl++` / `Ctrl+=`: 放大
- `Ctrl+-`: 縮小
- `Ctrl+0`: 重設縮放
- `F2`: 直接在目前標籤頁重新命名已存檔的檔案（macOS 使用 `Return`）

已存檔的標籤頁也可直接雙擊名稱進入重新命名；副檔名會保留不變。

## Project Docs

- [PRD](https://github.com/codemee/fshot/blob/main/PRD.md): 原始產品需求。
- [Architecture](https://github.com/codemee/fshot/blob/main/docs/architecture.md): 專案結構、主要模組與資料流。
- [Cross-Platform Notes](https://github.com/codemee/fshot/blob/main/docs/cross-platform.md): Windows/macOS/Linux 差異與 macOS 後續實作重點。

## Development

```shell
uv sync
uv run pytest -q
uv run python -m compileall src tests
```

若 FShot 正在執行，`compileall` 有時會因 `__pycache__` 或 executable 被鎖而失敗；先關閉或停止 `fshot.exe` 後再重跑。

## 桌面應用程式打包

FShot 使用 PyInstaller，而且必須在目標作業系統上建置；Windows runner 產生 x64 單一 EXE，Apple Silicon macOS runner 產生包含 `FShot.app` 與 Applications 捷徑的 arm64 DMG。專案不建立 Intel Mac 版本。

本機建置：

```powershell
uv sync
uv run python scripts/build_app.py
```

輸出位於 `dist/`。發布 GitHub Release 後，`Package desktop apps` 工作流程會自動在 Windows 與 macOS 原生 runner 執行測試和打包，再將 EXE、DMG 與 `SHA256SUMS.txt` 附加至該 Release。打包流程不使用 Authenticode、Apple Developer ID 或 notarization 憑證，因此發行檔仍會遇到前述 SmartScreen／Gatekeeper 提示。開發與手動補發細節請參閱 [Desktop Packaging](docs/packaging.md)。
