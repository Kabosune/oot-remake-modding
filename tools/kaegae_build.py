#!/usr/bin/env python3
"""Build the files that several mods share, from the player's own dump: what `kaegae build` does.

The resource size table: mods ask for entries in it with [[romfs-patch]] kind = "size-table" in
their mod.toml; this merges every request into one copy of the game's table (the largest request
for a file wins) and writes it as a mod folder of its own.

BYML / BGYML values (kind = "byml"): mods name a file (and, for a pack, a file inside it) and the
keys to set; this applies every mod's changes to the file from the player's dump, refuses two
mods setting one key to different values, writes the changed file into the same folder and raises
its size table entries (the file's size + 512, as the game's own files have room).

Everything is made on the player's machine from their dump, so no mod has to ship a game file.
The table's format is in docs/romfs.md. Needs: pip install zstandard
"""
import struct
import zlib
from pathlib import Path

BUILT_ID = "kaegae.built"
BUILT_NAME = "KaeGae Built Files"
TABLE_DIR = "System/Resource"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
RSTB_NAME = "ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs"   # the 1.1.1 table, in TABLE_DIR
ROOM = 512          # bytes a changed file gets on top of its size in the table
HEADER = 22         # "RESTBL", u32 version, u32 name size, u32 hashed count, u32 named count


class TableError(Exception):
    pass


def _zstd():
    try:
        import zstandard
    except ImportError as e:
        raise TableError("the size table is zstd-compressed: pip install zstandard") from e
    return zstandard


def is_size_table(path):
    name = Path(path).name
    return "ResourceSizeTable" in name and name.endswith((".rsizetable", ".rsizetable.zs"))


def unpack(data):
    """The table's bytes, decompressed if needed and checked."""
    if data[:4] == ZSTD_MAGIC:
        data = _zstd().ZstdDecompressor().decompress(data, max_output_size=1 << 28)
    if data[:6] != b"RESTBL" or struct.unpack_from("<I", data, 6)[0] != 1:
        raise TableError("not a resource size table (RESTBL version 1)")
    name_size, hashed, named = struct.unpack_from("<III", data, 10)
    if len(data) != HEADER + 8 * hashed + (name_size + 4) * named:
        raise TableError("the size table's length doesn't match its header")
    return bytes(data)


def pack(table):
    z = _zstd()
    packed = z.ZstdCompressor(level=19, write_content_size=True).compress(table)
    assert z.ZstdDecompressor().decompress(packed) == table
    return packed


def entries(table):
    """({crc32 of path: offset of its size}, {path: offset of its size}) for the two kinds of entry."""
    name_size, hashed, named = struct.unpack_from("<III", table, 10)
    by_hash = {struct.unpack_from("<I", table, HEADER + 8 * i)[0]: HEADER + 8 * i + 4 for i in range(hashed)}
    by_name, base = {}, HEADER + 8 * hashed
    for i in range(named):
        at = base + (name_size + 4) * i
        by_name[table[at:at + name_size].split(b"\0", 1)[0].decode("utf-8", "replace")] = at + name_size
    return by_hash, by_name


def size_of(table, path):
    """The size the table holds for a romfs path (written without .zs), or None."""
    by_hash, by_name = entries(table)
    at = by_name.get(path, by_hash.get(zlib.crc32(path.encode())))
    return None if at is None else struct.unpack_from("<I", table, at)[0]


def merge(table, requests):
    """Raise entries to at least the requested sizes.

    requests: {romfs path without .zs: bytes}. Returns (new table, changes, missing) where changes
    is [(path, old, new)] and missing lists paths the game's table has no entry for. Sizes are
    rounded up to a multiple of 8, as the game's own are. An entry is never lowered."""
    out = bytearray(table)
    by_hash, by_name = entries(table)
    changes, missing = [], []
    for path, wanted in sorted(requests.items()):
        at = by_name.get(path, by_hash.get(zlib.crc32(path.encode())))
        if at is None:
            missing.append(path)
            continue
        old = struct.unpack_from("<I", out, at)[0]
        new = max(old, (wanted + 7) & ~7)
        struct.pack_into("<I", out, at, new)
        changes.append((path, old, new))
    return bytes(out), changes, missing


def collect(mods):
    """{path: (size, [mod names])} from the manifests of these mod folders: the largest request wins."""
    out = {}
    for mod in mods:
        if not mod.manifest:
            continue
        for path, size in mod.manifest.size_table.items():
            best, who = out.get(path, (0, []))
            out[path] = (max(best, size), who + [mod.name])
    return out


class PatchError(Exception):
    pass


def collect_byml(mods):
    """{(path, file or None): {key path: (value, mod name)}} from the [[romfs-patch]] kind = "byml" tables.

    Two mods setting one key to different values is a PatchError; the same value is fine."""
    out = {}
    for mod in mods:
        if not mod.manifest:
            continue
        for patch in mod.manifest.patches:
            if patch.get("kind") != "byml":
                continue
            where = (patch["path"], patch.get("file"))
            keys = out.setdefault(where, {})
            for key, value in patch["set"].items():
                if key in keys and keys[key][0] != value:
                    raise PatchError(f"{where[0]}{' > ' + where[1] if where[1] else ''}: {key} is set to {keys[key][0]!r} "
                                     f"by {keys[key][1]} and to {value!r} by {mod.name}")
                keys.setdefault(key, (value, mod.name))
    return out


def _set(root, key, value):
    """Set a dotted key path in a BYML document. A new value keeps the old one's type (a float stays a float,
    an unsigned stays unsigned), so a manifest can write 0 for 0.0."""
    *parents, last = key.split(".")
    node = root
    for part in parents:
        if not isinstance(node.get(part), dict):
            raise PatchError(f"{key}: {part} is not a dictionary in this file")
        node = node[part]
    old = node.get(last)
    if old is not None and not isinstance(value, (dict, list)) and type(old) is not type(value):
        if isinstance(old, bool) or isinstance(value, bool) or isinstance(value, str) != isinstance(old, str):
            raise PatchError(f"{key}: the game has {old!r} here, a {type(old).__name__}; {value!r} doesn't fit")
        value = type(old)(value)
    node[last] = value
    return old


def apply_byml(romfs, patches):
    """Apply collected byml patches to the files in the player's romfs folder.

    Returns ({romfs path: new file bytes}, {romfs path without .zs: size table request}, [(where, key, old, new, mod)])."""
    import byml
    import zsmod
    import zstool
    romfs = Path(romfs)
    dict_file = romfs / "Pack" / "ZsDic.pack.zs"
    dicts = zsmod.dicts_by_id(dict_file) if dict_file.exists() else {}
    by_path = {}
    for (path, inner), keys in patches.items():
        by_path.setdefault(path, {})[inner] = keys
    files, sizes, log = {}, {}, []
    for path, parts in sorted(by_path.items()):
        src = romfs / path
        if not src.is_file():
            raise PatchError(f"{path}: not in {romfs} (give your dump's romfs folder with --romfs)")
        data = src.read_bytes()
        raw, did = zsmod.unzs(data, dicts)

        def change(doc_bytes, where, keys):
            doc = byml.loads(doc_bytes)
            for key, (value, who) in keys.items():
                old = _set(doc, key, value)
                log.append((where, key, old, value, who))
            return byml.dumps(doc)

        if any(inner for inner in parts):
            if None in parts:
                raise PatchError(f"{path}: patched both as a pack and as a file")
            sarc = zstool.Sarc(raw)
            inner_files = {str(n): sarc.read(str(n)) for n in sarc.names()}
            for inner, keys in parts.items():
                if inner not in inner_files:
                    raise PatchError(f"{path}: has no file {inner}")
                inner_files[inner] = change(inner_files[inner], f"{path} > {inner}", keys)
                sizes[inner] = len(inner_files[inner]) + ROOM
            new = zsmod.sarc_pack(inner_files, like=raw)
        else:
            new = change(raw, path, parts[None])
        sizes[path[:-3] if path.endswith(".zs") else path] = len(new) + ROOM
        files[path] = zsmod.zs(new, did, dicts) if did is not None else new
    return files, sizes, log


def manifest_text(title, table_name, requests, changes, log=()):
    lines = ["# Written by `kaegae build`: files several mods share, made from this player's own dump.",
             "# Don't share this folder: it holds a changed copy of a game file. Run `kaegae build` again",
             "# after installing or removing a mod that asks for size table entries.",
             "manifest = 1", "", f'id       = "{BUILT_ID}"', f'name     = "{BUILT_NAME}"', 'version  = "1.0.0"',
             'authors  = ["kaegae build"]', 'license  = "not for redistribution"', "", "[game]", f'title = "{title}"', "",
             f"# romfs/{TABLE_DIR}/{table_name}: the game's table with these entries raised"]
    done = {path: (old, new) for path, old, new in changes}
    for path, (size, who) in sorted(requests.items()):
        old, new = done.get(path, (None, None))
        lines.append(f"#   {path}: {old} -> {new}  (asked for {size} by {', '.join(who)})")
    if log:
        lines.append("# changed values (romfs files in this folder, from your dump):")
        lines += [f"#   {where}: {key} {old!r} -> {new!r}  ({who})" for where, key, old, new, who in log]
    return "\n".join(lines) + "\n"


def write_folder(dest, title, game_table_path, mods, romfs=None):
    """Make the built-files folder at `dest` from the game's table, the player's romfs (for byml
    patches) and the mods' requests.

    Returns (changes, missing, requests, log). Writes nothing when no mod asks for anything."""
    requests = collect(mods)
    patches = collect_byml(mods)
    files, log = {}, []
    if patches:
        if romfs is None:
            raise PatchError("mods change game files (" + ", ".join(sorted({p for p, _ in patches}))
                             + "): give your dump's romfs folder with --romfs")
        files, sizes, log = apply_byml(romfs, patches)
        who = sorted({w for keys in patches.values() for _, w in keys.values()})
        for path, size in sizes.items():
            best, names = requests.get(path, (0, []))
            requests[path] = (max(best, size), names + [n for n in who if n not in names])
    if not requests:
        return [], [], requests, log
    table = unpack(Path(game_table_path).read_bytes())
    merged, changes, missing = merge(table, {path: size for path, (size, _) in requests.items()})
    name = Path(game_table_path).name
    name = name if name.endswith(".zs") else name + ".zs"
    out = Path(dest) / "romfs" / TABLE_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(pack(merged))
    for path, data in files.items():
        (Path(dest) / "romfs" / path).parent.mkdir(parents=True, exist_ok=True)
        (Path(dest) / "romfs" / path).write_bytes(data)
    (Path(dest) / "mod.toml").write_text(manifest_text(title, name, requests, changes, log), encoding="utf-8")
    return changes, missing, requests, log


def built_table(mod):
    """The table inside a built-files folder, or None."""
    for path in mod.romfs:
        if is_size_table(path):
            try:
                return unpack((mod.path / "romfs" / path).read_bytes())
            except (OSError, TableError):
                return None
    return None
