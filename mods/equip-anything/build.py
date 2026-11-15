#!/usr/bin/env python3
"""Build Equip Anything from your own copy of the game.

    python3 mods/equip-anything/build.py <PouchTable.game__ui__PouchTable.bgyml> <out folder> [--game-table <rsizetable.zs>]

The input is romfs/UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml from your own dump
(game 1.1.1). The output is a mod folder for the emulator's load/0400486024DEC000/ folder:
mod.toml, README.md and romfs/UI/Pouch/PouchTable/... with every item usable by both ages.

The file grows by 424 bytes (14,412 -> 14,836 on 1.1.1). Its size table entry (46,824) is not just
the file: the game builds the menu's objects in the same memory, and 0.1.0 (no table change) crashed
at boot when that ran out (14 Nov). So the entry is raised by the growth plus spare room. With
--game-table (romfs/System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs from
your dump) the changed table is written into the mod folder; without it, run
`python3 tools/kaegae.py build --game-table <that file>` after installing (mod.toml asks for the entry).
"""
import shutil
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import byml  # noqa: E402

ROMFS_PATH = "UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml"
SIZE_ENTRY = 46824          # the game's size table entry for ROMFS_PATH on 1.1.1
SPARE = 2048                # extra room on top of the growth
TABLE_PATH = "System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs"
SKIP = {"NoDisplayArray"}   # items the menu never shows (Deku Seeds, Normal Boots, ...)


def unlock(root):
    """Set IsUsableChild and IsUsableAdult on every item the pause menu shows. Returns how many changed."""
    changed = 0
    for key, buttons in root.items():
        if key in SKIP or not isinstance(buttons, list):
            continue
        for button in buttons:
            if not isinstance(button, dict):
                continue
            for actor in button.get("Actor") or []:
                if not isinstance(actor, dict) or "ActorShort" not in actor:
                    continue
                for flag in ("IsUsableChild", "IsUsableAdult"):
                    if actor.get(flag) is not True:
                        actor[flag] = True
                        changed += 1
    # 0.2.0 test: masks come off when picked again because their button is SpecialDeal: Mask.
    # Give the other equipment buttons (swords, shields, tunics) without a SpecialDeal the same.
    for button in root.get("EquipmentArray") or []:
        if isinstance(button, dict) and "SpecialDeal" not in button:
            button["SpecialDeal"] = "Mask"
            changed += 1
    return changed


def raise_entry(table_zs, path, at_least):
    """The game's size table with path's entry raised to at least at_least bytes (zstd, as the game reads it)."""
    import zstandard
    t = bytearray(zstandard.ZstdDecompressor().decompress(table_zs, max_output_size=1 << 28))
    if t[:6] != b"RESTBL":
        sys.exit("not the game's size table")
    _, n_hashed, _ = struct.unpack_from("<III", t, 10)
    want = zlib.crc32(path.encode())
    for i in range(n_hashed):
        if struct.unpack_from("<I", t, 22 + 8 * i)[0] == want:
            old = struct.unpack_from("<I", t, 26 + 8 * i)[0]
            struct.pack_into("<I", t, 26 + 8 * i, max(old, at_least + 7 & ~7))
            return zstandard.ZstdCompressor(level=19, write_content_size=True).compress(bytes(t)), old
    sys.exit(f"{path} isn't in the size table")


def main():
    args = sys.argv[1:]
    table = None
    if "--game-table" in args:
        i = args.index("--game-table")
        table = Path(args[i + 1]).read_bytes()
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    sys.argv[1:] = args
    src = Path(sys.argv[1]).read_bytes()
    root = byml.loads(src)
    if byml.dumps(root) != src:
        sys.exit("this PouchTable doesn't read back to the same bytes: not the 1.1.1 file?")
    n = unlock(root)
    data = byml.dumps(root)
    need = SIZE_ENTRY + (len(data) - len(src)) + SPARE
    out = Path(sys.argv[2])
    (out / "romfs" / ROMFS_PATH).parent.mkdir(parents=True, exist_ok=True)
    (out / "romfs" / ROMFS_PATH).write_bytes(data)
    for name in ("mod.toml", "README.md"):
        shutil.copy(HERE / name, out / name)
    if table:
        packed, old = raise_entry(table, ROMFS_PATH, need)
        (out / "romfs" / TABLE_PATH).parent.mkdir(parents=True, exist_ok=True)
        (out / "romfs" / TABLE_PATH).write_bytes(packed)
        print(f"size table entry {old} -> {need + 7 & ~7}")
    else:
        print(f"no --game-table: run kaegae build so the size table entry becomes at least {need}")
    print(f"{n} flags set, {len(src)} -> {len(data)} bytes, wrote {out}")


if __name__ == "__main__":
    main()
