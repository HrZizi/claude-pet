"""Turns a sprite pack + (state, tick) into one frame of pixels.

For every state the pack either supplies an animation (a strip of frames) or the engine derives one from the
pack's `idle` animation: it adds motion (shake, hop, wobble) and effect glyphs (zzz, typing dots, hearts, sparkles,
sweat, a petting hand). Packs that draw everything themselves set `"effects": false` (the built-in pets do).

No Tk in here, so it is unit-testable and also drives the README GIFs.
"""
from . import glyphs

KEY = "#010203"          # colour treated as transparent by the Windows window
PAD_X, PAD_TOP = 4, 8    # room around the frame for shaking, hopping and effect glyphs (packs with effects only)

COLORS = {
    "work": "#4FC3F7", "attn": "#FF5252", "good": "#4CAF50", "gold": "#FFD54F",
    "sleep": "#90A4AE", "heart": "#FF6B9D", "sweat": "#7FD1FF",
}


def pads(pack):
    return (PAD_X, PAD_TOP) if pack.uses_effects else (0, 0)


def grid_size(pack):
    px, pt = pads(pack)
    return pack.frame_w + 2 * px, pack.frame_h + pt


def _motion(state, t):
    """(dx, dy, mirror) the engine adds when a state has no animation of its own."""
    if state == "attention":
        return (1 if t % 2 else -1), 0, False
    if state == "celebrate":
        return 0, (0, 2, 3, 3, 2, 0)[t % 6], (t // 6) % 2 == 1
    if state == "wants":
        return 0, (1 if (t // 4) % 3 == 0 else 0), False
    if state == "petted":
        return (1 if (t // 3) % 2 else 0), 0, False
    return 0, 0, False


def _hearts(t, n, speed):
    out = []
    for i in range(n):
        ph = (t // speed + i * (12 // n)) % 12
        out.append(("heart" if i % 2 == 0 else "heart3", 4 + i * 7 + (ph % 3), -ph // 2 - 1, COLORS["heart"]))
    return out


def _effects(state, t):
    """Effect glyphs as (glyph, x, y, colour): x from the sprite's left edge (24 px reference), y from its top."""
    ov = []
    if state == "sleep":
        ph = (t // 5) % 6
        ov.append(("zs", 17 + ph // 2, -1 - ph, COLORS["sleep"]))
        ph2 = (t // 5 + 3) % 6
        ov.append(("z", 19 + ph2 // 2, -3 - ph2, COLORS["sleep"]))
    elif state == "working":
        for i in range(3):
            if (t // 4) % 4 > i:
                ov.append(("dot", 18 + i * 3, -3, COLORS["work"]))
    elif state == "attention":
        ov.append(("sweat", 19, 1, COLORS["sweat"]))
        if (t // 4) % 2:
            ov.append(("!", 21, -5, COLORS["attn"]))
    elif state == "celebrate":
        sp = COLORS["gold"]
        ov += [("spark", 20 if t % 2 else 1, -4 + t % 3, sp), ("spark", 3 if t % 2 else 21, -2 + (t + 1) % 3, sp)]
        ov.append(("check", 11, -5, COLORS["good"]))
    elif state == "wants":
        ov += _hearts(t, 2, 4)
        ov.append(("spark", 18 + (t // 6) % 2, -1, COLORS["gold"]))
    elif state == "petted":
        stroke = (-3, -1, 1, 3, 1, -1)[t % 6]
        ov.append(("hand", 7 + stroke, -3, None))
        ov += _hearts(t, 3, 2)
    return ov


def pose(pack, state, tick):
    """Hashable description of one frame: (frames used, frame index, dx, dy, mirror, effects)."""
    anim = pack.states.get(state)
    derived = anim is None
    base = anim or pack.states["idle"]
    idx = (tick // base.hold) % base.count
    motion = base.motion if base.motion is not None else derived
    effects = base.effects if base.effects is not None else pack.effects
    dx, dy, mirror = _motion(state, tick) if motion else (0, 0, False)
    ov = tuple(_effects(state, tick)) if effects else ()
    return (state if not derived else "idle", idx, dx, dy, mirror, ov)


def grid(pack, key):
    """Rows of colour strings ('#rrggbb', or KEY for transparent) for a pose() key."""
    used, idx, dx, dy, mirror, ov = key
    frame = pack.frames(used)[idx]
    px, pt = pads(pack)
    gw, gh = grid_size(pack)
    g = [[KEY] * gw for _ in range(gh)]

    def put(x, y, c):
        if 0 <= x < gw and 0 <= y < gh:
            g[y][x] = c

    top = None
    for y, row in enumerate(frame):
        if mirror:
            row = row[::-1]
        for x, c in enumerate(row):
            if c is not None:
                if top is None:
                    top = y
                put(px + x + dx, pt + y - dy, c)
    top = top or 0
    shift = (pack.frame_w - 24) // 2                 # glyph positions are laid out for a 24 px wide sprite
    for name, ox, oy, color in ov:
        multi = glyphs.MULTI.get(name)
        for j, r in enumerate(glyphs.GLYPHS[name]):
            for i, ch in enumerate(r):
                if ch != ".":
                    put(px + shift + ox + i, pt + top + oy + j - dy, multi[ch] if multi else color)
    return g
