#!/usr/bin/env python3
"""Lay an uncompressed NSO (main) out as a flat module image: module offset N = byte N.

    python3 tools/flatten_nso.py <plain main> <main.bin>

The main inside a Switch 2 dump is ZBIC-compressed; make it plain first (see docs/getting-started.md).
Prints the build ID and segment layout so you can check you have the build the symbols are for.
"""
import struct
import sys


def main():
    raw = open(sys.argv[1], "rb").read()
    if raw[:4] != b"NSO0":
        sys.exit("not an NSO")
    flags = struct.unpack_from("<I", raw, 0xC)[0]
    if flags & 0x80:
        sys.exit("this NSO is still ZBIC-compressed: unpack it first")
    if flags & 0x7:
        sys.exit("this NSO is LZ4-compressed: unpack it first")
    segs = [struct.unpack_from("<4I", raw, 0x10 + 0x10 * i) for i in range(3)]
    bss = struct.unpack_from("<I", raw, 0x3C)[0]
    print("build id", raw[0x40:0x54].hex().upper())
    top = max(m + s for _, m, s, _ in segs)
    img = bytearray(top + bss)
    for name, (f, m, s, _) in zip(("text", "ro", "data"), segs):
        print(f"{name:5} {m:#010x}..{m + s:#010x}")
        img[m:m + s] = raw[f:f + s]
    print(f"bss   {top:#010x}..{top + bss:#010x}")
    open(sys.argv[2], "wb").write(img)


if __name__ == "__main__":
    main()
