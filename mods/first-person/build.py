#!/usr/bin/env python3
"""Build the First Person mod (exefs IPS32 for main build E0F3CCFA).

    python3 mods/first-person/build.py                          # releases/first-person.zip
    python3 mods/first-person/build.py --verify-main main.bin   # also check against your own main
    python3 mods/first-person/build.py --forward 0.25 --height-add 0.1

main.bin is a flat image of main (tools/flatten_nso.py makes one from an uncompressed main).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools"))
import nxpatch  # noqa: E402

TITLE_ID = "0400486024DEC000"
BUILD_ID = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
CAVE = 0x3C46B00   # module offset; see docs/memory-map.md for who uses which part of the padding
HOOKS = [
    # (site, original instruction, cave entry)
    (0x804E5068, 0xF9401268, "fp_view_hook"),    # ldr x8, [x19, #0x20]
    (0x82C41720, 0x910CA277, "fp_actor_hook"),   # add x23, x19, #0x328
]
README = """First Person (Ocarina of Time, Switch 2, main build E0F3CCFA)

Press R3 (click the right stick) to switch first person on or off.
Right stick looks around, left stick walks, everything else is the game's own.
Keyboard (turn on the emulator's keyboard emulation): ',' eye down, '.' eye up, '/' back to 0,
';' show / hide Link while in first person (Link is hidden by default).
Each press moves the eye 2 cm. The offset stays until you restart the game.
Source and notes: see the repository this came from.
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--verify-main", type=Path, help="flat main image to check the patched bytes against")
    p.add_argument("--forward", type=float, default=0.15, help="metres in front of Link's eyes (default 0.15)")
    p.add_argument("--height-add", type=float, default=0.0, help="added to the measured eye height (default 0)")
    p.add_argument("--height-min", type=float, default=0.4)
    p.add_argument("--height-max", type=float, default=2.2)
    p.add_argument("--height-fixed", type=float, help="use this eye height instead of measuring it at toggle")
    p.add_argument("--toggle-bit", type=int, default=5, help="Npad button bit (5 = R3, 4 = L3)")
    p.add_argument("--stale-limit", type=int, default=30, help="views without a Link update before pausing")
    p.add_argument("--height-step", type=float, default=0.02, help="metres per ',' / '.' press (default 0.02)")
    p.add_argument("--no-height-keys", action="store_true", help="leave out the keyboard keys")
    p.add_argument("--no-hide", action="store_true", help="leave out hiding Link (he stays visible, no ';')")
    p.add_argument("--diagnostic", action="store_true",
                   help="when Link isn't found, use the camera's look-at point as the eye (for testing the hooks)")
    p.add_argument("--name", default="First Person", help="mod folder name inside the zip")
    p.add_argument("--out", type=Path, default=REPO / "releases" / "first-person.zip")
    a = p.parse_args()

    defines = {
        "FORWARD": a.forward, "HEIGHT_ADD": a.height_add, "HEIGHT_MIN": a.height_min, "HEIGHT_MAX": a.height_max,
        "HEIGHT_FIXED": a.height_fixed if a.height_fixed is not None else 0.0,
        "FIXED_HEIGHT": 1 if a.height_fixed is not None else 0,
        "TOGGLE_BIT": a.toggle_bit, "STALE_LIMIT": a.stale_limit,
        "FALLBACK_TARGET": 1 if a.diagnostic else 0,
        "HEIGHT_KEYS": 0 if a.no_height_keys else 1, "HEIGHT_STEP": a.height_step,
        "HIDE_LINK": 0 if a.no_hide else 1,
    }
    records, size = nxpatch.build(HERE / "first_person.S", REPO / "symbols" / "e0f3ccfa.ld", CAVE, HOOKS, defines)
    if a.verify_main:
        nxpatch.verify(records, a.verify_main)
        print("verified against", a.verify_main)
    patch = nxpatch.ips32(records)
    nxpatch.write_zip(a.out, TITLE_ID, a.name, BUILD_ID, patch, README, HERE / "mod.toml")
    print(f"cave {CAVE:#x}..{CAVE + size:#x} ({size} bytes), {len(HOOKS)} hooks -> {a.out}")


if __name__ == "__main__":
    main()
