"""Claude taskbar pet: a small animated pet that shows whether Claude is working, done, or needs you.

Run with:  claude-pet   (or ClaudePet.exe / python -m claude_pet).
Right-click (macOS: two-finger / Ctrl-click) for options. Click the pet to pet it; drag it anywhere and it
snaps to the taskbar / Dock edge when you drop it near it.
"""
import json
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path

from . import demo as demo_data
from . import paths
from .art import render, sprites
from .claude import accounts, integration, limits_api, usage
from .ui import platform_support as ps
from .ui.popup_menu import Menu, rounded

LOCK_PORT = 47653       # single-instance lock (demo mode uses the next port so it can run beside the real pet)
TICK_MS = 125
SNAP = 40
PANEL_W = 158
PET_TIME, WANT_TIME, AWAKE_TIME = 3.5, 120, 20
HDR = 16                # height of the account header line on the usage card
LIMITS_EVERY = 180      # seconds between usage-limit requests (when enabled)

DEFAULTS = {"pet": "claude", "scale": 3, "show_usage": True, "usage_view": "rotate", "usage_rotate_s": 8,
            "limits_api": False,
            "account": "auto", "logins": [], "names": {},
            "x": None, "dock": "bottom"}
VIEWS = [("Rotate (limits / tokens)", "rotate"), ("Limits only", "limits"), ("Tokens only", "tokens")]
STATE_LABELS = [("Auto (follow Claude)", None), ("Asleep (idle)", "sleep"), ("Awake", "idle"),
                ("Working", "working"), ("Just finished", "celebrate"), ("Wants a pet", "wants"),
                ("Being petted", "petted"), ("Distraught (needs you)", "attention")]
THEMES = {
    "dark": dict(bg="#2B2B30", border="#46464D", text="#F2F2F4", muted="#A0A0AA", track="#47474F", hover="#3B3B42"),
    "light": dict(bg="#F7F7F8", border="#D2D2D8", text="#1F1F24", muted="#6E6E78", track="#DEDEE3", hover="#E7E7EB"),
}


# ---------------------------------------------------------------- app
class PetApp:
    def __init__(self, demo=False):
        self.demo = demo
        self.cfg_path = paths.config_file()
        self.state_path = paths.state_file()
        self.cfg = dict(DEFAULTS)
        try:
            self.cfg.update(json.loads(self.cfg_path.read_text(encoding="utf-8-sig")))
        except Exception:
            pass
        if self.cfg["pet"] not in sprites.PETS:
            self.cfg["pet"] = "claude"
        c = self.cfg
        if not isinstance(c.get("logins"), list):
            c["logins"] = []
        c["logins"] = [m for m in c["logins"] if isinstance(m, dict) and m.get("dir")]
        if not isinstance(c.get("names"), dict):
            c["names"] = {}
        if not isinstance(c.get("account"), str):
            c["account"] = "auto"

        self.root = tk.Tk()
        self.root.title("claude-pet")
        bg = ps.setup_window(self.root)
        self.canvas = tk.Canvas(self.root, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.images = {}
        self.sessions = {}
        self._state_mtime = None
        self.forced = None
        self.petted_at = 0.0
        self.theme = THEMES["light" if ps.light_theme() else "dark"]
        self.tick_n = 0
        self.started = time.time()
        self.limits = None
        self.api = {}                 # account id -> {limits, status, plan}
        self._wake = threading.Event()
        self._last_active = None
        self.tokens = {}
        self.local = {None: usage.LocalTokens()}      # transcript root (None = ~/.claude) -> scanner
        self.accts, self.owner, self.last = [], {}, {}
        self.menu = None
        self.menu_open = False
        self.refresh_accounts()
        self.x = self.y = 0
        self.w = self.h = 1
        self._drag = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        for ev in ps.RIGHT_CLICK:
            self.canvas.bind(ev, self.on_menu)

        self.relayout(initial=True)
        if not self.demo:
            threading.Thread(target=self._token_loop, daemon=True).start()
            threading.Thread(target=self._limits_loop, daemon=True).start()
            self.root.after(2500, self._offer_connect)
        self.tick()
        self.root.after(3000, self.housekeeping)
        self.root.after(20000, self._refresh_timer)

    # ---- config
    def save(self):
        try:
            self.cfg_path.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ---- geometry
    def sprite_px(self):
        gw, gh = render.grid_size(self.cfg["pet"])
        return gw * self.cfg["scale"], gh * self.cfg["scale"]

    def panel_h(self):
        if not self.cfg["show_usage"]:
            return 0
        return (62 if self.limits else 46) + HDR

    def relayout(self, initial=False):
        sw, sh = self.sprite_px()
        self.w = sw + (PANEL_W + 8 if self.cfg["show_usage"] else 0)
        self.h = max(sh, self.panel_h())
        wa = ps.work_area(self.root)
        if initial:
            self.x = self.cfg["x"] if self.cfg["x"] is not None else wa[2] - self.w - 220
            self.y = wa[3] - self.h
        else:
            self.y += self._last_h - self.h if hasattr(self, "_last_h") else 0
        self._last_h = self.h
        self.canvas.configure(width=self.w, height=self.h)
        self.apply_dock()

    def clamp(self):
        vx0, vy0, vx1, vy1 = ps.virtual_screen(self.root)
        self.x = max(vx0 - self.w + 20, min(self.x, vx1 - 20))
        self.y = max(vy0, min(self.y, vy1 - 20))

    def apply_dock(self):
        wa = ps.work_area(self.root)
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
        wa = ps.work_area(self.root)
        dist = {"bottom": abs(self.y + self.h - wa[3]), "top": abs(self.y - wa[1]),
                "left": abs(self.x - wa[0]), "right": abs(self.x + self.w - wa[2])}
        side = min(dist, key=dist.get)
        self.cfg["dock"] = side if dist[side] <= SNAP else None
        self.cfg["x"] = self.x
        self.apply_dock()
        self.save()

    def reset_position(self):
        wa = ps.work_area(self.root)
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
                    if e.y_root - self.y < y0 + HDR + 2 and len(self.accts) > 1:
                        self.next_account()     # click the card header: switch account
                    else:
                        self.cycle_view()       # click the card: switch limits / tokens / rotate
                else:
                    self.petted_at = time.time()   # click the pet: pet it
            else:
                self.snap()

    # ---- state
    def read_state(self):
        try:
            mt = self.state_path.stat().st_mtime_ns
        except OSError:
            return
        if mt == self._state_mtime:
            return
        self._state_mtime = mt
        try:
            self.sessions = json.loads(self.state_path.read_text(encoding="utf-8-sig")).get("sessions", {})
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
            if ps.needs_alpha_images():
                for yy, row in enumerate(g):
                    for xx, col in enumerate(row):
                        if col == render.KEY:
                            small.transparency_set(xx, yy, True)
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
        font, bold = ps.ui_font(8), ps.ui_font(8, True)
        pad = 11
        view = self.usage_view()
        act = self.active()
        info = self.api.get(act["id"], {})
        if view == "limits":
            head = act["name"] + (" \u00b7 " + info["plan"] if info.get("plan") else "")
        else:
            head = act["name"] + " \u00b7 tokens"
        c.create_text(x0 + pad, y0 + 11, text=head, anchor="w", fill=th["muted"], font=ps.ui_font(7))
        if len(self.accts) > 1:
            c.create_text(x1 - pad, y0 + 11, text="\u21c4", anchor="e", fill=th["muted"], font=ps.ui_font(8))
        c.create_line(x0 + pad, y0 + HDR, x1 - pad, y0 + HDR, fill=th["track"])
        y0 += HDR
        ph -= HDR
        if view == "limits":
            names = {"5h": "5-hour", "7d": "Weekly"}
            for i, label in enumerate(l for l in ("5h", "7d") if l in self.limits):
                pct, reset = self.limits[label]
                y = y0 + 8 + i * 26
                c.create_text(x0 + pad, y + 5, text=names[label], anchor="w", fill=th["text"], font=bold)
                if reset:
                    c.create_text(x1 - pad - 32, y + 5, text="↻ " + usage.fmt_delta(reset - time.time()),
                                  anchor="e", fill=th["muted"], font=ps.ui_font(8))
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
            a = self.active()
            if a["id"] != self._last_active:                 # the active account changed (auto mode / switch)
                self._last_active = a["id"]
                self._wake.set()
            lim = usage.read_limits() if a["source"] == "cli" else None      # statusLine data is the CLI login's
            if not lim and self.cfg["limits_api"]:
                lim = self.api.get(a["id"], {}).get("limits")
            self.limits = lim
            self.tokens = self.tokens_for(a)
            if self.demo:
                self.limits, self.tokens = demo_data.limits(), demo_data.TOKENS
            if not self.demo:
                self.theme = THEMES["light" if ps.light_theme() else "dark"]
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
        if not self.menu_open:                       # never raise the pet over an open menu
            self.root.attributes("-topmost", True)
            self.root.lift()
        self.root.after(3000, self.housekeeping)

    def _token_loop(self):
        while True:
            for root in [None] + [a["dir"] and str(Path(a["dir"]) / "projects") for a in self.accts if a["dir"]]:
                try:
                    if root not in self.local:
                        self.local[root] = usage.LocalTokens(root)
                    self.local[root].scan()
                except Exception:
                    pass
            time.sleep(60)

    def tokens_for(self, a):
        cli = self.accts[0]["id"]
        total = dict(self.local[None].totals(self.owner, a["id"], cli))
        if a["dir"]:                                   # a CLI login folder has its own transcripts
            loc = self.local.get(str(Path(a["dir"]) / "projects"))
            if loc:
                for k, v in loc.totals().items():
                    total[k] = total.get(k, 0) + v
        return total

    # ---- accounts
    def refresh_accounts(self):
        if self.demo:
            self.accts, self.owner, self.last = demo_data.accounts(), {}, {}
            self.api = {a["id"]: {"plan": a.get("plan", ""), "status": "ok"} for a in self.accts}
            return
        owner, last = accounts.scan_desktop()
        self.accts = accounts.detect(self.cfg["logins"], self.cfg["names"], last)
        self.owner, self.last = owner, last

    def _refresh_timer(self):
        try:
            self.refresh_accounts()
        finally:
            self.root.after(20000, self._refresh_timer)

    def selection(self):
        """'auto' or the id of the account the user pinned (unknown / stale values count as auto)."""
        sel = self.cfg["account"]
        return sel if sel in [a["id"] for a in self.accts] else "auto"

    def active_id(self):
        ids = [a["id"] for a in self.accts]
        if self.selection() != "auto":
            return self.selection()
        best_t, best = 0, None                           # auto: whoever was active most recently
        for sid, st in self.sessions.items():
            o = self.owner.get(sid, ids[0])              # not a Desktop session: a terminal CLI session
            if o in ids and st.get("ts", 0) > best_t:
                best_t, best = st.get("ts", 0), o
        for acc, t in self.last.items():
            if acc in ids and t > best_t:
                best_t, best = t, acc
        return best or ids[0]

    def active(self):
        aid = self.active_id()
        return next(a for a in self.accts if a["id"] == aid)

    def fetchable(self, a):
        return (a["source"] == "cli" or bool(a["dir"])) and limits_api.has_login(a["dir"])

    def _limits_loop(self):
        while True:
            self._wake.clear()
            try:
                a = self.active()
                info = self.api.setdefault(a["id"], {})
                if self.fetchable(a):
                    info["plan"] = limits_api.plan_label(a["dir"])
                    if self.cfg["limits_api"]:
                        try:
                            info["limits"] = limits_api.fetch(a["dir"])
                            info["status"] = "ok"
                        except limits_api.LimitsError as e:
                            info["status"], info["limits"] = str(e), None
                    else:
                        info["status"] = "off"
                else:
                    info["status"], info["limits"] = "no login", None
                ok = info["status"] in ("ok", "off", "no login")
            except Exception:
                ok = False
            self._wake.wait(LIMITS_EVERY if ok else 60)

    def toggle_limits_api(self):
        self.cfg["limits_api"] = not self.cfg["limits_api"]
        self.save()
        self._wake.set()

    def switch_account(self, sel):
        self.cfg["account"] = sel
        self.save()
        self.limits = None
        self.tick_n -= self.tick_n % 40 + 1          # refresh the card on the next tick
        self._wake.set()

    def next_account(self):
        order = ["auto"] + [a["id"] for a in self.accts]
        cur = self.selection()
        self.switch_account(order[(order.index(cur) + 1) % len(order)])

    def add_account(self):
        folder = filedialog.askdirectory(parent=self.root, mustexist=False, initialdir=str(Path.home()),
                                         title="Pick (or create) a Claude config folder to sign a login into")
        if not folder:
            return
        folder = str(Path(folder))
        if any(m["dir"] == folder for m in self.cfg["logins"]):
            messagebox.showinfo("Add login", "That folder is already added.")
            return
        name = (simpledialog.askstring(
            "Name this login", "Name (e.g. Work).\nIf the login turns out to belong to a detected Desktop "
            "account it is linked to that account automatically.", parent=self.root,
            initialvalue=Path(folder).name) or "").strip() or Path(folder).name
        self.cfg["logins"].append({"name": name, "dir": folder})
        self.save()
        self.refresh_accounts()
        if not limits_api.has_login(folder):
            cmd = ('$env:CLAUDE_CONFIG_DIR="%s"; claude' if ps.IS_WIN else 'CLAUDE_CONFIG_DIR="%s" claude') % folder
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(cmd)
            except tk.TclError:
                pass
            messagebox.showinfo("Sign in once", "No login in that folder yet.\n\nOpen a terminal, paste this "
                                "(already copied to your clipboard), type /login and sign in with the account you "
                                "want to track:\n\n%s" % cmd)
        if not self.cfg["limits_api"] and messagebox.askyesno(
                "Usage limits", "Fetch real limits from Anthropic using these logins?\n(Reads the login token in "
                "the folder; read-only requests to api.anthropic.com.)"):
            self.toggle_limits_api()
        self._wake.set()

    def rename_account(self):
        a = self.active()
        new = (simpledialog.askstring("Rename account", "New name:", parent=self.root,
                                      initialvalue=a["name"]) or "").strip()
        if new:
            self.cfg["names"][a["id"]] = new
            self.save()
            self.refresh_accounts()

    def remove_login(self):
        a = self.active()
        if a["dir"] and messagebox.askyesno(
                "Remove login", "Stop using the login folder for '%s'?\n(The folder and its login are not "
                "touched.)" % a["name"]):
            self.cfg["logins"] = [m for m in self.cfg["logins"] if m["dir"] != a["dir"]]
            self.switch_account("auto")
            self.refresh_accounts()

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

    def toggle_hooks(self):
        try:
            if integration.is_installed():
                integration.uninstall()
            else:
                integration.install()
                messagebox.showinfo("Connected", "Hooks added to ~/.claude/settings.json (a backup was saved).\n"
                                    "Restart open Claude sessions so they pick them up.")
        except Exception as e:
            messagebox.showerror("Could not update Claude Code settings", str(e))

    def _offer_connect(self):
        """First run: offer to add the hooks (the pet cannot see Claude without them)."""
        if self.cfg.get("asked_connect") or integration.is_installed():
            return
        self.cfg["asked_connect"] = True
        self.save()
        if messagebox.askyesno("Connect to Claude Code?", "claude-pet needs a few Claude Code hooks to know when "
                               "Claude is working, done or waiting for you.\n\nAdd them to "
                               "~/.claude/settings.json now? (A backup is saved; right-click -> Connect to Claude "
                               "Code removes them again.)"):
            self.toggle_hooks()

    def toggle_startup(self):
        ps.set_startup(not ps.startup_enabled())

    def set_forced(self, v):
        self.forced = v

    def menu_items(self):
        act, sel = self.active(), self.selection()
        info = self.api.get(act["id"], {})
        acc = [("radio", "Auto \u2013 follow the active session", sel == "auto", lambda: self.switch_account("auto"))]
        for a in self.accts:
            label = a["name"] + ("   " + a["email"] if a["email"] else "")
            acc.append(("radio", label, sel == a["id"], lambda i=a["id"]: self.switch_account(i)))
        acc += [("sep",), ("item", "Add / link a login folder...", self.add_account),
                ("item", "Rename current...", self.rename_account)]
        if act["dir"]:
            acc.append(("item", "Remove login folder...", self.remove_login))
        items = [("sub", "Account: %s%s" % (act["name"], "  (auto)" if sel == "auto" else ""), acc)]

        items.append(("sub", "Pet", [("radio", spec["name"], self.cfg["pet"] == k, lambda k=k: self.set_pet(k))
                                      for k, spec in sprites.PETS.items()]))
        items.append(("sub", "Size", [("radio", lb, self.cfg["scale"] == n, lambda n=n: self.set_scale(n))
                                       for lb, n in (("Small", 2), ("Medium", 3), ("Large", 4), ("Huge", 5))]))
        items.append(("sep",))
        items.append(("check", "Show usage", self.cfg["show_usage"], self.toggle_usage))
        items.append(("sub", "Usage view", [("radio", lb, self.cfg.get("usage_view", "rotate") == v,
                                              lambda v=v: self.set_view(v)) for lb, v in VIEWS]))
        items.append(("check", "Fetch real limits (uses Claude login)", self.cfg["limits_api"], self.toggle_limits_api))
        notes = []
        if self.limits:
            for label, (pct, reset) in self.limits.items():
                t = "%s: %d%% used" % ("5-hour" if label == "5h" else "Weekly", round(pct))
                notes.append(t + (", resets in " + usage.fmt_delta(reset - time.time()) if reset else ""))
        elif info.get("status") == "no login":
            notes.append("No readable login for this account:")
            notes.append("link a CLI login folder to see its limits")
        elif self.cfg["limits_api"] and info.get("status") not in (None, "ok"):
            notes.append("limits: " + info["status"])
        elif not self.cfg["limits_api"]:
            notes.append("Tokens 5h %s \u00b7 7d %s" % (usage.fmt_tokens(self.tokens.get("5h", 0)),
                                                         usage.fmt_tokens(self.tokens.get("7d", 0))))
        items += [("label", n) for n in notes]
        items.append(("sep",))
        items.append(("sub", "Preview animation", [("radio", lb, (self.forced or None) == v,
                                                    lambda v=v: self.set_forced(v)) for lb, v in STATE_LABELS]))
        items.append(("item", "Snap to taskbar / Dock", self.reset_position))
        items.append(("check", "Start at login", ps.startup_enabled(), self.toggle_startup))
        if not self.demo:
            items.append(("check", "Connect to Claude Code (hooks)", integration.is_installed(), self.toggle_hooks))
        items.append(("sep",))
        items.append(("item", "Quit", self.root.destroy))
        return items

    def on_menu(self, e):
        if self.menu:
            self.menu.close()
        self.menu_open = True
        self.menu = Menu(self.root, self.theme, avoid=(self.x, self.y, self.x + self.w, self.y + self.h),
                         on_close=lambda: setattr(self, "menu_open", False))
        self.menu.open(self.menu_items(), e.x_root, e.y_root)

def run(demo=False, state=None):
    """Start the pet. demo: canned accounts / usage, nothing read from Claude. state: force an animation."""
    ps.init_process()
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", LOCK_PORT + (1 if demo else 0)))        # single instance
    except OSError:
        return 0
    app = PetApp(demo=demo)
    app.forced = state
    app.root.mainloop()
    return 0
