#!/usr/bin/env python3
"""Build KaeGae Core and core mods into modules for the game's exefs.

    python3 tools/kaemod.py                                   # Core alone -> releases/kaegae-core.zip
    python3 tools/kaemod.py api/examples/hello                # Core + the mod, each its own module
    python3 tools/kaemod.py api/examples/hello mods/mouse-grab --name "KaeGae Test" --out releases/test.zip
    python3 tools/kaemod.py mods/mouse-grab --bundle          # the mod linked into Core's module
    python3 tools/kaemod.py api/examples/hello --no-core      # the mod alone, for people who have Core installed

Each mod folder has a mod.toml whose [core] table lists its sources. Two ways to put mods in the game:

  separate (default)  Core is exefs/subsdk1 and each mod its own module, subsdk2 and up. The mods
                      import Core's kae_ functions by name and the game's rtld connects them.
  --bundle            Core and the mods are linked into one module, subsdk1.

The zip holds one mod folder for an emulator's load folder: the modules, Core's patch to main
(its hook points) and a mod.toml that says what is in it, for `tools/kaegae.py check / install`. Needs clang, ld.lld, llvm-nm, llvm-objcopy (LLVM 15+) and Python 3.11+.
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
import kaegae_font  # noqa: E402
import kaegae_symbols  # noqa: E402
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
                                   "platform.c", "alloc.c", "imports.c", "draw.c", "text.c", "menu.c", "input.c", "input_wrap.S", "motion.c",
                                   "hooks.c", "player.c", "settings.c", "keyboard.c",
                                   "view.c", "view_entry.S")]
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
    # settings saved between runs (core/settings.c); names read from the game's sdk module
    "_ZN2nn2fs19MountSdCardForDebugEPKc": "sdk (weak)",
    "_ZN2nn2fs15CreateDirectoryEPKc": "sdk (weak)",
    "_ZN2nn2fs10CreateFileEPKcl": "sdk (weak)",
    "_ZN2nn2fs8OpenFileEPNS0_10FileHandleEPKci": "sdk (weak)",
    "_ZN2nn2fs8ReadFileEPmNS0_10FileHandleElPvm": "sdk (weak)",
    "_ZN2nn2fs9WriteFileENS0_10FileHandleElPKvmRKNS0_11WriteOptionE": "sdk (weak)",
    "_ZN2nn2fs11SetFileSizeENS0_10FileHandleEl": "sdk (weak)",
    "_ZN2nn2fs9CloseFileENS0_10FileHandleE": "sdk (weak)",
    "_ZN2nn2fs19SetEnabledAutoAbortEb": "sdk (weak)",
    # the keyboard, for mods' keys (core/keyboard.c); names read from the game's sdk module
    "_ZN2nn3hid18InitializeKeyboardEv": "sdk (weak)",
    "_ZN2nn3hid16GetKeyboardStateEPNS0_13KeyboardStateE": "sdk (weak)",
}
CFLAGS = ["--target=aarch64-none-elf", "-O2", "-fPIC", "-ffreestanding", "-fno-builtin", "-fno-plt", "-fvisibility=hidden",
          "-fno-stack-protector", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-mno-outline-atomics",
          "-Wall", "-Wextra", "-Werror", "-std=c11", f"-I{INCLUDE}"]

# Core's patch to main: the hook point stubs (core/hookpoints.S), one IPS per game build. Each
# build's symbol pack says where they go ([core] hook-code), where the hook slots are ([core]
# hook-slots) and which instruction each hook point replaces ([hookpoint] site / replaces / stub);
# symbols/<build>.ld gives the addresses the stubs jump back to.
HOOK_BUILD_ID = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"   # 1.1.1: the build the tests run against


def hook_builds():
    """{build id: (pack, linker file, regions, sites)} for every pack that has Core's hook stubs."""
    out = {}
    for pack in kaegae_symbols.load_packs():
        code = pack.get("core", {}).get("hook-code")
        if not code:
            continue
        start, end = (int(x, 16) for x in code.split(".."))
        ld = pack["path"].with_suffix(".ld")
        assert ld.exists(), f"{pack['path'].name} has hook-code but no {ld.name}"
        sites = []
        for name, h in pack["hookpoint"].items():
            assert "stub" in h and "replaces" in h, f"{pack['path'].name}: hook point {name} needs stub and replaces"
            sites.append((nxpatch.BASE + h["site"], h["replaces"], h["stub"]))
        out[pack["build"]] = (pack, ld, [(start, end, [".text.hook", ".text", ".data", ".bss"])], sites)
    assert HOOK_BUILD_ID in out, "the 1.1.1 pack lost its hook-code"
    return out


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
    """The functions kaegae.h promises (every `KAE_API ... kae_name(`)."""
    return set(re.findall(r"^KAE_API\b[^;(]*?\b(kae_\w+)\s*\(", (INCLUDE / "kaegae.h").read_text(), re.M))


class Mod:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.manifest = tomllib.loads((self.folder / "mod.toml").read_text())
        core = self.manifest.get("core")
        assert core, f"{self.folder}/mod.toml has no [core] table: not a core mod"
        self.id, self.name = self.manifest["id"], self.manifest["name"]
        assert re.fullmatch(r"[a-z0-9-]+\.[a-z0-9-]+", self.id), f"{self.id}: an id is author.mod-name, lower case"
        written = tuple(int(x) for x in str(core["api"]).split("."))
        assert written[0] == api_version()[0] and written[1] <= api_version()[1], (
            f"{self.id} is written for API {core['api']}; this header is {api_version()[0]}.{api_version()[1]}")
        self.sources = []
        for pattern in core["sources"]:
            found = sorted(self.folder.glob(pattern))
            assert found, f"{self.id}: no source matches {pattern}"
            self.sources += found
        self.imports = dict(core.get("imports", {}))     # system functions the mod imports itself
        self.symbols = list(core.get("symbols", []))     # "function:Name", "field:Name" it asks Core for
        self.cflags = list(core.get("cflags", []))       # extra compiler flags for its sources (after Core's own)
        self.unsupported = {}                            # game version: names its pack lacks (check_symbols)
        self.raw_offsets = False                         # it reads the game by raw offset (kae_game_base)
        self.tested = [str(v) for v in self.manifest.get("game", {}).get("tested", [])]   # game versions its author tried
        text = "".join(s.read_text() for s in self.sources)
        assert f'"{self.id}"' in text, f"{self.id}: no KAE_MOD with this id in its sources"

    def check_symbols(self, packs):
        """Which game versions the mod can run on. A pack may lack names another has (a version
        that is still being ported): the mod still builds, Core gives it no address for those names
        on that version (kae_sym returns 0; the mod's start should then return an error, and Core
        shows it as off), and the build says so. Missing from every pack is an error."""
        self.unsupported = {}
        for pack in packs:
            known = set(kaegae_symbols.symbols(pack))
            fields = set(pack.get("field", {}))
            missing = [e for e in self.symbols
                       if e.partition(":")[2] not in (fields if e.partition(":")[0] == "field" else known)]
            if missing:
                self.unsupported[pack["version"]] = missing
        assert len(self.unsupported) < len(packs), (
            f"{self.id} needs names no symbol pack has: {sorted(set().union(*self.unsupported.values()))}")
        for version, missing in sorted(self.unsupported.items()):
            print(f"warning: {self.id} won't run on game version {version}: its symbol pack lacks {', '.join(missing)}",
                  file=sys.stderr)

    def objects(self, work):
        objs = compile_sources(self.sources, work / self.id, [f"-I{self.folder}", *self.cflags])
        self.check_raw_offsets(objs)
        return objs + compile_sources([SDK / "libc.c"], work / (self.id + "-libc"))

    def check_raw_offsets(self, objs):
        """A mod that calls kae_game_base reads the game at offsets of its own: those belong to one
        game version, so the mod runs only on the version they were found on (and on any other it
        reads the wrong code or data). Asking Core by name (kae_sym, kae_field) works on all."""
        out = subprocess.run(["llvm-nm", "--undefined-only", *map(str, objs)], check=True,
                             capture_output=True, text=True).stdout
        self.raw_offsets = any(line.split()[-1] == "kae_game_base" for line in out.splitlines() if line.strip())
        if self.raw_offsets:
            print(f"warning: {self.id} uses kae_game_base (the game's own offsets): it runs only on the game version "
                  f"those offsets are for. Ask Core by name (kae_sym, kae_field) to run on every version, or check "
                  f"kae_game_build() in start and return non-zero on any other", file=sys.stderr)

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


def core_version():
    """Core's own version: the API's two numbers and Core's patch number (KAE_CORE_PATCH)."""
    text = (INCLUDE / "kaegae.h").read_text()
    patch = int(re.search(r"#define KAE_CORE_PATCH\s+(\d+)", text).group(1))
    return "%d.%d.%d" % (api_version() + (patch,))


def api_version():
    text = (INCLUDE / "kaegae.h").read_text()
    return tuple(int(re.search(rf"#define KAE_API_{k}\s+(\d+)", text).group(1)) for k in ("MAJOR", "MINOR"))


def build_core(work, bundled=(), defines=()):
    """Core's module (ELF), with the mods in `bundled` linked into it. `defines` are extra -D flags
    for Core's sources only (the hardware test switches in core.h)."""
    work.mkdir(parents=True, exist_ok=True)
    packs = kaegae_symbols.load_packs()
    (work / "symbols_gen.h").write_text(kaegae_symbols.generate(packs))
    (work / "font_gen.h").write_text(kaegae_font.generate())
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
    assert exported == promised, (f"Core's exports and kaegae.h disagree: only exported {sorted(exported - promised)}, "
                                  f"only in the header {sorted(promised - exported)}")
    return elf


def hook_patch(verify_main=None, build=HOOK_BUILD_ID):
    """Core's patch to main for one game build, as IPS32 bytes (and its records)."""
    pack, ld, regions, sites = hook_builds()[build]
    cave = (regions[0][0], regions[0][1])
    records, used, _ = nxpatch.build_regions([CORE / "hookpoints.S"], ld, regions, sites, {}, cave=cave)
    if verify_main:
        nxpatch.verify(records, verify_main)
    return nxpatch.ips32(records), records


def main_build(image):
    """The build id of a flat main image, from where its MOD0 header is, or None."""
    data = Path(image).read_bytes()
    for build, (pack, *_rest) in hook_builds().items():
        at = pack["detect"]["mod0"]
        if data[at:at + 4] == b"MOD0" and len(data) == pack["detect"]["size"]:
            return build
    return None


def build(mods, bundle, work, verify_main=None, defines=(), with_core=True):
    """{path inside the mod folder: bytes} for Core and the given mods (the mods alone if not with_core).
    verify_main: flat main images (any builds) to check Core's patches against."""
    work = Path(work)
    packs = kaegae_symbols.load_packs()
    for mod in mods:
        mod.check_symbols(packs)
    ids = [m.id for m in mods]
    assert len(ids) == len(set(ids)), "two mods have the same id"
    files = {}
    if bundle:
        files[f"exefs/{CORE_SLOT}"] = mknso.pack(build_core(work, mods, defines).read_bytes())
    else:
        assert len(mods) <= len(MOD_SLOTS), f"only {len(MOD_SLOTS)} mods fit as separate modules: use --bundle"
        core = build_core(work, (), defines)      # built even when left out: its exports are what the mods are checked against
        if with_core:
            files[f"exefs/{CORE_SLOT}"] = mknso.pack(core.read_bytes())
        exports = dynamic_symbols(core, "defined")
        for slot, mod in zip(MOD_SLOTS, mods):
            files[f"exefs/{slot}"] = mknso.pack(mod.as_module(work, exports).read_bytes())
    if with_core:
        images = {}
        for image in verify_main or ():
            found = main_build(image)
            assert found, f"{image}: not a main image of any build with a symbol pack"
            images[found] = image
        for build_id in hook_builds():
            files[f"exefs/{build_id}.ips"] = hook_patch(images.get(build_id), build_id)[0]
    for mod in mods:     # files a mod's manifest asks to ship next to it (its licence, say)
        for rel in mod.manifest.get("ship", []):
            name = rel if len(mods) == 1 else f"{mod.id}/{rel}"
            files[name] = (mod.folder / rel).read_bytes()
    return files


def package_manifest(mods, bundle, name, with_core=True, package_id=None):
    """The mod.toml of a built folder: what each module is, and Core's claims on main if Core is in it."""
    core = "%s@%d.%d" % (("kaegae.core",) + api_version())      # what mods require: the API
    core_module = "kaegae.core@" + core_version()                  # what this Core is
    q = lambda text: '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'      # noqa: E731
    if len(mods) == 1:
        ident, version = mods[0].id, mods[0].manifest["version"]
    elif not mods:
        ident, version = "kaegae.core", core_version()
    else:
        ident, version = "pack." + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), "1.0.0"
    authors = sorted({a for m in mods for a in m.manifest.get("authors", [])} | ({"KaboWabo/Kabosune"} if with_core else set()))
    licenses = sorted({m.manifest.get("license", "") for m in mods} | ({"MIT"} if with_core else set()) - {""})
    lines = ["# Written by tools/kaemod.py: what this folder holds. Format: api/MANIFEST.md.", "manifest = 1", "",
             f"id       = {q(package_id or ident)}", f"name     = {q(name)}", f"version  = {q(version)}",
             f"authors  = [{', '.join(q(a) for a in authors)}]", f"license  = {q(' AND '.join(licenses))}",
             "", "[game]", f"title = {q(TITLE_ID)}"]
    tested = sorted({v for m in mods for v in m.tested}) if len(mods) == 1 else []
    if tested:
        lines.append(f"tested = [{', '.join(q(v) for v in tested)}]      # the game versions its author tried it on")
    lines += ["", "[modules]"]
    entries = [f"{m.id}@{m.manifest['version']}" for m in mods]
    if bundle:
        lines.append(f"{CORE_SLOT} = [{', '.join(q(e) for e in [core_module] + entries)}]      # linked into one module")
    else:
        lines += [f"{CORE_SLOT} = {q(core_module)}"] * with_core + [f"{slot} = {q(e)}" for slot, e in zip(MOD_SLOTS, entries)]
    if mods:
        lines += ["", "[core]", 'api = "%d.%d"      # the Core API the mods are built for' % api_version()]
    if with_core:
        for build_id, (pack, *_rest) in hook_builds().items():
            registry = f"registry/{build_id[:8].lower()}.toml"
            claim = tomllib.loads((REPO / registry).read_text())["claim"]
            claim = next(c for c in claim if c["owner"] == "kaegae.core")
            lines += ["", f"[build.{build_id}]      # {pack['version']}: KaeGae Core's hook points ({registry})",
                      f'ips    = "exefs/{build_id}.ips"'] + [
                      f"{key:<6} = [{', '.join(q(v) for v in claim[key])}]" for key in ("code", "memory", "hooks")]
    else:
        lines += ["", "[relations]", f"requires = [{q(core.replace('@', '>='))}]      # install KaeGae Core as well"]
    return "\n".join(lines) + "\n"


def write_zip(path, name, files, readme):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, blob in sorted({**files, "README.txt": readme.encode()}.items()):
            info = zipfile.ZipInfo(f"{TITLE_ID}/{name}/{rel}", date_time=(2026, 1, 1, 0, 0, 0))   # same input, same zip
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, blob)


def readme(mods, bundle, files, with_core=True):
    major, minor = api_version()
    gaps = [f"{m.name} doesn't run on game version {v} yet (its symbol pack lacks {', '.join(names)})."
            for m in mods for v, names in sorted(m.unsupported.items())]
    gaps += [f"{m.name} reads the game at offsets of its own: it runs only on the game version they're for."
             for m in mods if m.raw_offsets]
    gaps += [f"{m.name} was tested on game version{'s' if len(m.tested) > 1 else ''} {', '.join(m.tested)}."
             for m in mods if m.tested]
    if not with_core:
        lines = [", ".join(f"{m.name} {m.manifest['version']}" for m in mods) + " (Ocarina of Time, Switch 2)", "",
                 f"A KaeGae mod without KaeGae Core in the folder: it needs Core {major}.{minor} installed as well.",
                 "Without Core it loads and does nothing.", *gaps, "", "Files:"]
        return "\n".join(lines + [f"  {rel}  ({len(blob)} bytes)" for rel, blob in sorted(files.items())]) + "\n"
    versions = " and ".join(sorted(pack["version"] for pack, *_rest in hook_builds().values()))
    lines = [f"KaeGae Core {core_version()} (Ocarina of Time, Switch 2, game versions {versions})", ""]
    if mods:
        lines.append("With: " + ", ".join(f"{m.name} {m.manifest['version']}" for m in mods)
                     + (" (linked into Core's module)" if bundle else " (each its own module)"))
        lines.append("")
    if gaps:
        lines += gaps + [""]
    lines += ["Copy this folder into the emulator's load folder for the game, then close and reopen the",
              "emulator. Only one mod folder with an exefs/subsdk1 can be on at a time: turn off older",
              "KaeGae or Mouse Grab folders first.", "", "Files:"]
    lines += [f"  {rel}  ({len(blob)} bytes)" for rel, blob in sorted(files.items())]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mods", nargs="*", type=Path, help="mod folders (each with a mod.toml)")
    p.add_argument("--bundle", action="store_true", help="link the mods into Core's module instead of their own")
    p.add_argument("--no-core", action="store_true", help="leave Core out: only the mods' own modules (Core is installed separately)")
    p.add_argument("--id", help="the id in the folder's mod.toml (default: the mod's, or pack.<name> for several)")
    p.add_argument("--name", help="mod folder name inside the zip")
    p.add_argument("--out", type=Path, help="zip to write")
    p.add_argument("--verify-main", type=Path, action="append",
                   help="flat main image to check Core's patch against (repeatable: one per game build)")
    p.add_argument("--keep", type=Path, help="keep the ELF files and objects in this folder")
    p.add_argument("--define", action="append", default=[], metavar="NAME",
                   help="compile Core with -DNAME (repeatable): KAE_NO_DEBUG_OUT, KAE_LOAD_ONLY")
    a = p.parse_args(argv)
    mods = [Mod(folder) for folder in a.mods]
    name = a.name or (mods[0].name if len(mods) == 1 else "KaeGae Core")
    out = a.out or REPO / "releases" / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".zip")
    assert not (a.no_core and (a.bundle or not mods)), "--no-core builds mods as their own modules: give a mod, without --bundle"
    with tempfile.TemporaryDirectory() as tmp:
        files = build(mods, a.bundle, a.keep or Path(tmp), a.verify_main, a.define, not a.no_core)
    text = readme(mods, a.bundle, files, not a.no_core)
    files["mod.toml"] = package_manifest(mods, a.bundle, name, not a.no_core, a.id).encode()
    write_zip(out, name, files, text)
    for rel, blob in sorted(files.items()):
        print(f"  {rel}: {len(blob)} bytes")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
