#!/usr/bin/env python3
"""Build Mouse Grab with KaeGae Core.

    python3 mods/mouse-grab/build.py              # releases/mouse-grab.zip: the mod alone (install KaeGae Core next to it)
    python3 mods/mouse-grab/build.py --bundle --out x.zip   # Core and the mod linked into one exefs/subsdk1

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
    if "--bundle" not in args and "--no-core" not in args:
        args.append("--no-core")
    if "--name" not in args:
        args += ["--name", "Mouse Grab"]
    if "--out" not in args:
        args += ["--out", str(REPO / "releases" / "mouse-grab.zip")]
    kaemod.main([str(HERE), *args])
