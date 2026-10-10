"""Minimal PNG reader / writer using only the standard library (the runtime has no Pillow).

Reads non-interlaced PNGs of any colour type and bit depth (what pixel-art editors export) into RGBA bytes, and
writes RGBA PNGs. Defensive on purpose: sprite packs are untrusted data, so sizes are checked before inflating.
"""
import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PIXELS = 4_000_000          # decompression-bomb guard (a 2000 x 2000 image)


class PngError(ValueError):
    """The file is not a PNG this reader accepts; the message is meant for the pack author."""


def _chunks(data):
    if data[:8] != SIGNATURE:
        raise PngError("not a PNG file")
    pos = 8
    while pos + 12 <= len(data):
        length, typ = struct.unpack(">I4s", data[pos:pos + 8])
        end = pos + 8 + length
        if end + 4 > len(data):
            raise PngError("truncated PNG file")
        body = data[pos + 8:end]
        if zlib.crc32(typ + body) & 0xFFFFFFFF != struct.unpack(">I", data[end:end + 4])[0]:
            raise PngError("corrupt PNG file (bad checksum)")
        yield typ, body
        pos = end + 4
        if typ == b"IEND":
            return


def _header(data):
    for typ, body in _chunks(data):
        if typ == b"IHDR":
            w, h, depth, ctype, comp, filt, inter = struct.unpack(">IIBBBBB", body)
            return w, h, depth, ctype, comp, filt, inter
        break
    raise PngError("PNG has no header")


def read_size(data):
    """(width, height) without decoding the pixels."""
    w, h = _header(data)[:2]
    return w, h


_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
_DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}


def _unfilter(raw, w, h, rowbytes, bpp):
    rows, prev, pos = [], bytearray(rowbytes), 0
    for _ in range(h):
        ft = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + rowbytes])
        pos += 1 + rowbytes
        if ft == 1:
            for i in range(bpp, rowbytes):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            for i in range(rowbytes):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(rowbytes):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(rowbytes):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        elif ft != 0:
            raise PngError("corrupt PNG file (unknown filter %d)" % ft)
        rows.append(line)
        prev = line
    return rows


def _samples(line, depth, count):
    if depth == 8:
        return line
    if depth == 16:
        return line[0::2]                                   # keep the high byte
    per, mask = 8 // depth, (1 << depth) - 1
    out = []
    for byte in line:
        for k in range(per):
            out.append((byte >> (8 - depth * (k + 1))) & mask)
    return out[:count]


def read_png(data):
    """-> (width, height, rgba) where rgba is bytes of length width * height * 4."""
    w, h, depth, ctype, comp, filt, inter = _header(data)
    if ctype not in _CHANNELS or depth not in _DEPTHS[ctype] or comp or filt:
        raise PngError("unsupported PNG format (colour type %d, %d-bit)" % (ctype, depth))
    if inter:
        raise PngError("interlaced PNGs are not supported: export without interlacing")
    if w < 1 or h < 1 or w * h > MAX_PIXELS:
        raise PngError("image is too large (%d x %d)" % (w, h))
    palette, trns, idat = [], b"", []
    for typ, body in _chunks(data):
        if typ == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body) - 2, 3)]
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
    channels = _CHANNELS[ctype]
    bits = channels * depth
    rowbytes = (w * bits + 7) // 8
    bpp = max(1, bits // 8)
    expected = (1 + rowbytes) * h
    d = zlib.decompressobj()
    try:
        raw = d.decompress(b"".join(idat), expected + 1)
    except zlib.error:
        raise PngError("corrupt PNG file (bad image data)")
    if len(raw) != expected or d.unconsumed_tail:
        raise PngError("corrupt PNG file (unexpected image data size)")
    rows = _unfilter(raw, w, h, rowbytes, bpp)
    maxval = (1 << min(depth, 8)) - 1
    out = bytearray()
    for line in rows:
        if ctype == 6 and depth == 8:
            out += line
            continue
        s = _samples(line, depth, w * channels)
        if ctype == 6:
            for x in range(w):
                out += bytes(s[x * 4:x * 4 + 4])
        elif ctype == 2:
            key = tuple(trns[i * 2] for i in range(3)) if len(trns) == 6 and depth == 8 else None
            for x in range(w):
                px = (s[x * 3], s[x * 3 + 1], s[x * 3 + 2])
                out += bytes(px) + (b"\x00" if px == key else b"\xff")
        elif ctype == 0:
            key = trns[1] if len(trns) == 2 and depth <= 8 else None
            for x in range(w):
                v = s[x]
                g = v * 255 // maxval
                out += bytes((g, g, g)) + (b"\x00" if v == key else b"\xff")
        elif ctype == 4:
            for x in range(w):
                g = s[x * 2] * 255 // maxval
                out += bytes((g, g, g, s[x * 2 + 1] * 255 // maxval if depth < 8 else s[x * 2 + 1]))
        else:                                               # palette
            for x in range(w):
                i = s[x]
                if i >= len(palette):
                    raise PngError("corrupt PNG file (palette index out of range)")
                out += bytes(palette[i]) + bytes((trns[i] if i < len(trns) else 255,))
    return w, h, bytes(out)


def _chunk(typ, body):
    return struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)


def write_png(w, h, rgba):
    """RGBA (bytes, w*h*4) -> PNG file contents. Rows are stored unfiltered, which keeps reading them fast."""
    if len(rgba) != w * h * 4:
        raise ValueError("pixel data does not match the image size")
    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return (SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))
