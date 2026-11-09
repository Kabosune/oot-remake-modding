#!/usr/bin/env python3
"""Build the FPV Drone mod (exefs IPS32 for main build E0F3CCFA).

    python3 mods/fpv-drone/build.py                          # releases/fpv-drone.zip
    python3 mods/fpv-drone/build.py --verify-main main.bin   # also check against your own main
    python3 mods/fpv-drone/build.py --uptilt 30 --rate-max 800

main.bin is a flat image of main (tools/flatten_nso.py makes one from an uncompressed main).
"""
import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools"))
import nxpatch  # noqa: E402

TITLE_ID = "0400486024DEC000"
BUILD_ID = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
# The hooks and constants take one gap of the shared code cave; the C code is split over padding
# slots between the game's functions (module offsets; see docs/memory-map.md).
REGIONS = [(0x3C46610, 0x3C46B00, [".text.hook", ".text", ".rodata*"])]
SLOTS = REPO / "symbols" / "e0f3ccfa-slots.txt"
BR_X17 = 0xD61F0220
HOOKS = [
    # (site, original instruction, cave entry)
    (0x804E506C, 0xB4005868, "fpv_view_hook"),   # cbz x8, 0x804e5b78 (after the view matrix)
    (0x82C415E0, 0xD503237F, "fpv_actor_hook"),  # pacibsp (movement update of physics actors)
    # the last instruction (br x17) of each GetNpadStates import stub
    (0x83C627FC, BR_X17, "npad_wrap"),           # JoyDual
    (0x83C6280C, BR_X17, "npad_wrap"),           # FullKey (Pro Controller)
    (0x83C6281C, BR_X17, "npad_wrap"),           # Joy-Con left
    (0x83C6282C, BR_X17, "npad_wrap"),           # Joy-Con right
    (0x83C6283C, BR_X17, "npad_wrap"),           # Handheld
]
BUTTONS = {"a": 0, "b": 1, "x": 2, "y": 3, "l3": 4, "r3": 5, "l": 6, "r": 7, "zl": 8, "zr": 9,
           "left": 12, "up": 13, "right": 14, "down": 15}
README = """FPV Drone (Ocarina of Time, Switch 2, main build E0F3CCFA)

L3 (click the left stick): on / off. It starts where the game camera is, in Free fly.
While it's on, Link stands still and the game doesn't see your controller.

Modes:
  L  Free fly    (noclip camera, the mode at boot): left stick moves where you look,
                  right stick looks, ZL / ZR down / up; no physics
  Y  Angle mode  (drone, self-levelling; stick = tilt angle)
  X  Acro mode   (drone, stick = rotation rate; no levelling, flips and rolls)
  B  Simple mode (drone, self-levelling, holds height; throttle = climb / sink, lets go = stops)

Drone sticks (Mode 2, like a radio):
  left stick  up / down = throttle, left / right = yaw
  right stick up / down = pitch,    left / right = roll
  Throttle: stick centred = hover, up = up to 3.5 g, down = less thrust.

Other buttons:
  R  carry Link: his feet at camera height, 1 m behind it (out of view); R again drops him
  A  back to the game camera
  + or -  leaves (so menus work; also drops Link)

No collision: it flies through walls and floors.
Source and notes: see the repository this came from.
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--verify-main", type=Path, help="flat main image to check the patched bytes against")
    p.add_argument("--uptilt", type=float, default=20.0, help="camera tilted up from the drone body, degrees (default 20)")
    p.add_argument("--rate-center", type=float, default=200.0, help="Acro pitch / roll rate near centre stick, deg/s per full stick (default 200)")
    p.add_argument("--rate-max", type=float, default=670.0, help="Acro pitch / roll rate at full stick, deg/s (default 670)")
    p.add_argument("--yaw-center", type=float, default=120.0, help="yaw rate near centre stick, deg/s per full stick (default 120)")
    p.add_argument("--yaw-max", type=float, default=300.0, help="yaw rate at full stick, deg/s (default 300)")
    p.add_argument("--max-tilt", type=float, default=50.0, help="Angle / Simple mode tilt at full stick, degrees (default 50)")
    p.add_argument("--level-gain", type=float, default=8.0, help="Angle / Simple mode: how fast it tilts to the stick, 1/s (default 8)")
    p.add_argument("--thrust", type=float, default=3.5, help="full throttle, in g (default 3.5)")
    p.add_argument("--drag", type=float, default=0.04, help="quadratic drag, 1/m (default 0.04: about 29 m/s top speed)")
    p.add_argument("--gravity", type=float, default=9.81, help="m/s^2 (default 9.81)")
    p.add_argument("--climb-rate", type=float, default=4.0, help="Simple mode climb / sink speed at full stick, m/s (default 4)")
    p.add_argument("--brake", type=float, default=1.5, help="Simple mode extra slow-down, 1/s (default 1.5)")
    p.add_argument("--deadzone", type=float, default=0.06, help="stick dead zone, 0..1 (default 0.06)")
    p.add_argument("--free-speed", type=float, default=8.0, help="Free fly speed at full stick, m/s (default 8)")
    p.add_argument("--free-turn", type=float, default=120.0, help="Free fly look speed at full stick, deg/s (default 120)")
    p.add_argument("--carry-drop", type=float, default=0.0, help="carried Link's feet below the camera, m (default 0: at camera height)")
    p.add_argument("--carry-back", type=float, default=1.0, help="carried Link behind the camera, m (default 1: out of view)")
    p.add_argument("--throttle-half", action="store_true",
                   help="throttle stick centre = half thrust instead of hover (closer to a real radio)")
    p.add_argument("--toggle", choices=BUTTONS, default="l3", help="drone on / off (default l3)")
    p.add_argument("--reset", choices=BUTTONS, default="a", help="back to the game camera (default a)")
    p.add_argument("--acro", choices=BUTTONS, default="x", help="Acro mode (default x)")
    p.add_argument("--angle", choices=BUTTONS, default="y", help="Angle mode (default y)")
    p.add_argument("--simple", choices=BUTTONS, default="b", help="Simple mode (default b)")
    p.add_argument("--free", choices=BUTTONS, default="l", help="Free fly mode (default l)")
    p.add_argument("--carry", choices=BUTTONS, default="r", help="carry / drop Link (default r)")
    p.add_argument("--name", default="FPV Drone", help="mod folder name inside the zip")
    p.add_argument("--out", type=Path, default=REPO / "releases" / "fpv-drone.zip")
    a = p.parse_args()

    rad = math.radians
    f = lambda x: f"{x!r}f"   # noqa: E731  (C float literal)
    defines = {
        "DEADZONE": f(a.deadzone), "DT_MAX": "0.05f",
        "UPTILT_COS": f(math.cos(rad(a.uptilt))), "UPTILT_SIN": f(math.sin(rad(a.uptilt))),
        "YAW_CENTER": f(rad(a.yaw_center)), "YAW_MAX": f(rad(a.yaw_max)),
        "RATE_CENTER": f(rad(a.rate_center)), "RATE_MAX": f(rad(a.rate_max)),
        "LEVEL_GAIN": f(a.level_gain), "TILT_SIN": f(math.sin(rad(a.max_tilt))),
        "GRAVITY": f(a.gravity), "CLIMB_GAIN": "3.0f", "CLIMB_RATE": f(a.climb_rate),
        "SIMPLE_BRAKE": f(a.brake), "THRUST_MAX": f(a.thrust * a.gravity), "DRAG": f(a.drag),
        "THROTTLE_HOVER_CENTER": 0 if a.throttle_half else 1, "PAUSE_READS": 10,
        "TOGGLE_BIT": BUTTONS[a.toggle], "BTN_RESET": BUTTONS[a.reset], "BTN_ACRO": BUTTONS[a.acro],
        "BTN_ANGLE": BUTTONS[a.angle], "BTN_SIMPLE": BUTTONS[a.simple], "BTN_FREE": BUTTONS[a.free],
        "BTN_CARRY": BUTTONS[a.carry], "FREE_SPEED": f(a.free_speed), "FREE_TURN": f(rad(a.free_turn)),
        "CARRY_DROP": f(a.carry_drop), "CARRY_BACK": f(a.carry_back),
    }
    slots = nxpatch.load_slots(SLOTS)
    records, used, nslots = nxpatch.build_regions([HERE / "fpv.S", HERE / "fpv.c"], REPO / "symbols" / "e0f3ccfa.ld",
                                                  REGIONS, HOOKS, defines, slots)
    if a.verify_main:
        nxpatch.verify(records, a.verify_main)
        nxpatch.verify_slots(slots[:nslots], a.verify_main)
        print("verified against", a.verify_main)
    patch = nxpatch.ips32(records)
    nxpatch.write_zip(a.out, TITLE_ID, a.name, BUILD_ID, patch, README)
    for start, end, _ in REGIONS:
        print(f"cave {start:#x}..{end:#x}: {used[start]} of {end - start} bytes")
    print(f"code: {nslots} of {len(slots)} padding slots, {slots[0][0]:#x}..{slots[nslots - 1][0] + slots[nslots - 1][1]:#x}")
    print(f"{len(HOOKS)} hooks -> {a.out}")


if __name__ == "__main__":
    main()
