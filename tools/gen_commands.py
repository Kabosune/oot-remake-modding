#!/usr/bin/env python3
"""Find the game's script commands (OneShot*, Query*, Execute*, Seq*, Hold*, Trigger*) in main and write a CSV.

    python3 tools/gen_commands.py work/main.bin symbols/e0f3ccfa-commands.csv

Each command is a C++ class. Its vtable has (counting from the getName() slot as 0):
  slot 0   getName()      returns the command's name string     (this is how the classes are found)
  slot 1   getCategory()  returns "AI", "Sequence", "Logic", ...
  slot 9   parameter binder: registers the command's inputs and outputs
  slot 20  the command itself, for OneShot / Query / Trigger / SeqOneShot / SeqQuery
  slots 10-12  Execute* and Seq* keep their own code here instead (guess: enter / update / leave)
A slot is only written to the CSV when the function there belongs to this class (used by at most 3 vtables);
shared base-class functions are left out.

Command context: the actor a command runs on is [[[cmd + 8] + 8] + 0x1f0] (see f_80853d60).
"""
import csv
import collections
import re
import struct
import sys

BASE = 0x80020000
TEXT_END = 0x3C461D0
RO = (0x3C47000, 0x484C080)
DATA = (0x3C47000, 0x4D46B80)
NAME = re.compile(r"^(OneShot|Query|Execute|Seq|Trigger|Hold|Wait|Is)[A-Z0-9]")


def main():
    img = open(sys.argv[1], "rb").read()

    def cstr(addr):
        o = addr - BASE
        return img[o:img.index(b"\0", o)].decode("latin1")

    def u64(off):
        return struct.unpack_from("<Q", img, off)[0]

    # getters: adrp x0, page ; add x0, x0, #lo ; ret  -> a string in .rodata
    w = struct.unpack_from("<%dI" % (TEXT_END // 4), img, 0)
    getters = {}
    for i in range(len(w) - 2):
        a, b, c = w[i], w[i + 1], w[i + 2]
        if (a & 0x9F00001F) == 0x90000000 and (b & 0xFFC003FF) == 0x91000000 and c == 0xD65F03C0:
            imm = ((((a >> 5) & 0x7FFFF) << 2) | ((a >> 29) & 3))
            if imm & (1 << 20):
                imm -= 1 << 21
            s = ((BASE + i * 4) & ~0xFFF) + (imm << 12) + ((b >> 10) & 0xFFF)
            if RO[0] + BASE <= s < RO[1] + BASE:
                getters[i * 4] = cstr(s)

    # vtable entries pointing at getters (pointers in the image are module offsets until relocated)
    rows = []
    for o in range(DATA[0], DATA[1], 8):
        g = u64(o)
        if g in getters and NAME.match(getters[g]):
            end = next((k for k in range(2, 64) if u64(o + 8 * k) == 0 and u64(o + 8 * k + 8) == 0), None)
            rows.append((getters[g], getters.get(u64(o + 8), ""), o, end))

    use = collections.Counter(u64(o + 8 * k) for _, _, o, end in rows for k in range(2, end or 2))

    def own(o, k, end):
        if end is None or k >= end:
            return ""
        f = u64(o + 8 * k)
        return f"{f + BASE:#x}" if f and use[f] <= 3 else ""

    with open(sys.argv[2], "w", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(["name", "category", "vtable_slot0", "binder_slot9", "main_slot20", "slot10", "slot11", "slot12"])
        for name, cat, o, end in sorted(rows):
            out.writerow([name, cat, f"{o + BASE:#x}", own(o, 9, end), own(o, 20, end),
                          own(o, 10, end), own(o, 11, end), own(o, 12, end)])
    print(f"{len(rows)} commands -> {sys.argv[2]}")


if __name__ == "__main__":
    main()
