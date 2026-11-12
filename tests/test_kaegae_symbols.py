#!/usr/bin/env python3
"""Check that the two symbol lists for a build agree.

    python3 tests/test_kaegae_symbols.py

symbols/<build>.ld is what the IPS mods link against, symbols/<build>.toml is the pack compiled
into KaeGae Core. Needs no game files. It fails when:

- a pack entry names an `ld` symbol that the linker file doesn't have, or has at another address;
- a vtable, function or global in the linker file isn't in the pack (add it, with `ld = "<NAME>"`);
- Core's hook slots are not where the linker file says they are.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import kaegae_symbols  # noqa: E402

BASE = 0x80020000
SHARED = ("vtables", "functions", "globals")  # sections of the linker file that the pack must cover


def read_ld(path):
    """{name: (address, section)} from a linker symbol file."""
    out, section = {}, None
    for line in path.read_text().splitlines():
        heading = re.match(r"/\* --- (\w+)", line)
        if heading:
            section = heading.group(1)
            continue
        entry = re.match(r"(\w+)\s*=\s*0x([0-9a-fA-F]+)\s*;", line)
        if entry:
            assert entry.group(1) not in out, f"{path.name}: {entry.group(1)} is defined twice"
            out[entry.group(1)] = (int(entry.group(2), 16), section)
    return out


def main():
    checked = 0
    for pack in kaegae_symbols.load_packs():
        ld_path = pack["path"].with_suffix(".ld")
        if not ld_path.exists():
            print(f"{pack['path'].name}: no linker file next to it, skipped")
            continue
        ld = read_ld(ld_path)
        named = set()
        for kind in ("vtable", "function", "global"):
            for name, entry in pack.get(kind, {}).items():
                if "ld" not in entry:
                    continue
                assert entry["ld"] in ld, f"{pack['path'].name}: {kind}.{name} names {entry['ld']}, not in {ld_path.name}"
                want = ld[entry["ld"]][0]
                assert entry["offset"] + BASE == want, (
                    f"{kind}.{name}: pack has {entry['offset'] + BASE:#x}, {ld_path.name} has {entry['ld']} = {want:#x}")
                assert entry["ld"] not in named, f"{entry['ld']} is named by two pack entries"
                named.add(entry["ld"])
                if "alias" in entry and kind == "function":
                    assert entry["alias"] == f"f_{want:08x}", f"{kind}.{name}: alias {entry['alias']} doesn't match {want:#x}"
                checked += 1
        missing = sorted(n for n, (_, section) in ld.items() if section in SHARED and n not in named)
        assert not missing, f"{ld_path.name} has symbols the pack {pack['path'].name} lacks: {', '.join(missing)}"
        if "KP_HOOK_SLOTS" in ld:
            assert pack["core"]["hook-slots"] + BASE == ld["KP_HOOK_SLOTS"][0], "hook slots differ between the two files"
        print(f"{pack['path'].name} and {ld_path.name}: ok ({len(named)} shared symbols)")
    assert checked, "nothing was checked"
    print("all symbol tests passed")


if __name__ == "__main__":
    main()
