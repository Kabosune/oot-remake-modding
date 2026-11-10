#!/usr/bin/env python3
"""Build Mouse Grab: Kaepora Core's first skeleton and the cursor, linked into one module.

    python3 mods/mouse-grab/build.py            # releases/mouse-grab.zip

Needs clang and ld.lld. The zip holds a mod folder with exefs/subsdk1.
"""
import argparse
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CORE = REPO / "api" / "core"
sys.path.insert(0, str(REPO / "tools"))
import mknso  # noqa: E402

TITLE_ID = "0400486024DEC000"
SLOT = "subsdk1"
SOURCES = [CORE / "crt0.S", CORE / "core.c", CORE / "log.c", CORE / "imports.c", CORE / "draw.c", CORE / "hooks.c", CORE / "memory.c", CORE / "motion.c",
           HERE / "module" / "cursor.c", HERE / "module" / "ragdoll.c", HERE / "module" / "grab.c", HERE / "module" / "survey.c", HERE / "module" / "actors.c"]
sys.path.insert(0, str(REPO / "tools"))
import nxpatch  # noqa: E402
BUILD_ID = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
# Kaepora's hook point stubs live in the cave Mouse Probe used (it is retired).
HOOK_REGIONS = [(0x3C46310, 0x3C46400, [".text.hook", ".text", ".data", ".bss"])]
HOOK_SITES = [(0x82C415E4, 0xFC180FEA, "kp_hook_move")]   # str d10, [sp, #-0x80]!
# What the module may import, and which of the game's modules exports it.
IMPORTS = {
    "nnMain": "main",
    "aligned_alloc": "main",
    "nvnBootstrapLoader": "sdk",
    "_ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi": "sdk",
    "_ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE": "sdk",
}
CFLAGS = ["--target=aarch64-none-elf", "-O2", "-fPIC", "-ffreestanding", "-fno-builtin", "-fno-plt", "-fvisibility=hidden",
          "-fno-stack-protector", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-Wall", "-Wextra", "-Werror",
          "-std=c11", f"-I{CORE}"]
README = """Mouse Grab, cursor test build (Ocarina of Time, Switch 2, game version 1.1.1)

Draws a cursor at the mouse position. Right click: Link ragdolls (test). In an emulator, turn
on its emulated mouse. exefs/subsdk1 is the mod; the .ips adds one hook point to main.
"""


def undefined_symbols(elf):
    out = subprocess.run(["llvm-nm", "-D", "--undefined-only", elf], check=True, capture_output=True, text=True).stdout
    return {line.split()[-1] for line in out.splitlines() if line.strip()}


def build(out_dir):
    out_dir = Path(out_dir)
    objects = []
    for src in SOURCES:
        obj = out_dir / (src.name + ".o")
        subprocess.run(["clang", *CFLAGS, "-c", str(src), "-o", str(obj)], check=True)
        objects.append(str(obj))
    elf = out_dir / "module.elf"
    subprocess.run(["ld.lld", "-shared", "-Bsymbolic", "--hash-style=both", "--build-id=sha1", "-z", "norelro",
                    "-z", "max-page-size=4096", "-init", "kp_module_init", "-T", str(CORE / "module.ld"),
                    "-o", str(elf), *objects], check=True)
    extra = undefined_symbols(str(elf)) - set(IMPORTS)
    if extra:
        sys.exit(f"the module imports symbols the game isn't known to export: {sorted(extra)}")
    return elf


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", default="Mouse Grab", help="mod folder name inside the zip")
    p.add_argument("--out", type=Path, default=REPO / "releases" / "mouse-grab.zip")
    p.add_argument("--verify-main", type=Path, help="flat main image to check the patch against")
    p.add_argument("--keep", type=Path, help="also keep module.elf and the NSO in this folder")
    a = p.parse_args()
    records, used, _ = nxpatch.build_regions([CORE / "hookpoints.S"], REPO / "symbols" / "e0f3ccfa.ld", HOOK_REGIONS,
                                             HOOK_SITES, {})
    if a.verify_main:
        nxpatch.verify(records, a.verify_main)
        print("patch verified against", a.verify_main)
    ips = nxpatch.ips32(records)
    with tempfile.TemporaryDirectory() as tmp:
        work = a.keep or Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        elf = build(work)
        nso = mknso.pack(elf.read_bytes())
        (work / SLOT).write_bytes(nso)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in ((f"exefs/{SLOT}", nso), (f"exefs/{BUILD_ID}.ips", ips), ("README.txt", README.encode())):
            info = zipfile.ZipInfo(f"{TITLE_ID}/{a.name}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
            z.writestr(info, blob)
    print(f"{SLOT}: {len(nso)} bytes, hook stubs {used[HOOK_REGIONS[0][0]]} bytes -> {a.out}")


if __name__ == "__main__":
    main()
