#!/usr/bin/env python3
"""Build Mouse Grab with Kaepora Core.

    python3 mods/mouse-grab/build.py              # releases/mouse-grab-test.zip: Core and the mod in exefs/subsdk1
    python3 mods/mouse-grab/build.py --separate   # Core in subsdk1, the mod its own module in subsdk2

This is tools/kaemod.py with Mouse Grab's defaults; see it for the other options
(--verify-main, --keep, --name, --out). Needs clang and ld.lld.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools"))
import kaemod  # noqa: E402

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--separate" in args:
        args.remove("--separate")
    else:
        args.append("--bundle")
    if "--out" not in args:
        args += ["--out", str(REPO / "releases" / "mouse-grab-test.zip")]
    kaemod.main([str(HERE), *args])
