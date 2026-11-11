#!/usr/bin/env python3
"""Build Kaepora Core and core mods into modules for the game's exefs.

    python3 tools/kaemod.py                                   # Core alone -> releases/kaepora-core.zip
    python3 tools/kaemod.py api/examples/hello                # Core + the mod, each its own module
    python3 tools/kaemod.py api/examples/hello mods/mouse-grab --name "Kaepora Test" --out releases/test.zip
    python3 tools/kaemod.py mods/mouse-grab --bundle          # the mod linked into Core's module

Each mod folder has a mod.toml whose [core] table lists its sources. Two ways to put mods in the game:

  separate (default)  Core is exefs/subsdk1 and each mod its own module, subsdk2 and up. The mods
                      import Core's kae_ functions by name and the game's rtld connects them.
  --bundle            Core and the mods are linked into one module, subsdk1.

The zip holds one mod folder for an emulator's load folder: the modules and Core's patch to main
(its hook points). Needs clang, ld.lld, llvm-nm, llvm-objcopy (LLVM 15+) and Python 3.11+.
"""
import argparse
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import kaepora_font  # noqa: E402
import kaepora_symbols  # noqa: E402
import mknso  # noqa: E402
import nxpatch  # noqa: E402

API = REPO / "api"
CORE = API / "core"
SDK = API / "sdk"
INCLUDE = API / "include"
TITLE_ID = "0400486024DEC000"
CORE_SLOT = "subsdk1"
MOD_SLOTS = [f"subsdk{n}" for n in range(2, 9)]   # subsdk9 is left to standalone mods (sloperinaGZ)

CORE_SOURCES = [CORE / f for f in ("crt0.S", "core.c", "mods.c", "events.c", "symbols.c", "log.c", "format.c",
                                   "platform.c", "alloc.c", "imports.c", "draw.c", "text.c", "input.c", "input_wrap.S", "motion.c",
                                   "hooks.c")]
# What Core imports, and which of the game's modules exports it. The second group is imported
# weakly: Core runs without them (the build can't check the system's exports, only the game can).
CORE_IMPORTS = {
    "nnMain": "main",
    "aligned_alloc": "main",
    "nvnBootstrapLoader": "sdk",
    "_ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE": "sdk",
    "_ZN2nn3hid15GetNpadStyleSetERKj": "sdk (weak)",
    "_ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj": "sdk (weak)",
    "_ZN2nn3hid13GetNpadStatesEPNS0_17NpadHandheldStateEiRKj": "sdk (weak)",
    "_ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyDualStateEiRKj": "sdk (weak)",
    "_ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyLeftStateEiRKj": "sdk (weak)",
    "_ZN2nn3hid13GetNpadStatesEPNS0_17NpadJoyRightStateEiRKj": "sdk (weak)",
}
CFLAGS = ["--target=aarch64-none-elf", "-O2", "-fPIC", "-ffreestanding", "-fno-builtin", "-fno-plt", "-fvisibility=hidden",
          "-fno-stack-protector", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-mno-outline-atomics",
          "-Wall", "-Wextra", "-Werror", "-std=c11", f"-I{INCLUDE}"]

# Core's patch to main for build E0F3CCFA: the hook point stubs, in the code cave (docs/memory-map.md).
HOOK_BUILD_ID = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
HOOK_SYMBOLS = REPO / "symbols" / "e0f3ccfa.ld"
HOOK_REGIONS = [(0x3C46310, 0x3C46400, [".text.hook", ".text", ".data", ".bss"])]
HOOK_SITES = [(0x82C415E4, 0xFC180FEA, "kp_hook_move")]   # str d10, [sp, #-0x80]!


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def compile_sources(sources, work, flags=()):
    work.mkdir(parents=True, exist_ok=True)
    objects = []
    for n, src in enumerate(sources):
        obj = work / f"{n}-{Path(src).name}.o"
        run("clang", *CFLAGS, *flags, "-c", src, "-o", obj)
        objects.append(obj)
    return objects


def link_module(objects, elf, init):
    run("ld.lld", "-shared", "-Bsymbolic", "--hash-style=both", "--build-id=sha1", "-z", "norelro",
        "-z", "max-page-size=4096", "-init", init, "-T", CORE / "module.ld", "-o", elf, *objects)
    return elf


def dynamic_symbols(elf, which):
    """Names the module imports (which='undefined') or exports ('defined')."""
    out = subprocess.run(["llvm-nm", "-D", f"--{which}-only", str(elf)], check=True, capture_output=True, text=True).stdout
    return {line.split()[-1] for line in out.splitlines() if line.strip()}


def api_functions():
    """The functions kaepora.h promises (every `KAE_API ... kae_name(`)."""
    return set(re.findall(r"^KAE_API\b[^;(]*?\b(kae_\w+)\s*\(", (INCLUDE / "kaepora.h").read_text(), re.M))


class Mod:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.manifest = tomllib.loads((self.folder / "mod.toml").read_text())
        core = self.manifest.get("core")
        assert core, f"{self.folder}/mod.toml has no [core] table: not a core mod"
        self.id, self.name = self.manifest["id"], self.manifest["name"]
        assert re.fullmatch(r"[a-z0-9-]+\.[a-z0-9-]+", self.id), f"{self.id}: an id is author.mod-name, lower case"
        want = f"{api_version()[0]}.{api_version()[1]}"
        assert core["api"] == want, f"{self.id} is written for API {core['api']}; this Core is {want}"
        self.sources = []
        for pattern in core["sources"]:
            found = sorted(self.folder.glob(pattern))
            assert found, f"{self.id}: no source matches {pattern}"
            self.sources += found
        self.imports = dict(core.get("imports", {}))     # system functions the mod imports itself
        self.symbols = list(core.get("symbols", []))     # "function:Name", "field:Name" it asks Core for
        text = "".join(s.read_text() for s in self.sources)
        assert f'"{self.id}"' in text, f"{self.id}: no KAE_MOD with this id in its sources"

    def check_symbols(self, packs):
        for pack in packs:
            known = set(kaepora_symbols.symbols(pack))
            fields = set(pack.get("field", {}))
            for entry in self.symbols:
                kind, _, name = entry.partition(":")
                ok = name in fields if kind == "field" else name in known
                assert ok, f"{self.id} needs {entry}, which game version {pack['version']}'s symbol pack doesn't have"

    def objects(self, work):
        return compile_sources(self.sources + [SDK / "libc.c"], work / self.id, [f"-I{self.folder}"])

    def as_module(self, work, core_exports):
        """The mod as its own module (ELF)."""
        objs = self.objects(work) + compile_sources([CORE / "crt0.S", SDK / "modcrt.c"], work / (self.id + "-crt"))
        elf = link_module(objs, work / f"{self.id}.elf", "kae_module_init")
        wanted = dynamic_symbols(elf, "undefined")
        missing = {s for s in wanted if s.startswith("kae_")} - core_exports
        assert not missing, f"{self.id} uses functions this Core doesn't have: {sorted(missing)}"
        extra = {s for s in wanted if not s.startswith("kae_")} - set(self.imports)
        assert not extra, f"{self.id} imports {sorted(extra)}: list them under imports in its mod.toml"
        return elf

    def as_object(self, work):
        """The mod as one object to link into Core's module, its own names kept to itself."""
        obj = work / f"{self.id}.bundle.o"
        run("ld.lld", "-r", "-o", obj, *self.objects(work))
        run("llvm-objcopy", "--localize-hidden", obj)
        return obj


def api_version():
    text = (INCLUDE / "kaepora.h").read_text()
    return tuple(int(re.search(rf"#define KAE_API_{k}\s+(\d+)", text).group(1)) for k in ("MAJOR", "MINOR"))


def build_core(work, bundled=(), defines=()):
    """Core's module (ELF), with the mods in `bundled` linked into it. `defines` are extra -D flags
    for Core's sources only (the hardware test switches in core.h)."""
    work.mkdir(parents=True, exist_ok=True)
    packs = kaepora_symbols.load_packs()
    (work / "symbols_gen.h").write_text(kaepora_symbols.generate(packs))
    (work / "font_gen.h").write_text(kaepora_font.generate())
    for mod in bundled:
        mod.check_symbols(packs)
    objs = compile_sources(CORE_SOURCES + [SDK / "libc.c"], work / "core", ["-DKAE_BUILDING_CORE", f"-I{work}",
                                                                   *(f"-D{d}" for d in defines)])
    objs += [mod.as_object(work) for mod in bundled]
    elf = link_module(objs, work / "core.elf", "kp_module_init")
    allowed = set(CORE_IMPORTS)
    for mod in bundled:
        allowed |= set(mod.imports)
    extra = dynamic_symbols(elf, "undefined") - allowed
    assert not extra, f"the module imports symbols the game isn't known to export: {sorted(extra)}"
    exported, promised = dynamic_symbols(elf, "defined"), api_functions()
    assert exported == promised, (f"Core's exports and kaepora.h disagree: only exported {sorted(exported - promised)}, "
                                  f"only in the header {sorted(promised - exported)}")
    return elf


def hook_patch(verify_main=None):
    """Core's patch to main as IPS32 bytes."""
    records, used, _ = nxpatch.build_regions([CORE / "hookpoints.S"], HOOK_SYMBOLS, HOOK_REGIONS, HOOK_SITES, {})
    if verify_main:
        nxpatch.verify(records, verify_main)
    return nxpatch.ips32(records), records


def build(mods, bundle, work, verify_main=None, defines=()):
    """{path inside the mod folder: bytes} for Core and the given mods."""
    work = Path(work)
    packs = kaepora_symbols.load_packs()
    for mod in mods:
        mod.check_symbols(packs)
    ids = [m.id for m in mods]
    assert len(ids) == len(set(ids)), "two mods have the same id"
    files = {}
    if bundle:
        files[f"exefs/{CORE_SLOT}"] = mknso.pack(build_core(work, mods, defines).read_bytes())
    else:
        assert len(mods) <= len(MOD_SLOTS), f"only {len(MOD_SLOTS)} mods fit as separate modules: use --bundle"
        core = build_core(work, (), defines)
        files[f"exefs/{CORE_SLOT}"] = mknso.pack(core.read_bytes())
        exports = dynamic_symbols(core, "defined")
        for slot, mod in zip(MOD_SLOTS, mods):
            files[f"exefs/{slot}"] = mknso.pack(mod.as_module(work, exports).read_bytes())
    files[f"exefs/{HOOK_BUILD_ID}.ips"] = hook_patch(verify_main)[0]
    return files


def write_zip(path, name, files, readme):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, blob in sorted({**files, "README.txt": readme.encode()}.items()):
            info = zipfile.ZipInfo(f"{TITLE_ID}/{name}/{rel}", date_time=(2026, 1, 1, 0, 0, 0))   # same input, same zip
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, blob)


def readme(mods, bundle, files):
    major, minor = api_version()
    lines = [f"Kaepora Core {major}.{minor} (Ocarina of Time, Switch 2, game version 1.1.1)", ""]
    if mods:
        lines.append("With: " + ", ".join(f"{m.name} {m.manifest['version']}" for m in mods)
                     + (" (linked into Core's module)" if bundle else " (each its own module)"))
        lines.append("")
    lines += ["Copy this folder into the emulator's load folder for the game, then close and reopen the",
              "emulator. Only one mod folder with an exefs/subsdk1 can be on at a time: turn off older",
              "Kaepora or Mouse Grab folders first.", "", "Files:"]
    lines += [f"  {rel}  ({len(blob)} bytes)" for rel, blob in sorted(files.items())]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mods", nargs="*", type=Path, help="mod folders (each with a mod.toml)")
    p.add_argument("--bundle", action="store_true", help="link the mods into Core's module instead of their own")
    p.add_argument("--name", help="mod folder name inside the zip")
    p.add_argument("--out", type=Path, help="zip to write")
    p.add_argument("--verify-main", type=Path, help="flat main image to check Core's patch against")
    p.add_argument("--keep", type=Path, help="keep the ELF files and objects in this folder")
    p.add_argument("--define", action="append", default=[], metavar="NAME",
                   help="compile Core with -DNAME (repeatable): KAE_NO_DEBUG_OUT, KAE_LOAD_ONLY")
    a = p.parse_args(argv)
    mods = [Mod(folder) for folder in a.mods]
    name = a.name or (mods[0].name if len(mods) == 1 else "Kaepora Core")
    out = a.out or REPO / "releases" / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".zip")
    with tempfile.TemporaryDirectory() as tmp:
        files = build(mods, a.bundle, a.keep or Path(tmp), a.verify_main, a.define)
    write_zip(out, name, files, readme(mods, a.bundle, files))
    for rel, blob in sorted(files.items()):
        print(f"  {rel}: {len(blob)} bytes")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
