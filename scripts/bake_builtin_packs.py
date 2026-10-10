"""Bakes the three built-in pets from their procedural drawing code (scripts/procedural) into ordinary sprite packs:

    python scripts/bake_builtin_packs.py

Writes src/claude_pet/packs/<id>/{pack.json, <state>.png}. The generated files are committed; run this only when you
change the procedural art. Every animation loop is baked at its exact period, so it repeats seamlessly.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "procedural"))

import pose      # noqa: E402
import sprites   # noqa: E402
from claude_pet.art import pack as packmod, png   # noqa: E402

OUT = ROOT / "src" / "claude_pet" / "packs"
FPS = 8
KEY = pose.KEY


def loop_length(pet, state, limit=240):
    """Smallest n so that the animation repeats exactly: pose(t + n) == pose(t) for a long stretch of t."""
    for n in range(1, limit + 1):
        if all(pose.pose(pet, state, t + n) == pose.pose(pet, state, t) for t in range(max(96, 2 * n))):
            return n
    raise SystemExit("%s/%s does not loop within %d frames" % (pet, state, limit))


def rgba_of(grid):
    out = bytearray()
    for row in grid:
        for c in row:
            if c == KEY:
                out += b"\x00\x00\x00\x00"
            else:
                out += bytes((int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), 255))
    return bytes(out)


def bake(pet):
    folder = OUT / pet
    folder.mkdir(parents=True, exist_ok=True)
    states, report = {}, []
    for state in packmod.STATES:
        n = loop_length(pet, state)
        frames = [pose.grid(pose.pose(pet, state, t)) for t in range(n)]
        h, w = len(frames[0]), len(frames[0][0])
        strip = bytearray(w * n * h * 4)
        for f, g in enumerate(frames):
            data = rgba_of(g)
            for y in range(h):
                a = (y * w * n + f * w) * 4
                strip[a:a + w * 4] = data[y * w * 4:(y + 1) * w * 4]
        (folder / (state + ".png")).write_bytes(png.write_png(w * n, h, bytes(strip)))
        states[state] = {"file": state + ".png", "fps": FPS}
        report.append("%s=%d" % (state, n))
    manifest = {
        "format": packmod.FORMAT,
        "name": sprites.PETS[pet]["name"],
        "author": "claude-pet contributors",
        "license": "MIT",
        "description": "Built-in pet, baked from scripts/procedural/sprites.py",
        "frame": [w, h],
        "effects": False,
        "states": states,
    }
    (folder / "pack.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("%-10s frame %dx%d  loops: %s" % (pet, w, h, ", ".join(report)))


if __name__ == "__main__":
    for pet in sprites.PETS:
        bake(pet)
    for pet in sprites.PETS:                                  # prove the result loads
        packmod.validate(OUT / pet)
    print("baked and validated:", ", ".join(sprites.PETS))
