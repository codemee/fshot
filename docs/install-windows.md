# Windows 應用程式安裝

[繁體中文](install-windows.md) | [English](install-windows.en.md)

FShot 的 Windows 應用程式是一個不需安裝的單一 EXE。這是個人專案版本，沒有 Authenticode 發行者簽章，因此 Windows 可能顯示「未知的發行者」或 Microsoft Defender SmartScreen 警告。

Code signing policy（程式碼簽章政策）：[簽章範圍、負責人與隱私說明](code-signing-policy.md)。

## 下載與驗證

1. 只從 [FShot GitHub Releases](https://github.com/codemee/fshot/releases) 下載 `FShot-<版本>-windows-x64.exe`。
2. 同時下載該版本的 `SHA256SUMS.txt`。
3. 在 PowerShell 執行：

```powershell
Get-FileHash .\FShot-*-windows-x64.exe -Algorithm SHA256
```

比對輸出與 `SHA256SUMS.txt`。雜湊可確認下載內容完整，但不能取代發行者簽章；仍應確認檔案來自官方 GitHub repository。

## 第一次執行

直接執行 EXE。若 SmartScreen 顯示「Windows 已保護您的電腦」：

1. 確認檔名、下載來源與 SHA-256。
2. 選擇「其他資訊」。
3. 確認應用程式為 FShot，然後選擇「仍要執行」。

單一執行檔每次啟動會先解壓必要元件到使用者暫存目錄，因此第一次啟動可能稍慢，也可能比一般安裝程式更容易觸發防毒軟體的啟發式警告。若檔案被隔離，請先重新確認來源及雜湊，再從 Windows Security 檢視處理，不要任意為整個資料夾關閉防護。

## 更新

打包版會檢查 GitHub Releases。發現新版時會開啟下載頁面，不會自動覆寫目前的未簽章 EXE。請下載新檔、完成相同驗證後，再以新版本取代舊檔。
