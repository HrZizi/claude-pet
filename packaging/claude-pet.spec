# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec. Build with:  python scripts/build.py      (or: pyinstaller packaging/claude-pet.spec)
#
# Produces an "onedir" bundle (fast start-up matters: the hook runs on every prompt / tool call):
#   dist/ClaudePet/ClaudePet.exe          windowed app (the pet)
#   dist/ClaudePet/claude-pet-cli.exe     console tool (hook, install, doctor, limits)
#   macOS: dist/ClaudePet.app
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

icon = None
if IS_WIN and (ROOT / "assets" / "icon.ico").exists():
    icon = str(ROOT / "assets" / "icon.ico")
elif IS_MAC and (ROOT / "assets" / "icon.icns").exists():
    icon = str(ROOT / "assets" / "icon.icns")

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    hiddenimports=[],
    excludes=["PIL", "numpy", "pytest", "unittest", "pydoc", "test", "setuptools", "pip", "distutils"],
    noarchive=False,
)
pyz = PYZ(a.pure)

version = str(ROOT / "packaging" / "windows" / "version_info.txt") if IS_WIN else None

gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ClaudePet", icon=icon, console=False,
          version=version, upx=False)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="claude-pet-cli", icon=icon, console=True,
          version=version, upx=False)
coll = COLLECT(gui, cli, a.binaries, a.datas, name="ClaudePet", upx=False)

if IS_MAC:
    app = BUNDLE(coll, name="ClaudePet.app", icon=icon, bundle_identifier="io.github.claude-pet",
                 info_plist={"LSUIElement": True,          # no Dock icon / menu bar: it is a floating pet
                             "CFBundleShortVersionString": "0.1.0",
                             "NSHighResolutionCapable": True})
