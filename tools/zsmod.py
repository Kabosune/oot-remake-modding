#!/usr/bin/env python3
"""Change values inside the game's data files and write them back as a .zs the game loads.

    python3 tools/zsmod.py get  <file.zs>  [<inner path>:]<field path>            [--dict ZsDic.pack.zs]
    python3 tools/zsmod.py set  <file.zs> <out.zs> [<inner path>:]<field path>=<value> ...  [--dict ...]
    python3 tools/zsmod.py check <file.zs>                                         [--dict ...]

<file.zs> is a SARC pack (Pack/Actor/Player_Base.pack.zs, ...) or a single BYML (.byml.zs). For a pack, put the
file's path inside it before a colon. A field path is the BYML keys joined with "/" (array items by number):

    python3 tools/zsmod.py set Player_Base.pack.zs out/Player_Base.pack.zs --dict ZsDic.pack.zs \
        "Player/PlayerGameParam/Player.game__player__PlayerGameParam.bgyml:GroundSpeedScale=1.5"

What it does, and what it does not:
 - Edits are in place and keep the value's type: a float stays a 32-bit float, an int stays an int, a bool a bool.
   Only plain numbers and bools can be changed (no strings, no new keys). Nothing else in the file moves, so the
   file's size and every other byte stay the same.
 - The SARC is then rewritten with zstool's layout rules (names sorted by hash, files at their original
   alignment). `check` proves, for a file of yours, that unpack -> repack gives back the same bytes.
 - The result is compressed with the dictionary the original used (read from the zstd frame's dictionary ID),
   so the game's loader picks the same one. The compressed bytes differ from Nintendo's (other zstd build); the
   decompressed bytes are what matters.
Only needs: pip install zstandard
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zstool  # noqa: E402


# ---------------------------------------------------------------- zstd, with the dictionary's ID

def dicts_by_id(path):
    """{dictionary ID: ZstdCompressionDict} from the game's Pack/ZsDic.pack.zs."""
    import zstandard
    if not path:
        return {}
    sarc = zstool.Sarc(zstandard.ZstdDecompressor().decompress(Path(path).read_bytes(), max_output_size=1 << 30))
    out = {}
    for n in sarc.names():
        if n.endswith(".zsdic"):
            d = zstandard.ZstdCompressionDict(sarc.read(n))
            out[d.dict_id()] = d
    return out


def unzs(data, dicts):
    """-> (decompressed bytes, dictionary ID used (0 = none), or None if `data` wasn't zstd)."""
    import zstandard
    if data[:4] != b"\x28\xb5\x2f\xfd":
        return data, None
    did = zstandard.get_frame_parameters(data).dict_id
    if did and did not in dicts:
        sys.exit(f"this file needs the game's dictionary {did} (--dict <your dump>/Pack/ZsDic.pack.zs)")
    dec = zstandard.ZstdDecompressor(dict_data=dicts[did] if did else None)
    return dec.decompress(data, max_output_size=1 << 31), did


def zs(raw, did, dicts, level=19):
    import zstandard
    c = zstandard.ZstdCompressor(level=level, dict_data=dicts[did] if did else None,
                                 write_checksum=False, write_content_size=True)
    return c.compress(raw)


# ---------------------------------------------------------------- SARC writer

def sarc_hash(name):
    h = 0
    for c in name.encode():
        h = (h * 0x65 + c) & 0xFFFFFFFF
    return h


def _align(x, a):
    return (x + a - 1) & ~(a - 1)


def _alignment(x, cap=0x2000):
    return min(x & -x, cap) if x else cap


def sarc_pack(files, like=None):
    """Build a SARC from {name: bytes}. With `like` (the original SARC's bytes) the layout follows it: each file keeps
    the alignment its original offset implies (new names get 4) and the data section keeps its original
    alignment. Without it every file is aligned to 4."""
    if like is not None:
        if like[6:8] != b"\xff\xfe":                  # byte order mark: only little endian is supported
            raise ValueError("only little-endian SARC is supported")
        old, ver = zstool.Sarc(like), struct.unpack_from("<H", like, 0x10)[0]
    else:
        old, ver = None, 0x100
    order = sorted(files, key=sarc_hash)
    names = bytearray()
    name_at = {}
    for n in order:
        name_at[n] = len(names)
        names += n.encode() + b"\0"
        names += b"\0" * (-len(names) % 4)
    count = len(order)
    sfat_at = 0x14
    names_at = sfat_at + 0xC + 16 * count + 8
    data_at = _align(names_at + len(names), _alignment(old.data_at) if old else 4)
    body = bytearray()
    nodes = bytearray()
    for n in order:
        a = _alignment(old.files[n][0]) if old and n in old.files else 4
        body += b"\0" * (_align(data_at + len(body), a) - data_at - len(body))
        start = len(body)
        body += files[n]
        nodes += struct.pack("<4I", sarc_hash(n), 0x01000000 | (name_at[n] // 4), start, len(body))
    total = data_at + len(body)
    out = bytearray(b"SARC" + struct.pack("<HHIIHH", 0x14, 0xFEFF, total, data_at, ver, 0))
    out += b"SFAT" + struct.pack("<HHI", 0xC, count, 0x65) + nodes
    out += b"SFNT" + struct.pack("<HH", 8, 0) + names
    out += b"\0" * (data_at - len(out))
    out += body
    return bytes(out)


# ---------------------------------------------------------------- BYML: find a value, change it in place

class _Keys(zstool.Byml):
    """zstool.Byml without decoding the whole tree: only the header and the key table (all a lookup needs)."""

    def __init__(self, data):
        if data[:2] not in (b"YB", b"BY"):
            raise ValueError("not a BYML")
        self.e = "<" if data[:2] == b"YB" else ">"
        self.d = data
        self.version, keys, _, _ = struct.unpack_from(self.e + "H3I", data, 2)
        self.keys = self._table(keys) if keys else []


def byml_find(data, path):
    """-> (type byte, offset of the 4-byte value slot) for a field path like "A/B/0"."""
    y = _Keys(data)
    e, d = y.e, y.d
    root = struct.unpack_from(e + "I", d, 0xC)[0]
    if not root:
        raise KeyError("empty BYML")
    t, at = d[root], root
    comps = path.split("/")
    for k, comp in enumerate(comps):
        n = y.u24(at + 1)
        if t == 0xC1:
            for i in range(n):
                p = at + 4 + 8 * i
                if y.keys[y.u24(p)] == comp:
                    t, slot = d[p + 3], p + 4
                    break
            else:
                raise KeyError(f"no key {comp!r}")
        elif t in (0x20, 0x21):       # hash maps: the key is the hash, written 0x9dd6b6 or in decimal
            size = 8 if t == 0x20 else 12
            want = int(comp, 0)
            for i in range(n):
                p = at + 4 + size * i
                if struct.unpack_from(e + ("I" if t == 0x20 else "Q"), d, p)[0] == want:
                    t, slot = d[at + 4 + size * n + i], p + size - 4
                    break
            else:
                raise KeyError(f"no hash {comp!r}")
        elif t == 0xC0:
            if not comp.isdigit() or int(comp) >= n:
                raise KeyError(f"{comp!r}: not an index below {n}")
            vals_at = at + 4 + ((n + 3) & ~3)
            t, slot = d[at + 4 + int(comp)], vals_at + 4 * int(comp)
        else:
            raise KeyError(f"{comp!r} is below a value that isn't a map or array")
        if k < len(comps) - 1:
            if t not in (0xC0, 0xC1, 0x20, 0x21):
                raise KeyError(f"{comp!r} is a plain value, nothing below it")
            at = struct.unpack_from(e + "I", d, slot)[0]
    return t, slot


_KINDS = {0xD0: "bool", 0xD1: "int", 0xD2: "float", 0xD3: "uint", 0xD4: "int64", 0xD5: "uint64", 0xD6: "double"}


def byml_get(data, path):
    t, slot = byml_find(data, path)
    e = "<" if data[:2] == b"YB" else ">"
    if t not in _KINDS:
        raise ValueError(f"{path}: type {t:#x} is not a plain number or bool")
    raw = struct.unpack_from(e + "I", data, slot)[0]
    if t == 0xD0:
        return bool(raw)
    if t == 0xD1:
        return struct.unpack(e + "i", struct.pack(e + "I", raw))[0]
    if t == 0xD2:
        return struct.unpack(e + "f", struct.pack(e + "I", raw))[0]
    if t == 0xD3:
        return raw
    return {0xD4: struct.unpack_from(e + "q", data, raw)[0], 0xD5: struct.unpack_from(e + "Q", data, raw)[0],
            0xD6: struct.unpack_from(e + "d", data, raw)[0]}[t]


def byml_set(data, path, text):
    """Return `data` with the value at `path` replaced by `text` (parsed as the field's own type)."""
    t, slot = byml_find(data, path)
    e = "<" if data[:2] == b"YB" else ">"
    if t not in _KINDS:
        raise ValueError(f"{path}: type {t:#x} is not a plain number or bool, can't change it")
    out = bytearray(data)
    try:
        if t == 0xD0:
            v = {"true": 1, "false": 0, "1": 1, "0": 0}[str(text).lower()]
            struct.pack_into(e + "I", out, slot, v)
        elif t == 0xD1:
            struct.pack_into(e + "i", out, slot, int(text))
        elif t == 0xD2:
            struct.pack_into(e + "f", out, slot, float(text))
        elif t == 0xD3:
            struct.pack_into(e + "I", out, slot, int(text))
        else:
            at = struct.unpack_from(e + "I", out, slot)[0]
            fmt = {0xD4: ("q", int), 0xD5: ("Q", int), 0xD6: ("d", float)}[t]
            struct.pack_into(e + fmt[0], out, at, fmt[1](text))
    except (KeyError, ValueError, struct.error) as ex:
        raise ValueError(f"{path}: can't use {text!r} as a {_KINDS[t]} ({ex})") from None
    return bytes(out)


# ---------------------------------------------------------------- the three commands

def _open(path, dict_path):
    dicts = dicts_by_id(dict_path)
    raw, did = unzs(Path(path).read_bytes(), dicts)
    return raw, did, dicts


def _split(spec, is_sarc):
    if is_sarc:
        if ":" not in spec:
            sys.exit("this is a pack: write <path inside it>:<field path>")
        inner, field = spec.rsplit(":", 1)
        return inner, field
    return None, spec


def cmd_get(a):
    raw, _, _ = _open(a.file, a.dict)
    is_sarc = raw[:4] == b"SARC"
    inner, field = _split(a.spec, is_sarc)
    print(byml_get(zstool.Sarc(raw).read(inner) if is_sarc else raw, field))


def cmd_set(a):
    raw, did, dicts = _open(a.file, a.dict)
    is_sarc = raw[:4] == b"SARC"
    sarc = zstool.Sarc(raw) if is_sarc else None
    files = {n: sarc.read(n) for n in sarc.names()} if is_sarc else {None: raw}
    for item in a.edits:
        if "=" not in item:
            sys.exit(f"{item!r}: write <field path>=<value>")
        spec, value = item.rsplit("=", 1)
        inner, field = _split(spec, is_sarc)
        if inner not in files:
            sys.exit(f"no file {inner!r} in the pack")
        before = byml_get(files[inner], field)
        files[inner] = byml_set(files[inner], field, value)
        print(f"{field}: {before} -> {byml_get(files[inner], field)}")
    new = sarc_pack(files, raw) if is_sarc else files[None]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_bytes(zs(new, did, dicts, a.level) if did is not None else new)
    print(f"wrote {a.out} ({len(new)} bytes unpacked)")


def cmd_check(a):
    raw, did, dicts = _open(a.file, a.dict)
    ok = True
    if raw[:4] == b"SARC":
        s = zstool.Sarc(raw)
        again = sarc_pack({n: s.read(n) for n in s.names()}, raw)
        same = again == raw
        ok &= same
        print(f"SARC repack ({len(s.names())} files): {'identical' if same else 'DIFFERENT'}")
        if not same:
            print(f"  original {len(raw)} bytes, repacked {len(again)} bytes")
    back, _ = unzs(zs(raw, did, dicts, a.level), dicts) if did is not None else (raw, None)
    print(f"zstd (dictionary {did}) compress -> decompress: {'identical' if back == raw else 'DIFFERENT'}")
    ok &= back == raw
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get")
    g.add_argument("file")
    g.add_argument("spec")
    g.set_defaults(fn=cmd_get)
    s = sub.add_parser("set")
    s.add_argument("file")
    s.add_argument("out")
    s.add_argument("edits", nargs="+")
    s.set_defaults(fn=cmd_set)
    c = sub.add_parser("check")
    c.add_argument("file")
    c.set_defaults(fn=cmd_check)
    for x in (g, s, c):
        x.add_argument("--dict", help="the game's Pack/ZsDic.pack.zs")
        x.add_argument("--level", type=int, default=19, help="zstd level when recompressing (default 19)")
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
