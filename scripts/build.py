"""Build the redistributables:  python scripts/build.py

Outputs (everything else is a throw-away intermediate and is cleaned up):

  Windows   dist/ClaudePet-Setup-<version>.exe              installer (wizard, shortcuts, uninstaller; no admin needed)
            dist/ClaudePet-<version>-windows-portable.zip   unzip anywhere and run ClaudePet.exe; keeps its data beside it
  macOS     dist/ClaudePet-<version>-macos.zip              ClaudePet.app

Do NOT run executables from build/: that is PyInstaller's scratch folder and is deleted at the end.
Needs the dev extras:  pip install -e ".[dev]"
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from claude_pet import __version__   # noqa: E402

DIST = ROOT / "dist"
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

PORTABLE_README = """Claude Pet {v} (portable)

Run ClaudePet.exe. Right-click the pet -> "Connect to Claude Code (hooks)" once.
Settings are kept in the "data" folder next to ClaudePet.exe (nothing is written to AppData).
If you move this folder, right-click -> "Connect to Claude Code" twice (off, on) to repoint the hooks.
To remove everything: right-click -> uncheck "Connect to Claude Code", then delete this folder.
"""


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def pyinstaller(*args, work):
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--workpath", work, *args])


def zip_dir(src, dest, arcname):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(Path(src).rglob("*")):
            if f.is_file():
                z.write(f, Path(arcname) / f.relative_to(src))


def main():
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir()
    scratch = Path(tempfile.mkdtemp(prefix="claude-pet-build-"))      # intermediates never land in the repo
    try:
        if not (ROOT / "assets" / "icon.ico").exists():
            run([sys.executable, ROOT / "scripts" / "make_assets.py"])
        stage = scratch / "dist"
        pyinstaller("--distpath", stage, ROOT / "packaging" / "claude-pet.spec", work=scratch / "work")

        if IS_MAC:
            app = stage / "ClaudePet.app"
            out = DIST / ("ClaudePet-%s-macos.zip" % __version__)
            run(["ditto", "-c", "-k", "--keepParent", app, out])
            print("built", out)
            return

        bundle = stage / "ClaudePet"
        # 1) portable zip: same files + a flag that makes the app keep its data next to the exe
        port = scratch / "portable"
        shutil.copytree(bundle, port / "ClaudePet")
        (port / "ClaudePet" / "portable.flag").write_text("portable build: data lives in .\\data\n")
        (port / "ClaudePet" / "README.txt").write_text(PORTABLE_README.format(v=__version__))
        zip_dir(port / "ClaudePet", DIST / ("ClaudePet-%s-windows-portable.zip" % __version__), "ClaudePet")

        # 2) installer: a single exe carrying the app as payload.zip
        if IS_WIN:
            payload = scratch / "payload"
            payload.mkdir()
            zip_dir(bundle, payload / "payload.zip", ".")
            # payload.zip entries must extract straight into the install folder (no leading ./ObjectName)
            with zipfile.ZipFile(payload / "payload.zip") as z:
                names = z.namelist()
            assert any(n.endswith("ClaudePet.exe") for n in names)
            (payload / "VERSION").write_text(__version__)
            sep = ";"
            pyinstaller("--distpath", DIST, "--onefile", "--windowed", "--name", "ClaudePet-Setup-%s" % __version__,
                        "--icon", ROOT / "assets" / "icon.ico",
                        "--add-data", "%s%s." % (payload / "payload.zip", sep),
                        "--add-data", "%s%s." % (payload / "VERSION", sep),
                        "--add-data", "%s%s." % (ROOT / "assets" / "icon.ico", sep),
                        "--version-file", ROOT / "packaging" / "windows" / "version_info.txt",
                        "--specpath", scratch,                       # keep the generated .spec (local paths) out of the repo
                        ROOT / "packaging" / "windows" / "setup_app.py", work=scratch / "work-setup")
        for f in sorted(DIST.iterdir()):
            print("built", f.name, "%.1f MB" % (f.stat().st_size / 1e6))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(ROOT / "build", ignore_errors=True)


if __name__ == "__main__":
    main()
