# 桌面應用程式打包

[繁體中文](packaging.md) | [English](packaging.en.md) · [開發指南](development.md)

本文件供開發與發布版本使用。下載正式安裝檔請見 [README](../README.md)；安裝與權限設定請見 [Windows](install-windows.md)／[macOS](install-macos.md) 安裝說明。

## 建置方式

FShot 使用 PyInstaller，必須在目標作業系統上建置。Windows runner 產生 x64 單一 EXE；Apple Silicon macOS runner 產生 arm64 DMG，內含 `FShot.app` 與 Applications 捷徑。不建立 Intel Mac 版本。

安裝後的 `fshot` 指令使用 console entry point（`project.scripts`），沿用啟動它的終端機；桌面打包版使用 PyInstaller 的 windowed launcher。

## 本機打包

在專案根目錄執行：

```powershell
uv sync
uv run python scripts/build_app.py
```

輸出檔案：

- Windows：`dist/FShot-<version>-windows-x64.exe`。
- macOS：`dist/FShot-<version>-macos-arm64.dmg`。

產生的圖示與 Windows 版本資源位於 `build/package-assets`，不是原始碼檔案。PyInstaller spec 會帶入 FShot 的套件 metadata，供打包版的視窗標題與更新檢查讀取版本。

## GitHub Actions 與發布

發布 GitHub Release 後，`Package desktop apps` 工作流程會在 Windows 與 macOS 原生 runner 執行測試及打包，將 EXE、DMG 與 `SHA256SUMS.txt` 附加到該 Release。

工作流程也可手動執行：

- **ref**：要打包的 Git tag 或 ref。
- **release_tag**：接收檔案的既有 GitHub Release 標籤；省略時沿用 ref。
- **attach_to_release**：只有對應 Release 已存在時才啟用。

打包流程不使用 Authenticode、Apple Developer ID 或 notarization 憑證，因此發行檔仍可能出現 SmartScreen／Gatekeeper 提示；處理方式見各平台安裝說明。
