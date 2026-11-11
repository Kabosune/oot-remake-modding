"""tools/msbtmod.py: MSBT reading / rewriting, and the text form of messages with control codes. No game files:
it builds a small MSBT by hand.

    python3 tests/test_msbtmod.py

Needs Python 3.8+ and `pip install zstandard`. For the same checks on your own dump:
`python3 tools/msbtmod.py check Mals/USen.Product.110.sarc.zs --dict <dump>/Pack/ZsDic.pack.zs`.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import msbtmod  # noqa: E402
import zsmod  # noqa: E402
import zstool  # noqa: E402


def section(magic, body):
    return magic + struct.pack("<I", len(body)) + b"\0" * 8 + body + b"\xab" * (-len(body) % 16)


def build(messages):
    """messages: [(label, bytes)] -> an MSBT with a one-group LBL1 and a TXT2."""
    lbl = struct.pack("<I", 1) + struct.pack("<II", len(messages), 12)
    for i, (label, _) in enumerate(messages):
        lbl += bytes([len(label)]) + label.encode() + struct.pack("<I", i)
    n, at, offs, blob = len(messages), 4 + 4 * len(messages), [], b""
    for _, text in messages:
        offs.append(at + len(blob))
        blob += text
    txt = struct.pack("<I", n) + struct.pack("<%dI" % n, *offs) + blob
    body = section(b"LBL1", lbl) + section(b"TXT2", txt)
    head = b"MsgStdBn" + b"\xff\xfe" + b"\0\0" + bytes([0, 3]) + struct.pack("<H", 2) + b"\0\0" \
        + struct.pack("<I", 0x20 + len(body)) + b"\0" * 10
    return head + body


def check(cond, what):
    if not cond:
        sys.exit("FAIL: " + what)
    print("ok:", what)


def main():
    tag_open = b"\x0e" + struct.pack("<HHH", 3, 0, 3) + b"\x14\x01\x00"
    tag_pair_open = b"\x0e" + struct.pack("<HHH", 4, 0, 0)
    tag_pair_close = b"\x0f" + struct.pack("<HH", 0, 12)
    msgs = [("Talk_01", b"Hello, Link!\nHow are you?\0"),
            ("Talk_02", tag_open + b"Wait " + tag_pair_open + b"for it" + tag_pair_close + b" {braces} and \\ slash\0"),
            ("Empty", b"\0"),
            ("Jp", "こんにちは\0".encode())]
    data = build(msgs)

    m = msbtmod.Msbt(data)
    check(sorted(m.labels) == sorted(l for l, _ in msgs) and len(m.texts) == 4, "parses labels and messages")
    check(m.pack() == data, "rewrite without changes gives the same bytes")
    check(msbtmod.to_text(m.texts[0]) == "Hello, Link!\\nHow are you?", "text form: newline shown as \\n")
    t2 = msbtmod.to_text(m.texts[1])
    check(t2 == "{3:0:140100}Wait {4:0:}for it{/0:12} \\{braces} and \\\\ slash", "text form: codes, braces and backslash")
    check(all(msbtmod.from_text(msbtmod.to_text(t)) == t for t in m.texts), "text -> bytes gives the same bytes for every message")

    m.texts[m.labels["Talk_01"]] = msbtmod.from_text("Hi!")
    out = m.pack()
    m2 = msbtmod.Msbt(out)
    check(msbtmod.to_text(m2.texts[0]) == "Hi!" and msbtmod.to_text(m2.texts[3]) == "こんにちは", "a shorter message: others unchanged")
    check(struct.unpack_from("<I", out, 0x12)[0] == len(out) and len(out) % 16 == 0, "file size field is right and sections are padded")
    m2.texts[m2.labels["Empty"]] = msbtmod.from_text("x" * 100 + "{9:9:00ff}")
    m3 = msbtmod.Msbt(m2.pack())
    check(msbtmod.to_text(m3.texts[2]) == "x" * 100 + "{9:9:00ff}" and msbtmod.to_text(m3.texts[1]) == t2, "a longer message: the rest stays")

    for bad in ("\\q", "{1:2}", "{x:y:zz}"):
        try:
            msbtmod.from_text(bad)
        except (ValueError, IndexError):
            check(True, f"refuses {bad!r}")
        else:
            check(False, f"should refuse {bad!r}")

    pack = zsmod.sarc_pack({"A/one.msbt": data, "B/two.msbt": out})
    check(msbtmod.Msbt(zstool.Sarc(pack).read("B/two.msbt")).pack() == out, "an MSBT inside a SARC survives")
    print("all passed")


if __name__ == "__main__":
    main()
