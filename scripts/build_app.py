from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication

from fshot.icons import camera_icon


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DIST = ROOT / "dist"
GENERATED = BUILD / "package-assets"


def project_version() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(project["project"]["version"])


def generate_icons() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    del app
    png_path = GENERATED / "fshot.png"
    camera_icon(1024, macos=sys.platform == "darwin").pixmap(1024, 1024).save(str(png_path), "PNG")
    with Image.open(png_path) as source:
        image = source.convert("RGBA")
        image.save(
            GENERATED / "fshot.ico",
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        if sys.platform == "darwin":
            image.save(GENERATED / "fshot.icns", format="ICNS")


def generate_windows_version(version: str) -> None:
    parts = [int(part) for part in version.split(".")]
    numeric = tuple((parts + [0, 0, 0, 0])[:4])
    content = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric}, prodvers={numeric}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'codemee'),
      StringStruct('FileDescription', 'FShot screenshot utility'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'FShot'),
      StringStruct('OriginalFilename', 'FShot.exe'),
      StringStruct('ProductName', 'FShot'),
      StringStruct('ProductVersion', '{version}')
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)'''
    (GENERATED / "windows-version.txt").write_text(content, encoding="utf-8")


def generate_windows_uia_wrapper() -> None:
    import comtypes.client

    comtypes.client.GetModule("UIAutomationCore.dll")


def reset_directory(path: Path) -> None:
    resolved = path.resolve()
    if BUILD.resolve() not in resolved.parents:
        raise RuntimeError(f"Refusing to reset path outside build directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def build_macos_dmg(version: str) -> Path:
    machine = platform.machine().lower()
    if machine not in {"arm64", "aarch64"}:
        raise SystemExit("FShot macOS packages support Apple Silicon (arm64) only")
    architecture = "arm64"
    staging = BUILD / "dmg-root"
    reset_directory(staging)
    shutil.copytree(DIST / "FShot.app", staging / "FShot.app", symlinks=True)
    os.symlink("/Applications", staging / "Applications")
    output = DIST / f"FShot-{version}-macos-{architecture}.dmg"
    output.unlink(missing_ok=True)
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            "FShot",
            "-srcfolder",
            str(staging),
            "-format",
            "UDZO",
            "-ov",
            str(output),
        ],
        check=True,
    )
    return output


def package_windows_directory(version: str) -> Path:
    shutil.copy2(ROOT / "LICENSE", DIST / "FShot" / "LICENSE")
    return Path(shutil.make_archive(str(DIST / f"FShot-{version}-windows-x64"),
                                   "zip", root_dir=DIST, base_dir="FShot"))


def main() -> int:
    if sys.platform not in {"win32", "darwin"}:
        raise SystemExit("Desktop packaging currently supports Windows and macOS only")
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows-layout", choices=("onedir", "onefile"), default="onedir",
                        help="Onefile is retained only for startup comparisons")
    args = parser.parse_args()
    os.environ["FSHOT_WINDOWS_LAYOUT"] = args.windows_layout
    version = project_version()
    generate_icons()
    if sys.platform == "win32":
        generate_windows_version(version)
        generate_windows_uia_wrapper()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            str(ROOT / "packaging" / "fshot.spec"),
        ],
        cwd=ROOT,
        check=True,
    )
    if sys.platform == "win32":
        executable = DIST / "FShot" / "FShot.exe" if args.windows_layout == "onedir" else DIST / "FShot.exe"
        with tempfile.TemporaryDirectory(prefix="fshot-package-cwd-") as cwd:
            subprocess.run([str(executable), "--version"], cwd=cwd, check=True, timeout=60)
            subprocess.run([str(executable), "--self-test"], cwd=cwd, check=True, timeout=120)
        if args.windows_layout == "onedir":
            output = package_windows_directory(version)
        else:
            output = DIST / f"FShot-{version}-windows-x64-onefile.exe"
            output.unlink(missing_ok=True)
            (DIST / "FShot.exe").replace(output)
    else:
        executable = DIST / "FShot.app" / "Contents" / "MacOS" / "FShot"
        with tempfile.TemporaryDirectory(prefix="fshot-package-cwd-") as cwd:
            subprocess.run([str(executable), "--version"], cwd=cwd, check=True, timeout=60)
            subprocess.run([str(executable), "--self-test"], cwd=cwd, check=True, timeout=120)
        output = build_macos_dmg(version)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
