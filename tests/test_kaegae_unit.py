"""KaeGae Core's portable parts (mod list, events, symbols, log format, memory pool, text), built for
this PC and run here. Also checks the symbol packs against symbols/*.ld.

    python3 tests/test_kaegae_unit.py

Needs clang (any host) and Python 3.11+. No game files.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import kaegae_font  # noqa: E402
import kaegae_symbols  # noqa: E402

CORE = REPO / "api" / "core"
SOURCES = [CORE / f for f in ("mods.c", "events.c", "symbols.c", "log.c", "format.c", "alloc.c", "text.c", "menu.c", "settings.c")]


def packs_match_ld(packs):
    """Every pack entry with an `ld` name has the same address in the .ld the IPS mods link against."""
    checked = 0
    for pack in packs:
        ld = pack["path"].with_suffix(".ld")
        values = {m[1]: int(m[2], 16) for m in re.finditer(r"^(\w+)\s*=\s*(0x[0-9a-fA-F]+);", ld.read_text(), re.M)}
        for kind in ("function", "global", "vtable"):
            for name, entry in pack.get(kind, {}).items():
                if "ld" in entry:
                    assert values[entry["ld"]] - 0x80020000 == entry["offset"], f"{name} != {entry['ld']} in {ld.name}"
                    checked += 1
                if entry.get("alias", "").startswith("f_"):
                    assert int(entry["alias"][2:], 16) - 0x80020000 == entry["offset"], f"{name}: alias and offset disagree"
                    checked += 1
        assert values["KP_HOOK_SLOTS"] - 0x80020000 == pack["core"]["hook-slots"]
        for h in pack.get("hookpoint", {}).values():
            assert h["site"] + 0x80020000 + 4 == values["MOVE_SECOND_RET"]
    return checked


def main():
    packs = kaegae_symbols.load_packs()
    print(f"symbol packs agree with the .ld files: ok ({packs_match_ld(packs)} addresses)")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "symbols_gen.h").write_text(kaegae_symbols.generate(packs))
        (tmp / "font_gen.h").write_text(kaegae_font.generate())
        exe = tmp / "unit"
        command = ["clang", "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror", "-DKAE_BUILDING_CORE",
                   "-DKP_POOL_BYTES=4096", f"-I{CORE}", f"-I{REPO / 'api' / 'include'}", f"-I{tmp}", *map(str, SOURCES),
                   str(REPO / "tests" / "kaegae" / "unit.c"), "-o", str(exe)]
        sanitizers = ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
        if subprocess.run(command + sanitizers, capture_output=True).returncode:
            print("(this clang has no sanitizer libraries: running without them)")
            subprocess.run(command, check=True)
        names = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.split()
        for name in names:
            r = subprocess.run([str(exe), name], capture_output=True, text=True)
            print(r.stdout.strip() or r.stderr.strip())
            if r.returncode:
                sys.exit(r.stderr or 1)
    print("all unit tests passed")


if __name__ == "__main__":
    main()
