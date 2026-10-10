"""Procedural pixel-art pets.

Each pet is built from shaded, outlined shapes (ellipses / polygons) so poses can change
(ears, tail, lying down, faces) without hand-drawing every frame.
draw(pet, **pose) -> {(x, y): '#rrggbb'} on a 24x24 canvas.
"""
import math

W = H = 24

PETS = {
    "claude": {"name": "Claude", "accent": "#D97757"},
    "eevee": {"name": "Eevee", "accent": "#C08A4E"},
    "bulbasaur": {"name": "Bulbasaur", "accent": "#6CC4A6"},
}


# ----------------------------------------------------------------- shape masks
def _clip(m):
    return {p for p in m if 0 <= p[0] < W and 0 <= p[1] < H}


def ell(cx, cy, rx, ry):
    m = set()
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            if ((x + .5 - cx) / rx) ** 2 + ((y + .5 - cy) / ry) ** 2 <= 1:
                m.add((x, y))
    return _clip(m)


def poly(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    m = set()
    for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
        for x in range(int(min(xs)) - 1, int(max(xs)) + 2):
            px, py, inside = x + .5, y + .5, False
            j = len(pts) - 1
            for i in range(len(pts)):
                xi, yi, xj, yj = pts[i][0], pts[i][1], pts[j][0], pts[j][1]
                if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                m.add((x, y))
    return _clip(m)


def rect(x0, y0, x1, y1):
    return _clip({(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)})


def mir(pts):
    return [(W - x, y) for x, y in pts]


def mirm(mask):
    return {(W - 1 - x, y) for x, y in mask}


def dilate(m):
    return {(x + dx, y + dy) for x, y in m for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}


def scaled(pts, k):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts]


class Cv:
    def __init__(self):
        self.px = {}

    def paint(self, mask, color, halo=None, rim=None):
        if halo:
            for p in dilate(mask) - mask:
                if 0 <= p[0] < W and 0 <= p[1] < H:
                    self.px[p] = halo
        for p in mask:
            self.px[p] = color
        if rim:
            for x, y in mask:
                if (x, y + 1) not in mask:
                    self.px[(x, y)] = rim

    def put(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.px[(x, y)] = c


# ----------------------------------------------------------------- faces
BLUSH = "#F28DA6"
WATER = "#9FDCFF"
WHITE = "#FFFFFF"


def face(cv, p, a):
    """Draw eyes / mouth. a = anchors: lx, ey, w, h, mx, my, ink, iris, lid, lidc, mouth, nose."""
    f, w, h, ey, ink = p["face"], a["w"], a["h"], a["ey"], a["ink"]
    iris = a.get("iris", ink)
    for side in (0, 1):
        x = a["lx"] if side == 0 else W - 1 - (a["lx"] + w - 1)
        inner = x + w - 1 if side == 0 else x
        outer = x if side == 0 else x + w - 1
        s = 1 if side == 0 else -1
        if f == "open":
            for yy in range(h):
                for xx in range(w):
                    cv.put(x + xx, ey + yy, ink if (a.get("lid") and yy == 0) else iris)
            cv.put(inner, ey + (1 if a.get("lid") else 0), WHITE)
        elif f == "blink":
            for xx in range(w):
                cv.put(x + xx, ey + h - 1, ink)
        elif f == "sleep":
            for xx in range(w):
                cv.put(x + xx, ey + h - 1, ink)
            cv.put(x - 1, ey + h - 2, ink)
            cv.put(x + w, ey + h - 2, ink)
        elif f == "happy":
            for xx in range(w):
                cv.put(x + xx, ey + 1, ink)
            cv.put(x - 1, ey + 2, ink)
            cv.put(x + w, ey + 2, ink)
            for k in (1, 2):
                cv.put(outer - s * k - (s if k == 1 else 0) * 0, ey + h + 1, BLUSH)
        elif f == "focus":
            gx = p.get("gaze", 0)
            for xx in range(w + 2):
                cv.put(x - 1 + xx, ey, a.get("lidc", ink))
            for yy in range(1, h):
                for xx in range(w):
                    cv.put(x + xx + gx, ey + yy, ink)
        elif f == "sad":
            for yy in range(h):
                for xx in range(w):
                    cv.put(x + xx, ey + yy, ink if (a.get("lid") and yy == 0) else iris)
            cv.put(inner, ey + (1 if a.get("lid") else 0), WHITE)
            cv.put(outer, ey + h - 1, WATER)                      # welling up
            brow = a.get("brow", ink)
            for k in range(w + 1):                                # thin worried brow, inner end raised
                bx = (x - 1 + k) if side == 0 else (x + w - k)
                cv.put(bx, ey - 2 if k <= w // 2 else ey - 3, brow)
            t = p.get("tear", -1)
            if t >= 0:                                            # tear rolling down the cheek
                cv.put(outer, ey + h, WATER)
                cv.put(outer, ey + h + 1 + t, WATER)
                cv.put(outer, ey + h + 2 + t, "#CFEFFF")
        elif f == "beg":
            x0 = x - 1 if side == 0 else x
            for yy in range(h + 1):
                for xx in range(w + 1):
                    cv.put(x0 + xx, ey - 1 + yy, ink if (a.get("lid") and yy == 0) else iris)
            cv.put(inner if side == 1 else x0 + w, ey - 1 + (1 if a.get("lid") else 0), WHITE)
            cv.put(x0 if side == 0 else x0 + w, ey + h - 1, WHITE)
            cv.put(outer - 2 * s, ey + h + 1, BLUSH)
            cv.put(outer - 2 * s - s, ey + h + 1, BLUSH)
    # nose + mouth
    mx, my = a["mx"], a["my"]
    if a.get("nose") is not None:
        cv.put(mx - 1, a["nose"], ink)
        cv.put(mx, a["nose"], ink)
    if f in ("happy", "beg"):
        for dx in (-2, 1):
            cv.put(mx + dx, my, ink)
        for dx in (-1, 0):
            cv.put(mx + dx, my + 1, ink)
        if f == "happy":
            for dx in (-1, 0):
                cv.put(mx + dx, my, "#E8667F")
    elif f == "sad":                                # wailing mouth
        wide = p.get("tear", 0) % 2
        for dx in (-1, 0):
            cv.put(mx + dx, my, ink)
        if wide:
            for dx in (-2, 1):
                cv.put(mx + dx, my + 1, ink)
        for dx in (-1, 0):
            cv.put(mx + dx, my + 1, "#E8667F")
    elif a.get("mouth") and f in ("open", "focus"):
        for dx in (-1, 0):
            cv.put(mx + dx, my, ink)


# ----------------------------------------------------------------- Claude
def claude(p):
    cv = Cv()
    O, S, L, INK = "#D97757", "#B85C3E", "#EC9B7B", "#1B1B1B"
    if p["lie"]:
        cv.paint(rect(3, 16, 20, 22), O, rim=S)
        for x in range(3, 21):
            cv.put(x, 16, L)
        cv.paint(rect(6, 23, 7, 23), S)
        cv.paint(rect(16, 23, 17, 23), S)
        face(cv, p, dict(lx=6, ey=17, w=2, h=3, mx=12, my=20, ink=INK))
        return cv.px
    arm = p["arm"]
    left_up = arm in (1, 2)
    right_up = arm == 1
    lm = rect(1, 7, 3, 12) if left_up else rect(1, 12, 3, 15)
    rm = rect(20, 7, 22, 12) if right_up else rect(20, 12, 22, 15)
    if arm == 3:                                    # typing: arms forward
        lm, rm = rect(2, 15, 4, 17), rect(19, 15, 21, 17)
    cv.paint(lm, O, rim=S)
    cv.paint(rm, O, rim=S)
    for x0 in (5, 8, 14, 17):
        cv.paint(rect(x0, 20, x0 + 1, 23), S)
    cv.paint(rect(4, 9, 19, 19), O, rim=S)
    for x in range(4, 20):
        cv.put(x, 9, L)
    for y in range(9, 20):
        cv.put(4, y, L)
    a = dict(lx=7, ey=11, w=2, h=3, mx=12, my=16, ink=INK, lidc=S, brow=S, mouth=False)
    face(cv, p, a)
    return cv.px


# ----------------------------------------------------------------- Eevee
def eevee(p):
    cv = Cv()
    B, Bd, Bl = "#C48C50", "#8E5E30", "#DDAA6A"
    C, Cd = "#F7E8C4", "#D8C393"
    K, T = "#3B2515", "#7A4A2A"
    lie = p["lie"]
    hy = 15 if lie else 10           # head centre y
    tx = p["tail"]

    if lie:
        tail = poly([(14, 21), (19, 18), (22 + tx, 17), (24, 20), (22, 23.5), (14, 23.5)])
    else:
        tail = poly([(16, 21), (19, 18), (20 + tx, 14), (22 + tx, 10), (24, 12), (24, 18), (23, 21)])
    cv.paint(tail, B, halo=K, rim=Bd)
    for q in {q for q in tail if (q[1] <= 13 if not lie else q[0] >= 21)}:
        cv.px[q] = C

    if lie:
        cv.paint(ell(12, 20, 10.5, 3.6), B, halo=K, rim=Bd)
        cv.paint(ell(7.5, 21.5, 3, 1.8), C, halo=K)
        cv.paint(ell(16.5, 21.5, 3, 1.8), C, halo=K)
    else:
        cv.paint(ell(12, 18.5, 8, 5), B, halo=K, rim=Bd)
        cv.paint(ell(8, 21.6, 2.4, 2.2), B, halo=K, rim=Bd)
        cv.paint(ell(16, 21.6, 2.4, 2.2), B, halo=K, rim=Bd)
        for x in (7, 9, 15, 17):
            cv.put(x, 23, Cd)
        ruff = poly([(5, 15), (19, 15), (20.5, 17), (19, 17.5), (18.5, 19.5), (16, 18.5), (14.5, 20.5),
                     (12, 19), (9.5, 20.5), (8, 18.5), (5.5, 19.5), (5, 17.5), (3.5, 17)])
        cv.paint(ruff, C, halo=K, rim=Cd)

    # cheek tufts
    tuft = [(5, hy + 1), (1.5, hy + 2.5), (3, hy + 3.5), (2, hy + 5.5), (6, hy + 5)]
    cv.paint(poly(tuft), Bl, halo=K)
    cv.paint(poly(mir(tuft)), Bl, halo=K)

    # ears
    ear = p["ear"]
    tips = [(3, hy - 10), (0.5, hy - 6.5), (-1, hy - 3)][ear]
    base_a, base_b = (4 if ear == 2 else 3.5, hy + 1.5 if ear == 2 else hy + .5), (10.5, hy - 4.5 + (ear == 2) * 1.5)
    left = [base_a, tips, base_b]
    for pts in (left, mir(left)):
        m = poly(pts)
        cv.paint(m, B, halo=K, rim=Bd)
        for q in poly(scaled(pts, .5)):
            cv.px[q] = T
        tp = pts[1]
        for q in m:
            if (q[0] + .5 - tp[0]) ** 2 + (q[1] + .5 - tp[1]) ** 2 <= 5.5:
                cv.px[q] = C

    cv.paint(ell(12, hy, 8, 5.8), B, halo=K, rim=Bd)
    for q in ell(12, hy - 3.6, 3.4, .9):
        cv.px[q] = Bl

    ey = int(hy) - 1 if not lie else int(hy)
    face(cv, p, dict(lx=7, ey=ey, w=3, h=3, mx=12, my=int(hy) + 4, nose=int(hy) + 3, ink=K, lidc=Bd, brow=Bd))
    return cv.px


# ----------------------------------------------------------------- Bulbasaur
def bulbasaur(p):
    cv = Cv()
    G, Gd, Gl = "#6CC4A6", "#4B9B84", "#8FDDC2"
    Sp = "#3F8F7A"
    L, Ld, Ll = "#62C24E", "#3F9A35", "#93E37A"
    K, T = "#1F3B2A", "#35806C"
    lie = p["lie"]
    hy = 14.5 if lie else 12.5

    # bulb
    by = 9.5 if lie else 7
    cv.paint(poly([(9.5, by - 3), (12, by - 7.5), (14.5, by - 3)]), L, halo=K)
    cv.paint(ell(12, by, 7.5, 6), L, halo=K, rim=Ld)
    for y in range(int(by) - 4, int(by) + 5):
        sh = 3.6 * math.sin(math.pi * (y - (by - 5)) / 10.5)
        for sgn in (-1, 1):
            cv.put(int(round(12 + sgn * sh - (0.5 if sgn < 0 else -0.5) * 0)), y, Ld)
    for q in ell(9.5, by - 2, 1.6, 1.2):
        cv.px[q] = Ll

    if lie:
        cv.paint(ell(12, 20, 10.5, 3.6), G, halo=K, rim=Gd)
    else:
        cv.paint(ell(12, 18, 9.5, 5.6), G, halo=K, rim=Gd)
        for cx, cy, rx, ry in ((7.5, 16.5, 1.7, 1.2), (16, 19.5, 1.9, 1.3), (11, 21.5, 1.4, .8)):
            for q in ell(cx, cy, rx, ry):
                cv.px[q] = Sp
        for cx in (6, 18):
            cv.paint(ell(cx, 21.5, 3.4, 2.4), G, halo=K, rim=Gd)
        for x in (4, 6, 8, 15, 17, 19):
            cv.put(x, 23, WHITE)

    # ears
    ear = p["ear"]
    tip = [(1.5, hy - 9.5), (-.5, hy - 6), (-1, hy - 2)][ear]
    left = [(3.2, hy + .5), tip, (10, hy - 5)]
    for pts in (left, mir(left)):
        cv.paint(poly(pts), G, halo=K, rim=Gd)
        for q in poly(scaled(pts, .5)):
            cv.px[q] = T

    cv.paint(ell(12, hy, 9, 5.8), G, halo=K, rim=Gd)
    for q in ell(8.5, hy - 3.3, 2.8, 1.0):
        cv.px[q] = Gl
    for q in ell(16.5, hy - 3.3, 2.0, 1.0):
        cv.px[q] = Gl

    for cx, cy, rx, ry in ((6.5, hy - 2.2, 1.5, 1.0), (17.5, hy - 2.4, 1.4, 1.0), (12, hy - 4.2, 1.3, .8)):
        for q in ell(cx, cy, rx, ry):
            cv.px[q] = Sp
    ey = int(hy) - (1 if not lie else 0)
    face(cv, p, dict(lx=5, ey=ey, w=3, h=3, mx=12, my=int(hy) + 3, ink=K, iris="#D32F2F",
                     lid=True, lidc=Gd, brow=Gd, mouth=True))
    return cv.px


DRAWERS = {"claude": claude, "eevee": eevee, "bulbasaur": bulbasaur}
BASE = dict(face="open", ear=0, tail=0, lie=False, arm=0, tear=-1, gaze=0)


def draw(pet, **pose):
    p = dict(BASE)
    p.update(pose)
    return DRAWERS[pet](p)


# ----------------------------------------------------------------- overlay glyphs
GLYPHS = {
    "!": ["X", "X", "X", ".", "X"],
    "z": ["XXXXX", "...X.", "..X..", ".X...", "XXXXX"],
    "zs": ["XXX", ".X.", "XXX"],
    "check": ["...X", "..X.", "X.X.", ".X.."],
    "spark": [".X.", "XXX", ".X."],
    "dot": ["X", "X"],
    "heart": [".X.X.", "XXXXX", ".XXX.", "..X.."],
    "heart3": ["X.X", "XXX", ".X."],
    "sweat": [".X.", "XXX", "XXX", ".X."],
    "hand": ["..KKKK..", ".KSSSSKK", "KSSSSSSSK", "KSSSSSSSK", ".KSSSSSK.", "..KKKKK.."],
}
MULTI = {"hand": {"K": "#8A5A3C", "S": "#F6CFA5"}}
