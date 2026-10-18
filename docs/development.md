# 開發指南

[繁體中文](development.md) | [English](development.en.md) · [返回 README](../README.md)

本文件提供開發環境、測試及文件維護指令。安裝正式版本與一般操作請閱讀 [README](../README.md)。

## 從原始碼執行

在專案根目錄使用 uv 管理環境：

```powershell
uv sync
uv run fshot
```

若要直接安裝 GitHub `main` 的最新開發成果：

```powershell
uv tool install --force "fshot @ git+https://github.com/codemee/fshot.git@main"
```

## 測試

```powershell
uv run pytest -q
uv run python -m compileall src tests
```

若 FShot 正在執行，Windows 可能因 executable 或 `__pycache__` 檔案被鎖而使環境更新或 `compileall` 失敗；先關閉 FShot 後再重跑。

## 維護文件圖示

```powershell
uv run python scripts/export_toolbar_icons.py
```

指令會從應用程式的繪圖程式同時匯出淺色與深色各 31 張圖示：

- `docs/images/toolbar/`：淺色圖示，同時作為備用圖片。
- `docs/images/toolbar/dark/`：深色圖示。

README 使用 `<picture>` 與 `prefers-color-scheme` 選擇版本；不支援切換的 Markdown viewer 顯示帶淺色底的 `<img>` 備用圖片，以保留對比。新增或修改圖示時，請一併檢查兩種配色、備用圖片及 README 引用。

## Windows 預覽效能量測

```powershell
uv run python scripts/benchmark_windows_preview.py
```

比較本機 DXGI 與 MSS 預覽擷取路徑；實際速度取決於系統與顯示驅動。設定與操作流程請見 [虛擬螢幕擷取指南](virtual-screen.md)。

## 技術文件

- [架構](architecture.md)：專案結構、主要模組與資料流。
- [跨平台說明](cross-platform.md)：平台差異、權限與手動驗收。
- [桌面應用程式打包](packaging.md)：本機打包與 GitHub Release 流程。
- [PRD](../PRD.md)：原始產品需求。
- [uv-tool-updater 規格草案](uv-tool-updater-spec.md)：更新套件設計與整合狀態。
- [macOS 虛擬螢幕實作紀錄](macos-virtual-screen.md)：分階段開發與驗收紀錄。
