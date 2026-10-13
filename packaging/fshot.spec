from pathlib import Path
import sys
import tomllib

from PyInstaller.utils.hooks import copy_metadata


ROOT = Path.cwd()
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
GENERATED = ROOT / "build" / "package-assets"

hidden_imports = []
if sys.platform == "win32":
    hidden_imports.append("comtypes.gen.UIAutomationClient")
elif sys.platform == "darwin":
    hidden_imports.extend(["AppKit", "ApplicationServices", "Quartz", "ScreenCaptureKit", "CoreMedia", "libdispatch"])

analysis = Analysis(
    [str(ROOT / "src" / "fshot" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=copy_metadata("fshot"),
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

if sys.platform == "win32":
    executable = EXE(
        pyz,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name="FShot",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=str(GENERATED / "fshot.ico"),
        version=str(GENERATED / "windows-version.txt"),
    )
elif sys.platform == "darwin":
    executable = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name="FShot",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
    )
    collected = COLLECT(
        executable,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        name="FShot",
    )
    app = BUNDLE(
        collected,
        name="FShot.app",
        icon=str(GENERATED / "fshot.icns"),
        bundle_identifier="com.codemee.fshot",
        info_plist={
            "CFBundleDisplayName": "FShot",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHighResolutionCapable": True,
            "NSScreenCaptureUsageDescription": "FShot captures windows and virtual displays for screenshots.",
        },
    )
else:
    raise SystemExit("Desktop packaging currently supports Windows and macOS only")
