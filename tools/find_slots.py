#!/usr/bin/env python3
"""List padding slots in a flat main: runs of zero words between functions that mods can fill.

    python3 tools/find_slots.py main.bin                       # summary: best 32 KB windows
    python3 tools/find_slots.py main.bin --window 0x817976a8   # slot list for that window

A slot is a run of zero words (udf #0, the compiler's alignment padding) of at least --min bytes,
right after an instruction that ends the flow (ret, b, br), with no branch, adr / adrp+add or data
pointer anywhere in .text / .rodata / .data aimed into it. Slots of one mod must sit within 32 KB
of each other, the reach of tbz, because nxpatch.split_into_slots chains them with branches.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nxpatch import BASE, TEXT_END, is_terminator  # noqa: E402

DATA = (0x3C47000, 0x4D46B80)   # .rodata + .data


def references(img):
    """Every address in .text that something points at (module offsets)."""
    w = np.frombuffer(img[:TEXT_END], dtype="<u4").astype(np.int64)
    pc = np.arange(len(w), dtype=np.int64) * 4
    out = []

    def signed(v, bits):
        return np.where(v & (1 << (bits - 1)), v - (1 << bits), v)

    m = ((w >> 26) == 0x25) | ((w >> 26) == 0x05)                              # b, bl
    out.append(pc[m] + signed(w[m] & 0x3FFFFFF, 26) * 4)
    m = ((w & 0xFF000010) == 0x54000000) | ((w & 0x7E000000) == 0x34000000)    # b.cond, cbz, cbnz
    out.append(pc[m] + signed((w[m] >> 5) & 0x7FFFF, 19) * 4)
    m = (w & 0x7E000000) == 0x36000000                                          # tbz, tbnz
    out.append(pc[m] + signed((w[m] >> 5) & 0x3FFF, 14) * 4)
    m = (w & 0x9F000000) == 0x10000000                                          # adr
    out.append(pc[m] + signed((((w[m] >> 5) & 0x7FFFF) << 2) | ((w[m] >> 29) & 3), 21))
    adrp = np.nonzero((w & 0x9F000000) == 0x90000000)[0]                        # adrp + add
    for i in adrp.tolist():
        x = int(w[i])
        page = ((i * 4) & ~0xFFF) + (int(signed(np.int64((((x >> 5) & 0x7FFFF) << 2) | ((x >> 29) & 3)), 21)) << 12)
        if not 0 <= page < TEXT_END:
            continue
        for j in range(i + 1, min(i + 17, len(w))):
            y = int(w[j])
            if (y & 0xFFC00000) == 0x91000000 and ((y >> 5) & 31) == (x & 31):
                out.append(np.array([page + ((y >> 10) & 0xFFF)]))
                break
    data = np.frombuffer(img[DATA[0]:DATA[1]], dtype="<u8").astype(np.int64)
    out.append(data[(data > 0) & (data < TEXT_END)])
    out.append(data[(data > BASE) & (data < BASE + TEXT_END)] - BASE)
    return np.unique(np.concatenate(out))


def slots(img, minimum):
    w = np.frombuffer(img[:TEXT_END], dtype="<u4")
    z = np.diff(np.concatenate([[0], (w == 0).astype(np.int8), [0]]))
    starts, ends = np.nonzero(z == 1)[0], np.nonzero(z == -1)[0]
    refs = references(img)
    found = []
    for s, e in zip(starts.tolist(), ends.tolist()):
        if (e - s) * 4 < minimum or s == 0 or not is_terminator(int(w[s - 1])):
            continue
        lo, hi = np.searchsorted(refs, [s * 4, e * 4])
        if hi > lo:
            continue
        found.append((BASE + s * 4, (e - s) * 4))
    return found


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("main", type=Path)
    p.add_argument("--min", type=int, default=16, help="smallest slot, bytes (default 16)")
    p.add_argument("--window", type=lambda v: int(v, 0), help="list the slots in the 32 KB from this address")
    a = p.parse_args()
    found = slots(a.main.read_bytes(), a.min)
    if a.window is not None:
        for address, length in found:
            if a.window <= address and address + length <= a.window + 0x8000:
                print(f"{address:#x} {length}")
        return
    addresses = np.array([f[0] for f in found])
    usable = np.array([f[1] - 4 for f in found])
    sums = np.concatenate([[0], np.cumsum(usable)])
    upto = np.searchsorted(addresses, addresses + 0x8000)
    totals = sums[upto] - sums[np.arange(len(found))]
    print(f"{len(found)} slots of {a.min}+ bytes")
    for k in np.argsort(-totals)[:5]:
        print(f"  window {addresses[k]:#x}: {int(totals[k])} usable bytes")


if __name__ == "__main__":
    main()
