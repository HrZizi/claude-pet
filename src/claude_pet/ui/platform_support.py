"""Everything OS-specific lives here: transparent window, work area (taskbar / Dock), theme,
start-at-login, fonts. Windows is tested; macOS is written from documentation and untested."""
import os
import plistlib
import subprocess
import sys
import tkinter as tk
from pathlib import Path

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
KEY = "#010203"                      # colour keyed out as transparent on Windows

# right-click: Button-3 on Windows/Linux; Button-2 or Ctrl-click on macOS
RIGHT_CLICK = ("<Button-2>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",)

STARTUP_VBS = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/claude-pet.vbs"
LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/com.claude-pet.plist"


# ---------------------------------------------------------------- process / window
def init_process():
    if IS_WIN:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def setup_window(root):
    """Borderless, always-on-top, see-through window. Returns the colour the canvas must use as its background."""
    if IS_MAC:
        try:
            root.tk.call("::tk::unsupported::MacWindowStyle", "style", root._w, "plain", "none")
        except tk.TclError:
            root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparent", True)
        root.configure(bg="systemTransparent")
        return "systemTransparent"
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    if IS_WIN:
        root.attributes("-transparentcolor", KEY)
    root.configure(bg=KEY)
    return KEY


def needs_alpha_images():
    """macOS has no colour key, so transparent pixels must be real alpha in the PhotoImage."""
    return not IS_WIN


# ---------------------------------------------------------------- screen geometry
def _screen(root):
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def virtual_screen(root):
    if IS_WIN:
        import ctypes
        gm = ctypes.windll.user32.GetSystemMetrics
        x, y, w, h = gm(76), gm(77), gm(78), gm(79)
        return x, y, x + w, y + h
    return _screen(root)


def monitor_work_area(root, x, y):
    """(left, top, right, bottom) of the usable area of the single monitor containing point (x, y)."""
    try:
        if IS_WIN:
            import ctypes
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
            u = ctypes.windll.user32
            u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            u.MonitorFromPoint.restype = wintypes.HANDLE
            u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
            hmon = u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)      # MONITOR_DEFAULTTONEAREST
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                return r.left, r.top, r.right, r.bottom
        elif IS_MAC:
            from AppKit import NSScreen
            screens = NSScreen.screens()
            h0 = screens[0].frame().size.height
            for scr in screens:
                v = scr.visibleFrame()
                l, t = v.origin.x, h0 - (v.origin.y + v.size.height)
                r, b = l + v.size.width, t + v.size.height
                if l <= x < r and t <= y < b + 200:
                    return int(l), int(t), int(r), int(b)
    except Exception:
        pass
    return work_area(root)


def work_area(root):
    """(left, top, right, bottom) of the primary screen excluding the taskbar / Dock / menu bar."""
    if IS_WIN:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)   # SPI_GETWORKAREA
        return r.left, r.top, r.right, r.bottom
    if IS_MAC:
        wa = _mac_work_area(root)
        if wa:
            return wa
    return _screen(root)


def _mac_work_area(root):
    sx0, sy0, sw, sh = 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
    try:                                     # exact: needs `pip install pyobjc-framework-Cocoa`
        from AppKit import NSScreen
        scr = NSScreen.screens()[0]
        f, v = scr.frame(), scr.visibleFrame()
        top = f.size.height - (v.origin.y + v.size.height)      # Cocoa y grows upward, Tk y grows downward
        bottom = f.size.height - v.origin.y
        return int(v.origin.x), int(top), int(v.origin.x + v.size.width), int(bottom)
    except Exception:
        pass
    try:                                     # approximate from the Dock preferences
        def dock(key, default=None):
            r = subprocess.run(["defaults", "read", "com.apple.dock", key], capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else default
        if dock("autohide") == "1":
            return sx0, 25, sw, sh
        size = int(float(dock("tilesize", "48"))) + 28
        where = dock("orientation", "bottom")
        if where == "left":
            return size, 25, sw, sh
        if where == "right":
            return 0, 25, sw - size, sh
        return 0, 25, sw, sh - size
    except Exception:
        return None


# ---------------------------------------------------------------- theme / fonts
def light_theme():
    try:
        if IS_WIN:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(k, "SystemUsesLightTheme")[0] == 1
        if IS_MAC:
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                               capture_output=True, text=True, timeout=5)
            return "dark" not in r.stdout.lower()
    except Exception:
        pass
    return False


def ui_font(size=8, bold=False):
    if IS_MAC:        # Tk on macOS renders points smaller than Windows
        return ("Helvetica Neue", size + 3, "bold" if bold else "normal")
    return ("Segoe UI Semibold" if bold else "Segoe UI", size)


# ---------------------------------------------------------------- start at login
def startup_enabled():
    return (LAUNCH_AGENT if IS_MAC else STARTUP_VBS).exists()


def _launch_argv():
    """argv that starts the pet again (used for start-at-login)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = Path(sys.executable)
    if IS_WIN and exe.with_name("pythonw.exe").exists():
        exe = exe.with_name("pythonw.exe")                    # no console window
    return [str(exe), "-m", "claude_pet"]


def set_startup(enable):
    argv = _launch_argv()
    try:
        if IS_MAC:
            if not enable:
                LAUNCH_AGENT.unlink(missing_ok=True)
                return
            LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
            with open(LAUNCH_AGENT, "wb") as f:
                plistlib.dump({"Label": "com.claude-pet", "ProgramArguments": argv,
                               "RunAtLoad": True, "KeepAlive": False}, f)
        elif IS_WIN:
            if not enable:
                STARTUP_VBS.unlink(missing_ok=True)
                return
            cmdline = " ".join('""%s""' % a for a in argv)
            STARTUP_VBS.write_text('CreateObject("WScript.Shell").Run "%s", 0\n' % cmdline, encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- mouse state (for closing popup menus)
def mouse_buttons_down():
    """True/False if any mouse button is held (Windows); None where unavailable (callers use focus loss)."""
    if IS_WIN:
        import ctypes
        gk = ctypes.windll.user32.GetAsyncKeyState
        return any(gk(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))
    return None
