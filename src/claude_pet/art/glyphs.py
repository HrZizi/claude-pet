"""Small pixel-art effect glyphs the engine draws on top of a pet (zzz, hearts, sparkles, ...).

'X' pixels take the glyph colour; glyphs listed in MULTI use their own palette (letters -> colours).
"""

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
