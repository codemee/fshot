# Code signing status / 程式碼簽章狀態

FShot's Windows EXE releases are currently **not Authenticode signed**. No code signing service or certificate is configured for this project. The macOS DMG and PyPI packages are also not covered by a Windows code signature.

FShot 的 Windows EXE 發行檔目前**沒有 Authenticode 簽章**。專案目前沒有設定程式碼簽章服務或憑證。macOS DMG 與 PyPI 套件也不屬於 Windows 簽章範圍。

Download FShot only from the [official GitHub Releases page](https://github.com/codemee/fshot/releases). Compare the downloaded file's SHA-256 hash with `SHA256SUMS.txt` from the same release. A matching checksum verifies the file against the published checksum but does not establish a publisher identity.

請只從[官方 GitHub Releases 頁面](https://github.com/codemee/fshot/releases)下載 FShot，並將下載檔案的 SHA-256 與同版本的 `SHA256SUMS.txt` 比對。相符的雜湊可確認檔案與公布的校驗碼一致，但不能證明發行者身分。
