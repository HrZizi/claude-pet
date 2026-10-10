"""Turns (pet, state, tick) into a small grid of colours. No Tk in here so it can be previewed.

States: sleep (idle), idle (awake, just woke), working, attention (distraught),
        celebrate (just finished), wants (wants a pet), petted.
"""
import sprites

KEY = "#010203"          # colour treated as transparent by the window
GW = 28                  # grid width: 24px sprite + room to shake / glyphs
X0 = 2                   # sprite x offset
HEAD = 6                 # free rows above the 24px sprite canvas
GH = sprites.H + HEAD

COLORS = {
    "work": "#4FC3F7", "attn": "#FF5252", "good": "#4CAF50", "gold": "#FFD54F",
    "sleep": "#90A4AE", "heart": "#FF6B9D", "sweat": "#7FD1FF",
}
LAPTOP = {"K": "#2B2D31", "G": "#A8AEB7", "g": "#8A9099", "T": "#4A4E55"}


def grid_size(pet=None):
    return GW, GH


def pose(pet, state, t):
    """Hashable description of one animation frame."""
    d = dict(face="open", ear=0, tail=0, lie=False, arm=0, tear=-1, gaze=0,
             mirror=False, dx=0, dy=0, laptop=None)
    ov = []

    def hearts(n, speed=3):
        for i in range(n):
            ph = (t // speed + i * (12 // n)) % 12
            ov.append(("heart" if i % 2 == 0 else "heart3", 4 + i * 7 + (ph % 3), -ph // 2 - 1, COLORS["heart"]))

    if state == "sleep":
        d.update(lie=True, face="sleep", dy=1 if (t // 10) % 2 else 0)
        ph = (t // 5) % 6
        ov.append(("zs", 17 + ph // 2, -1 - ph, COLORS["sleep"]))
        ph2 = (t // 5 + 3) % 6
        ov.append(("z", 19 + ph2 // 2, -3 - ph2, COLORS["sleep"]))
    elif state == "idle":                       # awake and calm
        d.update(face="blink" if t % 36 in (0, 1) else "open",
                 tail=(0, 1, 0, -1)[(t // 6) % 4],
                 ear=1 if t % 50 in (10, 11, 12) else 0)
    elif state == "working":
        d.update(face="focus", gaze=(0, 1, 1, 0, -1, -1)[(t // 5) % 6], laptop=(t // 2) % 2,
                 tail=(0, 1, 0, -1)[(t // 3) % 4], arm=3, dy=0)
        for i in range(3):
            if (t // 4) % 4 > i:
                ov.append(("dot", 18 + i * 3, -3, COLORS["work"]))
    elif state == "attention":                  # distraught
        d.update(face="sad", ear=2, tail=-1, dx=1 if t % 2 else -1, tear=(t // 2) % 3,
                 arm=2 if (t // 3) % 2 else 1)
        ov.append(("sweat", 19, 1, COLORS["sweat"]))
        if (t // 4) % 2:
            ov.append(("!", 21, -5, COLORS["attn"]))
    elif state == "celebrate":
        d.update(face="happy", tail=(1, -1)[t % 2], arm=1,
                 dy=(0, 2, 3, 3, 2, 0)[t % 6], mirror=(t // 6) % 2 == 1)
        sp = COLORS["gold"]
        ov += [("spark", 20 if t % 2 else 1, -4 + t % 3, sp), ("spark", 3 if t % 2 else 21, -2 + (t + 1) % 3, sp)]
        ov.append(("check", 11, -5, COLORS["good"]))
    elif state == "wants":                      # "pet me!"
        d.update(face="beg", ear=0, tail=(1, -1)[(t // 2) % 2], arm=1,
                 dy=1 if (t // 4) % 3 == 0 else 0)
        hearts(2, 4)
        ov.append(("spark", 18 + (t // 6) % 2, -1, COLORS["gold"]))
    elif state == "petted":
        stroke = (-3, -1, 1, 3, 1, -1)[t % 6]
        d.update(face="happy", ear=1, tail=(1, -1)[t % 2], arm=0, dx=1 if (t // 3) % 2 else 0)
        ov.append(("hand", 7 + stroke, -3, None))
        hearts(3, 2)
    return (pet, tuple(sorted(d.items())), tuple(ov))


def grid(key):
    pet, dtuple, ov = key
    d = dict(dtuple)
    mirror, dx, dy, laptop = d.pop("mirror"), d.pop("dx"), d.pop("dy"), d.pop("laptop")
    px = sprites.draw(pet, **d)
    if mirror:
        px = {(sprites.W - 1 - x, y): c for (x, y), c in px.items()}
    top = min(y for _, y in px)
    g = [[KEY] * GW for _ in range(GH)]

    def put(x, y, c):
        if 0 <= x < GW and 0 <= y < GH:
            g[y][x] = c

    for (x, y), c in px.items():
        put(X0 + x + dx, HEAD + y - dy, c)

    if laptop is not None:
        accent = sprites.PETS[pet]["accent"]
        glow = "#FFE082" if laptop else accent
        lid = ["..KKKKKKKKKKKKKK..",
               ".KGGGGGGGGGGGGGGK.",
               ".KGGGGGGGGGGGGGGK.",
               ".KGGGGGGggGGGGGGK.",
               ".KGGGGGgYYgGGGGGK.",
               ".KGGGGGGggGGGGGGK.",
               "KKKKKKKKKKKKKKKKKK",
               "KTTTTTTTTTTTTTTTTK"]
        x0, y0 = X0 + 3, HEAD + 16
        pal = dict(LAPTOP, Y=glow)
        for j, row in enumerate(lid):
            for i, ch in enumerate(row):
                if ch != ".":
                    put(x0 + i, y0 + j, pal[ch])
        for i, base in enumerate((x0 + 3, x0 + 12)):             # typing paws
            up = (laptop + i) % 2
            for jj in (5, 6):
                put(base, y0 + jj - up, accent)
                put(base + 1, y0 + jj - up, accent)

    for name, ox, oy, color in ov:
        rows = sprites.GLYPHS[name]
        multi = sprites.MULTI.get(name)
        for j, r in enumerate(rows):
            for i, ch in enumerate(r):
                if ch == ".":
                    continue
                put(X0 + ox + i, HEAD + top + oy + j - dy, multi[ch] if multi else color)
    return g
