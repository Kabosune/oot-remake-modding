#!/usr/bin/env python3
"""Build Equip Anything from your own copy of the game.

    python3 mods/equip-anything/build.py <PouchTable.game__ui__PouchTable.bgyml> <out folder>

The input is romfs/UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml from your own dump
(game 1.1.1). The output is a mod folder for the emulator's load/0400486024DEC000/ folder:
mod.toml, README.md and romfs/UI/Pouch/PouchTable/... with every item usable by both ages.

The file grows by about 400 bytes (14,412 -> 14,836 on 1.1.1). The game's size table sets aside
46,824 bytes for it, so the size table needs no change.
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import byml  # noqa: E402

ROMFS_PATH = "UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml"
SIZE_ENTRY = 46824          # the game's size table entry for ROMFS_PATH on 1.1.1
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
    return changed


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).read_bytes()
    root = byml.loads(src)
    if byml.dumps(root) != src:
        sys.exit("this PouchTable doesn't read back to the same bytes: not the 1.1.1 file?")
    n = unlock(root)
    data = byml.dumps(root)
    if len(data) > SIZE_ENTRY:
        sys.exit(f"the new file ({len(data)} bytes) is bigger than the game's size table entry ({SIZE_ENTRY})")
    out = Path(sys.argv[2])
    (out / "romfs" / ROMFS_PATH).parent.mkdir(parents=True, exist_ok=True)
    (out / "romfs" / ROMFS_PATH).write_bytes(data)
    for name in ("mod.toml", "README.md"):
        shutil.copy(HERE / name, out / name)
    print(f"{n} flags set, {len(src)} -> {len(data)} bytes, wrote {out}")


if __name__ == "__main__":
    main()
