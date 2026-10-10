import struct
import zlib

import pytest

from claude_pet.art import png
from pngutil import chunk, make_png

W, H = 5, 4


def test_write_then_read_roundtrip():
    rgba = bytes(v for y in range(H) for x in range(W) for v in (x * 10, y * 20, 99, 255 if (x + y) % 2 else 0))
    data = png.write_png(W, H, rgba)
    assert png.read_png(data) == (W, H, rgba)
    assert png.read_size(data) == (W, H)


@pytest.mark.parametrize("filter_type", [0, 1, 2, 3, 4])
def test_all_scanline_filters(filter_type):
    rows = [bytes((x * 31 + y * 17 + c * 5) & 255 for x in range(W) for c in range(4)) for y in range(H)]
    w, h, rgba = png.read_png(make_png(W, H, 6, 8, rows, filter_type=filter_type))
    assert rgba == b"".join(rows)


def test_rgb_8bit_gets_opaque_alpha():
    rows = [bytes(v for x in range(W) for v in (x, 2 * x, 3 * x)) for _ in range(H)]
    _, _, rgba = png.read_png(make_png(W, H, 2, 8, rows))
    assert rgba[:8] == bytes((0, 0, 0, 255, 1, 2, 3, 255))


def test_palette_4bit_with_transparency():
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    # indices 0,1,2,0,1 packed two per byte: 0x01 0x20 0x10
    rows = [bytes((0x01, 0x20, 0x10)) for _ in range(H)]
    _, _, rgba = png.read_png(make_png(W, H, 3, 4, rows, palette=palette, trns=bytes((255, 0))))
    px = [tuple(rgba[i * 4:i * 4 + 4]) for i in range(W)]
    assert px == [(255, 0, 0, 255), (0, 255, 0, 0), (0, 0, 255, 255), (255, 0, 0, 255), (0, 255, 0, 0)]


def test_grayscale_1bit_and_gray_alpha():
    rows = [bytes((0b10101000,)) for _ in range(H)]
    _, _, rgba = png.read_png(make_png(W, H, 0, 1, rows))
    assert [rgba[i * 4] for i in range(W)] == [255, 0, 255, 0, 255]
    rows = [bytes(v for x in range(W) for v in (x * 50, 200)) for _ in range(H)]
    _, _, rgba = png.read_png(make_png(W, H, 4, 8, rows))
    assert tuple(rgba[4:8]) == (50, 50, 50, 200)


def test_16bit_rgba_keeps_the_high_byte():
    rows = [bytes(v for x in range(W) for v in (200, 7, 100, 8, 50, 9, 255, 255)) for _ in range(H)]
    _, _, rgba = png.read_png(make_png(W, H, 6, 16, rows))
    assert tuple(rgba[:4]) == (200, 100, 50, 255)


def test_rejects_interlaced_and_says_why():
    rows = [bytes(W * 4) for _ in range(H)]
    with pytest.raises(png.PngError, match="interlaced"):
        png.read_png(make_png(W, H, 6, 8, rows, interlace=1))


def test_rejects_garbage_truncation_and_bad_checksums():
    good = make_png(W, H, 6, 8, [bytes(W * 4) for _ in range(H)])
    with pytest.raises(png.PngError, match="not a PNG"):
        png.read_png(b"GIF89a....")
    with pytest.raises(png.PngError):
        png.read_png(good[:-20])
    corrupt = bytearray(good)
    corrupt[20] ^= 0xFF                                    # inside IHDR
    with pytest.raises(png.PngError, match="checksum"):
        png.read_png(bytes(corrupt))


def test_decompression_bomb_is_refused_before_inflating():
    header = struct.pack(">IIBBBBB", 60000, 60000, 8, 6, 0, 0, 0)
    evil = png.SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(1000))) + chunk(b"IEND", b"")
    with pytest.raises(png.PngError, match="too large"):
        png.read_png(evil)


def test_short_image_data_is_an_error_not_a_crash():
    header = struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)
    short = png.SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(10))) + chunk(b"IEND", b"")
    with pytest.raises(png.PngError):
        png.read_png(short)
