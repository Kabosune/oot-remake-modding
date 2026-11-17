#!/usr/bin/env python3
"""Look inside the game's .bntx textures (Switch 2, platform tag "Ounc"): header info, and the pixels as a PNG.

    python3 tools/bntx.py info <file.bntx>                 texture name, format, size, mips, block height, mip offsets
    python3 tools/bntx.py png  <file.bntx> <out.png>       mip 0 as a PNG (needs: pip install texture2ddecoder pillow numpy)

<file> must be unpacked already (tools/zstool.py x, or zsmod.unzs). Read-only.

Layout (checked 17 Nov 2026 on the stone block's textures, Stone_SacredForest_Prop_A_06_Alb / _Rgh):
- One texture per file, its info block (BRTI) at 0x208: mips u16 at +0x16, format u32 at +0x1C (the Switch 1 codes
  fit the sizes: 0x3206 ASTC 8x5 sRGB, 0x2F01 ASTC 5x5, 0x1D01 BC4), width / height at +0x24 / +0x28, block height
  as log2 of GOBs at +0x34, image size at +0x50, offset of the mip offset table (u64 file offsets) at +0x70.
- Pixels are block-linear in 64-byte x 8-row GOBs, like the Switch 1, **but the GOB's inner order differs**: inside a
  GOB the byte at (x, y) is at x%16 + 16*(y&1) + 32*((y>>1)&1) + 64*((x>>4)&1) + 128*((y>>2)&1) + 256*((x>>5)&1).
  (The Switch 1 order swaps the 32 and 64 terms.) Found by trying every order of those five bits: only this one gives
  continuous pictures, for the ASTC albedo (1-GOB blocks) and the BC4 roughness (16-GOB blocks) alike.
- Each mip's block height is the file's, halved while the mip's rows of blocks fit in half of it (as on the Switch 1).
"""
import struct
import sys

import numpy as np

BRTI = 0x208
FORMATS = {   # high byte of the format: (name, block w, block h, bytes per block)
    0x0B: ("RGBA8", 1, 1, 4), 0x1A: ("BC1", 4, 4, 8), 0x1B: ("BC2", 4, 4, 16), 0x1C: ("BC3", 4, 4, 16),
    0x1D: ("BC4", 4, 4, 8), 0x1E: ("BC5", 4, 4, 16), 0x1F: ("BC6H", 4, 4, 16), 0x20: ("BC7", 4, 4, 16),
    0x2D: ("ASTC 4x4", 4, 4, 16), 0x2E: ("ASTC 5x4", 5, 4, 16), 0x2F: ("ASTC 5x5", 5, 5, 16),
    0x30: ("ASTC 6x5", 6, 5, 16), 0x31: ("ASTC 6x6", 6, 6, 16), 0x32: ("ASTC 8x5", 8, 5, 16),
    0x33: ("ASTC 8x6", 8, 6, 16), 0x34: ("ASTC 8x8", 8, 8, 16),
}


def _gob():
    o = np.zeros((8, 64), np.int64)
    for y in range(8):
        for x in range(64):
            o[y, x] = (x % 16 + 16 * (y & 1) + 32 * ((y >> 1) & 1) + 64 * ((x >> 4) & 1)
                       + 128 * ((y >> 2) & 1) + 256 * ((x >> 5) & 1))
    return o


GOB = _gob()


def address_map(width_bytes, rows, gobs_high):
    """Block-linear byte address of each (row, byte) of a linear image width_bytes x rows."""
    gw = (width_bytes + 63) // 64
    y = np.arange(rows)[:, None]
    x = np.arange(width_bytes)[None, :]
    return ((y // (8 * gobs_high)) * (gw * 512 * gobs_high) + (x // 64) * (512 * gobs_high)
            + ((y % (8 * gobs_high)) // 8) * 512 + GOB[y % 8, x % 64])


def mip_gobs(rows, gobs_high):
    while gobs_high > 1 and rows <= (gobs_high // 2) * 8:
        gobs_high //= 2
    return gobs_high


def deswizzle(data, width_bytes, rows, gobs_high):
    return np.frombuffer(data, np.uint8)[address_map(width_bytes, rows, gobs_high)].tobytes()


def swizzle(linear, width_bytes, rows, gobs_high, size):
    """The inverse, into a buffer of `size` bytes (padding left zero)."""
    out = np.zeros(size, np.uint8)
    out[address_map(width_bytes, rows, gobs_high)] = np.frombuffer(linear, np.uint8).reshape(rows, width_bytes)
    return out.tobytes()


def info(d):
    if d[:4] != b"BNTX" or d[BRTI:BRTI + 4] != b"BRTI":
        raise ValueError("not a one-texture .bntx with BRTI at 0x208")
    mips = struct.unpack_from("<H", d, BRTI + 0x16)[0]
    fmt = struct.unpack_from("<I", d, BRTI + 0x1C)[0]
    w, h = struct.unpack_from("<ii", d, BRTI + 0x24)
    bh = 1 << struct.unpack_from("<I", d, BRTI + 0x34)[0]
    ptrs = struct.unpack_from("<Q", d, BRTI + 0x70)[0]
    offs = [struct.unpack_from("<Q", d, ptrs + 8 * i)[0] for i in range(mips)]
    name_at = struct.unpack_from("<Q", d, BRTI + 0x60)[0]
    n = struct.unpack_from("<H", d, name_at)[0]
    return {"name": d[name_at + 2:name_at + 2 + n].decode(), "format": fmt, "width": w, "height": h, "mips": mips,
            "gobs_high": bh, "mip_offsets": offs, "platform": d[0x20:0x24].decode(errors="replace")}


def mip0_linear(d, t):
    name, bw, bhh, bpb = FORMATS[t["format"] >> 8]
    width_bytes = (t["width"] + bw - 1) // bw * bpb
    rows = (t["height"] + bhh - 1) // bhh
    size = t["mip_offsets"][1] - t["mip_offsets"][0] if t["mips"] > 1 else len(d) - t["mip_offsets"][0]
    return deswizzle(d[t["mip_offsets"][0]:t["mip_offsets"][0] + size], width_bytes, rows,
                     mip_gobs(rows, t["gobs_high"]))


def to_png(d, out):
    import texture2ddecoder as t2d
    from PIL import Image
    t = info(d)
    name, bw, bhh, _ = FORMATS[t["format"] >> 8]
    lin = mip0_linear(d, t)
    w, h = t["width"], t["height"]
    if name.startswith("ASTC"):
        px = t2d.decode_astc(lin, w, h, bw, bhh)
    elif name == "RGBA8":
        px = np.frombuffer(lin, np.uint8).reshape(h, w, 4)[..., [2, 1, 0, 3]].tobytes()
    else:
        px = getattr(t2d, "decode_" + name.lower())(lin, w, h)
    Image.frombytes("RGBA", (w, h), px, "raw", "BGRA").save(out)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("info", "png"):
        sys.exit(__doc__)
    d = open(sys.argv[2], "rb").read()
    if sys.argv[1] == "info":
        t = info(d)
        fmt = FORMATS.get(t["format"] >> 8, ("?",))[0]
        print(f"{t['name']}: {fmt} (0x{t['format']:04x}), {t['width']} x {t['height']}, {t['mips']} mips, "
              f"{t['gobs_high']}-GOB blocks, platform {t['platform']!r}")
        print("mip offsets:", ", ".join(hex(o) for o in t["mip_offsets"]))
    else:
        to_png(d, sys.argv[3])
        print("wrote", sys.argv[3])


if __name__ == "__main__":
    main()
