# uv-tool-updater 規格草案

- 狀態：Draft
- 日期：2026-08-16
- 文件整理日期：2026-10-08
- 工作名稱：`uv-tool-updater`
- Python import 名稱：`uv_tool_updater`
- 第一個整合專案：FShot

> 套件名稱只是工作名稱。正式建立 PyPI 專案前，仍須確認名稱可用性。

### 目前 FShot 整合狀態

本文保留原始套件規格草案與未來設計方向，不代表每個要求都已驗收。FShot 目前已在 `pyproject.toml` 採用 `uv-tool-updater>=0.1.9,<0.2`；實際整合以 [app.py](../src/fshot/app.py) 與 [updates.py](../src/fshot/updates.py) 為準，架構請見 [architecture.md](architecture.md)。文內套件名稱確認、首次發布與整合階段保留為原始規劃紀錄。

- `uv tool install` 安裝：背景查詢 PyPI，使用者同意並處理未儲存截圖後，啟動外部 helper，等待 FShot 正常結束，再更新及重新啟動。
- 獨立 EXE／App：由 FShot 查詢 GitHub Release 並開啟下載頁，不自動覆寫應用程式；這不是核心套件新增的安裝 backend。
- `uvx`、原始碼 checkout 與一般虛擬環境：提供手動更新指引。
- FShot 以 Qt thread pool 執行同步檢查，以 `QSettings` 保存自動檢查開關、檢查時間與略過版本；重新啟動後消費更新結果。以下驗收清單保留為規格要求，未因本次文件整理勾選。

## 1. 摘要

`uv-tool-updater` 是提供給 Python CLI、桌面程式與系統匣程式使用的更新協調套件。目標應用程式必須由 `uv tool install` 安裝；套件負責檢查新版本、判斷目前安裝方式、安排應用程式結束後的更新、重新啟動應用程式，以及回報更新結果。

套件不直接下載或覆寫 wheel，也不直接修改 uv 管理的工具環境。實際安裝一律委派給：

```console
uv tool upgrade <package-name>
```

這個設計讓 uv 繼續負責解析版本、下載套件、驗證套件、處理依賴與替換工具環境；`uv-tool-updater` 只負責應用程式生命週期與跨平台程序協調。

## 2. 目標

第一版必須達成：

- 支援由 `uv tool install` 安裝的 Python 工具。
- 支援 Windows、macOS 與 Linux。
- 取得目前已安裝版本。
- 從 PyPI 或可替換的 metadata provider 取得最新版本。
- 使用 PEP 440 規則比較版本。
- 能辨識目前程序是否位於 uv tool 管理的環境。
- 能在目標應用程式完全結束後執行 `uv tool upgrade`。
- 更新完成後能重新啟動原命令。
- 更新失敗時能保留錯誤資訊，並依設定重新啟動原版本。
- 不依賴任何特定 GUI framework。
- 提供讓 Qt、Tkinter、CLI 或其他應用程式自行整合的 API 與 hook。
- 絕大多數測試不需要發布至正式 PyPI。

## 3. 非目標

第一版不處理：

- 不實作背景常駐 daemon 或作業系統服務。
- 不直接支援 pip、pipx、Homebrew、Scoop 或獨立安裝包。
- 不自行修改 virtual environment 或 `site-packages`。
- 不自行下載、解壓或執行 PyPI wheel。
- 不提供強制、無提示更新。
- 不替應用程式決定如何處理未儲存資料。
- 不提供完整 GUI；UI 應由使用套件的應用程式控制。
- 不保證能更新以精確版本限制安裝的工具，例如 `fshot==1.2.3`。
- 不以解析 uv 的人類可讀輸出作為主要狀態判斷方式。

## 4. 核心設計決策

| 項目 | 決策 |
| --- | --- |
| 真正的更新引擎 | `uv tool upgrade` |
| 目前版本來源 | `importlib.metadata.version()` |
| 版本比較 | `packaging.version.Version` |
| 預設版本來源 | PyPI JSON API |
| 自訂版本來源 | `ReleaseProvider` protocol |
| 更新時機 | 目標應用程式完全結束後 |
| 跨平台更新程序 | 位於目標 uv 環境之外的暫存 helper |
| UI | 由使用端實作 |
| 網路套件 | MVP 使用標準函式庫，不依賴 `requests` |
| 排程與設定儲存 | protocol 加上可選預設實作 |
| 正式安裝修改 | 只能透過 uv，不直接寫入工具環境 |

## 5. 支援範圍

建議初始支援：

- Python 3.10–3.14。
- Windows 10/11。
- 目前仍受支援的 macOS 版本。
- 主流 Linux desktop/server distribution。
- 由 uv standalone、Scoop、Homebrew 或其他正式方式安裝的 uv，只要 `uv` 可被找到並正常執行。

套件本身的 runtime dependency 應盡量維持只有：

```toml
dependencies = [
    "packaging>=24",
]
```

若未來提供 Qt adapter，應放在 optional dependency：

```toml
[project.optional-dependencies]
qt = ["pyside6>=6.8"]
```

核心套件不可強制依賴 PySide6。

## 6. 名詞

- **Host application**：整合本套件的應用程式，例如 FShot。
- **Tool package**：透過 `uv tool install` 安裝的 Python distribution，例如 `fshot`。
- **Command**：tool package 暴露的 console entry point，例如 `fshot`。
- **Provider**：提供最新版本 metadata 的來源。
- **Backend**：負責呼叫特定安裝器完成更新；MVP 只有 uv backend。
- **Helper**：在 host application 結束後仍能繼續執行的外部程序或腳本。
- **Update session**：一次從準備、等待退出、升級到重新啟動的完整更新工作。

## 7. 責任邊界

### 7.1 `uv-tool-updater` 負責

- 讀取目前套件版本。
- 查詢最新版本。
- 版本比較與 prerelease policy。
- 尋找 uv executable。
- 判斷目前是否可能是 uv tool 安裝。
- 建立安全的更新計畫。
- 產生及啟動外部 helper。
- 等待 host PID 結束。
- 呼叫 `uv tool upgrade`。
- 保存 exit code、log 與結果資料。
- 重新啟動指定 command。
- 提供可測試的 protocol 與替代實作。

### 7.2 Host application 負責

- 決定何時檢查更新。
- 顯示更新提示與 release notes。
- 處理翻譯與 UI。
- 確認是否有未儲存資料。
- 決定允許、取消或延後更新。
- 在 helper 已成功啟動後安全結束自己。
- 重新啟動後顯示更新結果。
- 決定是否允許 prerelease。
- 決定是否略過特定版本。

## 8. 套件結構

建議 repository 結構：

```text
uv-tool-updater/
├── src/
│   └── uv_tool_updater/
│       ├── __init__.py
│       ├── models.py
│       ├── checker.py
│       ├── providers.py
│       ├── installation.py
│       ├── backend.py
│       ├── session.py
│       ├── launcher.py
│       ├── result.py
│       ├── state.py
│       ├── errors.py
│       └── qt.py              # optional，MVP 可延後
├── tests/
│   ├── fixtures/
│   ├── test_checker.py
│   ├── test_providers.py
│   ├── test_installation.py
│   ├── test_backend.py
│   ├── test_session.py
│   ├── test_launcher.py
│   └── integration/
├── docs/
├── pyproject.toml
├── README.md
├── LICENSE
└── uv.lock
```

## 9. 資料模型

以下 API 是設計方向，不要求第一版逐字一致。

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from packaging.version import Version


@dataclass(frozen=True)
class InstalledTool:
    package_name: str
    command_name: str
    current_version: Version
    executable_path: Path
    python_prefix: Path
    uv_path: Path | None
    uv_tool_dir: Path | None
    managed_by_uv: bool


@dataclass(frozen=True)
class ReleaseInfo:
    package_name: str
    version: Version
    release_url: str | None = None
    published_at: datetime | None = None
    yanked: bool = False
    prerelease: bool = False


class UpdateStatus(str, Enum):
    UPDATE_AVAILABLE = "update_available"
    UP_TO_DATE = "up_to_date"
    UNSUPPORTED_INSTALLATION = "unsupported_installation"
    CHECK_FAILED = "check_failed"


@dataclass(frozen=True)
class UpdateCheck:
    status: UpdateStatus
    installed: InstalledTool
    release: ReleaseInfo | None = None
    message: str | None = None


class InstallStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NO_CHANGE = "no_change"
    APP_EXIT_TIMEOUT = "app_exit_timeout"
    RESTART_FAILED = "restart_failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class UpdateResult:
    status: InstallStatus
    package_name: str
    previous_version: str
    requested_version: str | None
    actual_version: str | None
    uv_exit_code: int | None
    started_at: datetime
    finished_at: datetime
    log_path: Path | None
    error: str | None = None
```

## 10. Provider API

版本檢查必須與安裝 backend 解耦。

```python
from typing import Protocol


class ReleaseProvider(Protocol):
    def latest_release(
        self,
        package_name: str,
        *,
        allow_prereleases: bool = False,
        timeout: float = 5.0,
    ) -> ReleaseInfo:
        ...
```

### 10.1 `PyPIJsonProvider`

預設查詢：

```text
GET https://pypi.org/pypi/<package-name>/json
Accept: application/json
User-Agent: uv-tool-updater/<version>
```

要求：

- HTTPS only。
- 預設 timeout 5 秒，呼叫端可調整。
- 驗證回傳的 package name 與 version。
- 不把 `downloads` 或其他 deprecated 欄位當成必要資料。
- 不選擇 yanked release。
- 預設不選擇 prerelease。
- HTTP、JSON、schema 或版本解析失敗時回傳型別化錯誤。
- 不在核心層重試超過一次；較長的 retry policy 交給 host application。

### 10.2 自訂 index

`uv tool upgrade` 會沿用 uv 安裝時保存的設定，但 updater 的「版本檢查」不一定知道原始 index。因此：

- MVP 預設只假設公開 PyPI。
- 使用自訂 index 的 host 必須傳入相符的 provider。
- 不依賴 uv 未公開的 receipt 格式推測 metadata URL。
- provider URL 必須可設定，方便企業 index、本機測試與 TestPyPI。

### 10.3 `StaticProvider`

提供測試與離線應用：

```python
provider = StaticProvider(
    ReleaseInfo(package_name="demo-tool", version=Version("1.1.0"))
)
```

## 11. 安裝偵測

偵測順序：

1. 以 `importlib.metadata.version(package_name)` 讀取目前版本。
2. 以明確傳入的 `uv_path` 為最高優先。
3. 若環境變數 `UV` 指向可執行檔，驗證後使用。
4. 否則使用 `shutil.which("uv")`。
5. 執行 `uv tool dir` 取得 uv tool root。
6. 比較目前 `sys.prefix` 是否位於 tool root 之下。
7. 以 `shutil.which(command_name)` 取得重新啟動 command。

要求：

- 所有路徑比較先正規化與解析符號連結。
- Windows 路徑比較不區分大小寫。
- 偵測不確定時採保守結果 `managed_by_uv=False`。
- 偵測失敗不應讓 host application 無法啟動。
- `uv run`、editable source checkout 與一般 virtualenv 預設視為不支援自動安裝。
- 不支援時仍可檢查版本，但只能提示手動更新方式。

## 12. 公開 Facade API

建議提供一個簡單入口：

```python
from uv_tool_updater import Updater


updater = Updater(
    package_name="fshot",
    command_name="fshot",
)

check = updater.check()
```

應用程式確認可以退出後：

```python
session = updater.prepare_update(
    release=check.release,
    restart_args=[],
    restart_on_failure=True,
)

session.start_helper(host_pid=os.getpid())
application.quit()
```

重要限制：

- `prepare_update()` 只建立不可變的更新計畫與暫存檔。
- `start_helper()` 成功後才允許 host application 結束。
- 套件不應直接呼叫 GUI framework 的 quit API。
- Host application 若無法確認安全退出，就不應呼叫 `start_helper()`。

## 13. 更新流程

### 13.1 自動檢查

```text
Host 啟動
  → 延後數秒啟動背景檢查
  → 讀取目前版本
  → Provider 取得最新版本
  → 使用 PEP 440 比較
  → 回傳 UpdateCheck
  → Host 決定是否通知使用者
```

核心 `check()` 可以是同步 API，但文件必須明確要求 GUI 應用程式在 worker thread 中呼叫，避免阻塞 UI。未來可另外提供 async API，但 MVP 不必同時維護兩套網路實作。

### 13.2 使用者確認更新

```text
使用者按「更新並重新啟動」
  → Host 檢查未儲存資料
  → Host 停止新的長時間工作
  → Updater 建立 session
  → Updater 啟動外部 helper
  → Host 註銷快捷鍵／隱藏 tray／正常退出
```

### 13.3 Helper 流程

```text
Helper 啟動
  → 驗證 session 資料
  → 等待 host PID 結束
  → timeout 則停止，不強制終止 host
  → 執行 uv tool upgrade <package>
  → 保存 stdout、stderr、exit code
  → 依設定重新啟動 command
  → 寫入結果 JSON
  → best-effort 清理 helper 與暫存資料
```

### 13.4 重新啟動後

```text
新版 Host 啟動
  → 讀取 pending result
  → 再次以 importlib.metadata 取得實際版本
  → 比較 previous／requested／actual version
  → 顯示成功、無變更或失敗
  → 標記 result 已消費
```

不應只因 `uv` exit code 為 0 就宣稱版本已更新；重新啟動後必須讀取實際 metadata 確認。

## 14. Helper 實作

### 14.1 共通要求

- Helper 必須在 uv tool environment 之外執行。
- 不可使用該 tool environment 的 Python interpreter 執行 helper。
- 使用絕對 `uv` 路徑。
- 使用已解析的 command path 重新啟動。
- 不以未驗證字串拼接 shell command。
- 等待 host，而不是強制結束 host。
- 預設等待 timeout 建議 10 分鐘。
- timeout 後不得執行更新。
- 捕捉 stdout/stderr 至 UTF-8 log。
- Helper 與 session 檔案應使用隨機名稱。

### 14.2 Windows

建議使用系統內建 Windows PowerShell 啟動暫存 `.ps1`：

- `Wait-Process -Id <pid>` 等待 host 結束。
- 以 call operator 和獨立 argument array 呼叫 uv。
- 使用 `Start-Process` 重新啟動 command。
- 啟動 helper 時不顯示多餘 console window。
- 正確處理包含空白、Unicode 與單引號的路徑。

不可在 FShot 或其他 host 尚未結束時執行更新；Windows 可能鎖住 command executable 或 environment 中的檔案。

### 14.3 macOS/Linux

建議使用 `/bin/sh` 暫存腳本：

- 輪詢 host PID 是否仍存在，並設定 timeout。
- 正確引用所有路徑與 argument。
- 更新後以背景方式重新啟動 command。
- 不假設 bash、zsh 或特定 terminal 存在。

如果使用 PID 輪詢，需限制等待時間以降低 PID 重用造成的風險。未來可評估更可靠的 process handle 或平台 API。

## 15. 更新命令

MVP 固定使用結構化參數：

```python
[
    str(uv_path),
    "tool",
    "upgrade",
    package_name,
]
```

要求：

- 不使用 `shell=True`。
- 不自動加入 `--reinstall`。
- 不用 `uv tool install --force` 取代 upgrade。
- 尊重使用者原始版本限制與 index 設定。
- 若版本限制使更新無法進行，結果應為 `NO_CHANGE` 或明確錯誤，而不是擅自解除限制。
- 允許進階使用者透過受控 option 增加 uv 的安全參數，但不可接受任意 command string。

## 16. State 與結果儲存

提供 protocol：

```python
class UpdateStateStore(Protocol):
    def load(self) -> UpdateState: ...
    def save(self, state: UpdateState) -> None: ...
```

建議 state 包含：

```text
last_checked_at
skipped_version
pending_session_id
last_result_id
```

提供簡單的 JSON 預設實作，但允許 host 使用 QSettings、registry、database 或其他設定系統。

Result JSON 建議 schema：

```json
{
  "schema_version": 1,
  "session_id": "uuid",
  "package_name": "fshot",
  "previous_version": "0.0.10",
  "requested_version": "0.0.11",
  "uv_exit_code": 0,
  "status": "succeeded",
  "started_at": "2026-08-16T12:00:00Z",
  "finished_at": "2026-08-16T12:00:09Z",
  "log_path": "..."
}
```

要求：

- 寫入採 atomic replace。
- Unix 權限預設限制為目前使用者可讀寫。
- 不保存 token、Authorization header 或完整環境變數。
- log 必須對可能的 credentials 做基本遮蔽。
- 舊版讀到未知 schema 時應忽略並保留診斷訊息，不可崩潰。

## 17. 錯誤模型

提供具體 exception hierarchy：

```text
UpdaterError
├── MetadataError
│   ├── PackageNotInstalledError
│   └── InvalidVersionError
├── ProviderError
│   ├── NetworkError
│   ├── InvalidResponseError
│   └── ReleaseNotFoundError
├── InstallationError
│   ├── UvNotFoundError
│   ├── UnsupportedInstallationError
│   └── ToolDirectoryError
├── SessionError
│   ├── InvalidSessionError
│   └── HelperLaunchError
└── RestartError
```

所有對外錯誤必須：

- 提供適合 logging 的技術訊息。
- 提供穩定 error code，讓 UI 能翻譯。
- 保留原始 exception 作為 cause。
- 避免把完整 command environment 或秘密資訊放入訊息。

## 18. 安全需求

### 18.1 信任邊界

- Provider metadata 只能用來比較版本與顯示 URL。
- 不執行 provider 回傳的 command、script 或任意 URL 內容。
- 真正套件來源由 uv 安裝設定決定。
- 預設 PyPI provider 必須使用 HTTPS。

### 18.2 Command injection

- Python 呼叫 uv 時使用 argument list。
- Package name 必須符合 Python distribution name 正規格式。
- Command path 必須是已解析的本機檔案。
- Restart arguments 必須以陣列保存與傳遞。
- 產生 PowerShell 或 shell helper 時必須使用平台專用 quoting 函式並有 adversarial tests。

### 18.3 檔案安全

- 所有刪除只限本次 session 建立的明確檔案。
- 不遞迴刪除 uv tool directory。
- 不直接修改 `site-packages`。
- 不跟隨 result/helper cleanup 中的非預期 symlink。
- Temp file 使用安全 API 建立，不自行生成可預測檔名。

### 18.4 程序安全

- 永不強制終止 host application。
- Host 未在 timeout 內退出時取消更新。
- Helper 啟動失敗時 host 不應退出。
- 更新失敗後預設嘗試重新啟動原 command。
- 避免同一個 package 同時存在兩個 update session；使用 session lock。

## 19. 隱私需求

- 不收集 telemetry。
- 不上傳目前版本以外的使用者資料。
- User-Agent 可包含 updater 版本，但不包含 machine ID、username 或路徑。
- Log 僅保存在本機。
- Host application 應能停用自動檢查。

## 20. Host 整合建議

### 20.1 檢查頻率

推薦預設：

- 啟動後延遲 5 秒檢查。
- 每 24 小時最多自動檢查一次。
- 手動「檢查更新」不受 24 小時限制。
- 網路錯誤不顯示阻斷式對話框。
- 使用者可關閉自動檢查。

這些是 host policy；核心套件只提供 state 與判斷 helper，不應自行建立 timer。

### 20.2 更新 UI

推薦選項：

```text
有新版本 1.2.0 可用
[更新並重新啟動] [略過此版本] [稍後]
```

不支援的安裝方式：

```text
目前版本不是由 uv tool 管理，請手動更新：
uv tool install --force <package>
```

精確安裝限制阻止更新時，不應建議自動解除限制；只顯示原始限制與可選的手動指令。

### 20.3 未儲存資料

核心套件只提供 hook。Host 必須在啟動 helper 前：

- 儲存文件；或
- 取得使用者明確同意放棄；或
- 取消更新。

## 21. FShot 整合範例

FShot 是第一個 consumer，但不可把 FShot 特有邏輯放入核心套件。

FShot 整合負責（目前已建立對應流程，平台行為仍需按下述策略驗收）：

- 在系統匣加入「檢查更新」。
- 使用既有 i18n 顯示中英文訊息。
- 使用 `QSettings` 保存檢查時間與略過版本。
- 使用 worker thread 執行 `Updater.check()`。
- 檢查 dirty documents。
- 註銷全域快捷鍵。
- 隱藏 tray icon。
- 呼叫 `session.start_helper()` 後正常退出。
- 重新啟動後顯示 result。

概念程式碼：

```python
def update_and_restart(self, check: UpdateCheck) -> None:
    if not self.window.confirm_safe_to_quit():
        return

    session = self.updater.prepare_update(
        release=check.release,
        restart_args=[],
        restart_on_failure=True,
    )
    session.start_helper(host_pid=os.getpid())
    self.quit_for_update()
```

FShot 發布第一個包含 updater 的版本後，既有使用者仍需手動升級一次；後續版本才可由新機制更新。

## 22. 測試策略

### 22.1 單元測試

必須涵蓋：

- installed metadata 正常、缺失與無效版本。
- stable、prerelease、post release 與 local version 比較。
- 相同版本、降版與 yanked release。
- PyPI timeout、404、5xx、無效 JSON 與缺少欄位。
- uv path 顯式設定、環境變數與 PATH fallback。
- uv tool environment、uvx cache、一般 venv 與 editable checkout 偵測。
- Windows 大小寫與 Unicode 路徑。
- package name、command path 與 restart arguments 驗證。
- Helper command quoting。
- Session lock 與重複 session。
- Result atomic write、schema version 與消費流程。
- uv success、failure、no change 與 restart failure。

所有網路與 subprocess 在單元測試中必須 mock。

### 22.2 本機整合測試

不使用正式 PyPI。測試建立一個沒有外部依賴的 fixture tool，並建置兩個版本：

```text
fixture-tool 1.0.0
fixture-tool 1.1.0
```

使用臨時目錄：

```text
UV_TOOL_DIR=<temp>/tools
UV_TOOL_BIN_DIR=<temp>/bin
```

測試流程：

1. 本機 flat index 起初只放 `1.0.0`。
2. 使用 uv tool 安裝未 pin 版本的 fixture tool。
3. 啟動會持續執行的 fixture command。
4. 將 `1.1.0` 加入 flat index。
5. 啟動 helper。
6. 正常結束 fixture command。
7. 驗證 helper 等待、升級及重新啟動。
8. 驗證新程序回報 `1.1.0`。
9. 驗證真正的使用者 uv tool directory 完全未被修改。

### 22.3 平台整合測試

CI matrix 至少包含：

- Windows：執行檔鎖定、PowerShell quoting、隱藏視窗、重新啟動。
- macOS：`/bin/sh` helper、symlink command、重新啟動。
- Linux：`/bin/sh` helper、PATH 與 headless command。

### 22.4 TestPyPI

TestPyPI 是可選的手動或 release-candidate 測試，用於驗證真實 HTTP index 與 upload/install 流程。它不是一般測試的必要條件。

### 22.5 正式 PyPI

只有最終 smoke test 需要更高的正式版本，用來驗證：

- PyPI metadata 傳播。
- 正式 index 解析。
- 真實 end-user `uv tool upgrade`。
- 正式 wheel/sdist 安裝。

不可為每次開發測試發布正式版本，因為 PyPI release 與檔名不可覆寫。

## 23. CI 要求

每個 pull request：

- 格式與 lint。
- type check。
- 單元測試。
- Windows、macOS、Linux integration tests。
- Python 最低與最高支援版本。
- 建置 wheel 與 sdist。
- 驗證 wheel metadata。
- 從 wheel 安裝後執行 smoke test。

Release workflow：

1. tag 與 package version 必須一致。
2. 建置 wheel 與 sdist。
3. 執行完整測試。
4. 發布 GitHub Release。
5. 使用 PyPI Trusted Publishing 發布。
6. 透過 PyPI version-specific API 驗證檔案。

## 24. 文件要求

新專案至少應提供：

- README：用途、限制、安裝、最小範例。
- Architecture：provider/backend/helper/session 邊界。
- Security：信任模型、command injection 與 temp file 策略。
- Testing：如何使用 local flat index 執行完整更新測試。
- Integration guide：CLI 與 GUI application 範例。
- FShot example：作為真實 consumer，但不放入核心套件。
- Changelog：記錄公開 API 與平台行為改變。

## 25. 發布與相容性策略

建議初始版本：

```text
0.1.0  核心偵測、PyPI provider、uv backend、helper、測試工具
0.2.0  穩定 state/result API 與 FShot 整合回饋
0.3.0  可選 Qt adapter
1.0.0  公開 API 與 result schema 穩定
```

在 `1.0.0` 前仍應：

- 對公開 dataclass、enum 與 protocol 變更提供 migration note。
- Result JSON 一開始就包含 `schema_version`。
- 避免暴露 uv 私有檔案格式。
- 不承諾支援尚未實作的 installer backend。

## 26. MVP 驗收標準

MVP 完成必須同時符合：

- [ ] 能正確取得自己的 installed package version。
- [ ] 能從 PyPI JSON API 找到較新的 stable release。
- [ ] 網路失敗不影響 host application 啟動。
- [ ] 能辨識一般 uv tool 安裝。
- [ ] 能拒絕在一般 venv 或 editable checkout 自動更新。
- [ ] Windows host 執行期間不會提前修改 tool environment。
- [ ] Helper 會等待 host 正常退出。
- [ ] Host 不退出時 helper timeout 且不強制終止 host。
- [ ] `uv tool upgrade` 成功後 command 會重新啟動。
- [ ] 更新失敗後可重新啟動原 command 並保留 log。
- [ ] 新程序能讀取並消費 update result。
- [ ] 能以本機 flat index 完成 1.0.0 → 1.1.0 end-to-end test。
- [ ] 測試不修改開發者真正的 `UV_TOOL_DIR` 或 `UV_TOOL_BIN_DIR`。
- [ ] 路徑包含空白、Unicode 與 shell metacharacter 時仍安全。
- [ ] 核心套件不依賴 GUI framework。
- [ ] wheel 與 sdist 均可安裝。

## 27. 後續功能

MVP 之後再評估：

- asyncio-native provider。
- Qt adapter。
- GitHub Releases provider。
- PEP 691 Simple JSON provider。
- pipx backend。
- Homebrew/Scoop backend。
- 更新下載進度 UI。
- Release notes 與 changelog provider。
- 代理伺服器與企業 CA 的明確設定 API。
- TUF metadata；僅在改為自行管理 standalone bundle 時考慮。
- 多 command tool package 的重新啟動策略。

## 28. 開放問題

建立新專案時需要決定：

1. 正式 PyPI 名稱是否為 `uv-tool-updater`。
2. 最低 Python 是否選擇 3.10 或 3.11。
3. License 使用 MIT 或 Apache-2.0。
4. MVP 是否直接包含 Qt adapter，或等 FShot 整合後再抽象。
5. 預設 result/state 目錄由 host 明確傳入，或加入 `platformdirs` dependency。
6. Windows helper 使用 Windows PowerShell 5.1 或優先尋找 PowerShell 7。
7. 是否在 MVP 支援 prerelease channel。
8. 是否提供開發用 CLI，例如 `uv-tool-updater diagnose <package>`。

建議初始答案：

- Python `>=3.10`。
- MIT license。
- MVP 不包含 Qt adapter。
- Host 明確傳入 state directory，避免額外依賴。
- Windows 以內建 Windows PowerShell 為 baseline，若找到 PowerShell 7 可使用但不可依賴。
- MVP 支援 `allow_prereleases` 參數，但預設關閉。
- 開發診斷 CLI 延後到 `0.2.0`。

## 29. 建議實作順序

### Phase A：純 Python 核心

1. 建立 repository、`pyproject.toml`、license 與 CI。
2. 實作資料模型與 exception hierarchy。
3. 實作 installed version 讀取與 PEP 440 比較。
4. 實作 `ReleaseProvider`、`PyPIJsonProvider` 與 `StaticProvider`。
5. 完成不含 subprocess 的單元測試。

### Phase B：uv 偵測與 backend

1. 尋找 uv executable。
2. 執行 `uv tool dir` 並判斷安裝環境。
3. 產生結構化 `uv tool upgrade` command。
4. 實作 unsupported installation 與 pinned version 的錯誤呈現。
5. 使用 mock subprocess 完成跨平台單元測試。

### Phase C：外部 helper

1. 定義 session 與 result JSON schema。
2. 實作 Windows PowerShell helper。
3. 實作 macOS/Linux `/bin/sh` helper。
4. 實作 PID wait、timeout、log、restart 與 cleanup。
5. 加入惡意字元、Unicode、空白路徑與重複 session 測試。

### Phase D：本機端到端測試

1. 建立無依賴 fixture tool。
2. 建置兩個 fixture 版本。
3. 使用臨時 uv tool/bin 目錄與 local flat index。
4. 驗證執行中等待、更新、重新啟動與結果消費。
5. 在 Windows、macOS、Linux CI 執行。

### Phase E：FShot 整合

1. 先以相鄰 repository 的 editable dependency 整合。
2. 加入系統匣入口與背景檢查。
3. 串接 dirty document、hotkey 與 tray shutdown 流程。
4. 驗證 Windows 執行檔鎖定情境。
5. 將 FShot 特有邏輯留在 FShot repository。

### Phase F：首次發布

1. 發布 updater `0.1.0` 到 PyPI。
2. 在 FShot 以正式版本範圍加入 updater dependency。
3. 發布第一個包含 updater 的 FShot 版本。
4. 從舊版 FShot 手動升級一次以取得 updater。
5. 下一個 FShot 版本進行正式 PyPI end-to-end smoke test。

## 30. 參考資料

- uv Tools：https://docs.astral.sh/uv/concepts/tools/
- uv Package Indexes：https://docs.astral.sh/uv/concepts/indexes/
- uv Storage：https://docs.astral.sh/uv/reference/storage/
- uv CLI Reference：https://docs.astral.sh/uv/reference/cli/
- PyPI JSON API：https://docs.pypi.org/api/json/
- TestPyPI：https://packaging.python.org/en/latest/guides/using-testpypi/
- Python `importlib.metadata`：https://docs.python.org/3/library/importlib.metadata.html
- Packaging version：https://packaging.pypa.io/en/stable/version.html
