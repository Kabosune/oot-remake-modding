#!/usr/bin/env python3
"""Pack a linked module (ELF with three PT_LOAD segments: code, read-only data, data + bss)
into an NSO, the format of the files in a game's exefs.

    python3 tools/mknso.py module.elf subsdk1

The segments are stored uncompressed, with their SHA-256 hashes.
"""
import hashlib
import struct
import sys


def segments(elf):
    assert elf[:4] == b"\x7fELF" and elf[4] == 2 and elf[5] == 1, "not a 64-bit little-endian ELF"
    phoff, = struct.unpack_from("<Q", elf, 0x20)
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x36)
    loads = []
    for i in range(phnum):
        p_type, flags, offset, vaddr, _, filesz, memsz, _ = struct.unpack_from("<IIQQQQQQ", elf, phoff + i * phentsize)
        if p_type == 1:
            loads.append((flags, vaddr, elf[offset:offset + filesz], memsz))
    assert [f for f, *_ in loads] == [5, 4, 6], "expected code (r-x), read-only (r--) and data (rw-) segments"
    return loads


def build_id(elf):
    """The GNU build ID note's bytes, or zeros."""
    i = elf.find(b"\x03\x00\x00\x00GNU\x00")     # note type 3 (NT_GNU_BUILD_ID), name "GNU"
    if i < 8:
        return bytes(0x20)
    namesz, descsz = struct.unpack_from("<II", elf, i - 8)
    return elf[i + 8:i + 8 + descsz][:0x20].ljust(0x20, b"\0")


def pack(elf):
    (_, tv, text, _), (_, rv, ro, _), (_, dv, data, dmem) = segments(elf)
    for v in (tv, rv, dv):
        assert v % 0x1000 == 0, "segments must be page-aligned"
    assert tv == 0
    off = 0x100
    header = bytearray(0x100)
    struct.pack_into("<4sIII", header, 0, b"NSO0", 0, 0, 0x38)             # flags: check the three hashes
    for i, (vaddr, blob, extra) in enumerate(((tv, text, 1), (rv, ro, 1), (dv, data, dmem - len(data)))):
        struct.pack_into("<IIII", header, 0x10 + 0x10 * i, off, vaddr, len(blob), extra)   # extra: alignment / bss size
        struct.pack_into("<I", header, 0x60 + 4 * i, len(blob))            # stored size
        header[0xA0 + 0x20 * i:0xC0 + 0x20 * i] = hashlib.sha256(blob).digest()
        off += len(blob)
    header[0x40:0x60] = build_id(elf)
    return bytes(header) + text + ro + data


if __name__ == "__main__":
    out = pack(open(sys.argv[1], "rb").read())
    open(sys.argv[2], "wb").write(out)
    print(f"{sys.argv[2]}: {len(out)} bytes")
