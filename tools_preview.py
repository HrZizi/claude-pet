"""Dev helper: render a contact sheet of every pet/state to preview.png
usage: python tools_preview.py [scale] [pet ...]"""
import sys
from PIL import Image
import render, sprites

S = int(sys.argv[1]) if len(sys.argv) > 1 else 6
pets = sys.argv[2:] or list(sprites.PETS)
states = [("sleep", 0), ("idle", 5), ("idle", 36), ("working", 0), ("working", 11), ("attention", 2),
          ("celebrate", 2), ("wants", 4), ("petted", 2)]
cw, ch = render.GW * S, render.GH * S
sheet = Image.new("RGB", (cw * len(states), ch * len(pets)), (52, 54, 60))
for r, pet in enumerate(pets):
    for c, (st, t) in enumerate(states):
        g = render.grid(render.pose(pet, st, t))
        for y, row in enumerate(g):
            for x, col in enumerate(row):
                if col != render.KEY:
                    rgb = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
                    for yy in range(S):
                        for xx in range(S):
                            sheet.putpixel((c * cw + x * S + xx, r * ch + y * S + yy), rgb)
sheet.save("preview.png")
