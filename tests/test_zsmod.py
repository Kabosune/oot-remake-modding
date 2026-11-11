"""tools/zsmod.py: editing numbers in BYML, repacking SARC, zstd round trip. No game files: it builds a small BYML
and SARC by hand.

    python3 tests/test_zsmod.py

Needs Python 3.8+ and `pip install zstandard`. For the same checks on your own dump, run
`python3 tools/zsmod.py check <pack.zs> --dict <dump>/Pack/ZsDic.pack.zs`.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import zsmod  # noqa: E402
import zstool  # noqa: E402


def table(strings):
    """A BYML string / key table node: 0xC2, u24 count, count + 1 offsets, then the NUL-terminated strings."""
    head = 4 + 4 * (len(strings) + 1)
    offs, body = [], b""
    for s in strings:
        offs.append(head + len(body))
        body += s.encode() + b"\0"
    offs.append(head + len(body))
    out = b"\xc2" + len(strings).to_bytes(3, "little") + struct.pack("<%dI" % len(offs), *offs) + body
    return out + b"\0" * (-len(out) % 4)


def build_byml():
    """{'Speed': 1.0f, 'Count': -3, 'On': True, 'Big': 4000000000u, 'Name': 'x', 'Inner': {'Lat': [1.2f, 1.6f]},
    'Hash': {0x1234: 7}}  (keys sorted, as the game's files have them)."""
    keys = sorted(["Speed", "Count", "On", "Big", "Name", "Inner", "Lat", "Hash"])
    k = {n: i for i, n in enumerate(keys)}
    ktab, stab = table(keys), table(["x"])
    base = 0x10 + len(ktab) + len(stab)
    root_at = base
    inner_at = root_at + 4 + 8 * 7
    arr_at = inner_at + 4 + 8
    hash_at = arr_at + 4 + 4 + 8
    f = lambda x: struct.unpack("<I", struct.pack("<f", x))[0]  # noqa: E731
    entries = {  # key: (type, value)
        "Speed": (0xD2, f(1.0)), "Count": (0xD1, (-3) & 0xFFFFFFFF), "On": (0xD0, 1), "Big": (0xD3, 4000000000),
        "Name": (0xA0, 0), "Inner": (0xC1, inner_at), "Hash": (0x20, hash_at)}
    root = b"\xc1" + (7).to_bytes(3, "little")
    for name in sorted(entries, key=lambda n: k[n]):
        t, v = entries[name]
        root += k[name].to_bytes(3, "little") + bytes([t]) + struct.pack("<I", v)
    inner = b"\xc1" + (1).to_bytes(3, "little") + k["Lat"].to_bytes(3, "little") + b"\xc0" + struct.pack("<I", arr_at)
    arr = b"\xc0" + (2).to_bytes(3, "little") + bytes([0xD2, 0xD2, 0, 0]) + struct.pack("<2I", f(1.2), f(1.6))
    hashmap = b"\x20" + (1).to_bytes(3, "little") + struct.pack("<II", 0x1234, 7) + bytes([0xD1, 0, 0, 0])
    data = b"YB" + struct.pack("<H3I", 7, 0x10, 0x10 + len(ktab), root_at) + ktab + stab + root + inner + arr + hashmap
    assert len(root) == 4 + 8 * 7 and data.index(inner) == inner_at and data.index(arr) == arr_at
    assert data.index(hashmap) == hash_at
    return data


def check(cond, what):
    if not cond:
        sys.exit("FAIL: " + what)
    print("ok:", what)


def main():
    b = build_byml()
    y = zstool.Byml(b)       # the reader agrees with the layout built above
    check(y.root["Inner"]["Lat"][1] > 1.59 and y.root["Count"] == -3 and y.root["On"] is True,
          "hand-built BYML reads back with zstool")

    check(abs(zsmod.byml_get(b, "Speed") - 1.0) < 1e-6 and zsmod.byml_get(b, "Count") == -3, "get float, int")
    check(zsmod.byml_get(b, "On") is True and zsmod.byml_get(b, "Big") == 4000000000, "get bool, uint")
    check(abs(zsmod.byml_get(b, "Inner/Lat/1") - 1.6) < 1e-6, "get through a map and an array")
    check(zsmod.byml_get(b, "Hash/0x1234") == 7 and zsmod.byml_get(b, "Hash/4660") == 7, "get from a hash map")

    c = zsmod.byml_set(b, "Speed", "1.5")
    check(len(c) == len(b) and zsmod.byml_get(c, "Speed") == 1.5, "set float keeps the file size")
    changed = [i for i in range(len(b)) if b[i] != c[i]]
    check(len(changed) <= 4, f"only the value's own bytes change ({len(changed)})")
    check(zsmod.byml_get(zsmod.byml_set(b, "Inner/Lat/0", "9"), "Inner/Lat/0") == 9.0, "set an array item (int text on a float)")
    check(zsmod.byml_get(zsmod.byml_set(b, "On", "false"), "On") is False, "set bool")
    check(zsmod.byml_get(zsmod.byml_set(b, "Count", "12"), "Count") == 12, "set int")
    check(zsmod.byml_set(b, "Speed", repr(zsmod.byml_get(b, "Speed"))) == b, "setting the value it already has changes nothing")

    for path, text, why in (("Name", "1", "a string"), ("Nope", "1", "a missing key"), ("Inner/Lat/5", "1", "a bad index"),
                            ("Speed/x", "1", "below a plain value"), ("Count", "1.5", "a float text on an int"),
                            ("On", "maybe", "a bad bool"), ("Hash/0x99", "1", "a missing hash")):
        try:
            zsmod.byml_set(b, path, text)
        except (KeyError, ValueError):
            check(True, "refuses " + why)
        else:
            check(False, "should refuse " + why)

    files = {"A/one.bgyml": b, "B/two.bin": b"\x01\x02\x03", "C.txt": b"hello" * 100}
    s1 = zsmod.sarc_pack(files)
    r = zstool.Sarc(s1)
    check(r.names() == sorted(files) and all(r.read(n) == files[n] for n in files), "SARC pack -> zstool reads every file")
    check(zsmod.sarc_pack({n: r.read(n) for n in r.names()}, s1) == s1, "repack with the original as a guide is identical")
    bigger = dict(files, **{"B/two.bin": b"x" * 5000})
    s2 = zstool.Sarc(zsmod.sarc_pack(bigger, s1))
    check(all(s2.read(n) == bigger[n] for n in bigger), "a file that grew: all files still read back")
    check(all(s2.files[n][0] % 4 == 0 for n in s2.files), "files are 4-aligned")
    s3 = zstool.Sarc(zsmod.sarc_pack(dict(files, **{"D/new.bin": b"new"}), s1))
    check(s3.read("D/new.bin") == b"new" and len(s3.names()) == 4, "a new file can be added")

    import zstandard  # noqa: F401
    z = zsmod.zs(s1, 0, {}, 3)
    back, did = zsmod.unzs(z, {})
    check(back == s1 and did == 0, "zstd without a dictionary round-trips and reports dictionary ID 0")
    print("all passed")


if __name__ == "__main__":
    main()
