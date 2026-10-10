"""Helpers for building PNGs and sprite packs in tests."""
import json
import struct
import zlib
from pathlib import Path

from claude_pet.art import png


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)


def chunk(typ, body):
    return struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)


def make_png(w, h, ctype, depth, rows, palette=None, trns=None, filter_type=0, interlace=0):
    """rows: list of already bit-packed scanlines (bytes). Applies the given PNG filter to every row."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, channels * depth // 8)
    raw, prev = b"", bytes(len(rows[0]))
    for line in rows:
        out = bytearray()
        for i, b in enumerate(line):
            a = line[i - bpp] if i >= bpp else 0
            up = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            pred = {0: 0, 1: a, 2: up, 3: (a + up) >> 1, 4: paeth(a, up, c)}[filter_type]
            out.append((b - pred) & 255)
        raw += bytes([filter_type]) + bytes(out)
        prev = line
    data = png.SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, interlace))
    if palette:
        data += chunk(b"PLTE", b"".join(bytes(p) for p in palette))
    if trns is not None:
        data += chunk(b"tRNS", trns)
    return data + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def rgba_strip(frames):
    """frames: list of (w, h, fn(x, y) -> (r, g, b, a)) all the same size -> (w*n, h, rgba bytes)."""
    w, h = frames[0][0], frames[0][1]
    out = bytearray(w * len(frames) * h * 4)
    for f, (_, _, fn) in enumerate(frames):
        for y in range(h):
            for x in range(w):
                i = (y * w * len(frames) + f * w + x) * 4
                out[i:i + 4] = bytes(fn(x, y))
    return w * len(frames), h, bytes(out)


def solid(color, w=8, h=8, shape=None):
    """A frame description: `color` everywhere (or only where shape(x, y) is true), transparent elsewhere."""
    def fn(x, y):
        return (color + (255,)) if (shape is None or shape(x, y)) else (0, 0, 0, 0)
    return (w, h, fn)


def write_pack(root, states, frame=(8, 8), name="Test Pet", effects=True, extra=None, manifest_states=None):
    """states: {state: [frame, ...]} (frames from solid()). Writes <root>/pack.json and one PNG strip per state."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    ms = {}
    for state, frames in states.items():
        w, h, rgba = rgba_strip(frames)
        (root / (state + ".png")).write_bytes(png.write_png(w, h, rgba))
        ms[state] = {"file": state + ".png", "fps": 8}
    manifest = {"format": 1, "name": name, "frame": list(frame), "effects": effects,
                "states": manifest_states if manifest_states is not None else ms}
    manifest.update(extra or {})
    (root / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root
