"""Claude Pet installer / uninstaller for Windows.

scripts/build.py bundles this into one self-contained ClaudePet-Setup-<version>.exe together with the app
(payload.zip), so installing needs no other tools and no admin rights:

    ClaudePet-Setup-x.y.z.exe                  wizard
    ClaudePet-Setup-x.y.z.exe --silent         unattended (options below)
    ClaudePet-Uninstall.exe                    (copied into the install folder) removes everything

Options: --dir PATH  --no-connect  --no-start-menu  --desktop-shortcut  --no-register  --no-launch  --silent
Uninstall: --uninstall [--silent] [--keep-hooks]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

APP = "Claude Pet"
EXE, CLI, UNINSTALLER = "ClaudePet.exe", "claude-pet-cli.exe", "ClaudePet-Uninstall.exe"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ClaudePet"
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Programs" / "ClaudePet"
NO_WINDOW = 0x08000000


def resource(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def version():
    try:
        return resource("VERSION").read_text().strip()
    except OSError:
        return "dev"


def start_menu_link():
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / (APP + ".lnk")


def desktop_link():
    return Path(os.environ["USERPROFILE"]) / "Desktop" / (APP + ".lnk")


def run_hidden(args, **kw):
    return subprocess.run(args, creationflags=NO_WINDOW, capture_output=True, **kw)


def make_shortcut(link, target, workdir):
    link.parent.mkdir(parents=True, exist_ok=True)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');$s.TargetPath='%s';"
          "$s.WorkingDirectory='%s';$s.IconLocation='%s,0';$s.Description='Claude Pet';$s.Save()"
          % (link, target, workdir, target))
    run_hidden(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])


def stop_running():
    run_hidden(["taskkill", "/F", "/IM", EXE])
    time.sleep(0.6)


def rmtree_retry(path, tries=8):
    for i in range(tries):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(0.5)
    return False


# ---------------------------------------------------------------- install
def install(target, connect=True, start_menu=True, desktop=False, register=True, progress=None):
    target = Path(target)
    stop_running()
    if (target / "_internal").exists():
        rmtree_retry(target / "_internal")                       # clean upgrade
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(resource("payload.zip")) as z:
        names = z.namelist()
        for i, n in enumerate(names, 1):
            z.extract(n, target)
            if progress:
                progress(i / len(names) * 0.9)
    if getattr(sys, "frozen", False):                            # the uninstaller is this very exe
        shutil.copy2(sys.executable, target / UNINSTALLER)
    exe = target / EXE
    if start_menu:
        make_shortcut(start_menu_link(), exe, target)
    if desktop:
        make_shortcut(desktop_link(), exe, target)
    if register:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            for name, val in (("DisplayName", APP), ("DisplayVersion", version()), ("Publisher", "claude-pet contributors"),
                              ("InstallLocation", str(target)), ("DisplayIcon", str(exe)),
                              ("UninstallString", '"%s" --uninstall' % (target / UNINSTALLER))):
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
    if connect:
        run_hidden([str(target / CLI), "install"])
    if progress:
        progress(1.0)
    return exe


# ---------------------------------------------------------------- uninstall
def installed_dir():
    """Where we are installed: the folder of this exe, or the registered location."""
    here = Path(sys.executable).resolve().parent
    if (here / EXE).exists():
        return here
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            return Path(winreg.QueryValueEx(k, "InstallLocation")[0])
    except OSError:
        return None


def uninstall(target, keep_hooks=False):
    target = Path(target)
    stop_running()
    if not keep_hooks and (target / CLI).exists():
        run_hidden([str(target / CLI), "uninstall"])            # remove the hooks from ~/.claude/settings.json
    for link in (start_menu_link(), desktop_link()):
        try:
            link.unlink()
        except OSError:
            pass
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    return rmtree_retry(target)


def relaunch_from_temp(target, args):
    """The uninstaller lives inside the folder it must delete: run a temporary copy instead."""
    tmp = Path(tempfile.mkdtemp(prefix="claudepet-uninst-")) / "uninstall.exe"
    shutil.copy2(sys.executable, tmp)
    subprocess.Popen([str(tmp), "--uninstall", "--relocated", str(target)] + args, creationflags=NO_WINDOW)


# ---------------------------------------------------------------- wizard
def wizard(args):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("%s Setup %s" % (APP, version()))
    root.resizable(False, False)
    try:
        root.iconbitmap(default=str(resource("icon.ico")))
    except Exception:
        pass
    pad = dict(padx=16, pady=4)
    ttk.Label(root, text="Install %s" % APP, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
    ttk.Label(root, text="An animated taskbar pet that shows what Claude Code is doing.\n"
                         "Installs for your user only; no administrator rights needed.",
              justify="left").pack(anchor="w", **pad)
    row = ttk.Frame(root)
    row.pack(fill="x", **pad)
    path = tk.StringVar(value=str(args.dir or DEFAULT_DIR))
    ttk.Entry(row, textvariable=path, width=52).pack(side="left", fill="x", expand=True)

    def browse():
        d = filedialog.askdirectory(initialdir=path.get(), title="Install folder")
        if d:
            path.set(str(Path(d) / "ClaudePet") if Path(d).name != "ClaudePet" else d)
    ttk.Button(row, text="Browse...", command=browse).pack(side="left", padx=(6, 0))
    connect, menu, desk, launch = (tk.BooleanVar(value=v) for v in (True, True, False, True))
    for var, text in ((connect, "Connect to Claude Code (adds hooks to ~/.claude/settings.json, backup written first)"),
                      (menu, "Start menu shortcut"), (desk, "Desktop shortcut"), (launch, "Launch Claude Pet when finished")):
        ttk.Checkbutton(root, text=text, variable=var).pack(anchor="w", padx=16)
    bar = ttk.Progressbar(root, length=420, maximum=1.0)
    bar.pack(padx=16, pady=(12, 4))
    btn = ttk.Button(root, text="Install")
    btn.pack(anchor="e", padx=16, pady=(4, 14))

    def go():
        btn.state(["disabled"])
        try:
            exe = install(path.get(), connect.get(), menu.get(), desk.get(), True,
                          progress=lambda f: (bar.configure(value=f), root.update()))
        except Exception as e:
            messagebox.showerror("Setup failed", str(e))
            btn.state(["!disabled"])
            return
        if launch.get():
            subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=NO_WINDOW)
        messagebox.showinfo("Done", "%s is installed.\n\nRestart any open Claude Code sessions so they pick up "
                                    "the hooks." % APP if connect.get() else "%s is installed." % APP)
        root.destroy()
    btn.configure(command=go)
    root.mainloop()


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--dir")
    ap.add_argument("--no-connect", action="store_true")
    ap.add_argument("--no-start-menu", action="store_true")
    ap.add_argument("--desktop-shortcut", action="store_true")
    ap.add_argument("--no-register", action="store_true")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--keep-hooks", action="store_true")
    ap.add_argument("--relocated")
    args = ap.parse_args(argv)

    if args.uninstall:
        target = Path(args.relocated) if args.relocated else installed_dir()
        if not target:
            return 1
        if not args.relocated:
            if not args.silent:
                import tkinter as tk
                from tkinter import messagebox
                r = tk.Tk()
                r.withdraw()
                if not messagebox.askyesno("Uninstall %s" % APP, "Remove %s and its hooks from Claude Code?\n\n"
                                           "(Your settings in %%LOCALAPPDATA%%\\ClaudePet are kept.)" % APP):
                    return 0
            relaunch_from_temp(target, (["--silent"] if args.silent else []) + (["--keep-hooks"] if args.keep_hooks else []))
            return 0
        ok = uninstall(target, args.keep_hooks)
        if not args.silent:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showinfo("Uninstall", "%s was removed." % APP if ok else
                                "Some files could not be removed; delete %s manually." % target)
        return 0 if ok else 1

    if args.silent:
        exe = install(args.dir or DEFAULT_DIR, not args.no_connect, not args.no_start_menu, args.desktop_shortcut,
                      not args.no_register)
        if not args.no_launch:
            subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=NO_WINDOW)
        return 0
    wizard(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
