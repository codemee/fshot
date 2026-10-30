# Code signing policy / 程式碼簽章政策

## Status / 目前狀態

As of 2026-10-30, FShot has not applied for a SignPath Foundation subscription. Existing releases are unsigned. This policy describes the intended process for future signed Windows releases; it does not claim that any current download is signed.

截至 2026-10-30，FShot 尚未申請 SignPath Foundation 方案。現有版本未簽章。本政策說明未來 Windows 版本的簽章流程，並不表示目前下載檔已有簽章。

## Signed artifacts / 簽章範圍

Once approved, the project will sign its own `FShot-<version>-windows-x64.exe` release artifact using Authenticode. The certificate publisher will be **SignPath Foundation**, not the project maintainer. macOS DMG files and PyPI packages are outside this Windows code signing process. Third-party binaries bundled by PyInstaller are not individually signed with the project's certificate.

核准後，專案會以 Authenticode 簽署自行建置的 `FShot-<version>-windows-x64.exe`。憑證發行者會顯示為 **SignPath Foundation**，不是專案維護者。macOS DMG 與 PyPI 套件不在此 Windows 簽章流程內；PyInstaller 封裝的第三方二進位檔不會以本專案憑證逐一簽署。

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

## Team and release control / 團隊與發佈控管

- Committer and reviewer: [codemee](https://github.com/codemee). Contributions from others are reviewed before merging.
- Signing approver: [codemee](https://github.com/codemee). Each release signing request requires manual approval.
- The Windows executable is built from this [public repository](https://github.com/codemee/fshot) by GitHub-hosted Actions. Only the signed output will be attached to a signed release after signature verification.

提交者與審查者為 [codemee](https://github.com/codemee)；其他人的貢獻須經審查才能合併。簽章核准者為 codemee，每次發行均須人工核准。Windows exe 由 GitHub 託管的 Actions runner 從公開原始碼建置；實施簽章後，通過驗證的已簽檔案才會附加至對應 Release。

## Privacy and network access / 隱私與網路連線

FShot processes screenshots locally. The portable desktop app checks the public GitHub Releases API for updates, by default no more often than once per day; automatic update checks can be disabled in the system tray menu. When an update is available, FShot opens the release page only if the user chooses to download it. The `uv tool` distribution checks PyPI for updates. On Windows, FShot uses WinGet to obtain the optional Virtual Display Driver only after the user agrees to install it. FShot does not upload screenshots or other user content to these services.

FShot 在本機處理截圖。可攜版預設最多每天一次查詢公開的 GitHub Releases API，並可在系統匣選單關閉自動檢查；只有使用者選擇下載更新時才會開啟發佈頁。`uv tool` 版本會向 PyPI 查詢更新。Windows 虛擬螢幕驅動程式只會在使用者同意安裝後透過 WinGet 取得。FShot 不會將截圖或其他使用者內容上傳至這些服務。
