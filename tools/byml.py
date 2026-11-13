#!/usr/bin/env python3
"""Read and write BYML (version 7, little endian, as this game uses), keeping every value's type.

Unlike zstool.py (read only) and zsmod.py (numbers in place only), this rebuilds the whole file, so strings can
change and keys, actors and array items can be added or removed.

Types: a Python bool, str, float, int, list and dict map to BYML bool, string, f32, s32, array and dictionary.
The other number types are kept with small wrapper classes: U32 (0xD3), S64 (0xD4), U64 (0xD5), F64 (0xD6).

    python3 tools/byml.py json  <file> [out.json]  [--dict ZsDic.pack.zs]   BYML -> JSON (types kept as tags)
    python3 tools/byml.py build <in.json> <out>     [--dict ...]            JSON -> BYML (.zs: compressed)
    python3 tools/byml.py check <file>              [--dict ...]            read, write, read again, compare

In JSON, plain numbers are s32 (whole) or f32 (with a point); other types are {"$u32": n}, {"$u64": n},
{"$s64": n}, {"$f64": x}; binary data is {"$bin": "<hex>"}.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zsmod  # noqa: E402  (zstd with the game's dictionaries)


class U32(int):
    pass


class S64(int):
    pass


class U64(int):
    pass


class F64(float):
    pass


CONTAINERS = (0xC0, 0xC1, 0x20, 0x21)


# ---------------------------------------------------------------- reading

def loads(data):
    if data[:2] != b"YB":
        raise ValueError("not a little-endian BYML")
    version, keys_at, strings_at, root_at = struct.unpack_from("<H3I", data, 2)
    r = _Reader(data)
    r.keys = r.table(keys_at) if keys_at else []
    r.strings = r.table(strings_at) if strings_at else []
    return r.node(data[root_at], root_at) if root_at else None


class _Reader:
    def __init__(self, d):
        self.d = d

    def u24(self, at):
        return int.from_bytes(self.d[at:at + 3], "little")

    def table(self, at):
        n = self.u24(at + 1)
        offs = struct.unpack_from("<%dI" % (n + 1), self.d, at + 4)
        return [self.d[at + offs[i]:self.d.index(b"\0", at + offs[i])].decode("utf-8") for i in range(n)]

    def value(self, t, raw):
        d = self.d
        if t in CONTAINERS:
            return self.node(t, raw)
        if t == 0xA0:
            return self.strings[raw]
        if t == 0xA1:
            n = struct.unpack_from("<I", d, raw)[0]
            return bytes(d[raw + 4:raw + 4 + n])
        if t == 0xD0:
            return bool(raw)
        if t == 0xD1:
            return struct.unpack("<i", struct.pack("<I", raw))[0]
        if t == 0xD2:
            return struct.unpack("<f", struct.pack("<I", raw))[0]
        if t == 0xD3:
            return U32(raw)
        if t == 0xD4:
            return S64(struct.unpack_from("<q", d, raw)[0])
        if t == 0xD5:
            return U64(struct.unpack_from("<Q", d, raw)[0])
        if t == 0xD6:
            return F64(struct.unpack_from("<d", d, raw)[0])
        if t == 0xFF:
            return None
        raise ValueError(f"unknown BYML type {t:#x}")

    def node(self, t, at):
        d = self.d
        n = self.u24(at + 1)
        if t == 0xC0:
            types = d[at + 4:at + 4 + n]
            vals = at + 4 + ((n + 3) & ~3)
            return [self.value(types[i], struct.unpack_from("<I", d, vals + 4 * i)[0]) for i in range(n)]
        if t == 0xC1:
            out = {}
            for i in range(n):
                p = at + 4 + 8 * i
                out[self.keys[self.u24(p)]] = self.value(d[p + 3], struct.unpack_from("<I", d, p + 4)[0])
            return out
        raise ValueError(f"hash-map node {t:#x} not supported for writing yet")


# ---------------------------------------------------------------- writing

def _type(v):
    if v is None:
        return 0xFF
    if isinstance(v, bool):
        return 0xD0
    if isinstance(v, str):
        return 0xA0
    if isinstance(v, (bytes, bytearray)):
        return 0xA1
    if isinstance(v, U32):
        return 0xD3
    if isinstance(v, S64):
        return 0xD4
    if isinstance(v, U64):
        return 0xD5
    if isinstance(v, F64):
        return 0xD6
    if isinstance(v, int):
        return 0xD1
    if isinstance(v, float):
        return 0xD2
    if isinstance(v, list):
        return 0xC0
    if isinstance(v, dict):
        return 0xC1
    raise TypeError(f"can't store {type(v).__name__} in BYML")


def _collect(v, keys, strings):
    if isinstance(v, dict):
        for k, x in v.items():
            keys.add(k)
            _collect(x, keys, strings)
    elif isinstance(v, list):
        for x in v:
            _collect(x, keys, strings)
    elif isinstance(v, str):
        strings.add(v)


def _table(names):
    names = sorted(names, key=lambda s: s.encode("utf-8"))
    n = len(names)
    head = 4 + 4 * (n + 1)
    offs, blob = [], b""
    for s in names:
        offs.append(head + len(blob))
        blob += s.encode("utf-8") + b"\0"
    offs.append(head + len(blob))
    out = bytes([0xC2]) + n.to_bytes(3, "little") + struct.pack("<%dI" % (n + 1), *offs) + blob
    return out + b"\0" * (-len(out) % 4), {s: i for i, s in enumerate(names)}


def _sig(v):
    t = _type(v)
    if isinstance(v, dict):
        return (t, tuple((k, _sig(x)) for k, x in v.items()))
    if isinstance(v, list):
        return (t, tuple(_sig(x) for x in v))
    if t == 0xD2:
        return (t, struct.pack("<f", v))
    if t == 0xA1:
        return (t, bytes(v))
    return (t, v)


def dumps(root, version=7):
    keys, strings = set(), set()
    _collect(root, keys, strings)
    out = bytearray(16)
    keys_at = strings_at = 0
    if keys:
        keys_at = len(out)
        t, key_ix = _table(keys)
        out += t
    else:
        key_ix = {}
    if strings:
        strings_at = len(out)
        t, str_ix = _table(strings)
        out += t
    else:
        str_ix = {}

    def align(a):
        out.extend(b"\0" * (-len(out) % a))

    def scalar(v):
        t = _type(v)
        if t == 0xA0:
            return str_ix[v]
        if t == 0xD0:
            return int(v)
        if t == 0xD1:
            return struct.unpack("<I", struct.pack("<i", v))[0]
        if t == 0xD2:
            return struct.unpack("<I", struct.pack("<f", v))[0]
        if t == 0xD3:
            return int(v) & 0xFFFFFFFF
        if t == 0xFF:
            return 0
        raise AssertionError

    seen = {}                        # identical containers and 64-bit values are stored once, like Nintendo's files

    def big(v):                      # 64-bit numbers and binary live outside their container
        t = _type(v)
        sig = (t, bytes(v) if t == 0xA1 else v)
        if sig in seen:
            return seen[sig]
        align(8 if t != 0xA1 else 4)
        at = len(out)
        if t == 0xD4:
            out.extend(struct.pack("<q", v))
        elif t == 0xD5:
            out.extend(struct.pack("<Q", v))
        elif t == 0xD6:
            out.extend(struct.pack("<d", v))
        else:
            out.extend(struct.pack("<I", len(v)) + bytes(v))
        seen[sig] = at
        return at

    def container(v):
        sig = _sig(v)
        if sig in seen:
            return seen[sig]
        align(4)
        at = len(out)
        seen[sig] = at
        if isinstance(v, list):
            n = len(v)
            types = bytes(_type(x) for x in v)
            out.extend(bytes([0xC0]) + n.to_bytes(3, "little") + types + b"\0" * (-n % 4))
            vals_at = len(out)
            out.extend(b"\0" * (4 * n))
            items = list(enumerate(v))
        else:
            ks = sorted(v, key=lambda k: key_ix[k])
            n = len(ks)
            out.extend(bytes([0xC1]) + n.to_bytes(3, "little"))
            for k in ks:
                out.extend(key_ix[k].to_bytes(3, "little") + bytes([_type(v[k])]) + b"\0\0\0\0")
            vals_at = at + 8
            items = [(i, v[k]) for i, k in enumerate(ks)]
        stride = 4 if isinstance(v, list) else 8
        for i, x in items:
            t = _type(x)
            if t in CONTAINERS:
                raw = container(x)
            elif t in (0xD4, 0xD5, 0xD6, 0xA1):
                raw = big(x)
            else:
                raw = scalar(x)
            struct.pack_into("<I", out, vals_at + stride * i, raw)
        return at

    root_at = container(root) if root is not None else 0
    align(4)
    struct.pack_into("<2sH3I", out, 0, b"YB", version, keys_at, strings_at, root_at)
    return bytes(out)


# ---------------------------------------------------------------- JSON

def to_json(v):
    if isinstance(v, dict):
        return {k: to_json(x) for k, x in v.items()}
    if isinstance(v, list):
        return [to_json(x) for x in v]
    if isinstance(v, U32):
        return {"$u32": int(v)}
    if isinstance(v, S64):
        return {"$s64": int(v)}
    if isinstance(v, U64):
        return {"$u64": int(v)}
    if isinstance(v, F64):
        return {"$f64": float(v)}
    if isinstance(v, (bytes, bytearray)):
        return {"$bin": bytes(v).hex()}
    return v


_TAGS = {"$u32": U32, "$s64": S64, "$u64": U64, "$f64": F64}


def from_json(v):
    if isinstance(v, dict):
        if len(v) == 1:
            (k, x), = v.items()
            if k in _TAGS:
                return _TAGS[k](x)
            if k == "$bin":
                return bytes.fromhex(x)
        return {k: from_json(x) for k, x in v.items()}
    if isinstance(v, list):
        return [from_json(x) for x in v]
    return v


def same(a, b):
    """Equal values and equal types (f32 compared as stored)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if type(a) is float:
        return struct.pack("<f", a) == struct.pack("<f", b)
    return a == b


# ---------------------------------------------------------------- files

def read(path, dicts=None):
    raw = Path(path).read_bytes()
    return loads(zsmod.unzs(raw, dicts or {})[0])


def write(root, path, dict_id=None, dicts=None):
    data = dumps(root)
    if str(path).endswith(".zs"):
        data = zsmod.zs(data, dict_id, dicts or {})
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(data)
    return data


def frame_dict_id(path):
    import zstandard
    return zstandard.get_frame_parameters(Path(path).read_bytes()).dict_id or None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["json", "build", "check"])
    ap.add_argument("file")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--dict", help="the game's Pack/ZsDic.pack.zs")
    ap.add_argument("--dict-id", type=int, help="dictionary to compress with (build); default: 3 for .bcett, 1 otherwise")
    a = ap.parse_args()
    dicts = zsmod.dicts_by_id(a.dict) if a.dict else {}
    if a.cmd == "json":
        text = json.dumps(to_json(read(a.file, dicts)), indent=1, ensure_ascii=False)
        Path(a.out).write_text(text, encoding="utf-8") if a.out else print(text)
    elif a.cmd == "build":
        root = from_json(json.loads(Path(a.file).read_text(encoding="utf-8")))
        did = a.dict_id if a.dict_id is not None else (3 if ".bcett." in a.out else 1)
        write(root, a.out, did if a.out.endswith(".zs") else None, dicts)
    else:
        v = read(a.file, dicts)
        again = loads(dumps(v))
        print("same" if same(v, again) else "DIFFERENT")
        sys.exit(0 if same(v, again) else 1)


if __name__ == "__main__":
    main()
