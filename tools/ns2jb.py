#!/usr/bin/env python3
"""Repack a mod zip from the emulator layout into ns2jb-modloader's layout (real Switch 2).

    python3 tools/ns2jb.py releases/first-person.zip out.zip

Emulator layout (Lichii / Fritchii / Eden load folder):

    <title id>/<mod name>/exefs/<build id>.ips
    <title id>/<mod name>/exefs/subsdk1           (and other whole exefs files)
    <title id>/<mod name>/romfs/...

ns2jb-modloader layout (https://github.com/SebaaMG/ns2jb-modloader), copied to the root of the
microSD card:

    ns2jb-modloader/exefs_patches/<mod name>/<build id>.ips
    ns2jb-modloader/contents/<title id>/exefs/subsdk1
    ns2jb-modloader/contents/<title id>/romfs/...

Whole exefs files and romfs share one folder per game there, so only one such mod fits at a time.
"""
import sys
import zipfile
from pathlib import Path


def convert(src, dst, readme=None):
    """Writes dst; `readme` replaces the zip's README.txt (the emulator install steps) when given."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        def add(name, data):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))   # same input, same zip
            info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(info, data)
        out = {}
        for name in zin.namelist():
            if name.endswith("/"):
                continue
            parts = name.split("/")
            assert len(parts) >= 3, f"{name}: not <title id>/<mod name>/..."
            title, mod, rest = parts[0], parts[1], parts[2:]
            data = zin.read(name)
            if rest == ["README.txt"]:
                out["README.txt"] = data if readme is None else readme.encode()
            elif rest[0] == "exefs" and len(rest) == 2 and rest[1].endswith(".ips"):
                out[f"ns2jb-modloader/exefs_patches/{mod}/{rest[1]}"] = data
            elif rest[0] in ("exefs", "romfs"):
                out[f"ns2jb-modloader/contents/{title}/{'/'.join(rest)}"] = data
            else:
                raise SystemExit(f"{name}: don't know where this goes for ns2jb-modloader")
        for name in sorted(out):
            add(name, out[name])
    return sorted(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    for n in convert(sys.argv[1], sys.argv[2]):
        print(" ", n)
    print("->", sys.argv[2])
