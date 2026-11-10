#!/usr/bin/env python3
"""Build the input probe (exefs IPS32 for main build E0F3CCFA).

    python3 mods/mouse-grab/probe/build.py                          # releases/mouse-probe.zip
    python3 mods/mouse-grab/probe/build.py --verify-main main.bin   # also check against your own main

A test build, not a mod to play with: it logs the mouse and motion sensor values the game can
read, so we know what an emulator (or a console) feeds it. See mods/mouse-grab/README.md.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO / "tools"))
import nxpatch  # noqa: E402

TITLE_ID = "0400486024DEC000"
BUILD_ID = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
REGIONS = [(0x3C46278, 0x3C46400, [".text.hook", ".text", ".rodata*"])]
SLOTS = REPO / "symbols" / "e0f3ccfa-slots.txt"
FIRST_SLOT = 113   # FPV Drone's code takes slots 0-112
BR_X17 = 0xD61F0220
HOOKS = [
    # the last instruction (br x17) of three import stubs
    (0x83C627EC, BR_X17, "style_wrap"),   # GetNpadStyleSet
    (0x83C628AC, BR_X17, "six_wrap"),     # GetSixAxisSensorStates
    (0x83C6480C, BR_X17, "mouse_wrap"),   # GetMouseStates
]
README = """Mouse probe (Ocarina of Time, Switch 2, main build E0F3CCFA)

A test build for the mouse-grab mod. It changes nothing in the game. Twice a second it writes
a line starting with "MGP" to the emulator's log: the mouse state and the motion sensor state
the game can read. Remove it when the test is done.
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--verify-main", type=Path, help="flat main image to check the patched bytes against")
    p.add_argument("--name", default="Mouse Probe", help="mod folder name inside the zip")
    p.add_argument("--out", type=Path, default=REPO / "releases" / "mouse-probe.zip")
    a = p.parse_args()

    slots = nxpatch.load_slots(SLOTS)[FIRST_SLOT:]
    records, used, nslots = nxpatch.build_regions([HERE / "probe.S", HERE / "probe.c"], REPO / "symbols" / "e0f3ccfa.ld",
                                                  REGIONS, HOOKS, {}, slots)
    if a.verify_main:
        nxpatch.verify(records, a.verify_main)
        nxpatch.verify_slots(slots[:nslots], a.verify_main)
        print("verified against", a.verify_main)
    nxpatch.write_zip(a.out, TITLE_ID, a.name, BUILD_ID, nxpatch.ips32(records), README)
    for start, end, _ in REGIONS:
        print(f"cave {start:#x}..{end:#x}: {used[start]} of {end - start} bytes")
    print(f"code: {nslots} of {len(slots)} free padding slots, {slots[0][0]:#x}..{slots[nslots - 1][0] + slots[nslots - 1][1]:#x}")
    print(f"{len(HOOKS)} hooks -> {a.out}")


if __name__ == "__main__":
    main()
