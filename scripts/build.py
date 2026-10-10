"""Build the redistributable:  python scripts/build.py [--installer] [--clean]

  * runs PyInstaller (packaging/claude-pet.spec)         -> dist/ClaudePet/   (macOS: dist/ClaudePet.app)
  * zips it as a portable download                        -> dist/ClaudePet-<version>-<os>.zip
  * --installer (Windows, needs Inno Setup's `iscc` on PATH) -> dist/ClaudePet-Setup-<version>.exe
Needs the dev extras:  pip install -e ".[dev]"
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from claude_pet import __version__   # noqa: E402

DIST = ROOT / "dist"


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def main():
    if "--clean" in sys.argv:
        shutil.rmtree(DIST, ignore_errors=True)
        shutil.rmtree(ROOT / "build", ignore_errors=True)
    if not (ROOT / "assets" / "icon.ico").exists():
        run([sys.executable, ROOT / "scripts" / "make_assets.py"])
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", DIST, "--workpath", ROOT / "build",
         ROOT / "packaging" / "claude-pet.spec"])

    osname = "windows" if sys.platform.startswith("win") else "macos" if sys.platform == "darwin" else "linux"
    target = DIST / ("ClaudePet.app" if sys.platform == "darwin" else "ClaudePet")
    zip_base = DIST / ("ClaudePet-%s-%s" % (__version__, osname))
    if sys.platform == "darwin":
        run(["ditto", "-c", "-k", "--keepParent", target, str(zip_base) + ".zip"])
    else:
        shutil.make_archive(str(zip_base), "zip", DIST, "ClaudePet")
    print("portable zip:", str(zip_base) + ".zip")

    if "--installer" in sys.argv:
        iscc = shutil.which("iscc") or shutil.which("ISCC")
        if not (sys.platform.startswith("win") and iscc):
            sys.exit("--installer needs Windows and Inno Setup (iscc) on PATH: https://jrsoftware.org/isdl.php")
        run([iscc, "/DAppVersion=" + __version__, ROOT / "packaging" / "windows" / "claude-pet.iss"])


if __name__ == "__main__":
    main()
