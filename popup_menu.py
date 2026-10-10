"""Custom context menu styled like the usage card (rounded, themed, always on top of the pet).

Items:  ("item", text, command)            ("check", text, checked, command)
        ("radio", text, selected, command) ("label", text)   ("sep",)
        ("sub", text, [items])
"""
import tkinter as tk
from tkinter import font as tkfont

import platform_support as ps

PAD, ROW_H, SEP_H, LABEL_H, IND_W = 7, 27, 11, 22, 24
ACCENT = "#D97757"


def rounded(c, x0, y0, x1, y1, r, **kw):
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, splinesteps=8, **kw)


class _Panel:
    def __init__(self, menu, items, depth):
        self.menu, self.items, self.depth = menu, items, depth
        self.hover = -1
        self.win = tk.Toplevel(menu.root)
        self.win.withdraw()
        bg = ps.setup_window(self.win)
        self.cv = tk.Canvas(self.win, bg=bg, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.f = tkfont.Font(font=ps.ui_font(9))
        self.fb = tkfont.Font(font=ps.ui_font(9, True))
        self.fs = tkfont.Font(font=ps.ui_font(8))
        # layout
        self.rows, y, wmax = [], PAD, 0
        for it in items:
            kind = it[0]
            if kind == "sep":
                h, w = SEP_H, 0
            elif kind == "label":
                h, w = LABEL_H, self.fs.measure(it[1]) + 8
            else:
                h = ROW_H
                w = IND_W + self.f.measure(it[1]) + (18 if kind == "sub" else 0)
            self.rows.append((y, y + h))
            y += h
            wmax = max(wmax, w)
        self.w = max(190, min(400, wmax + 2 * PAD + 22))
        self.h = y + PAD
        self.cv.configure(width=self.w, height=self.h)
        self.cv.bind("<Motion>", self.on_motion)
        self.cv.bind("<Leave>", self.on_leave)
        self.cv.bind("<ButtonRelease-1>", self.on_click)
        self.win.bind("<Escape>", lambda e: menu.close())
        self.child = None
        self._sub_job = None

    # ---- geometry
    def place(self, x, y):
        self.x, self.y = x, y
        self.win.geometry("%dx%d+%d+%d" % (self.w, self.h, x, y))
        self.win.deiconify()
        self.win.attributes("-topmost", True)
        self.win.lift()
        self.draw()

    def rect(self):
        return self.x, self.y, self.x + self.w, self.y + self.h

    def row_at(self, y):
        for i, (a, b) in enumerate(self.rows):
            if a <= y < b:
                return i
        return -1

    @staticmethod
    def _enabled(it):
        return it[0] not in ("sep", "label")

    # ---- drawing
    def draw(self):
        th, c = self.menu.th, self.cv
        c.delete("all")
        rounded(c, 1, 1, self.w - 1, self.h - 1, 10, fill=th["bg"], outline=th["border"])
        for i, it in enumerate(self.items):
            y0, y1 = self.rows[i]
            kind = it[0]
            if kind == "sep":
                c.create_line(PAD + 6, (y0 + y1) / 2, self.w - PAD - 6, (y0 + y1) / 2, fill=th["track"])
                continue
            if kind == "label":
                c.create_text(PAD + 8, (y0 + y1) / 2, text=it[1], anchor="w", fill=th["muted"], font=self.fs)
                continue
            if i == self.hover:
                rounded(c, PAD, y0, self.w - PAD, y1, 7, fill=th["hover"], outline="")
            mid = (y0 + y1) / 2
            on = (kind == "check" and it[2]) or (kind == "radio" and it[2])
            if on:
                c.create_text(PAD + 13, mid, text="✓" if kind == "check" else "●", fill=ACCENT,
                              font=self.fb if kind == "check" else self.fs)
            c.create_text(PAD + IND_W, mid, text=it[1], anchor="w", fill=th["text"], font=self.f)
            if kind == "sub":
                c.create_text(self.w - PAD - 10, mid, text="›", anchor="e", fill=th["muted"], font=self.fb)

    # ---- events
    def on_motion(self, e):
        i = self.row_at(e.y)
        if i != self.hover:
            self.hover = i if i >= 0 and self._enabled(self.items[i]) else -1
            self.draw()
            if self._sub_job:
                self.win.after_cancel(self._sub_job)
                self._sub_job = None
            if self.child and not (self.hover >= 0 and self.items[self.hover][0] == "sub"):
                self.menu.close_from(self.depth + 1)
            if self.hover >= 0 and self.items[self.hover][0] == "sub":
                self._sub_job = self.win.after(160, lambda i=self.hover: self.open_sub(i))

    def on_leave(self, e):
        if not self.child:
            self.hover = -1
            self.draw()

    def open_sub(self, i):
        self._sub_job = None
        if self.hover != i:
            return
        self.menu.close_from(self.depth + 1)
        self.menu.show(self.items[i][2], self, self.rows[i][0])

    def on_click(self, e):
        i = self.row_at(e.y)
        if i < 0 or not self._enabled(self.items[i]):
            return
        it = self.items[i]
        if it[0] == "sub":
            self.open_sub(i)
            return
        cmd = it[-1]
        self.menu.close()
        if cmd:
            self.menu.root.after(15, cmd)


class Menu:
    def __init__(self, root, theme, avoid=None, on_close=None):
        self.root, self.th, self.avoid, self.on_close = root, theme, avoid, on_close
        self.panels = []
        self._poll = None
        self._armed = False

    @property
    def is_open(self):
        return bool(self.panels)

    # ---- opening
    def open(self, items, x, y):
        self.close()
        self.th = dict(self.th)
        self.th.setdefault("hover", "#3A3A41" if self.th["bg"][1] < "8" else "#E8E8EC")
        self.show(items, None, 0, cursor=(x, y))
        self._armed = False
        self._poll = self.root.after(40, self._watch)

    def show(self, items, parent, row_y, cursor=None):
        p = _Panel(self, items, len(self.panels) if parent is None else parent.depth + 1)
        sx0, sy0, sx1, sy1 = ps.virtual_screen(self.root)
        if parent is None:
            x = min(max(cursor[0], sx0 + 4), sx1 - p.w - 4)
            y = cursor[1]
            if self.avoid:                      # never sit on top of the pet: go above it (or below if no room)
                ax0, ay0, ax1, ay1 = self.avoid
                if ay0 - sy0 >= p.h + 6:
                    y = ay0 - p.h - 6
                elif sy1 - ay1 >= p.h + 6:
                    y = ay1 + 6
            y = min(max(y, sy0 + 4), sy1 - p.h - 4)
        else:
            px0, py0, px1, py1 = parent.rect()
            x = px1 - 4
            if x + p.w > sx1 - 4:
                x = px0 - p.w + 4
            y = min(max(py0 + row_y - PAD, sy0 + 4), sy1 - p.h - 4)
        p.place(int(x), int(y))
        self.panels.append(p)
        if parent is not None:
            parent.child = p
        else:
            p.win.focus_force()

    # ---- closing
    def close_from(self, depth):
        while len(self.panels) > depth:
            p = self.panels.pop()
            try:
                p.win.destroy()
            except tk.TclError:
                pass
        if self.panels:
            self.panels[-1].child = None
            self.panels[-1].draw()

    def close(self):
        if self._poll:
            try:
                self.root.after_cancel(self._poll)
            except tk.TclError:
                pass
            self._poll = None
        was = self.is_open
        self.close_from(0)
        if was and self.on_close:
            self.on_close()

    # ---- click outside closes the menu
    def _watch(self):
        self._poll = None
        if not self.is_open:
            return
        down = ps.mouse_buttons_down()
        if down is None:                                    # no global mouse state: fall back to focus loss
            try:
                f = self.root.focus_get()
            except (KeyError, tk.TclError):
                f = None
            if f is None and self._armed:
                self.close()
                return
            self._armed = self._armed or f is not None
        elif not down:
            self._armed = True
        elif self._armed:
            px, py = self.root.winfo_pointerxy()
            if not any(r[0] <= px < r[2] and r[1] <= py < r[3] for r in (p.rect() for p in self.panels)):
                self.close()
                return
        self._poll = self.root.after(40, self._watch)
