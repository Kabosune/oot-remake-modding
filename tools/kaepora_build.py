#!/usr/bin/env python3
"""Build the files that several mods share, from the player's own dump: what `kaepora build` does.

So far that is one file, the resource size table. Mods ask for entries in it with
[[romfs-patch]] kind = "size-table" in their mod.toml; this merges every request into one copy of
the game's table (the largest request for a file wins) and writes it as a mod folder of its own.
The table is made on the player's machine from their dump, so no mod has to ship it.

The table's format is in docs/romfs.md. Needs: pip install zstandard
"""
import struct
import zlib
from pathlib import Path

BUILT_ID = "kaepora.built"
BUILT_NAME = "Kaepora Built Files"
TABLE_DIR = "System/Resource"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
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


def manifest_text(title, table_name, requests, changes):
    lines = ["# Written by `kaepora build`: files several mods share, made from this player's own dump.",
             "# Don't share this folder: it holds a changed copy of a game file. Run `kaepora build` again",
             "# after installing or removing a mod that asks for size table entries.",
             "manifest = 1", "", f'id       = "{BUILT_ID}"', f'name     = "{BUILT_NAME}"', 'version  = "1.0.0"',
             'authors  = ["kaepora build"]', 'license  = "not for redistribution"', "", "[game]", f'title = "{title}"', "",
             f"# romfs/{TABLE_DIR}/{table_name}: the game's table with these entries raised"]
    done = {path: (old, new) for path, old, new in changes}
    for path, (size, who) in sorted(requests.items()):
        old, new = done.get(path, (None, None))
        lines.append(f"#   {path}: {old} -> {new}  (asked for {size} by {', '.join(who)})")
    return "\n".join(lines) + "\n"


def write_folder(dest, title, game_table_path, mods):
    """Make the built-files folder at `dest` from the game's table and the mods' requests.

    Returns (changes, missing, requests). Writes nothing when no mod asks for anything."""
    requests = collect(mods)
    if not requests:
        return [], [], requests
    table = unpack(Path(game_table_path).read_bytes())
    merged, changes, missing = merge(table, {path: size for path, (size, _) in requests.items()})
    name = Path(game_table_path).name
    name = name if name.endswith(".zs") else name + ".zs"
    out = Path(dest) / "romfs" / TABLE_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(pack(merged))
    (Path(dest) / "mod.toml").write_text(manifest_text(title, name, requests, changes), encoding="utf-8")
    return changes, missing, requests


def built_table(mod):
    """The table inside a built-files folder, or None."""
    for path in mod.romfs:
        if is_size_table(path):
            try:
                return unpack((mod.path / "romfs" / path).read_bytes())
            except (OSError, TableError):
                return None
    return None
