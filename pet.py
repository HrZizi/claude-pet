"""Claude taskbar pet: a small animated pet that shows whether Claude is working, done, or needs you.

Run with:  pythonw pet.py     (or double-click start.bat)
Right-click the pet for options. Drag it anywhere; it snaps to the taskbar edge when you drop it near it.
"""
import ctypes
import json
import os
import socket
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

import render
import sprites
import usage

DIR = Path(__file__).resolve().parent
CFG = DIR / "config.json"
STATE = DIR / "state.json"
TICK_MS = 125
SNAP = 40
PANEL_W = 158
PET_TIME, WANT_TIME, AWAKE_TIME = 3.5, 120, 20
STARTUP_VBS = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/claude-pet.vbs"

DEFAULTS = {"pet": "claude", "scale": 3, "show_usage": True, "usage_view": "rotate", "usage_rotate_s": 8,
            "x": None, "dock": "bottom"}
VIEWS = [("Rotate (limits / tokens)", "rotate"), ("Limits only", "limits"), ("Tokens only", "tokens")]
STATE_LABELS = [("Auto (follow Claude)", None), ("Asleep (idle)", "sleep"), ("Awake", "idle"),
                ("Working", "working"), ("Just finished", "celebrate"), ("Wants a pet", "wants"),
                ("Being petted", "petted"), ("Distraught (needs you)", "attention")]
THEMES = {
    "dark": dict(bg="#2B2B30", border="#46464D", text="#F2F2F4", muted="#A0A0AA", track="#47474F"),
    "light": dict(bg="#F7F7F8", border="#D2D2D8", text="#1F1F24", muted="#6E6E78", track="#DEDEE3"),
}


def light_theme():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "SystemUsesLightTheme")[0] == 1
    except Exception:
        return False


def rounded(c, x0, y0, x1, y1, r, **kw):
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, splinesteps=8, **kw)


# ---------------------------------------------------------------- Windows helpers
def _dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def work_area():
    r = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)   # SPI_GETWORKAREA
    return r.left, r.top, r.right, r.bottom


def virtual_screen():
    gm = ctypes.windll.user32.GetSystemMetrics
    x, y, w, h = gm(76), gm(77), gm(78), gm(79)
    return x, y, x + w, y + h


def hexcolor(c):
    return c


# ---------------------------------------------------------------- app
class PetApp:
    def __init__(self):
        self.cfg = dict(DEFAULTS)
        try:
            self.cfg.update(json.loads(CFG.read_text(encoding="utf-8")))
        except Exception:
            pass
        if self.cfg["pet"] not in sprites.PETS:
            self.cfg["pet"] = "claude"

        self.root = tk.Tk()
        self.root.title("claude-pet")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", render.KEY)
        self.root.configure(bg=render.KEY)
        self.canvas = tk.Canvas(self.root, bg=render.KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.images = {}
        self.sessions = {}
        self._state_mtime = None
        self.forced = None
        self.petted_at = 0.0
        self.theme = THEMES["light" if light_theme() else "dark"]
        self.tick_n = 0
        self.started = time.time()
        self.limits = None
        self.tokens = {}
        self.local = usage.LocalTokens()
        self.x = self.y = 0
        self.w = self.h = 1
        self._drag = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_menu)

        self.relayout(initial=True)
        threading.Thread(target=self._token_loop, daemon=True).start()
        self.tick()
        self.root.after(3000, self.housekeeping)

    # ---- config
    def save(self):
        try:
            CFG.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ---- geometry
    def sprite_px(self):
        gw, gh = render.grid_size(self.cfg["pet"])
        return gw * self.cfg["scale"], gh * self.cfg["scale"]

    def panel_h(self):
        if not self.cfg["show_usage"]:
            return 0
        return 62 if self.limits else 46

    def relayout(self, initial=False):
        sw, sh = self.sprite_px()
        self.w = sw + (PANEL_W + 8 if self.cfg["show_usage"] else 0)
        self.h = max(sh, self.panel_h())
        wa = work_area()
        if initial:
            self.x = self.cfg["x"] if self.cfg["x"] is not None else wa[2] - self.w - 220
            self.y = wa[3] - self.h
        else:
            self.y += self._last_h - self.h if hasattr(self, "_last_h") else 0
        self._last_h = self.h
        self.canvas.configure(width=self.w, height=self.h)
        self.apply_dock()

    def clamp(self):
        vx0, vy0, vx1, vy1 = virtual_screen()
        self.x = max(vx0 - self.w + 20, min(self.x, vx1 - 20))
        self.y = max(vy0, min(self.y, vy1 - 20))

    def apply_dock(self):
        wa = work_area()
        d = self.cfg.get("dock")
        if d == "bottom":
            self.y = wa[3] - self.h
        elif d == "top":
            self.y = wa[1]
        elif d == "left":
            self.x = wa[0]
        elif d == "right":
            self.x = wa[2] - self.w
        self.clamp()
        self.root.geometry("%dx%d+%d+%d" % (self.w, self.h, self.x, self.y))

    def snap(self):
        wa = work_area()
        dist = {"bottom": abs(self.y + self.h - wa[3]), "top": abs(self.y - wa[1]),
                "left": abs(self.x - wa[0]), "right": abs(self.x + self.w - wa[2])}
        side = min(dist, key=dist.get)
        self.cfg["dock"] = side if dist[side] <= SNAP else None
        self.cfg["x"] = self.x
        self.apply_dock()
        self.save()

    def reset_position(self):
        wa = work_area()
        self.cfg["dock"] = "bottom"
        self.x = wa[2] - self.w - 220
        self.cfg["x"] = self.x
        self.apply_dock()
        self.save()

    # ---- dragging
    def on_press(self, e):
        self._drag = (e.x_root - self.x, e.y_root - self.y)

    def on_drag(self, e):
        if self._drag:
            self.x, self.y = e.x_root - self._drag[0], e.y_root - self._drag[1]
            self.root.geometry("+%d+%d" % (self.x, self.y))

    def on_release(self, e):
        if self._drag:
            moved = abs(e.x_root - self.x - self._drag[0]) + abs(e.y_root - self.y - self._drag[1])
            self._drag = None
            if moved < 4:                       # a click, not a drag
                x0, y0, x1, y1 = getattr(self, "panel_rect", (-1, -1, -1, -1))
                if self.cfg["show_usage"] and x0 <= e.x_root - self.x <= x1 and y0 <= e.y_root - self.y <= y1:
                    self.cycle_view()           # click the card: switch limits / tokens / rotate
                else:
                    self.petted_at = time.time()   # click the pet: pet it
            else:
                self.snap()

    # ---- state
    def read_state(self):
        try:
            mt = STATE.stat().st_mtime_ns
        except OSError:
            return
        if mt == self._state_mtime:
            return
        self._state_mtime = mt
        try:
            self.sessions = json.loads(STATE.read_text(encoding="utf-8")).get("sessions", {})
        except Exception:
            pass

    def summarize(self):
        """-> animation state name"""
        now = time.time()
        working = attn = False
        last_done = last_any = 0
        for s in self.sessions.values():
            ts, st = s.get("ts", 0), s.get("state")
            age = now - ts
            last_any = max(last_any, ts)
            if st == "working" and age < 600:
                working = True
            elif st == "attention" and age < 1800:
                attn = True
            elif st == "done":
                last_done = max(last_done, ts)
        if attn:
            return "attention"
        if now - self.petted_at < PET_TIME:
            return "petted"
        if working:
            return "working"
        if last_done and now - last_done < 4:
            return "celebrate"
        if last_done and now - last_done < WANT_TIME and self.petted_at < last_done:
            return "wants"
        if now - max(last_any, self.petted_at, self.started) > AWAKE_TIME:
            return "sleep"
        return "idle"

    # ---- drawing
    def image_for(self, key):
        sc = self.cfg["scale"]
        k = (key, sc)
        img = self.images.get(k)
        if img is None:
            g = render.grid(key)
            small = tk.PhotoImage(width=len(g[0]), height=len(g))
            small.put(" ".join("{" + " ".join(row) + "}" for row in g), to=(0, 0))
            img = small.zoom(sc, sc)
            if len(self.images) > 600:
                self.images.clear()
            self.images[k] = img
        return img

    def usage_view(self):
        v = self.cfg.get("usage_view", "rotate")
        if not self.limits or v == "tokens":
            return "tokens"
        if v == "limits":
            return "limits"
        return "limits" if int(time.time() // max(2, self.cfg.get("usage_rotate_s", 8))) % 2 == 0 else "tokens"

    def draw_panel(self):
        c, th = self.canvas, self.theme
        ph = self.panel_h()
        x0, y0 = self.sprite_px()[0] + 7, self.h - ph
        x1, y1 = x0 + PANEL_W, self.h
        self.panel_rect = (x0, y0, x1, y1)
        rounded(c, x0, y0, x1, y1, 9, fill=th["bg"], outline=th["border"])
        # little tail pointing at the pet
        ty = y1 - 18
        c.create_polygon(x0 + 1, ty - 5, x0 - 6, ty, x0 + 1, ty + 5, fill=th["bg"], outline="")
        c.create_line(x0 + 1, ty - 5, x0 - 6, ty, x0 + 1, ty + 5, fill=th["border"])
        c.create_line(x0 + 1, ty - 4, x0 + 1, ty + 4, fill=th["bg"])
        font, bold = ("Segoe UI", 8), ("Segoe UI Semibold", 8)
        pad = 11
        if self.usage_view() == "limits":
            names = {"5h": "5-hour", "7d": "Weekly"}
            for i, label in enumerate(l for l in ("5h", "7d") if l in self.limits):
                pct, reset = self.limits[label]
                y = y0 + 9 + i * 26
                c.create_text(x0 + pad, y + 5, text=names[label], anchor="w", fill=th["text"], font=bold)
                if reset:
                    c.create_text(x1 - pad - 32, y + 5, text="↻ " + usage.fmt_delta(reset - time.time()),
                                  anchor="e", fill=th["muted"], font=("Segoe UI", 8))
                c.create_text(x1 - pad, y + 5, text="%d%%" % round(pct), anchor="e", fill=th["text"], font=bold)
                bx0, bx1, by = x0 + pad + 2, x1 - pad - 2, y + 18
                c.create_line(bx0, by, bx1, by, width=5, capstyle="round", fill=th["track"])
                color = "#E5484D" if pct >= 90 else "#F5A524" if pct >= 70 else "#D97757"
                fill_to = bx0 + max(0, (bx1 - bx0) * min(pct, 100) / 100)
                c.create_line(bx0, by, max(fill_to, bx0 + .1), by, width=5, capstyle="round", fill=color)
            return
        rows = []
        for label, name in (("5h", "Tokens, 5h"), ("7d", "Tokens, 7d")):
            n = self.tokens.get(label)
            budget = self.cfg.get("token_budget_" + label)
            if n is None:
                rows.append((name, "..."))
            elif budget:
                rows.append((name, "%d%%" % min(100, round(100 * n / budget))))
            else:
                rows.append((name, usage.fmt_tokens(n)))
        for i, (name, val) in enumerate(rows):
            y = y0 + ph * (i + 1) / 3
            c.create_text(x0 + pad, y, text=name, anchor="w", fill=th["muted"], font=font)
            c.create_text(x1 - pad, y, text=val, anchor="e", fill=th["text"], font=bold)

    def tick(self):
        self.read_state()
        if self.tick_n % 40 == 0:
            was = self.panel_h()
            self.limits = usage.read_limits()
            self.tokens = self.local.totals()
            self.theme = THEMES["light" if light_theme() else "dark"]
            if self.panel_h() != was:
                self.relayout()
        state = self.forced or self.summarize()
        self.tick_n += 1
        key = render.pose(self.cfg["pet"], state, self.tick_n)
        self.canvas.delete("all")
        self.canvas.create_image(0, self.h, anchor="sw", image=self.image_for(key))
        if self.cfg["show_usage"]:
            self.draw_panel()
        self.root.after(TICK_MS, self.tick)

    def housekeeping(self):
        if not self._drag:
            self.apply_dock()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.after(3000, self.housekeeping)

    def _token_loop(self):
        while True:
            try:
                self.local.scan()
            except Exception:
                pass
            time.sleep(60)

    # ---- menu
    def set_pet(self, key):
        self.cfg["pet"] = key
        self.save()
        self.relayout()

    def set_scale(self, n):
        self.cfg["scale"] = n
        self.save()
        self.relayout()

    def set_view(self, v):
        self.cfg["usage_view"] = v
        self.save()

    def cycle_view(self):
        order = [v for _, v in VIEWS]
        cur = self.cfg.get("usage_view", "rotate")
        self.set_view(order[(order.index(cur) + 1) % len(order)] if cur in order else "rotate")

    def toggle_usage(self):
        self.cfg["show_usage"] = not self.cfg["show_usage"]
        self.save()
        self.relayout()

    def toggle_startup(self):
        try:
            if STARTUP_VBS.exists():
                STARTUP_VBS.unlink()
            else:
                pyw = Path(sys.executable).with_name("pythonw.exe")
                exe = pyw if pyw.exists() else Path(sys.executable)
                STARTUP_VBS.write_text(
                    'CreateObject("WScript.Shell").Run """%s"" ""%s""", 0\n' % (exe, DIR / "pet.py"),
                    encoding="utf-8")
        except OSError:
            pass

    def set_forced(self, v):
        self.forced = v

    def on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        pets = tk.Menu(m, tearoff=0)
        pv = tk.StringVar(value=self.cfg["pet"])
        for k, spec in sprites.PETS.items():
            pets.add_radiobutton(label=spec["name"], variable=pv, value=k, command=lambda k=k: self.set_pet(k))
        m.add_cascade(label="Pet", menu=pets)
        sizes = tk.Menu(m, tearoff=0)
        sv = tk.IntVar(value=self.cfg["scale"])
        for label, n in (("Small", 2), ("Medium", 3), ("Large", 4), ("Huge", 5)):
            sizes.add_radiobutton(label=label, variable=sv, value=n, command=lambda n=n: self.set_scale(n))
        m.add_cascade(label="Size", menu=sizes)
        uv = tk.BooleanVar(value=self.cfg["show_usage"])
        m.add_checkbutton(label="Show usage", variable=uv, command=self.toggle_usage)
        vm = tk.Menu(m, tearoff=0)
        vv = tk.StringVar(value=self.cfg.get("usage_view", "rotate"))
        for label, v in VIEWS:
            vm.add_radiobutton(label=label, variable=vv, value=v, command=lambda v=v: self.set_view(v))
        m.add_cascade(label="Usage view (click the card to switch)", menu=vm)
        if self.limits:
            for label, (pct, reset) in self.limits.items():
                t = "%s limit: %d%% used" % (label, round(pct))
                if reset:
                    t += ", resets in " + usage.fmt_delta(reset - time.time())
                m.add_command(label="   " + t, state="disabled")
        elif self.tokens:
            m.add_command(label="   Local tokens 5h: %s | 7d: %s (no limit data yet)" % (
                usage.fmt_tokens(self.tokens.get("5h", 0)), usage.fmt_tokens(self.tokens.get("7d", 0))),
                state="disabled")
        m.add_separator()
        tests = tk.Menu(m, tearoff=0)
        fv = tk.StringVar(value=self.forced or "")
        for label, v in STATE_LABELS:
            tests.add_radiobutton(label=label, variable=fv, value=v or "", command=lambda v=v: self.set_forced(v))
        m.add_cascade(label="Preview animation", menu=tests)
        m.add_command(label="Snap to taskbar", command=self.reset_position)
        sv2 = tk.BooleanVar(value=STARTUP_VBS.exists())
        m.add_checkbutton(label="Start with Windows", variable=sv2, command=self.toggle_startup)
        m.add_separator()
        m.add_command(label="Quit", command=self.root.destroy)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()


def main():
    _dpi_aware()
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", 47653))        # single instance
    except OSError:
        return
    app = PetApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
