#!/usr/bin/env python3
"""Build the real-hardware test zips for issue #2 into releases/hardware-test/.

    python3 tools/build_hw_tests.py

Each zip is in ns2jb-modloader's layout (tools/ns2jb.py) and leaves out one suspect, so a result
on a console says which part breaks there:

  first-person-no-keyboard          First Person without the keyboard read (no , . / ; keys)
  first-person-no-keyboard-no-hide  ... and without hiding Link
  mouse-grab-load-only              Core + Mouse Grab whose start returns at once (does nothing)
  mouse-grab-no-debug-log           Mouse Grab with Core's log off (no svcOutputDebugString)

Needs what the normal builds need (clang, ld.lld, llvm-nm, llvm-objcopy, Python 3.11+).
"""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import ns2jb  # noqa: E402

OUT = REPO / "releases" / "hardware-test"
PY = sys.executable

BUILDS = [
    ("first-person-no-keyboard", "First Person (no keyboard)",
     [REPO / "mods/first-person/build.py", "--no-height-keys"],
     "Hardware test: First Person with no keyboard read at all. R3 toggles first person as usual;\n"
     "Link is always hidden (the ; key is gone with the keyboard).\n"),
    ("first-person-no-keyboard-no-hide", "First Person (no keyboard, no hide)",
     [REPO / "mods/first-person/build.py", "--no-height-keys", "--no-hide"],
     "Hardware test: First Person with no keyboard read and without hiding Link (he stays visible).\n"),
    ("mouse-grab-load-only", "Mouse Grab (load only)",
     [REPO / "mods/mouse-grab/build.py", "--define", "KAE_LOAD_ONLY"],
     "Hardware test: the module is loaded and does nothing. If the game boots and plays normally,\n"
     "loading the extra subsdk1 is fine on the console. Nothing visible changes in the game.\n"),
    ("mouse-grab-no-debug-log", "Mouse Grab (no debug log)",
     [REPO / "mods/mouse-grab/build.py", "--define", "KAE_NO_DEBUG_OUT"],
     "Hardware test: Mouse Grab with Kaepora Core's debug log switched off (it never calls\n"
     "svcOutputDebugString). Otherwise the same as mouse-grab-test.zip.\n"),
]

INSTALL = ("\nInstall: copy the ns2jb-modloader folder in this zip to the root of the microSD card, merging\n"
           "it with the one there. Only one test at a time: remove the previous test's files first\n"
           "(ns2jb-modloader/exefs_patches/<its name>/ and ns2jb-modloader/contents/0400486024DEC000/).\n"
           "Game version 1.1.1 only. Results: https://github.com/Kabosune/oot-remake-modding/issues/2\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for slug, name, cmd, note in BUILDS:
            emu = Path(tmp) / f"{slug}.zip"
            subprocess.run([PY, *map(str, cmd), "--name", name, "--out", str(emu)], check=True,
                           stdout=subprocess.DEVNULL)
            files = ns2jb.convert(emu, OUT / f"{slug}.zip", f"{name} (Ocarina of Time, Switch 2)\n\n{note}{INSTALL}")
            print(f"{slug}.zip")
            for f in files:
                print("  ", f)


if __name__ == "__main__":
    main()
