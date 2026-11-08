# Windows 應用程式安裝

[繁體中文](install-windows.md) | [English](install-windows.en.md)

FShot 的 Windows 應用程式是不需安裝的資料夾包（以 ZIP 散布）。這是個人專案版本，沒有 Authenticode 發行者簽章，因此 Windows 可能顯示「未知的發行者」或 Microsoft Defender SmartScreen 警告。

Code signing status（程式碼簽章狀態）：[下載驗證與目前的簽章狀態](code-signing-policy.md)。

## 下載與驗證

1. 只從 [FShot GitHub Releases](https://github.com/codemee/fshot/releases) 下載 `FShot-<版本>-windows-x64.zip`。
2. 同時下載該版本的 `SHA256SUMS.txt`。
3. 在 PowerShell 執行：

```powershell
Get-FileHash .\FShot-*-windows-x64.zip -Algorithm SHA256
```

比對輸出與 `SHA256SUMS.txt`。雜湊可確認下載內容完整，但不能取代發行者簽章；仍應確認檔案來自官方 GitHub repository。

## 第一次執行

先將 ZIP 完整解壓到固定位置，保留 `FShot.exe`、`_internal` 與 `LICENSE`，再執行資料夾內的 `FShot.exe`；不要在 ZIP 內直接執行，也不要只搬走 EXE。若 SmartScreen 顯示「Windows 已保護您的電腦」：

1. 確認檔名、下載來源與 SHA-256。
2. 選擇「其他資訊」。
3. 確認應用程式為 FShot，然後選擇「仍要執行」。

資料夾版將解壓成本移至首次解壓 ZIP，啟動時直接載入同目錄的必要元件。首次啟動仍可能受防毒掃描與檔案快取影響。若檔案被隔離，請先重新確認來源及雜湊，再從 Windows Security 檢視處理，不要任意為整個資料夾關閉防護。

## 更新

打包版會檢查 GitHub Releases。發現新版時會開啟下載頁面，不會自動覆寫目前的未簽章 EXE。請下載新版 ZIP、驗證後關閉 FShot，替換完整資料夾，避免混用新舊 DLL。若啟用「開機自動執行」，搬移前先取消，從新位置啟動後再啟用；捷徑也需更新。
