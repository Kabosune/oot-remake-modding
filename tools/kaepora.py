#!/usr/bin/env python3
"""kaepora: check, install and list Ocarina of Time (Switch 2) mods.

    python3 tools/kaepora.py check                      # the mods that are on in the emulator
    python3 tools/kaepora.py check my-mod other.zip     # these folders or zips, with each other
    python3 tools/kaepora.py list
    python3 tools/kaepora.py install my-mod.zip
    python3 tools/kaepora.py remove "My Mod"
    python3 tools/kaepora.py build --game-table <the game's size table>   # shared files, from your own dump
    python3 tools/kaepora.py inspect my-mod             # what a patch writes, and whose space that is
    python3 tools/kaepora.py init my-mod --id me.my-mod # write a mod.toml for an existing mod
    python3 tools/kaepora.py registry                   # who has claimed what
    python3 tools/kaepora.py targets                    # where this tool looks for emulators

Where the mods are: --target fritchii | eden | lichii, or --load-dir with the emulator's `load`
folder. With neither, the tool looks for the emulators it knows and uses the one it finds (if it
finds more than one, it asks you to choose). KAEPORA_TARGET and KAEPORA_LOAD_DIR set a default.

`check` changes nothing. `install` runs the check first and refuses when it finds an error.
The manifest format and the registry are described in api/MANIFEST.md. Needs Python 3.11+ (or
3.10 with `pip install tomli`).
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kaepora_build as kb  # noqa: E402
import kaepora_check as kc  # noqa: E402
import kaepora_manifest as km  # noqa: E402

TITLE_ID = "0400486024DEC000"
MOD_SLOTS = [f"subsdk{n}" for n in range(2, 9)]      # subsdk1 is Kaepora Core's, subsdk9 is left to standalone mods
BUILD_NAMES = {"E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": "1.1.1", "33FA6C2C23848282A77E8B88A0A93F4887C55920": "1.0.0"}

# Emulators and the folder each keeps its data in. On Windows that folder is in %APPDATA%; a
# folder called `user` next to the emulator's .exe takes its place if it exists (give that one
# with --load-dir). Elsewhere it is in $XDG_DATA_HOME (~/.local/share).
# Sources: Lichii's src/common/fs (6 November 2026) for `eden`; Fritchii v5.8.3 on Windows for
# `fritchii` (seen, not read from its source; the non-Windows place is assumed to match).
TARGETS = {
    "fritchii": {"dir": "fritchii", "builtin": "fritchii", "about": "Fritchii v5.8 and later"},
    "eden":     {"dir": "eden", "builtin": None, "about": "Eden"},
    "lichii":   {"dir": "eden", "builtin": "lichii", "about": "Lichii, and Fritchii before v5.8 (they share Eden's folder)"},
}


class Stop(Exception):
    """Something the user has to fix; printed without a traceback."""


# ---- where the mods are ----

def data_dir(target):
    name = TARGETS[target]["dir"]
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / name
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / name


class Place:
    """One emulator's mods for the game: <data>/load/<title id>/<mod folder>."""

    def __init__(self, title_dir, target=None, data=None):
        self.title_dir, self.target, self.data = Path(title_dir), target, data

    @property
    def builtin(self):
        return TARGETS[self.target]["builtin"] if self.target else None

    def folders(self):
        if not self.title_dir.is_dir():
            return []
        return sorted((p for p in self.title_dir.iterdir() if p.is_dir() and not p.name.endswith(".kaepora-new")),
                      key=lambda p: p.name)

    def disabled(self):
        """Folder names switched off in the emulator's Add-Ons list, or None if that can't be read."""
        if not self.data:
            return None
        return read_disabled(self.data / "config" / "qt-config.ini", TITLE_ID)


def read_disabled(ini, title_id):
    """The names listed as disabled for a title in a yuzu-family qt-config.ini (read only)."""
    try:
        text = Path(ini).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    section = re.search(r"^\[DisabledAddOns\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if not section:
        return set()
    entries = dict(re.findall(r"^([^=\n]+)=(.*)$", section.group(1), re.M))
    want = str(int(title_id, 16))
    for key, value in entries.items():
        m = re.fullmatch(r"(\d+)\\title_id", key)
        if m and value.strip() == want:
            n = m.group(1)
            size = int(entries.get(f"{n}\\disabled\\size", "0") or 0)
            names = (entries.get(f"{n}\\disabled\\{k}\\d") for k in range(1, size + 1))
            return {name.strip().strip('"') for name in names if name is not None}
    return set()


def find_place(args):
    load = args.load_dir or os.environ.get("KAEPORA_LOAD_DIR")
    target = args.target or os.environ.get("KAEPORA_TARGET")
    if target and target not in TARGETS:
        raise Stop(f"unknown target {target!r}: targets are {', '.join(TARGETS)}")
    if load:
        load = Path(load)
        title_dir = load if load.name.upper() == TITLE_ID else load / TITLE_ID
        data = load.parent if load.name.lower() == "load" else (load.parent.parent if load.parent.name.lower() == "load" else None)
        return Place(title_dir, target, data)
    if target:
        data = data_dir(target)
        return Place(data / "load" / TITLE_ID, target, data)
    found = [(name, data_dir(name)) for name in TARGETS if name != "lichii" and (data_dir(name) / "load").is_dir()]
    if not found:
        raise Stop("no emulator found. Say where the mods are: --target " + " | ".join(TARGETS)
                   + ", or --load-dir with the emulator's load folder")
    if len(found) > 1:
        raise Stop("more than one emulator found:\n" + "\n".join(f"  --target {n:<9} {d}" for n, d in found)
                   + "\nchoose one with --target (or set KAEPORA_TARGET)")
    name, data = found[0]
    return Place(data / "load" / TITLE_ID, name, data)


# ---- reading mods from folders and zips ----

def mod_roots(folder):
    """Mod folders inside an unpacked download: the folders that hold a mod.toml, exefs or romfs."""
    folder = Path(folder)
    marks = (km.MANIFEST_NAME, "exefs", "romfs", "romfslite")

    def is_root(p):
        return any((p / m).exists() for m in marks) or any(c.name.lower() in marks for c in p.iterdir())

    if is_root(folder):
        return [folder]
    roots = []
    for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
        if is_root(sub):
            roots.append(sub)
        else:
            roots += [s for s in sorted(p for p in sub.iterdir() if p.is_dir()) if is_root(s)]
    return roots


def unpack(source, work):
    """A folder, or a zip unpacked into `work`. Returns the mod folders found in it."""
    source = Path(source)
    if source.is_dir():
        roots = mod_roots(source)
    elif zipfile.is_zipfile(source):
        dest = Path(work) / re.sub(r"[^\w.-]+", "_", source.stem)
        dest.mkdir(parents=True)
        with zipfile.ZipFile(source) as z:
            for info in z.infolist():
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/") or re.match(r"[A-Za-z]:", name):
                    raise Stop(f"{source.name}: refusing to unpack {info.filename!r} (it points outside the zip)")
            z.extractall(dest)
        roots = mod_roots(dest)
        if roots == [dest]:                       # the zip's top level is the mod itself: name it after the zip
            named = dest.parent / source.stem
            dest.rename(named)
            roots = [named]
    else:
        raise Stop(f"{source}: not a folder or a zip")
    if not roots:
        raise Stop(f"{source}: no mod found in it (no folder with a mod.toml, exefs or romfs)")
    return roots


def installed(place, include_disabled=False):
    """(mods that are on, names that are off, whether the on/off state is known)."""
    disabled = place.disabled()
    mods, off = [], []
    for folder in place.folders():
        if disabled and folder.name in disabled and not include_disabled:
            off.append(folder.name)
        else:
            mods.append(km.load_folder(folder))
    return mods, off, disabled is not None


# ---- commands ----

def report(problems):
    for p in problems:
        print(f"  {p}")
    counts, text = kc.summary(problems)
    print(text if problems else "no problems found")
    return 1 if counts["error"] else 0


def cmd_check(args):
    registries = kc.load_registries(args.registry)
    main_image = Path(args.main).read_bytes() if args.main else None
    with tempfile.TemporaryDirectory() as work:
        mods, target = [], args.target
        if args.mods:
            for n, source in enumerate(args.mods):
                mods += [km.load_folder(r) for r in unpack(source, Path(work) / str(n))]
        if not args.mods or args.with_installed:
            place = find_place(args)
            target = place.builtin
            on, off, known = installed(place, args.all)
            names = {m.name for m in mods}
            mods += [m for m in on if m.name not in names]
            print(f"{place.title_dir}" + (f" ({place.target})" if place.target else ""))
            if off:
                print(f"  switched off in the emulator, not checked: {', '.join(off)}")
            if not known:
                print("  (the emulator's Add-Ons list couldn't be read: every folder is treated as on)")
        elif target:
            target = TARGETS[target]["builtin"] if target in TARGETS else target
        print(f"checking {len(mods)} mod folder(s): " + ", ".join(m.label for m in mods))
        return report(kc.check(mods, registries, target, main_image))


def describe(mod, registries):
    parts = []
    for build, records in sorted(mod.patches.items()):
        reg = registries.get(build)
        claim = kc.recognise(reg, km.runs(records)) if reg and records else None
        size = sum(len(b) for _, b in records)
        parts.append(f"patch for {BUILD_NAMES.get(build, build[:8])} ({size} bytes"
                     + (f", {claim.name}'s" if claim and not mod.manifest else "") + ")")
    modules = [n for n in mod.exefs if km.SLOT.fullmatch(n)]
    if modules:
        named = mod.manifest.modules if mod.manifest else {}
        parts.append("modules " + ", ".join(
            f"{n} = {' + '.join(f'{i} {v}' for i, v in named[n])}" if n in named else n for n in sorted(modules)))
    other = [n for n in mod.exefs if not km.SLOT.fullmatch(n)]
    if other:
        parts.append("exefs " + ", ".join(sorted(other)))
    if mod.romfs:
        parts.append(f"{len(mod.romfs)} romfs file(s)")
    return "; ".join(parts) or "nothing the game loads"


def cmd_list(args):
    place = find_place(args)
    registries = kc.load_registries(args.registry)
    disabled = place.disabled()
    print(f"{place.title_dir}" + (f" ({place.target})" if place.target else ""))
    folders = place.folders()
    if not folders:
        print("  no mods installed")
    for folder in folders:
        mod = km.load_folder(folder)
        state = "?  " if disabled is None else ("off" if folder.name in disabled else "on ")
        ident = f"{mod.manifest.id} {mod.manifest.version}" if mod.manifest else "no manifest"
        print(f"  {state} {folder.name}  [{ident}]")
        print(f"        {describe(mod, registries)}")
    if disabled is None:
        print("  (on / off isn't known: the emulator's Add-Ons list couldn't be read)")
    return 0


def assign_slots(mod, taken):
    """Move a new mod's modules out of slots that are taken. Returns [(old, new)]; changes the folder."""
    moves = []
    if not mod.manifest:
        return moves
    for slot in sorted(mod.manifest.modules):
        if slot not in taken:
            taken.add(slot)
            continue
        if any(mod_id == kc.CORE_ID for mod_id, _ in mod.manifest.modules[slot]):
            continue                    # a second Kaepora Core: the check reports it
        free = [s for s in MOD_SLOTS if s not in taken]
        if not free:
            raise Stop(f"{mod.name}: no module slot is free ({MOD_SLOTS[0]} to {MOD_SLOTS[-1]} are taken). "
                       "Remove a mod, or build several into one module with tools/kaemod.py --bundle")
        exefs = km._child(mod.path, "exefs")
        (exefs / slot).rename(exefs / free[0])
        manifest = mod.path / km.MANIFEST_NAME
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(re.sub(rf"^(\s*){slot}(\s*=)", rf"\g<1>{free[0]}\g<2>", text, count=1, flags=re.M), encoding="utf-8")
        taken.add(free[0])
        moves.append((slot, free[0]))
    return moves


def cmd_install(args):
    place = find_place(args)
    registries = kc.load_registries(args.registry)
    with tempfile.TemporaryDirectory() as work:
        roots = [r for n, s in enumerate(args.mods) for r in unpack(s, Path(work) / "in" / str(n))]
        names = [r.name for r in roots]
        if len(set(names)) != len(names):
            raise Stop(f"two of these have the same folder name ({', '.join(sorted(n for n in names if names.count(n) > 1))})")
        on, _, _ = installed(place)
        kept = [m for m in on if m.name not in names]
        taken = {name for m in kept for name in m.exefs if km.SLOT.fullmatch(name)}
        new, moved = [], []
        for root in roots:                              # work on a copy: the source is never changed
            copy = Path(work) / "out" / root.name
            shutil.copytree(root, copy)
            mod = km.load_folder(copy)
            if mod.manifest and mod.manifest.title and mod.manifest.title != TITLE_ID:
                raise Stop(f"{mod.name} is for title {mod.manifest.title}, not Ocarina of Time ({TITLE_ID})")
            moves = assign_slots(mod, taken)
            moved += [(mod.name, a, b) for a, b in moves]
            new.append(km.load_folder(copy) if moves else mod)
        together = new + kept
        print(f"installing into {place.title_dir}" + (f" ({place.target})" if place.target else ""))
        for name, a, b in moved:
            print(f"  {name}: {a} is taken, its module goes in {b}")
        print("check, as if these were installed: " + ", ".join(m.label for m in together))
        failed = report(kc.check(together, registries, place.builtin))
        if failed and not args.force:
            print("not installed: fix the errors above, switch the other mod off, or repeat with --force")
            return 1
        if args.dry_run:
            print("dry run: nothing was copied")
            return 0
        place.title_dir.mkdir(parents=True, exist_ok=True)
        for mod in new:
            dest = place.title_dir / mod.name
            staging = place.title_dir / f".{mod.name}.kaepora-new"
            try:
                if staging.exists():
                    shutil.rmtree(staging)
                shutil.copytree(mod.path, staging)
                replaced = dest.exists()
                if replaced:
                    shutil.rmtree(dest)
                staging.rename(dest)
            except PermissionError as e:
                shutil.rmtree(staging, ignore_errors=True)
                raise Stop(f"couldn't write {dest}: {e}\nThe emulator locks a mod's files while it runs: close it and try again") from e
            print(f"  {'replaced' if replaced else 'installed'} {mod.label}")
        print("Close and reopen the emulator before starting the game: it reads exefs files when the app starts.")
    return 0


def cmd_build(args):
    place = find_place(args)
    with tempfile.TemporaryDirectory() as work:
        mods = [km.load_folder(r) for n, s in enumerate(args.mods) for r in unpack(s, Path(work) / str(n))]
        names = {m.name for m in mods}
        mods += [m for m in installed(place)[0] if m.name not in names]
        mods = [m for m in mods if m.id != kb.BUILT_ID]
        dest = Path(args.out) if args.out else place.title_dir / kb.BUILT_NAME
        requests = kb.collect(mods)
        if not requests:
            print("no installed mod asks for anything to be built"
                  + (f"; {dest} is no longer needed and can be removed" if dest.exists() else ""))
            return 0
        if not args.game_table:
            raise Stop("these mods ask for resource size table entries: " + ", ".join(sorted(requests))
                       + "\ngive the game's own table with --game-table: romfs/System/Resource/"
                         "ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs from your dump (docs/romfs.md)")
        staging = Path(work) / "built"
        try:
            changes, missing, _ = kb.write_folder(staging, TITLE_ID, args.game_table, mods)
        except (kb.TableError, OSError) as e:
            raise Stop(f"{args.game_table}: {e}") from e
        for path, old, new in changes:
            print(f"  {path}: {old} -> {new}  ({', '.join(requests[path][1])})" if new != old
                  else f"  {path}: stays {old}, already enough  ({', '.join(requests[path][1])})")
        for path in missing:
            print(f"  {path}: the game's table has no entry for it, left out  ({', '.join(requests[path][1])})")
        if args.dry_run:
            print("dry run: nothing was written")
            return 0
        try:
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging, dest)
        except PermissionError as e:
            raise Stop(f"couldn't write {dest}: {e}\nClose the emulator and try again") from e
        print(f"wrote {dest}\nIt holds a changed copy of a game file: keep it on this machine.")
    return 1 if missing else 0


def cmd_remove(args):
    place = find_place(args)
    for name in args.names:
        dest = place.title_dir / name
        if Path(name).name != name or not dest.is_dir() or dest.parent != place.title_dir:
            raise Stop(f"no mod folder called {name!r} in {place.title_dir} (see `kaepora list`)")
        try:
            shutil.rmtree(dest)
        except PermissionError as e:
            raise Stop(f"couldn't remove {dest}: {e}\nClose the emulator and try again") from e
        print(f"removed {name}")
    return 0


def cmd_inspect(args):
    registries = kc.load_registries(args.registry)
    with tempfile.TemporaryDirectory() as work:
        for n, source in enumerate(args.mods):
            source = Path(source)
            if source.is_file() and source.suffix.lower() == ".ips":
                mods = [km.ModFolder(path=source, name=source.name,
                                     patches={source.stem.upper(): km.read_ips(source.read_bytes())})]
            else:
                mods = [km.load_folder(r) for r in unpack(source, Path(work) / str(n))]
            for mod in mods:
                print(mod.label)
                print(f"  {describe(mod, registries)}")
                for build, records in sorted(mod.patches.items()):
                    reg = registries.get(build)
                    print(f"  main, build {build} ({BUILD_NAMES.get(build, 'unknown game version')}):")
                    for start, end in km.runs(records):
                        where = ""
                        if reg:
                            owners = [c.owner for c in reg.claims if any(km.overlap((start, end), r) for r in c.code_ranges())]
                            space = reg.space_at("code", (start, end))
                            where = "  " + "; ".join(([f"in [{space}]"] if space else []) + [f"claimed by {', '.join(owners)}"] * bool(owners))
                        kind = "hook" if end - start == km.HOOK_SIZE and not (reg and reg.space_at("code", (start, end))) else "code"
                        print(f"    {start:#9x}..{end:#9x}  {end - start:5} bytes  {kind}{where}")
                for p in mod.problems:
                    print(f"  {p}")
    return 0


def claims_from_patch(records, reg):
    """Guess a manifest's code ranges and hooks from what a patch writes."""
    code, hooks = [], []
    for start, end in km.runs(records):
        in_space = reg.space_at("code", (start, end)) if reg else None
        if end - start == km.HOOK_SIZE and start % 4 == 0 and not in_space:
            hooks.append(start)
        else:
            code.append((start, end, in_space))
    merged = []
    for start, end, space in sorted(code):           # pieces close together in one free space become one range
        if merged and space and merged[-1][2] == space and start - merged[-1][1] <= 0x1000:
            merged[-1] = (merged[-1][0], end, space)
        else:
            merged.append((start, end, space))
    return [(s, e) for s, e, _ in merged], hooks


def cmd_init(args):
    folder = Path(args.folder)
    if not folder.is_dir():
        raise Stop(f"{folder}: not a folder")
    target = folder / km.MANIFEST_NAME
    if target.exists() and not args.force:
        raise Stop(f"{target} exists already (use --force to write over it)")
    if not km.ID.fullmatch(args.id):
        raise Stop(f"--id {args.id!r}: an id is author.mod-name, lower case letters, digits and -")
    mod = km.load_folder(folder)
    registries = kc.load_registries(args.registry)
    quote = lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'     # noqa: E731
    lines = ["# Kaepora manifest (api/MANIFEST.md in https://github.com/Kabosune/oot-remake-modding).",
             "manifest = 1", "",
             f"id       = {quote(args.id)}",
             f"name     = {quote(args.name or folder.name)}",
             f"version  = {quote(args.version)}",
             f"authors  = [{', '.join(quote(a) for a in (args.author or ['(your name)']))}]",
             f"license  = {quote(args.license)}" if args.license else '# license = "MIT"',
             "", "[game]", f'title = "{TITLE_ID}"']
    for build, records in sorted(mod.patches.items()):
        code, hooks = claims_from_patch(records, registries.get(build))
        lines += ["", f"[build.{build}]" + (f"      # {BUILD_NAMES[build]}" if build in BUILD_NAMES else ""),
                  f'ips    = "exefs/{build}.ips"',
                  "code   = [" + ", ".join(quote(km.fmt_range(r)) for r in code) + "]",
                  "hooks  = [" + ", ".join(quote(f"{h:#x}") for h in hooks) + "]",
                  "# memory = []      # writable memory the mod uses at run time: this tool can't see it, add it by hand"]
    modules = sorted(n for n in mod.exefs if km.SLOT.fullmatch(n))
    if modules:
        lines += ["", "[modules]"] + [f'{n} = "{args.id}@{args.version}"      # say what this module is' for n in modules]
    lines += ["", "# [input]            # the buttons the mod listens for, so clashes with other mods are found",
              '# toggle = "R3"']
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    again = km.load_folder(folder)
    print(f"wrote {target}")
    for p in again.problems:
        print(f"  {p}")
    print("Read it through: ranges are guessed from the patch. Then run `kaepora check` on the folder.")
    return 0


def cmd_registry(args):
    for build, reg in sorted(kc.load_registries(args.registry).items(), key=lambda kv: kv[1].version, reverse=True):
        print(f"build {build} (game version {reg.version})")
        for name, (kind, r) in reg.spaces.items():
            parts = [km.overlap(x, r) for c in reg.claims for x in getattr(c, kind)]
            used = sum(e - s for s, e in km.merge_ranges(o for o in parts if o))
            print(f"  [{name}] {kind} {km.fmt_range(r)}: {r[1] - r[0]} bytes, {used} claimed")
        for claim in reg.claims:
            tags = [t for t, on in (("not a standard mod", not claim.standard), ("retired", claim.retired),
                                    ("built into " + ", ".join(claim.builtin), bool(claim.builtin))) if on]
            print(f"  {claim.owner}: {claim.name}" + (f" ({'; '.join(tags)})" if tags else ""))
            for kind in ("code", "memory"):
                if getattr(claim, kind):
                    print(f"      {kind:<6} " + ", ".join(km.fmt_range(r) for r in getattr(claim, kind)))
            if claim.hooks:
                print("      hooks  " + ", ".join(f"{h:#x}" for h in claim.hooks))
        faults = kc.registry_problems(reg)
        for fault in faults:
            print(f"  FAULT: {fault}")
        if faults:
            return 1
    return 0


def cmd_targets(args):
    for name, t in TARGETS.items():
        data = data_dir(name)
        state = "found" if (data / "load").is_dir() else "not found"
        print(f"  {name:<9} {data / 'load' / TITLE_ID}  ({state})  {t['about']}")
    print("Any other emulator or a portable install: --load-dir <its load folder>.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="kaepora", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    where = argparse.ArgumentParser(add_help=False)
    where.add_argument("--target", help="the emulator: " + ", ".join(TARGETS))
    where.add_argument("--load-dir", type=Path, help="the emulator's load folder (or the game's folder inside it)")
    where.add_argument("--registry", type=Path, default=kc.REGISTRY_DIR, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", parents=[where], help="look for mods that can't be on together")
    c.add_argument("mods", nargs="*", help="mod folders or zips; without any, the installed mods that are on")
    c.add_argument("--with-installed", action="store_true", help="check the given mods together with the installed ones")
    c.add_argument("--all", action="store_true", help="include mods switched off in the emulator")
    c.add_argument("--main", type=Path, help="a flat image of the unpatched main (tools/flatten_nso.py): also check what patches replace")
    c.set_defaults(run=cmd_check)

    c = sub.add_parser("list", parents=[where], help="the installed mods")
    c.set_defaults(run=cmd_list)

    c = sub.add_parser("install", parents=[where], help="check, then copy mods into the emulator's load folder")
    c.add_argument("mods", nargs="+", help="mod folders or zips")
    c.add_argument("--force", action="store_true", help="install even when the check finds errors")
    c.add_argument("--dry-run", action="store_true", help="check only, copy nothing")
    c.set_defaults(run=cmd_install)

    c = sub.add_parser("build", parents=[where], help="make the files several mods share (the resource size table) from your dump")
    c.add_argument("mods", nargs="*", help="more mod folders or zips to count, besides the installed ones that are on")
    c.add_argument("--game-table", type=Path, help="the game's own resource size table, from your dump")
    c.add_argument("--out", type=Path, help=f"where to write the folder (default: '{kb.BUILT_NAME}' in the load folder)")
    c.add_argument("--dry-run", action="store_true", help="say what would change, write nothing")
    c.set_defaults(run=cmd_build)

    c = sub.add_parser("remove", parents=[where], help="delete an installed mod folder")
    c.add_argument("names", nargs="+", help="folder names, as `list` shows them")
    c.set_defaults(run=cmd_remove)

    c = sub.add_parser("inspect", parents=[where], help="show what a mod's patch writes")
    c.add_argument("mods", nargs="+", help="mod folders, zips or .ips files")
    c.set_defaults(run=cmd_inspect)

    c = sub.add_parser("init", parents=[where], help="write a mod.toml for an existing mod folder")
    c.add_argument("folder")
    c.add_argument("--id", required=True, help="author.mod-name")
    c.add_argument("--name")
    c.add_argument("--version", default="1.0.0")
    c.add_argument("--author", action="append")
    c.add_argument("--license")
    c.add_argument("--force", action="store_true")
    c.set_defaults(run=cmd_init)

    c = sub.add_parser("registry", parents=[where], help="print the registry: free space and who has claimed what")
    c.set_defaults(run=cmd_registry)
    c = sub.add_parser("targets", parents=[where], help="where this tool looks for emulators")
    c.set_defaults(run=cmd_targets)

    args = p.parse_args(argv)
    try:
        return args.run(args)
    except Stop as e:
        print(f"kaepora: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
