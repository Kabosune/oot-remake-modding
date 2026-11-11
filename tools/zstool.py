#!/usr/bin/env python3
"""Look inside the game's romfs files: .zs (zstd with the game's dictionaries), SARC (.pack, .sarc) and BYML (.byml, .bgyml).

    python3 tools/zstool.py ls   <file> [--dict ZsDic.pack.zs]          list a SARC's files
    python3 tools/zstool.py cat  <file>[:<inner path>] [--dict ...]     print a BYML as YAML-ish text
    python3 tools/zstool.py x    <file> <out dir> [--dict ...]          extract (decompressed, SARCs unpacked)

<file> can be .zs or already decompressed. Files compressed with a dictionary need --dict pointing at the
game's Pack/ZsDic.pack.zs (copied from your own dump). Only needs: pip install zstandard

Read-only: this doesn't write game formats back. To change numbers and repack, see tools/zsmod.py; for anything
bigger, use a full tool (Switch-Toolbox, Totk-tools, etc.).
"""
import argparse
import struct
import sys
from pathlib import Path


# ---------------------------------------------------------------- zstd

def load_dicts(path):
    import zstandard
    if not path:
        return []
    sarc = Sarc(zstandard.ZstdDecompressor().decompress(Path(path).read_bytes(), max_output_size=1 << 30))
    return [zstandard.ZstdCompressionDict(sarc.read(n)) for n in sarc.names() if n.endswith(".zsdic")]


def unzs(data, dicts):
    import zstandard
    if data[:4] != b"\x28\xb5\x2f\xfd":
        return data
    for d in [None] + dicts:
        try:
            dec = zstandard.ZstdDecompressor(dict_data=d) if d else zstandard.ZstdDecompressor()
            return dec.decompress(data, max_output_size=1 << 31)
        except zstandard.ZstdError:
            continue
    sys.exit("can't decompress: it needs one of the game's dictionaries (--dict <your dump>/Pack/ZsDic.pack.zs)")


# ---------------------------------------------------------------- SARC

class Sarc:
    def __init__(self, data):
        if data[:4] != b"SARC":
            raise ValueError("not a SARC")
        self.d = data
        hdr = struct.unpack_from("<H", data, 4)[0]
        self.data_at = struct.unpack_from("<I", data, 0xC)[0]
        sfat = hdr
        assert data[sfat:sfat + 4] == b"SFAT"
        count = struct.unpack_from("<H", data, sfat + 6)[0]
        nodes_at = sfat + 0xC
        names_at = nodes_at + 16 * count + 8          # past SFNT's 8-byte header
        self.files = {}
        for i in range(count):
            _, attrs, start, end = struct.unpack_from("<4I", data, nodes_at + 16 * i)
            if attrs & 0x01000000:
                at = names_at + (attrs & 0xFFFF) * 4
                name = data[at:data.index(b"\0", at)].decode()
            else:
                name = f"(unnamed {i})"
            self.files[name] = (self.data_at + start, self.data_at + end)

    def names(self):
        return sorted(self.files)

    def read(self, name):
        a, b = self.files[name]
        return self.d[a:b]


# ---------------------------------------------------------------- BYML

class Byml:
    def __init__(self, data):
        if data[:2] == b"YB":
            self.e = "<"
        elif data[:2] == b"BY":
            self.e = ">"
        else:
            raise ValueError("not a BYML")
        self.d = data
        self.version, keys, strings, root = struct.unpack_from(self.e + "H3I", data, 2)
        self.keys = self._table(keys) if keys else []
        self.strings = self._table(strings) if strings else []
        self.root = self._node(data[root], root) if root else None

    def u24(self, at):
        b = self.d[at:at + 3]
        return int.from_bytes(b, "little" if self.e == "<" else "big")

    def _table(self, at):
        n = self.u24(at + 1)
        offs = struct.unpack_from(self.e + "%dI" % (n + 1), self.d, at + 4)
        return [self.d[at + offs[i]:self.d.index(b"\0", at + offs[i])].decode("utf-8", "replace") for i in range(n)]

    def _value(self, t, raw, where):
        e, d = self.e, self.d
        if t in (0xC0, 0xC1, 0x20, 0x21):
            return self._node(t, raw)
        if t == 0xA0:
            return self.strings[raw]
        if t == 0xA1:
            n = struct.unpack_from(e + "I", d, raw)[0]
            return d[raw + 4:raw + 4 + n]
        if t == 0xD0:
            return bool(raw)
        if t == 0xD1:
            return struct.unpack(e + "i", struct.pack(e + "I", raw))[0]
        if t == 0xD2:
            return struct.unpack(e + "f", struct.pack(e + "I", raw))[0]
        if t == 0xD3:
            return raw
        if t == 0xD4:
            return struct.unpack_from(e + "q", d, raw)[0]
        if t == 0xD5:
            return struct.unpack_from(e + "Q", d, raw)[0]
        if t == 0xD6:
            return struct.unpack_from(e + "d", d, raw)[0]
        if t == 0xFF:
            return None
        return f"<type {t:#x} {raw:#x}>"

    def _node(self, t, at):
        e, d = self.e, self.d
        n = self.u24(at + 1)
        if t == 0xC0:
            types = d[at + 4:at + 4 + n]
            vals_at = at + 4 + ((n + 3) & ~3)
            return [self._value(types[i], struct.unpack_from(e + "I", d, vals_at + 4 * i)[0], vals_at + 4 * i)
                    for i in range(n)]
        if t == 0xC1:
            out = {}
            for i in range(n):
                p = at + 4 + 8 * i
                k = self.u24(p)
                vt = d[p + 3]
                out[self.keys[k]] = self._value(vt, struct.unpack_from(e + "I", d, p + 4)[0], p + 4)
            return out
        if t in (0x20, 0x21):   # hash maps keyed by 32 / 64-bit hashes (newer BYML)
            size = 8 if t == 0x20 else 12
            types_at = at + 4 + size * n
            out = {}
            for i in range(n):
                p = at + 4 + size * i
                h = struct.unpack_from(e + ("I" if t == 0x20 else "Q"), d, p)[0]
                v = struct.unpack_from(e + "I", d, p + size - 4)[0]
                out[f"{h:#x}"] = self._value(d[types_at + i], v, p + size - 4)
            return out
        return f"<node {t:#x}>"


def show(v, indent=0, out=sys.stdout):
    pad = "  " * indent
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                print(f"{pad}{k}:", file=out)
                show(x, indent + 1, out)
            else:
                print(f"{pad}{k}: {fmt(x)}", file=out)
    elif isinstance(v, list):
        for x in v:
            if isinstance(x, (dict, list)) and x:
                print(f"{pad}-", file=out)
                show(x, indent + 1, out)
            else:
                print(f"{pad}- {fmt(x)}", file=out)
    else:
        print(pad + fmt(v), file=out)


def fmt(x):
    if isinstance(x, float):
        return f"{x:g}"
    if isinstance(x, bytes):
        return f"<{len(x)} bytes>"
    if x == {} or x == []:
        return "{}" if x == {} else "[]"
    return str(x)


# ---------------------------------------------------------------- CLI

def open_any(spec, dicts):
    path, _, inner = spec.partition(":") if ":" in spec and not Path(spec).exists() else (spec, "", "")
    data = unzs(Path(path).read_bytes(), dicts)
    if inner:
        data = unzs(Sarc(data).read(inner), dicts)
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["ls", "cat", "x"])
    p.add_argument("file")
    p.add_argument("out", nargs="?")
    p.add_argument("--dict", help="the game's Pack/ZsDic.pack.zs")
    a = p.parse_args()
    dicts = load_dicts(a.dict)
    data = open_any(a.file, dicts)
    if a.cmd == "ls":
        s = Sarc(data)
        for n in s.names():
            x, y = s.files[n]
            print(f"{y - x:9}  {n}")
    elif a.cmd == "cat":
        show(Byml(data).root)
    else:
        out = Path(a.out or ".")
        if data[:4] == b"SARC":
            s = Sarc(data)
            for n in s.names():
                f = out / n
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(unzs(s.read(n), dicts))
        else:
            out.mkdir(parents=True, exist_ok=True)
            (out / Path(a.file).name.removesuffix(".zs")).write_bytes(data)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:   # (output piped into head and cut short)
        sys.stderr.close()
