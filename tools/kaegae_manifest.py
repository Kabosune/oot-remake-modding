#!/usr/bin/env python3
"""Read and check a KaeGae manifest (mod.toml), and read the patches a mod folder holds.

The format is described in api/MANIFEST.md. This module has no opinion about other mods: it only
says whether one folder is a well-formed package and whether its manifest tells the truth about
its own patch. tools/kaegae_check.py compares folders with each other.

Needs Python 3.11+ (or 3.10 with `pip install tomli`). Offsets everywhere are module offsets: the address in this repo's
docs minus 0x80020000, which is also the offset in an IPS32 patch minus the 0x100-byte NSO header.
"""
import re
import struct
try:
    import tomllib
except ImportError:          # Python 3.10: pip install tomli
    import tomli as tomllib
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_VERSION = 1
MANIFEST_NAME = "mod.toml"
NSO_HEADER_SIZE = 0x100
HOOK_SIZE = 4                       # one AArch64 instruction

ID = re.compile(r"[a-z0-9][a-z0-9-]*\.[a-z0-9][a-z0-9-]*")
VERSION = re.compile(r"\d+(\.\d+){0,2}([-+][0-9A-Za-z.-]+)?")
BUILD_ID = re.compile(r"[0-9A-F]{40}")
TITLE_ID = re.compile(r"[0-9A-F]{16}")
SLOT = re.compile(r"subsdk[0-9]")
RELATION = re.compile(r"\s*([a-z0-9.-]+)\s*(?:(>=|<=|==|>|<)\s*([0-9][0-9A-Za-z.+-]*))?\s*")

# Names a manifest may use for controller buttons. The first sixteen are the ones KaeGae Core
# knows (KAE_A ... KAE_DOWN in kaegae.h); a chord is written with "+" between names: "L+Left".
BUTTONS = ("A", "B", "X", "Y", "L", "R", "ZL", "ZR", "L3", "R3", "Plus", "Minus", "Up", "Down", "Left", "Right",
           "SL", "SR", "Home", "Capture", "C")
MOUSE = ("left", "right", "middle", "back", "forward")
EVENTS = ("frame", "input", "draw", "actor_move", "player_move", "view", "scene_change", "pause_change")
PATCH_KINDS = {
    "size-table": ("path", "at-least"),
    "byml": ("path", "set"),
    "text": ("path", "message", "text"),
    "binary": ("path", "sha256", "diff"),
    "script": ("run", "reads", "writes"),
}
TOP_KEYS = {"manifest", "id", "name", "version", "authors", "license", "homepage", "description",
            "game", "build", "modules", "romfs", "romfs-patch", "input", "relations", "core"}


class ManifestError(Exception):
    """The file can't be read as a manifest at all."""


@dataclass
class Problem:
    level: str          # "error", "warning" or "note"
    code: str           # a short, stable name for the kind of problem
    text: str
    mods: tuple = ()    # folder names it is about

    def __str__(self):
        who = " + ".join(self.mods)
        return f"{self.level}: {who + ': ' if who else ''}{self.text}  [{self.code}]"


def parse_int(value, what):
    if isinstance(value, bool):
        raise ValueError(f"{what}: {value!r} is not a number")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.replace("_", ""), 0)
        except ValueError:
            pass
    raise ValueError(f"{what}: {value!r} is not a number (write 0x3C46B00 or \"0x3C46B00\")")


def parse_range(value, what):
    """'0x3C46B00..0x3C46FB0' -> (start, end), end not included."""
    if not isinstance(value, str) or ".." not in value:
        raise ValueError(f"{what}: {value!r} is not a range (write \"0x3C46B00..0x3C46FB0\", end not included)")
    a, _, b = value.partition("..")
    start, end = parse_int(a.strip(), what), parse_int(b.strip(), what)
    if not 0 <= start < end:
        raise ValueError(f"{what}: {value!r} is empty or backwards")
    return start, end


def fmt_range(r):
    return f"{r[0]:#x}..{r[1]:#x}"


def overlap(a, b):
    """The part two ranges share, or None."""
    start, end = max(a[0], b[0]), min(a[1], b[1])
    return (start, end) if start < end else None


def merge_ranges(ranges):
    out = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def version_key(text):
    """'1.2.0-beta' -> (1, 2, 0). Anything after - or + is ignored when comparing."""
    core = re.split(r"[-+]", text, maxsplit=1)[0]
    parts = [int(p) for p in core.split(".") if p.isdigit()]
    return tuple(parts + [0] * (3 - len(parts)))


def parse_relation(text):
    """'kaegae.core>=0.3' -> ('kaegae.core', '>=', '0.3'); a bare id -> (id, None, None)."""
    m = RELATION.fullmatch(text) if isinstance(text, str) else None
    if not m or not ID.fullmatch(m.group(1)):
        raise ValueError(f"{text!r} is not \"author.mod-name\" with an optional version, such as \"kaegae.core>=0.3\"")
    return m.group(1), m.group(2), m.group(3)


def relation_holds(op, wanted, have):
    if op is None:
        return True
    a, b = version_key(have), version_key(wanted)
    return {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b}[op]


def parse_binding(text):
    """One default binding -> a canonical form, so that 'Left+L' and 'L+Left' compare equal.

    'R3', 'L+Left', 'key:,', 'mouse:left'. Raises ValueError for anything else."""
    if not isinstance(text, str) or not text:
        raise ValueError(f"{text!r} is not a button name")
    if text.startswith("key:"):
        if len(text) < 5:
            raise ValueError("key: needs a key after it, such as \"key:,\" or \"key:F5\"")
        return "key:" + text[4:].lower()
    if text.startswith("mouse:"):
        if text[6:] not in MOUSE:
            raise ValueError(f"{text!r}: mouse buttons are {', '.join(MOUSE)}")
        return text
    names = [n.strip() for n in text.split("+")]
    lookup = {b.lower(): b for b in BUTTONS}
    fixed = []
    for n in names:
        if n.lower() not in lookup:
            raise ValueError(f"{text!r}: {n!r} is not a button. Buttons are {', '.join(BUTTONS)}; "
                             "the + and - buttons are written Plus and Minus")
        fixed.append(lookup[n.lower()])
    if len(set(fixed)) != len(fixed):
        raise ValueError(f"{text!r} names a button twice")
    return "+".join(sorted(fixed, key=BUTTONS.index))


# ---- patches ----

def read_ips(data):
    """[(module offset, bytes)] from an IPS32 or classic IPS patch to an NSO.

    Offsets in the file count the 0x100-byte NSO header (as Lichii, yuzu and Atmosphere expect),
    so it is taken off here. A record that starts inside the header is an error."""
    if data[:5] == b"IPS32":
        width, end = 4, b"EEOF"
    elif data[:5] == b"PATCH":
        width, end = 3, b"EOF"
    else:
        raise ValueError("not an IPS file (it starts with neither IPS32 nor PATCH)")
    records, p = [], 5
    while True:
        if data[p:p + len(end)] == end:
            break
        if p + width + 2 > len(data):
            raise ValueError("the patch ends without its end marker")
        offset = int.from_bytes(data[p:p + width], "big")
        size = struct.unpack_from(">H", data, p + width)[0]
        p += width + 2
        if size:
            chunk = data[p:p + size]
            p += size
        else:                                   # run-length record: a count and one byte to repeat
            count = struct.unpack_from(">H", data, p)[0]
            chunk = data[p + 2:p + 3] * count
            size = count
            p += 3
        if len(chunk) != size:
            raise ValueError("the patch is cut off in the middle of a record")
        if offset < NSO_HEADER_SIZE:
            raise ValueError(f"a record at file offset {offset:#x} writes into the NSO header")
        records.append((offset - NSO_HEADER_SIZE, bytes(chunk)))
    return records


def runs(records):
    """Merge a patch's records into the stretches of the module it writes: [(start, end)]."""
    return merge_ranges((off, off + len(blob)) for off, blob in records)


def byte_map(records):
    """{module offset: byte} for a patch (later records win, as when it is applied)."""
    out = {}
    for off, blob in records:
        for k, value in enumerate(blob):
            out[off + k] = value
    return out


# ---- a manifest ----

@dataclass
class BuildClaims:
    build: str
    ips: str | None = None
    code: list = field(default_factory=list)       # ranges of main filled with new code or data
    memory: list = field(default_factory=list)     # ranges of main's writable memory used at run time
    hooks: list = field(default_factory=list)      # offsets of single instructions replaced


@dataclass
class Manifest:
    path: Path
    raw: dict
    id: str = ""
    name: str = ""
    version: str = ""
    title: str = ""
    builds: dict = field(default_factory=dict)      # build id -> BuildClaims
    modules: dict = field(default_factory=dict)     # "subsdk2" -> [(id, version)]: what is linked into that module
    inputs: dict = field(default_factory=dict)      # action -> canonical binding
    requires: list = field(default_factory=list)    # (id, op, version)
    conflicts: list = field(default_factory=list)
    load_after: list = field(default_factory=list)
    size_table: dict = field(default_factory=dict)  # romfs path -> at least this many bytes
    patches: list = field(default_factory=list)     # every [[romfs-patch]] table
    core: dict | None = None
    problems: list = field(default_factory=list)

    @property
    def level(self):
        """1 package, 2 registered (claims space in main), 3 core mod."""
        if self.core is not None:
            return 3
        return 2 if any(b.code or b.hooks or b.memory for b in self.builds.values()) else 1

    def module_ids(self):
        """[(id, version)] of everything linked into this folder's modules."""
        return [entry for entries in self.modules.values() for entry in entries]

    def provides(self):
        """{id: version} of everything this folder puts in the game: itself and its modules."""
        return {self.id: self.version, **dict(self.module_ids())}


def load_manifest(path):
    """Parse a mod.toml. Problems that don't stop parsing are collected in .problems."""
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise ManifestError(f"{path}: {e}") from e
    m = Manifest(path=path, raw=raw)
    err = lambda code, text: m.problems.append(Problem("error", code, text))        # noqa: E731
    warn = lambda code, text: m.problems.append(Problem("warning", code, text))     # noqa: E731

    if raw.get("manifest") != MANIFEST_VERSION:
        err("manifest-version", f"manifest = {raw.get('manifest')!r}; this tool reads manifest = {MANIFEST_VERSION}")
    for key in sorted(set(raw) - TOP_KEYS):
        warn("unknown-key", f"unknown key {key!r} (ignored; a typo?)")

    m.id = raw.get("id", "")
    if not isinstance(m.id, str) or not ID.fullmatch(m.id):
        err("id", f"id = {m.id!r}: an id is \"author.mod-name\", lower case letters, digits and -")
        m.id = str(m.id)
    m.name = raw.get("name", "")
    if not isinstance(m.name, str) or not m.name.strip():
        err("name", "name is missing")
        m.name = m.id
    m.version = raw.get("version", "")
    if not isinstance(m.version, str) or not VERSION.fullmatch(m.version):
        err("version", f"version = {m.version!r}: write it as \"1.2.0\"")
        m.version = "0"
    authors = raw.get("authors")
    if not (isinstance(authors, list) and authors and all(isinstance(a, str) for a in authors)):
        err("authors", "authors must be a list of at least one name")
    if not isinstance(raw.get("license"), str):
        warn("license", "no license given: other people can't tell whether they may share or build on the mod")

    game = raw.get("game", {})
    m.title = str(game.get("title", "")) if isinstance(game, dict) else ""
    if not TITLE_ID.fullmatch(m.title):
        err("title", f"[game] title = {m.title!r}: the title ID is 16 hex digits, upper case")

    for build, table in (raw.get("build") or {}).items():
        if not BUILD_ID.fullmatch(build):
            err("build-id", f"[build.{build}]: a build ID is 40 hex digits, upper case")
            continue
        claims = BuildClaims(build=build, ips=table.get("ips"))
        for key in sorted(set(table) - {"ips", "code", "memory", "hooks"}):
            hint = " (it is called code now)" if key == "cave" else ""
            warn("unknown-key", f"[build.{build[:8]}]: unknown key {key!r}{hint}")
        for key in ("code", "memory"):
            for entry in table.get(key, []):
                try:
                    getattr(claims, key).append(parse_range(entry, f"[build.{build[:8]}] {key}"))
                except ValueError as e:
                    err("range", str(e))
        for entry in table.get("hooks", []):
            try:
                off = parse_int(entry, f"[build.{build[:8]}] hooks")
                if off % 4:
                    raise ValueError(f"[build.{build[:8]}] hooks: {off:#x} is not on an instruction (a multiple of 4)")
                claims.hooks.append(off)
            except ValueError as e:
                err("hook", str(e))
        for key in ("code", "memory"):
            ranges = getattr(claims, key)
            for i, a in enumerate(ranges):
                for b in ranges[i + 1:]:
                    if overlap(a, b):
                        err("range", f"[build.{build[:8]}] {key}: {fmt_range(a)} and {fmt_range(b)} overlap")
        m.builds[build] = claims

    for slot, what in (raw.get("modules") or {}).items():
        entries = what if isinstance(what, list) else [what]
        parsed = []
        for entry in entries:
            mod_id, _, version = entry.partition("@") if isinstance(entry, str) else ("", "", "")
            if ID.fullmatch(mod_id) and VERSION.fullmatch(version):
                parsed.append((mod_id, version))
        if not SLOT.fullmatch(slot) or not parsed or len(parsed) != len(entries):
            err("modules", f"[modules] {slot} = {what!r}: write subsdk2 = \"author.mod-name@1.0.0\" "
                           "(a list of them when several are linked into one module)")
            continue
        if slot == "subsdk0":
            err("modules", "[modules] subsdk0 is the game's own module")
        m.modules[slot] = parsed
    ids = [mod_id for mod_id, _ in m.module_ids()]
    for mod_id in sorted({i for i in ids if ids.count(i) > 1}):
        err("modules", f"[modules] lists {mod_id} twice")
    for mod_id, version in m.module_ids():
        if mod_id == m.id and version != m.version:
            err("modules", f"[modules] has {mod_id}@{version}, but the manifest's own version is {m.version}")

    for action, binding in (raw.get("input") or {}).items():
        try:
            m.inputs[action] = parse_binding(binding)
        except ValueError as e:
            err("input", f"[input] {action}: {e}")

    relations = raw.get("relations") or {}
    for key in sorted(set(relations) - {"requires", "conflicts", "load-after"}):
        warn("unknown-key", f"[relations]: unknown key {key!r}")
    for key, target in (("requires", m.requires), ("conflicts", m.conflicts), ("load-after", m.load_after)):
        for entry in relations.get(key, []):
            try:
                target.append(parse_relation(entry))
            except ValueError as e:
                err("relation", f"[relations] {key}: {e}")

    patches = raw.get("romfs-patch") or []
    if not isinstance(patches, list):
        err("romfs-patch", "romfs-patch must be written [[romfs-patch]], once per change")
        patches = []
    for n, patch in enumerate(patches, 1):
        kind = patch.get("kind")
        if kind not in PATCH_KINDS:
            err("romfs-patch", f"[[romfs-patch]] {n}: kind = {kind!r}; kinds are {', '.join(PATCH_KINDS)}")
            continue
        missing = [k for k in PATCH_KINDS[kind] if k not in patch]
        if missing:
            err("romfs-patch", f"[[romfs-patch]] {n} ({kind}): missing {', '.join(missing)}")
            continue
        m.patches.append(patch)
        if kind == "size-table":
            try:
                size = parse_int(patch["at-least"], f"[[romfs-patch]] {n} at-least")
            except ValueError as e:
                err("romfs-patch", str(e))
                continue
            path_ = patch["path"]
            if path_.endswith(".zs"):
                err("romfs-patch", f"[[romfs-patch]] {n}: the size table names files without .zs: {path_[:-3]}")
            m.size_table[path_] = max(size, m.size_table.get(path_, 0))

    core = raw.get("core")
    if core is not None:
        m.core = core
        api = core.get("api", "")
        if not (isinstance(api, str) and re.fullmatch(r"\d+\.\d+", api)):
            err("core", f"[core] api = {api!r}: write the Core API version the mod is built for, such as \"0.3\"")
        for event in core.get("events", []):
            if event not in EVENTS:
                warn("core", f"[core] events: {event!r} is not an event this tool knows ({', '.join(EVENTS)})")
        for entry in core.get("symbols", []):
            kind, _, name = entry.partition(":") if isinstance(entry, str) else ("", "", "")
            if kind not in ("function", "field", "global", "vtable", "hookpoint") or not name:
                err("core", f"[core] symbols: {entry!r}: write \"function:Name\" or \"field:Name\"")
        holds_core = any(mod_id == "kaegae.core" for mod_id, _ in m.module_ids())
        if not holds_core and any(b.code or b.hooks for b in m.builds.values()):
            err("core", "a core mod doesn't patch main: remove code and hooks from [build.*], or remove [core]")
    return m


# ---- a mod folder ----

@dataclass
class ModFolder:
    """What one mod folder puts in the game, read from the files themselves."""
    path: Path
    name: str                                       # the folder's name: what the emulator calls the mod
    manifest: Manifest | None = None
    patches: dict = field(default_factory=dict)     # build id -> [(offset, bytes)] (main)
    exefs: dict = field(default_factory=dict)       # other exefs file name -> size
    romfs: dict = field(default_factory=dict)       # romfs path (forward slashes) -> size
    problems: list = field(default_factory=list)

    @property
    def id(self):
        return self.manifest.id if self.manifest else None

    @property
    def label(self):
        return f"{self.name} ({self.manifest.id} {self.manifest.version})" if self.manifest else self.name


def _child(folder, name):
    """A sub-folder by name, whatever its capitals (as the emulator finds it)."""
    for entry in folder.iterdir():
        if entry.is_dir() and entry.name.lower() == name:
            return entry
    return None


def load_folder(path):
    """Read one mod folder: its manifest if it has one, its patches to main and its files."""
    path = Path(path)
    mod = ModFolder(path=path, name=path.name)
    note = lambda level, code, text: mod.problems.append(Problem(level, code, text, (mod.name,)))    # noqa: E731

    manifest_path = path / MANIFEST_NAME
    if manifest_path.is_file():
        try:
            mod.manifest = load_manifest(manifest_path)
            for p in mod.manifest.problems:
                mod.problems.append(Problem(p.level, p.code, p.text, (mod.name,)))
        except ManifestError as e:
            note("error", "manifest-unreadable", f"mod.toml can't be read: {e}")

    exefs = _child(path, "exefs")
    if exefs:
        for file in sorted(exefs.iterdir()):
            if not file.is_file():
                continue
            if file.suffix.lower() == ".ips":
                build = file.stem.upper().rstrip("0") if len(file.stem) > 40 else file.stem.upper()
                try:
                    mod.patches.setdefault(build, []).extend(read_ips(file.read_bytes()))
                except ValueError as e:
                    note("error", "ips-unreadable", f"exefs/{file.name}: {e}")
            elif file.suffix.lower() == ".pchtxt":
                note("note", "pchtxt", f"exefs/{file.name} is an IPSwitch text patch: this tool doesn't read those, "
                                       "so its bytes are not checked")
            else:
                mod.exefs[file.name] = file.stat().st_size
    for sub in ("romfs", "romfslite"):
        root = _child(path, sub)
        if root:
            for file in sorted(root.rglob("*")):
                if file.is_file():
                    mod.romfs[file.relative_to(root).as_posix()] = file.stat().st_size

    if mod.manifest:
        _check_against_files(mod)
    return mod


def _check_against_files(mod):
    """Does the manifest say what the folder really does?"""
    m = mod.manifest
    err = lambda code, text: mod.problems.append(Problem("error", code, text, (mod.name,)))       # noqa: E731
    warn = lambda code, text: mod.problems.append(Problem("warning", code, text, (mod.name,)))    # noqa: E731

    for build in sorted(set(mod.patches) - set(m.builds)):
        err("undeclared-patch", f"exefs/{build}.ips patches main, but mod.toml has no [build.{build}] table")
    for build, claims in m.builds.items():
        records = mod.patches.get(build)
        if claims.ips and not (mod.path / claims.ips).is_file():
            err("ips-missing", f"[build.{build[:8]}] names {claims.ips}, which isn't in the folder")
        if (claims.code or claims.hooks) and not records:
            err("ips-missing", f"[build.{build[:8]}] claims code or hooks, but the folder has no exefs/{build}.ips")
        if not records:
            continue
        hook_ranges = [(h, h + HOOK_SIZE) for h in claims.hooks]
        allowed = merge_ranges(claims.code + hook_ranges)
        for start, end in runs(records):
            inside = [a for a in allowed if a[0] <= start and end <= a[1]]
            if not inside:
                err("undeclared-write", f"the patch for {build[:8]} writes main+{start:#x}..{end:#x}, "
                                        "which the manifest doesn't claim as code or as a hook")
        written = byte_map(records)
        for hook in claims.hooks:
            if not all(hook + k in written for k in range(HOOK_SIZE)):
                err("hook-not-written", f"[build.{build[:8]}] lists a hook at {hook:#x}, but the patch doesn't write there")
            if any(overlap((hook, hook + HOOK_SIZE), c) for c in claims.code):
                err("hook-in-code", f"[build.{build[:8]}] hook {hook:#x} is inside the mod's own code range")
        for code in claims.code:
            if not any(overlap(code, r) for r in runs(records)):
                warn("unused-claim", f"[build.{build[:8]}] claims {fmt_range(code)} but writes nothing there: "
                                     "give it back if it isn't needed")

    for slot in sorted(set(m.modules) - set(mod.exefs)):
        err("module-missing", f"[modules] lists {slot}, but there is no exefs/{slot}")
    for name in sorted(mod.exefs):
        if SLOT.fullmatch(name) and name not in m.modules:
            err("undeclared-module", f"exefs/{name} is a module the manifest's [modules] table doesn't list")
    for path_ in sorted(mod.romfs):
        if m.id == "kaegae.built":
            break       # the folder `kaegae build` writes: the merged table is the point of it
        if "ResourceSizeTable" in path_ and path_.endswith((".rsizetable", ".rsizetable.zs")):
            warn("ships-size-table", f"romfs/{path_} is a whole resource size table: a changed copy of a game file, "
                                     "and any two mods that ship one overwrite each other. Ask for the entries "
                                     "instead with [[romfs-patch]] kind = \"size-table\"")
