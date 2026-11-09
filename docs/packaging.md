# 桌面應用程式打包

[繁體中文](packaging.md) | [English](packaging.en.md) · [開發指南](development.md)

本文件供開發與發布版本使用。下載正式安裝檔請見 [README](../README.md)；安裝與權限設定請見 [Windows](install-windows.md)／[macOS](install-macos.md) 安裝說明。

## 建置方式

FShot 使用 PyInstaller，必須在目標作業系統上建置。Windows runner 以 onedir 產生 x64 資料夾，並以 ZIP 散布；Apple Silicon macOS runner 產生 arm64 DMG，內含 `FShot.app` 與 Applications 捷徑。不建立 Intel Mac 版本。

安裝後的 `fshot` 指令使用 console entry point（`project.scripts`），沿用啟動它的終端機；桌面打包版使用 PyInstaller 的 windowed launcher。

## 本機打包

在專案根目錄執行：

```powershell
uv sync
uv run python scripts/build_app.py
```

輸出檔案：

- Windows：`dist/FShot-<version>-windows-x64.zip`。
- macOS：`dist/FShot-<version>-macos-arm64.dmg`。

產生的圖示與 Windows 版本資源位於 `build/package-assets`，不是原始碼檔案。PyInstaller spec 會帶入 FShot 的套件 metadata，供打包版的視窗標題與更新檢查讀取版本。

## GitHub Actions 與發布

發布 GitHub Release 後，`Package desktop apps` 工作流程會在 Windows 與 macOS 原生 runner 執行測試及打包，將 ZIP、DMG 與 `SHA256SUMS.txt` 附加到該 Release。

來源 ref 先解析成固定 commit SHA，兩平台完整測試與封裝都使用此提交。兩邊成功且附件上傳完成後，工作流程保存來源 SHA／版本標籤；`Publish to PyPI` 以 `workflow_run` 自動接續，檢查標籤符合套件版本，再從相同 SHA 建置與發布。無須另行啟動 PyPI；失敗、取消或未附加到 Release 的純打包不發布 PyPI。重試時重新執行工作流程，已存在的 PyPI 檔案會略過。

工作流程也可手動執行：

- **ref**：要打包的 Git tag 或 ref。
- **release_tag**：接收檔案的既有 GitHub Release 標籤；省略時沿用 ref。
- **attach_to_release**：只有對應 Release 已存在時才啟用。

設為 true 也會在成功後接續 PyPI；正式版本請使用 `v<version>` 標籤作為 ref 與 release_tag。此工作流程調整需先合併至預設分支，後續發布才會使用新流程。

打包流程不使用 Authenticode、Apple Developer ID 或 notarization 憑證，因此發行檔仍可能出現 SmartScreen／Gatekeeper 提示；處理方式見各平台安裝說明。

Windows ZIP 內為 `FShot/FShot.exe`、`FShot/_internal/` 與 `FShot/LICENSE`；必須完整保留。Windows 與 macOS 建置後都從暫存工作目錄執行版本入口與 Qt GUI 自我檢查；不註冊快捷鍵或使用使用者設定。任一檢查失敗就停止產生成品。單檔比較基準可用 `uv run python scripts/build_app.py --windows-layout onefile` 建置；不作為預設發行產物。啟動量測見 [啟動效能](startup-performance.md)。
