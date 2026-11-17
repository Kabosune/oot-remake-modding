#!/usr/bin/env python3
"""Port a symbol pack from one build of main to another: a draft of symbols/<build>.toml.

    python3 tools/port_pack.py symbols/e0f3ccfa.toml <main.bin of that build> <main.bin of the other build> \\
        --version 1.0.0 --out draft.toml

Both main.bin files are flat module images (tools/flatten_nso.py, or an emulator's "dump decompressed
NSOs" file minus its 0x100-byte header). Needs numpy. Writes no game bytes, only offsets.

How each kind is found in the other build:

- functions and hook points: their first instructions, with every address in them masked (branch
  targets, adrp pages, literal loads, and the low 12 bits of an add / ldr / str right after an
  adrp), searched in the other build's code. One match = the answer. Struct offsets inside the
  instructions are not masked, so a match also means that code uses the same field offsets.
  No match or several: the function is found through its callers instead (each caller's own code
  is matched, then its bl / b is read). A hook point's instruction must be the same word in both.
- globals: the code that loads them (adrp + add / ldr) is matched and the address read from it.
- vtables: the function pointers in them are ported and that sequence looked for in the other
  build's data (pointers in main's data are stored in place: its relocations are RELR).
- fields: copied unchanged and marked "not checked".

Every entry gets a `port` line saying how it was found; anything not found is left out with a
comment. Check the draft before using it: a pack entry is a promise to every mod.
"""
import argparse
import collections
import struct
import sys
import tomllib
from pathlib import Path

import numpy as np

ADDR_MASKS = (   # (mask, value, bits to clear): instruction fields that hold addresses
    (0x7C000000, 0x14000000, 0x03FFFFFF),   # b, bl
    (0xFF000010, 0x54000000, 0x00FFFFE0),   # b.cond
    (0x7E000000, 0x34000000, 0x00FFFFE0),   # cbz, cbnz
    (0x7E000000, 0x36000000, 0x0007FFE0),   # tbz, tbnz
    (0x1F000000, 0x10000000, 0x60FFFFE0),   # adr, adrp
    (0x3B000000, 0x18000000, 0x00FFFFE0),   # ldr (literal)
)
WINDOWS = (12, 16, 24, 32, 48, 64)


class Image:
    def __init__(self, path):
        self.bytes = Path(path).read_bytes()
        mod0 = struct.unpack_from("<I", self.bytes, 4)[0]
        assert self.bytes[mod0:mod0 + 4] == b"MOD0", f"{path}: no MOD0 header (not a flat main image?)"
        self.mod0 = mod0
        self.text_end = self.find_text_end()
        self.words = np.frombuffer(self.bytes[:self.text_end], dtype="<u4")
        self.masked = mask(self.words)

    def find_text_end(self):
        # .text is followed by zero padding up to the read-only segment, which starts at a page
        # boundary at or before MOD0's page (MOD0 sits at the start of .rodata in these builds)
        end = self.mod0 & ~0xFFF
        while end > 0 and self.bytes[end - 4:end] == b"\0\0\0\0":
            end -= 4
        return end

    def word(self, offset):
        return struct.unpack_from("<I", self.bytes, offset)[0]

    def qwords(self):
        start = (self.text_end + 0xFFF) & ~0xFFF
        n = (len(self.bytes) - start) // 8
        return start, np.frombuffer(self.bytes[start:start + n * 8], dtype="<u8")


def mask(words):
    out = words.copy()
    for m, v, clear in ADDR_MASKS:
        out[(words & m) == v] &= ~np.uint32(clear)
    adrp = (words & 0x9F000000) == 0x90000000
    rd = np.where(adrp, (words & 0x1F).astype(np.int16), -1)
    rn = ((words >> 5) & 0x1F).astype(np.int16)
    candidate = ((words & 0x7F800000) == 0x11000000) | ((words & 0x3B000000) == 0x39000000)   # add imm; ldr/str imm
    after_adrp = np.zeros(len(words), bool)
    for k in range(1, 7):
        after_adrp |= np.concatenate([np.full(k, -1, np.int16), rd[:-k]]) == rn
    out[candidate & after_adrp] &= ~np.uint32(0x003FFC00)
    return out


def find(masked, pattern):
    c = np.nonzero(masked == pattern[0])[0]
    for i in range(1, len(pattern)):
        c = c[c + i < len(masked)]
        c = c[masked[c + i] == pattern[i]]
        if not len(c):
            break
    return c


def match(src, dst, offset, before=0):
    """offset in dst of the code at src offset, or None. `before`: start the window that many
    instructions earlier (for a spot inside a function)."""
    i = offset // 4 - before
    if i < 0:
        return None
    for n in WINDOWS:
        c = find(dst.masked, src.masked[i:i + n])
        if len(c) == 1:
            return (int(c[0]) + before) * 4
        if not len(c):
            return None
    return None


def branch_target(word, at):
    imm = word & 0x3FFFFFF
    if imm & (1 << 25):
        imm -= 1 << 26
    return at + imm * 4


def via_callers(src, dst, offset, limit=60):
    """Find a function through the b / bl instructions that reach it. Returns (offset, votes, callers)."""
    w = src.words
    is_branch = (w & 0x7C000000) == 0x14000000
    idx = np.nonzero(is_branch)[0]
    imm = (w[idx] & 0x3FFFFFF).astype(np.int64)
    imm = np.where(imm & (1 << 25), imm - (1 << 26), imm)
    callers = idx[(idx + imm) * 4 == offset]
    votes = collections.Counter()
    for c in callers[:limit]:
        for before in (6, 12):
            at = match(src, dst, int(c) * 4, before)
            if at is not None:
                word = dst.word(at)
                if (word & 0x7C000000) == 0x14000000:
                    votes[branch_target(word, at)] += 1
                break
    return votes, len(callers)


def adrp_page(word, at):
    imm = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3)
    if imm & (1 << 20):
        imm -= 1 << 21
    return (at & ~0xFFF) + (imm << 12)


def low12(word):
    """The address bits an add / ldr / str adds to an adrp page, or None."""
    if (word & 0x7F800000) == 0x11000000:
        return (word >> 10) & 0xFFF
    if (word & 0x3B000000) == 0x39000000:
        return ((word >> 10) & 0xFFF) << (word >> 30)
    return None


def references(img, target, limit=40):
    """(adrp index, use index) pairs in img that form the address target."""
    w = img.words
    idx = np.nonzero((w & 0x9F000000) == 0x90000000)[0]
    imm = ((((w[idx] >> 5) & 0x7FFFF).astype(np.int64) << 2) | ((w[idx] >> 29) & 3))
    imm = np.where(imm & (1 << 20), imm - (1 << 21), imm)
    pages = ((idx.astype(np.int64) * 4) & ~0xFFF) + (imm << 12)
    out = []
    for i in idx[pages == (target & ~0xFFF)]:
        rd = int(w[i]) & 0x1F
        for j in range(i + 1, min(i + 8, len(w))):
            word = int(w[j])
            if (word >> 5) & 0x1F != rd:
                continue
            if low12(word) == target & 0xFFF:
                out.append((int(i), j))
            break
        if len(out) >= limit:
            break
    return out


def port_address(src, dst, target):
    """A global's offset in dst, by matching the code that loads it. (offset, votes, references)."""
    votes = collections.Counter()
    refs = references(src, target)
    for i, j in refs:
        for before in (6, 10):
            at = match(src, dst, i * 4, before)
            if at is not None:
                k = at // 4
                lo = low12(int(dst.words[k + (j - i)]))
                if lo is not None and (int(dst.words[k]) & 0x9F000000) == 0x90000000:
                    votes[adrp_page(int(dst.words[k]), k * 4) + lo] += 1
                break
    return votes, len(refs)


def port_vtable(src, dst, offset, entries=12):
    """A vtable's offset in dst: port its function pointers and look for them in dst's data."""
    ptrs = [struct.unpack_from("<Q", src.bytes, offset + 8 * n)[0] for n in range(entries)]
    ported = [(n, match(src, dst, p)) for n, p in enumerate(ptrs) if 0 < p < src.text_end]
    ported = [(n, p) for n, p in ported if p is not None]
    start, q = dst.qwords()
    votes = collections.Counter()
    for n, p in ported:
        for at in np.nonzero(q == p)[0]:
            votes[start + (int(at) - n) * 8] += 1
    return votes, len(ported)


def hexs(n):
    return f"0x{n:X}"


def port_pack(pack, src, dst, version):
    lines = []
    out = lines.append
    nnmain = match(src, dst, pack["detect"]["nnmain"])
    out(f'# KaeGae symbol pack for main build <BUILD ID> (game version {version}).')
    out(f'# Draft written by tools/port_pack.py from {pack["path"].name} ({pack["version"]}). Check it before use.')
    out("")
    out('build   = "<BUILD ID>"')
    out(f'version = "{version}"')
    out("")
    out("[detect]")
    out(f"nnmain = {hexs(nnmain) if nnmain is not None else '0  # NOT FOUND'}")
    out(f"mod0   = {hexs(dst.mod0)}")
    out(f"size   = {hexs(len(dst.bytes))}")
    out("")
    out("[core]")
    out("hook-slots = 0  # FILL IN: a free spot in .bss nothing in the game uses")
    out('hook-code  = ""  # FILL IN: free space after .text for Core\'s hook stubs ("start..end")')
    found = missing = 0
    for name, e in pack.get("hookpoint", {}).items():
        site = e["site"]
        at = None
        for before in (0, 4, 8):
            at = match(src, dst, site, before)
            if at is not None:
                break
        out("")
        if at is None or dst.word(at) != src.word(site):
            out(f'# [hookpoint."{name}"]: NOT FOUND ({hexs(site)} in {pack["version"]})')
            missing += 1
            continue
        found += 1
        out(f'[hookpoint."{name}"]')
        out(f"site     = {hexs(at)}")
        out(f'slot     = {e["slot"]}')
        for key in ("stub",):
            if key in e:
                out(f'{key}     = "{e[key]}"')
        out(f"replaces = 0x{dst.word(at):08X}")
        out(f'context  = "{e.get("context", "")}"')
        out(f'port     = "matched ({pack["version"]} {hexs(site)})"')
    for kind in ("function", "global", "vtable"):
        for name, e in pack.get(kind, {}).items():
            off, how, at = e["offset"], "", None
            if kind == "function":
                at = match(src, dst, off)
                how = "matched"
                if at is None:
                    votes, n = via_callers(src, dst, off)
                    if votes and len(votes) == 1:
                        at, count = votes.most_common(1)[0]
                        how = f"through {count} of {n} callers"
            elif kind == "global":
                votes, n = port_address(src, dst, off)
                if votes and len(votes) == 1:
                    at, count = votes.most_common(1)[0]
                    how = f"from {count} of {n} references, all agreeing"
            else:
                votes, n = port_vtable(src, dst, off)
                best = votes.most_common(2)
                # nearly every ported pointer agrees (vtables of related classes share some functions)
                if best and best[0][1] >= max(2, n - 1) and (len(best) == 1 or best[0][1] > best[1][1]):
                    at = best[0][0]
                    how = f"{best[0][1]} of {n} ported pointers"
            out("")
            if at is None:
                out(f"# [{kind}.{name}]: NOT FOUND ({hexs(off)} in {pack['version']}): find it by hand")
                missing += 1
                continue
            found += 1
            out(f"[{kind}.{name}]")
            out(f"offset = {hexs(at)}")
            if kind == "function" and "alias" in e:
                out(f'alias  = "f_{0x80020000 + at:08x}"')
            for key in ("args", "ld", "note"):
                if key in e:
                    out(f"{key:<6} = " + toml_string(e[key]))
            out(f'port   = "{how} ({pack["version"]} {hexs(off)})"')
    for name, e in pack.get("field", {}).items():
        out("")
        out(f'[field."{name}"]')
        out(f"offset = {hexs(e['offset'])}")
        if "type" in e:
            out(f'type   = "{e["type"]}"')
        out(f'port   = "same as {pack["version"]}, not checked"')
    return "\n".join(lines) + "\n", found, missing


def toml_string(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pack", type=Path, help="the symbol pack to port (symbols/<build>.toml)")
    p.add_argument("src", type=Path, help="flat main image of the pack's build")
    p.add_argument("dst", type=Path, help="flat main image of the build to port to")
    p.add_argument("--version", required=True, help="game version of the build to port to, e.g. 1.0.0")
    p.add_argument("--out", type=Path, help="draft pack to write (default: print it)")
    a = p.parse_args(argv)
    pack = tomllib.loads(a.pack.read_text())
    pack["path"] = a.pack
    text, found, missing = port_pack(pack, Image(a.src), Image(a.dst), a.version)
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)
    print(f"{found} entries found, {missing} not found", file=sys.stderr)


if __name__ == "__main__":
    main()
