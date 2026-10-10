"""Generates the project's art assets from the pet's own renderer (run from the repo root):

    python scripts/make_assets.py            # icon + GIFs
    python scripts/make_assets.py --screens  # also real-app screenshots (Windows, needs a display; uses --demo data)

Outputs: assets/icon.ico, assets/icon.png, docs/images/*.gif, docs/images/*.png
"""
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from claude_pet.art import render, sprites   # noqa: E402

IMAGES = ROOT / "docs" / "images"
BG = (30, 30, 34)


def hexrgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def frame_image(pet, state, tick, scale, bg=BG):
    g = render.grid(render.pose(pet, state, tick))
    im = Image.new("RGB", (render.GW * scale, render.GH * scale), bg)
    px = im.load()
    for y, row in enumerate(g):
        for x, c in enumerate(row):
            if c != render.KEY:
                col = hexrgb(c)
                for yy in range(scale):
                    for xx in range(scale):
                        px[x * scale + xx, y * scale + yy] = col
    return im


# ---------------------------------------------------------------- icon
def make_icon():
    """32x32 pixel-art app icon: the Claude pet on a rounded dark tile with a little heart."""
    S = 32
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=7, fill=(43, 43, 48, 255), outline=(70, 70, 77, 255))
    px = sprites.draw("claude", face="happy", arm=1)
    xs, ys = [p[0] for p in px], [p[1] for p in px]
    ox = (S - (max(xs) - min(xs) + 1)) // 2 - min(xs)
    oy = (S - (max(ys) - min(ys) + 1)) // 2 - min(ys) + 2
    for (x, y), c in px.items():
        img.putpixel((x + ox, y + oy), hexrgb(c) + (255,))
    heart = sprites.GLYPHS["heart"]
    for j, row in enumerate(heart):
        for i, ch in enumerate(row):
            if ch == "X":
                img.putpixel((22 + i, 3 + j), (255, 107, 157, 255))
    return img


def write_icon():
    (ROOT / "assets").mkdir(exist_ok=True)
    small = make_icon()
    big = small.resize((256, 256), Image.NEAREST)
    big.save(ROOT / "assets" / "icon.png")
    try:                                                           # macOS app icon
        small.resize((1024, 1024), Image.NEAREST).save(ROOT / "assets" / "icon.icns")
    except Exception as e:                                         # pragma: no cover
        print("icns skipped:", e)
    big.save(ROOT / "assets" / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon written")


# ---------------------------------------------------------------- GIFs
STATE_TEXT = [
    ("sleep", "Idle: asleep", 40), ("working", "Working: typing away", 32), ("attention", "Needs you: distraught", 28),
    ("celebrate", "Done!", 20), ("wants", "Wants a pet", 32), ("petted", "Being petted", 28),
]


def save_gif(frames, path, duration=125):
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=duration, loop=0, optimize=True, disposal=2)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def write_gifs():
    IMAGES.mkdir(parents=True, exist_ok=True)
    scale = 5
    f = font(15)
    # one GIF per pet: all states in sequence, captioned
    for pet in sprites.PETS:
        frames = []
        for state, text, n in STATE_TEXT:
            for t in range(n):
                im = frame_image(pet, state, t, scale)
                canvas = Image.new("RGB", (im.width, im.height + 26), BG)
                canvas.paste(im, (0, 0))
                dr = ImageDraw.Draw(canvas)
                w = dr.textlength(text, font=f)
                dr.text(((canvas.width - w) / 2, im.height + 3), text, fill=(200, 200, 208), font=f)
                frames.append(canvas)
        save_gif(frames, IMAGES / ("pet-%s.gif" % pet))
    # hero: all three pets side by side, stepping through the states together
    frames = []
    pets = list(sprites.PETS)
    for state, text, n in STATE_TEXT:
        for t in range(n):
            ims = [frame_image(p, state, t, 4) for p in pets]
            w = sum(i.width for i in ims)
            canvas = Image.new("RGB", (w, ims[0].height + 30), BG)
            x = 0
            for im in ims:
                canvas.paste(im, (x, 0))
                x += im.width
            dr = ImageDraw.Draw(canvas)
            tw = dr.textlength(text, font=f)
            dr.text(((w - tw) / 2, ims[0].height + 5), text, fill=(210, 210, 218), font=f)
            frames.append(canvas)
    save_gif(frames, IMAGES / "hero.gif")
    # static contact sheet of every state
    s = 3
    cells = [(p, st) for p in pets for st, _, _ in STATE_TEXT]
    cw, ch = render.GW * s, render.GH * s
    sheet = Image.new("RGB", (cw * len(STATE_TEXT), ch * len(pets)), BG)
    for i, (p, st) in enumerate(cells):
        sheet.paste(frame_image(p, st, 6, s), ((i % len(STATE_TEXT)) * cw, (i // len(STATE_TEXT)) * ch))
    sheet.save(IMAGES / "states.png")
    print("gifs written")


# ---------------------------------------------------------------- real screenshots (demo data, solid backdrop)
def write_screens():
    import os
    import tkinter as tk
    tmp = tempfile.mkdtemp(prefix="claude-pet-shots-")
    os.environ["CLAUDE_PET_HOME"] = tmp                       # never touch the real config
    from PIL import ImageGrab
    from claude_pet import app as pet_app
    from claude_pet.ui import platform_support as ps

    ps.init_process()

    def settle(a, seconds=1.6):
        """Let the app's own timers run (animation ticks, usage refresh) before grabbing the screen."""
        end = time.time() + seconds
        while time.time() < end:
            a.root.update()
            time.sleep(0.03)

    def shoot(name, theme, view, menu=None, state="working", pet="eevee", size=(520, 440)):
        a = pet_app.PetApp(demo=True)
        a.cfg.update(pet=pet, scale=3, show_usage=True, usage_view=view, dock=None, account="auto")
        a.theme = pet_app.THEMES[theme]
        a.forced = state
        a.tick_n = 0
        a.relayout()
        a.root.update()
        W, H = size
        X0, Y0 = 200, 120
        back = tk.Toplevel(a.root)
        back.overrideredirect(True)
        back.geometry("%dx%d+%d+%d" % (W, H, X0, Y0))
        bg, bar = ("#12141a", "#1d2027") if theme == "dark" else ("#dfe3ea", "#f1f3f7")
        cv = tk.Canvas(back, width=W, height=H, bg=bg, highlightthickness=0)
        cv.pack()
        cv.create_rectangle(0, H - 48, W, H, fill=bar, outline="")
        back.lower(a.root)
        a.x, a.y = X0 + 150, Y0 + H - 48 - a.h
        a.root.geometry("%dx%d+%d+%d" % (a.w, a.h, a.x, a.y))
        settle(a)
        if menu:
            a.menu_open = True
            a.menu = pet_app.Menu(a.root, a.theme, avoid=(a.x, a.y, a.x + a.w, a.y + a.h), on_close=lambda: None)
            a.menu.open(a.menu_items(), a.x + 40, a.y + 40)
            if menu == "account":
                p0 = a.menu.panels[0]
                p0.hover = 0
                p0.open_sub(0)
            settle(a)
        img = ImageGrab.grab(bbox=(X0, Y0, X0 + W, Y0 + H))
        img.save(IMAGES / name)
        for job in a.root.tk.splitlist(a.root.tk.call("after", "info")):
            a.root.after_cancel(job)
        a.root.destroy()

    shoot("card-limits.png", "dark", "limits", state="working", size=(440, 190))
    shoot("card-tokens.png", "dark", "tokens", state="wants", pet="bulbasaur", size=(440, 190))
    shoot("card-light.png", "light", "limits", state="celebrate", pet="claude", size=(440, 190))
    shoot("menu.png", "dark", "limits", menu="main", state="sleep", size=(520, 520))
    shoot("menu-accounts.png", "dark", "limits", menu="account", state="sleep", size=(780, 520))
    print("screenshots written")


if __name__ == "__main__":
    write_icon()
    write_gifs()
    if "--screens" in sys.argv:
        write_screens()
