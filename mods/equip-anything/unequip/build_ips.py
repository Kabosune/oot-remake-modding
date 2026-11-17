#!/usr/bin/env python3
"""Build Equip Anything's unequip patch: exefs/E0F3CCFA....ips (game 1.1.1).

    python3 mods/equip-anything/unequip/build_ips.py <out folder>

Needs clang, ld.lld, llvm-objcopy. The cave and the padding slot are from registry/e0f3ccfa.toml.
"""
import subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import nxpatch  # noqa: E402

BUILD = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
SITE, SITE_ORIG = 0xA7ACD4, 0xD10603FF   # sub sp, sp, #0x180 (equip's second instruction)
CAVE = 0x3C461D0                          # 48 bytes of .text padding before Lichii's claim
PIECE = 0x177D208                         # a 24-byte padding slot (symbols/e0f3ccfa-slots.txt)


def main():
    out = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as w:
        w = Path(w)
        nxpatch.run("clang", "--target=aarch64-none-elf", "-march=armv8.3-a", "-c", HERE / "unequip.S", "-o", w / "u.o")
        (w / "l.ld").write_text(
            f"EQUIP_CONT = {nxpatch.BASE + SITE + 4:#x}; IS_EQUIPPED = {nxpatch.BASE + 0xA71080:#x}; UNEQUIP = {nxpatch.BASE + 0x33A6A40:#x};\n"
            f"SECTIONS {{ . = {nxpatch.BASE + PIECE:#x}; .piece : {{ *(.text.piece) }}\n"
            f". = {nxpatch.BASE + CAVE:#x}; .cave : {{ *(.text.cave) }} }}\n")
        nxpatch.run("ld.lld", "-e", "0", "-T", w / "l.ld", w / "u.o", "-o", w / "u.elf")
        cave = w / "cave.bin"; piece = w / "piece.bin"
        nxpatch.run("llvm-objcopy", "-O", "binary", "-j", ".cave", w / "u.elf", cave)
        nxpatch.run("llvm-objcopy", "-O", "binary", "-j", ".piece", w / "u.elf", piece)
        c, p = cave.read_bytes(), piece.read_bytes()
    assert len(c) <= 48 and len(p) <= 24, (len(c), len(p))
    hook = nxpatch.b_word(nxpatch.BASE + SITE, nxpatch.BASE + CAVE).to_bytes(4, "little")
    records = [(SITE, hook, SITE_ORIG.to_bytes(4, "little")), (CAVE, c, None), (PIECE, p, None)]
    (out / "exefs").mkdir(parents=True, exist_ok=True)
    (out / "exefs" / f"{BUILD}.ips").write_bytes(nxpatch.ips32(records))
    print(f"cave {len(c)} bytes, piece {len(p)} bytes, wrote {out}/exefs/{BUILD}.ips")


if __name__ == "__main__":
    main()
