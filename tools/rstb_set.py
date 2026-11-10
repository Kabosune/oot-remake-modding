#!/usr/bin/env python3
"""Raise entries in the game's resource size table. See docs/romfs.md.

    python3 tools/rstb_set.py <in.rsizetable[.zs]> <out.rsizetable.zs> <path>=<size> | <path>=+<extra> ...

<path> is the romfs path without .zs, e.g. AS/Dm_Zora_0010_KingZora.root.asb=+1024
The table (System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs, from your own dump)
says how much memory the game sets aside to load each file, so a file that grows needs a bigger entry.
The output goes at the same path in a romfs mod. It is a changed copy of a game file: don't put it in this
repository. Only needs: pip install zstandard
"""
import struct
import sys
import zlib

import zstandard


def load(path):
    data = open(path, "rb").read()
    if data[:4] == b"\x28\xb5\x2f\xfd":
        data = zstandard.ZstdDecompressor().decompress(data, max_output_size=1 << 28)
    return bytearray(data)


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    table = load(sys.argv[1])
    if table[:6] != b"RESTBL" or struct.unpack_from("<I", table, 6)[0] != 1:
        sys.exit("not a RESTBL version 1 file")
    name_size, n_hashed, n_named = struct.unpack_from("<III", table, 10)
    if len(table) != 22 + 8 * n_hashed + (name_size + 4) * n_named:
        sys.exit("unexpected table size")
    where = {struct.unpack_from("<I", table, 22 + 8 * i)[0]: 22 + 8 * i + 4 for i in range(n_hashed)}
    for arg in sys.argv[3:]:
        path, value = arg.rsplit("=", 1)
        at = where.get(zlib.crc32(path.encode()))
        if at is None:
            sys.exit(f"{path}: not in the table's hashed entries")
        old = struct.unpack_from("<I", table, at)[0]
        new = (old + int(value[1:]) if value[0] == "+" else int(value)) + 7 & ~7
        if new < old:
            sys.exit(f"{path}: {new} is below the game's {old}")
        struct.pack_into("<I", table, at, new)
        print(f"{path}: {old} -> {new}")
    packed = zstandard.ZstdCompressor(level=19, write_content_size=True).compress(bytes(table))
    assert zstandard.ZstdDecompressor().decompress(packed) == bytes(table)
    open(sys.argv[2], "wb").write(packed)
    print("wrote", sys.argv[2], len(packed), "bytes")


if __name__ == "__main__":
    main()
