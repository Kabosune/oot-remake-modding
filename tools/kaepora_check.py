#!/usr/bin/env python3
"""Compare mod folders with each other and with the registry: what `kaepora check` reports.

A check never changes anything. It reads each folder (tools/kaepora_manifest.py), then looks for
mods that can't be on together: patches that write the same bytes, two hooks on one instruction,
the same file from two folders, the same buttons, requirements nobody meets. Mods without a
manifest are checked by their bytes and files.

Levels: an error means the set of mods should not be started as it is; a warning means something
may not work as the player expects; a note is information.
"""
try:
    import tomllib
except ImportError:          # Python 3.10: pip install tomli
    import tomli as tomllib
from dataclasses import dataclass, field
from pathlib import Path

from kaepora_manifest import (BUILD_ID, HOOK_SIZE, ID, SLOT, Problem, byte_map, fmt_range, merge_ranges, overlap,
                              parse_int, parse_range, relation_holds, runs)

REPO = Path(__file__).resolve().parent.parent
REGISTRY_DIR = REPO / "registry"
CORE_ID = "kaepora.core"
CORE_SLOT = "subsdk1"
SPACE_KINDS = ("code", "memory")


# ---- the registry ----

@dataclass
class Claim:
    owner: str
    name: str
    code: list = field(default_factory=list)
    memory: list = field(default_factory=list)
    hooks: list = field(default_factory=list)
    standard: bool = True
    builtin: tuple = ()         # emulators that apply this patch themselves
    retired: bool = False
    shared: tuple = ()          # owners this claim is known to overlap (recorded, not approved)
    note: str = ""

    def code_ranges(self):
        return self.code + [(h, h + HOOK_SIZE) for h in self.hooks]


@dataclass
class Registry:
    build: str
    version: str
    path: Path
    spaces: dict = field(default_factory=dict)      # name -> (kind, (start, end))
    claims: list = field(default_factory=list)

    def claim_of(self, owner):
        return next((c for c in self.claims if c.owner == owner), None)

    def space_at(self, kind, r):
        """The free space of this kind that holds the whole range, or None."""
        for name, (k, space) in self.spaces.items():
            if k == kind and space[0] <= r[0] and r[1] <= space[1]:
                return name
        return None


def load_registry(path):
    path = Path(path)
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    where = path.name
    assert BUILD_ID.fullmatch(raw.get("build", "")), f"{where}: build must be 40 hex digits, upper case"
    reg = Registry(build=raw["build"], version=str(raw.get("version", "")), path=path)
    for name, space in raw.get("space", {}).items():
        assert space.get("kind") in SPACE_KINDS, f"{where}: [space.{name}] kind must be one of {SPACE_KINDS}"
        reg.spaces[name] = (space["kind"], parse_range(space["range"], f"{where} [space.{name}]"))
    for n, entry in enumerate(raw.get("claim", []), 1):
        owner = entry.get("owner", "")
        assert ID.fullmatch(owner), f"{where}: claim {n}: owner {owner!r} is not an id (author.mod-name)"
        assert reg.claim_of(owner) is None, f"{where}: {owner} has two [[claim]] tables: keep one per mod"
        what = f"{where} claim {owner}"
        reg.claims.append(Claim(
            owner=owner, name=entry.get("name", owner),
            code=[parse_range(r, what) for r in entry.get("code", [])],
            memory=[parse_range(r, what) for r in entry.get("memory", [])],
            hooks=[parse_int(h, what) for h in entry.get("hooks", [])],
            standard=entry.get("standard", True), builtin=tuple(entry.get("builtin", ())),
            retired=entry.get("retired", False), shared=tuple(entry.get("shared", ())), note=entry.get("note", "")))
    return reg


def load_registries(folder=REGISTRY_DIR):
    """{build id: Registry} for every registry/<build>.toml."""
    out = {}
    for path in sorted(Path(folder).glob("*.toml")):
        reg = load_registry(path)
        assert reg.build not in out, f"{path.name}: a second registry for build {reg.build}"
        out[reg.build] = reg
    return out


def registry_problems(reg):
    """Faults in the registry itself: overlapping claims, claims outside any free space."""
    out = []
    for i, a in enumerate(reg.claims):
        for kind in SPACE_KINDS:
            for r in getattr(a, kind):
                if a.standard and reg.spaces and reg.space_at(kind, r) is None:
                    out.append(f"{a.owner}: {kind} {fmt_range(r)} is not inside any [space] of kind {kind}")
        for b in reg.claims[i + 1:]:
            if b.owner in a.shared or a.owner in b.shared:
                continue
            for kind, ra, rb in _claim_overlaps(a, b):
                out.append(f"{a.owner} and {b.owner} both claim {kind} {fmt_range(overlap(ra, rb))}")
    return out


def _claim_overlaps(a, b):
    for ra in a.code_ranges():
        for rb in b.code_ranges():
            if overlap(ra, rb):
                yield "code", ra, rb
    for ra in a.memory:
        for rb in b.memory:
            if overlap(ra, rb):
                yield "memory", ra, rb


def recognise(reg, written):
    """The registry claim that all of a patch's written stretches fall inside, if there is one."""
    if not written:
        return None
    for claim in reg.claims:
        allowed = merge_ranges(claim.code_ranges())
        if allowed and all(any(a[0] <= s and e <= a[1] for a in allowed) for s, e in written):
            return claim
    return None


# ---- the check ----

def _pairs(items):
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            yield a, b


def _owner(mod, reg):
    """The id a folder's patch belongs to: its manifest's, or the one the registry recognises."""
    if mod.id:
        return mod.id
    if reg and reg.build in mod.patches:
        claim = recognise(reg, runs(mod.patches[reg.build]))
        return claim.owner if claim else None
    return None


def check(mods, registries=None, target=None, main_image=None):
    """Problems for a set of mod folders that would be on together.

    mods: ModFolder objects (enabled ones only). registries: {build id: Registry}.
    target: the emulator's name, to count its built-in patches ("fritchii", "lichii"); None leaves
    them as notes. main_image: a flat image of the unpatched main, to check what patches replace.
    """
    registries = registries or {}
    out = []
    for mod in mods:
        out += mod.problems
        if not mod.patches and not mod.exefs and not mod.romfs:
            out.append(Problem("note", "empty", "nothing here that the game loads (no exefs or romfs folder)", (mod.name,)))

    out += _check_ids(mods)
    out += _check_files(mods)
    for build in sorted({b for mod in mods for b in mod.patches} | {b for mod in mods if mod.manifest for b in mod.manifest.builds}):
        reg = registries.get(build)
        out += _check_build(mods, build, reg, target)
        if main_image is not None and reg is not None:
            out += _check_main(mods, build, reg, main_image)
    out += _check_inputs(mods)
    out += _check_relations(mods)
    out += _check_core(mods)
    out += _check_size_table(mods)
    order = {"error": 0, "warning": 1, "note": 2}
    return sorted(out, key=lambda p: order[p.level])


def _check_ids(mods):
    out, seen = [], {}
    for mod in mods:
        if mod.manifest:
            for mod_id, version in mod.manifest.provides().items():
                seen.setdefault(mod_id, []).append((mod, version))
    for mod_id, holders in sorted(seen.items()):
        if len(holders) > 1:
            names = tuple(m.name for m, _ in holders)
            versions = ", ".join(f"{m.name} has {v}" for m, v in holders)
            out.append(Problem("error", "duplicate-id", f"{mod_id} is in more than one folder ({versions}): "
                                                        "keep one of them on", names))
    return out


def _check_files(mods):
    out = []
    for a, b in _pairs(mods):
        for name in sorted(set(a.exefs) & set(b.exefs)):
            what = "a module slot" if SLOT.fullmatch(name) else "a file of the game's program"
            out.append(Problem("error", "exefs-clash", f"both have exefs/{name} ({what}): the game loads only one of them",
                               (a.name, b.name)))
        shared = sorted(set(a.romfs) & set(b.romfs))
        if shared:
            shown = ", ".join(shared[:3]) + (f" and {len(shared) - 3} more" if len(shared) > 3 else "")
            out.append(Problem("error", "romfs-clash", f"both replace romfs/{shown}: the game sees only one copy",
                               (a.name, b.name)))
    return out


def _check_build(mods, build, reg, target):
    out = []
    patched = [m for m in mods if build in m.patches]
    maps = {m.name: byte_map(m.patches[build]) for m in patched}

    # the bytes themselves, whoever wrote them
    for a, b in _pairs(patched):
        both = sorted(set(maps[a.name]) & set(maps[b.name]))
        if not both:
            continue
        ranges = merge_ranges((o, o + 1) for o in both)
        shown = ", ".join(f"main+{fmt_range(r)}" for r in ranges[:3]) + (" ..." if len(ranges) > 3 else "")
        if all(maps[a.name][o] == maps[b.name][o] for o in both):
            out.append(Problem("warning", "same-bytes", f"both write the same bytes at {shown} (build {build[:8]}). "
                                                         "That works, but it usually means two copies of one thing",
                               (a.name, b.name)))
        else:
            out.append(Problem("error", "byte-overlap", f"their patches overwrite each other at {shown} "
                                                        f"(build {build[:8]}, {len(both)} bytes)", (a.name, b.name)))

    # what the manifests claim, beyond what is written today
    claimed = [m for m in mods if m.manifest and build in m.manifest.builds]
    for a, b in _pairs(claimed):
        ca, cb = a.manifest.builds[build], b.manifest.builds[build]
        for hook in sorted(set(ca.hooks) & set(cb.hooks)):
            out.append(Problem("error", "hook-clash", f"both hook the instruction at main+{hook:#x} (build {build[:8]}). "
                                                      "An instruction can have one owner: ask for a Core hook point there",
                               (a.name, b.name)))
        for kind in ("code", "memory"):
            for ra in getattr(ca, kind):
                for rb in getattr(cb, kind):
                    if overlap(ra, rb):
                        out.append(Problem("error", f"{kind}-clash",
                                           f"both claim {kind} main+{fmt_range(overlap(ra, rb))} (build {build[:8]})",
                                           (a.name, b.name)))

    if reg is None:
        if patched:
            out.append(Problem("note", "no-registry", f"there is no registry for build {build[:8]}, so patches for it "
                                                      "were only compared with each other"))
        return out

    # against the registry: space registered to someone else, space nobody registered
    present = {_owner(m, reg) for m in mods}
    for mod in patched:
        owner = _owner(mod, reg)
        written = runs(mod.patches[build])
        if owner is None:
            out.append(Problem("note", "unknown-patch", f"no manifest, and its patch for {build[:8]} isn't one the "
                                                        f"registry knows ({len(written)} stretches of main)", (mod.name,)))
        elif not mod.id:
            out.append(Problem("note", "recognised", f"no manifest; its patch is {reg.claim_of(owner).name}'s ({owner})",
                               (mod.name,)))
        mine = reg.claim_of(owner) if owner else None
        if mod.id and mine is None:
            if mod.manifest.level == 2:
                out.append(Problem("warning", "unregistered", f"{mod.id} patches main but has no claim in "
                                                              f"registry/{reg.path.name}: add one so other mods keep clear",
                                   (mod.name,)))
        elif mod.id:
            allowed = merge_ranges(mine.code_ranges())
            for start, end in written:
                if not any(a[0] <= start and end <= a[1] for a in allowed):
                    out.append(Problem("warning", "outside-claim", f"writes main+{start:#x}..{end:#x}, outside what "
                                                                   f"{mod.id} has registered", (mod.name,)))
            for r in mod.manifest.builds[build].memory if build in mod.manifest.builds else []:
                if not any(a[0] <= r[0] and r[1] <= a[1] for a in mine.memory):
                    out.append(Problem("warning", "outside-claim", f"uses memory main+{fmt_range(r)}, outside what "
                                                                   f"{mod.id} has registered", (mod.name,)))
        for claim in reg.claims:
            if claim.owner == owner or claim.owner in present and not claim.builtin:
                continue        # its own space; or the other mod is installed and was compared above
            hits = [overlap(w, c) for w in written for c in claim.code_ranges() if overlap(w, c)]
            if not hits:
                continue
            where = ", ".join(f"main+{fmt_range(h)}" for h in merge_ranges(hits)[:3])
            if claim.builtin:
                if target in claim.builtin:
                    out.append(Problem("warning", "builtin-clash", f"writes {where}, which {claim.name} also uses. "
                                       f"On {target} one of the two is left out" + (f" ({claim.note})" if claim.note else ""),
                                       (mod.name,)))
                else:
                    out.append(Problem("note", "builtin-clash", f"writes {where}, which {claim.name} also uses "
                                       f"(matters on {', '.join(claim.builtin)})", (mod.name,)))
            elif not claim.retired:
                out.append(Problem("note", "registered-to-other", f"writes {where}, registered to {claim.name} "
                                   f"({claim.owner}): the two can't be on together", (mod.name,)))
    return out


def _check_main(mods, build, reg, image):
    """With the real main at hand: new code must land on zero padding."""
    out = []
    for mod in mods:
        if build not in mod.patches:
            continue
        for off, blob in mod.patches[build]:
            if len(blob) <= HOOK_SIZE:
                continue        # a hook: it replaces an instruction on purpose
            if off + len(blob) > len(image):
                out.append(Problem("error", "outside-main", f"writes main+{off:#x}, past the end of main", (mod.name,)))
            elif any(image[off:off + len(blob)]):
                out.append(Problem("error", "overwrites-game", f"its {len(blob)} bytes at main+{off:#x} replace bytes "
                                                               "that aren't zero padding: that is game code or data",
                                   (mod.name,)))
    return out


def _check_inputs(mods):
    out, uses = [], {}
    for mod in mods:
        if mod.manifest:
            for action, binding in mod.manifest.inputs.items():
                uses.setdefault(binding, []).append((mod, action))
    for binding, users in sorted(uses.items()):
        folders = {m.name for m, _ in users}
        if len(folders) > 1:
            who = ", ".join(f"{m.manifest.name}'s {action!r}" for m, action in users)
            out.append(Problem("warning", "input-clash", f"{binding} is the default for {who}: one press does all of them",
                               tuple(sorted(folders))))
    return out


def _check_relations(mods):
    out = []
    have = {}
    for mod in mods:
        if mod.manifest:
            have.update(mod.manifest.provides())
    for mod in mods:
        if not mod.manifest:
            continue
        for mod_id, op, version in mod.manifest.requires:
            if mod_id not in have:
                out.append(Problem("error", "requires", f"needs {mod_id}{(' ' + op + ' ' + version) if op else ''}, "
                                                        "which isn't installed (or has no manifest)", (mod.name,)))
            elif not relation_holds(op, version, have[mod_id]):
                out.append(Problem("error", "requires", f"needs {mod_id} {op} {version}; {have[mod_id]} is installed",
                                   (mod.name,)))
        for mod_id, op, version in mod.manifest.conflicts:
            if mod_id in have and mod_id not in mod.manifest.provides() and relation_holds(op, version or "0", have[mod_id]):
                other = next(m.name for m in mods if m.manifest and mod_id in m.manifest.provides())
                out.append(Problem("error", "conflicts", f"says it can't run with {mod_id}", (mod.name, other)))
    return out


def _check_core(mods):
    """Core mods: one Core, mods built for its API version."""
    out = []
    cores = [(m, version) for m in mods if m.manifest for mod_id, version in m.manifest.module_ids() if mod_id == CORE_ID]
    with_slot1 = [m for m in mods if CORE_SLOT in m.exefs]
    wanting = [m for m in mods if m.manifest and (m.manifest.core is not None
                                                  or any(i == CORE_ID for i, _, _ in m.manifest.requires))]
    for mod in wanting:
        asked = any(i == CORE_ID for i, _, _ in mod.manifest.requires)     # then "requires" has said it already
        if not cores and not with_slot1 and not asked:
            out.append(Problem("error", "no-core", "is a core mod, and Kaepora Core is not installed: "
                                                   "it will load and do nothing", (mod.name,)))
        api = (mod.manifest.core or {}).get("api")
        for holder, core_version in cores:
            core_api = ".".join(core_version.split(".")[:2])
            if api and api != core_api and api.split(".")[0] == "0":
                out.append(Problem("error", "api-mismatch", f"is built for Core API {api}; {holder.name} holds Core "
                                                            f"{core_version}. Before 1.0 the two must match exactly",
                                   (mod.name, holder.name)))
    for mod in with_slot1:
        if not (mod.manifest and CORE_SLOT in mod.manifest.modules):
            out.append(Problem("note", "unnamed-core", f"has exefs/{CORE_SLOT} (where Kaepora Core goes) but no manifest "
                                                       "saying which version it is", (mod.name,)))
    return out


def _check_size_table(mods):
    out, asks = [], {}
    for mod in mods:
        if mod.manifest:
            for path, size in mod.manifest.size_table.items():
                asks.setdefault(path, []).append((mod, size))
    shipping = [m for m in mods if any("ResourceSizeTable" in p for p in m.romfs)]
    if asks and shipping:
        out.append(Problem("warning", "size-table", "ships a whole resource size table while other mods ask for entries "
                                                    f"in it ({', '.join(sorted(asks))}): their requests are lost unless the "
                                                    "table is rebuilt with `kaepora build`", tuple(m.name for m in shipping)))
    if asks:
        n = sum(len(v) for v in asks.values())
        out.append(Problem("note", "size-table", f"{n} resource size table request(s) for {len(asks)} file(s): "
                                                 "they are merged, the largest wins"))
    return out


def summary(problems):
    counts = {level: sum(1 for p in problems if p.level == level) for level in ("error", "warning", "note")}
    return counts, ", ".join(f"{n} {level}{'s' if n != 1 else ''}" for level, n in counts.items())
