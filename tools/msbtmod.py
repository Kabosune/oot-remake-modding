#!/usr/bin/env python3
"""Read and change the game's text (Mals/<lang>.Product.110.sarc.zs, MSBT files) and write it back as a .zs.

    python3 tools/msbtmod.py ls    <Mals file.zs> [<msbt prefix>]                      list the message files
    python3 tools/msbtmod.py cat   <Mals file.zs> <msbt>                               print "label: text"
    python3 tools/msbtmod.py set   <Mals file.zs> <out.zs> <msbt>:<label>=<text> ...   change messages
    python3 tools/msbtmod.py check <Mals file.zs>                                      round-trip every file

                                                           [all take --dict <dump>/Pack/ZsDic.pack.zs]

Example (the file names are the ones inside the pack, e.g. `EventFlowMsg/AllSage.msbt`):

    python3 tools/msbtmod.py set USen.Product.110.sarc.zs out/Mals/USen.Product.110.sarc.zs --dict ZsDic.pack.zs \
        "EventFlowMsg/AllSage.msbt:Talk_03=Hello there.\\nSecond line."

How the text is written (UTF-8 in the game's files):
 - a new line is `\\n`, a backslash is `\\\\`, a literal `{` is `\\{`;
 - the game's inline control codes are shown, and read back, as `{group:type:hexparams}` and the closing code as
   `{/group:type}` (numbers in decimal; params as hex bytes, empty when there are none). Example: a code that
   waits or colours text turns up as `{3:0:140100}`. Copy the codes from `cat` output; changing one's numbers changes
   what it does, and what each code means is mostly not known.
 - the message's final NUL is added for you.

What it does: only the message texts change. The label table, the order and the other files stay as they were, the
text section and file sizes are rewritten, and the SARC is repacked with `zsmod.py`'s rules. `check` proves on your
dump that unpack -> rewrite gives back the same bytes for every message file in the pack. **Whether the game shows
an edited text correctly (line breaks, box sizes, fonts) has not been tried.**
Needs: pip install zstandard
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zsmod  # noqa: E402
import zstool  # noqa: E402


# ---------------------------------------------------------------- MSBT

class Msbt:
    """A little-endian UTF-8 MSBT with only LBL1 and TXT2 sections (all 540 files of the game are like that)."""

    def __init__(self, data):
        if data[:8] != b"MsgStdBn" or data[8:10] != b"\xff\xfe":
            raise ValueError("not a little-endian MSBT")
        if data[0xC] != 0:
            raise ValueError("only UTF-8 MSBT is supported")
        self.head = bytearray(data[:0x20])
        nsec = struct.unpack_from("<H", data, 0xE)[0]
        self.sections = []          # [magic, body bytes]
        self.texts = None
        p = 0x20
        for _ in range(nsec):
            magic, size = data[p:p + 4], struct.unpack_from("<I", data, p + 4)[0]
            body = data[p + 0x10:p + 0x10 + size]
            if magic not in (b"LBL1", b"TXT2"):
                raise ValueError(f"unsupported section {magic!r}")
            if magic == b"TXT2":
                n = struct.unpack_from("<I", body, 0)[0]
                offs = list(struct.unpack_from("<%dI" % n, body, 4)) + [len(body)]
                self.texts = [body[offs[i]:offs[i + 1]] for i in range(n)]
            self.sections.append([magic, body])
            p += 0x10 + ((size + 15) & ~15)
        if self.texts is None:
            raise ValueError("no TXT2 section")
        self.labels = self._labels(dict(self.sections)[b"LBL1"]) if b"LBL1" in dict(self.sections) else {}

    @staticmethod
    def _labels(body):
        out = {}
        n = struct.unpack_from("<I", body, 0)[0]
        for i in range(n):
            count, off = struct.unpack_from("<II", body, 4 + 8 * i)
            q = off
            for _ in range(count):
                ln = body[q]
                out[body[q + 1:q + 1 + ln].decode()] = struct.unpack_from("<I", body, q + 1 + ln)[0]
                q += 5 + ln
        return out

    def pack(self):
        out = bytearray()
        for magic, body in self.sections:
            if magic == b"TXT2":
                n = len(self.texts)
                offs, at = [], 4 + 4 * n
                for t in self.texts:
                    offs.append(at)
                    at += len(t)
                body = struct.pack("<I", n) + struct.pack("<%dI" % n, *offs) + b"".join(self.texts)
            out += magic + struct.pack("<I", len(body)) + b"\0" * 8 + body
            out += b"\xab" * (-len(body) % 16)
        head = bytearray(self.head)
        struct.pack_into("<I", head, 0x12, 0x20 + len(out))
        return bytes(head) + bytes(out)


# ---------------------------------------------------------------- text <-> bytes (control codes shown as {g:t:hex})

def to_text(raw):
    """A message's bytes -> editable text."""
    if raw[-1:] == b"\0":
        raw = raw[:-1]
    out, j, run = [], 0, bytearray()

    def flush():
        if run:
            s = run.decode("utf-8").replace("\\", "\\\\").replace("{", "\\{").replace("\n", "\\n")
            out.append(s)
            run.clear()
    while j < len(raw):
        c = raw[j]
        if c == 0x0E:
            g, t, n = struct.unpack_from("<HHH", raw, j + 1)
            flush()
            out.append("{%d:%d:%s}" % (g, t, raw[j + 7:j + 7 + n].hex()))
            j += 7 + n
        elif c == 0x0F:
            g, t = struct.unpack_from("<HH", raw, j + 1)
            flush()
            out.append("{/%d:%d}" % (g, t))
            j += 5
        else:
            run.append(c)
            j += 1
    flush()
    return "".join(out)


def from_text(text):
    """Editable text -> a message's bytes (with the NUL)."""
    out, j = bytearray(), 0
    while j < len(text):
        c = text[j]
        if c == "\\":
            nxt = text[j + 1:j + 2]
            if nxt == "n":
                out += b"\n"
            elif nxt in ("\\", "{"):
                out += nxt.encode()
            else:
                raise ValueError(f"bad escape \\{nxt} in {text!r}")
            j += 2
        elif c == "{":
            k = text.index("}", j)
            tag = text[j + 1:k]
            if tag.startswith("/"):
                g, t = (int(x) for x in tag[1:].split(":"))
                out += b"\x0f" + struct.pack("<HH", g, t)
            else:
                g, t, h = tag.split(":")
                params = bytes.fromhex(h)
                out += b"\x0e" + struct.pack("<HHH", int(g), int(t), len(params)) + params
            j = k + 1
        else:
            k = j
            while k < len(text) and text[k] not in "\\{":
                k += 1
            out += text[j:k].encode("utf-8")
            j = k
    return bytes(out) + b"\0"


# ---------------------------------------------------------------- commands

def _open(path, dict_path):
    dicts = zsmod.dicts_by_id(dict_path)
    raw, did = zsmod.unzs(Path(path).read_bytes(), dicts)
    return raw, did, dicts


def cmd_ls(a):
    raw, _, _ = _open(a.file, a.dict)
    s = zstool.Sarc(raw)
    for n in s.names():
        if n.startswith(a.prefix):
            m = Msbt(s.read(n))
            print(f"{n}\t{len(m.texts)} messages")


def cmd_cat(a):
    raw, _, _ = _open(a.file, a.dict)
    m = Msbt(zstool.Sarc(raw).read(a.msbt))
    for label, idx in sorted(m.labels.items(), key=lambda x: x[1]):
        print(f"{label}: {to_text(m.texts[idx])}")


def cmd_set(a):
    raw, did, dicts = _open(a.file, a.dict)
    s = zstool.Sarc(raw)
    files = {n: s.read(n) for n in s.names()}
    parsed = {}
    for item in a.edits:
        if "=" not in item or ":" not in item.split("=", 1)[0]:
            sys.exit(f"{item!r}: write <msbt>:<label>=<text>")
        spec, text = item.split("=", 1)
        name, label = spec.rsplit(":", 1)
        if name not in files:
            sys.exit(f"no file {name!r} in the pack")
        m = parsed.setdefault(name, Msbt(files[name]))
        if label not in m.labels:
            sys.exit(f"{name} has no message {label!r}")
        old = to_text(m.texts[m.labels[label]])
        m.texts[m.labels[label]] = from_text(text)
        print(f"{name}:{label}\n  was: {old}\n  now: {to_text(m.texts[m.labels[label]])}")
    for name, m in parsed.items():
        files[name] = m.pack()
    new = zsmod.sarc_pack(files, raw)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_bytes(zsmod.zs(new, did, dicts, a.level) if did is not None else new)
    print(f"wrote {a.out}")


def cmd_check(a):
    raw, _, _ = _open(a.file, a.dict)
    s = zstool.Sarc(raw)
    bad = []
    n_msg = 0
    for n in s.names():
        data = s.read(n)
        try:
            m = Msbt(data)
            same = m.pack() == data
            for t in m.texts:                     # text form must give the same bytes back
                n_msg += 1
                if from_text(to_text(t)) != (t if t[-1:] == b"\0" else t + b"\0"):
                    same = False
        except Exception as e:   # noqa: BLE001
            bad.append((n, repr(e)[:80]))
            continue
        if not same:
            bad.append((n, "different after rewrite"))
    print(f"{len(s.names())} files, {n_msg} messages: {len(bad)} problems")
    for b in bad[:10]:
        print("  ", *b)
    sys.exit(1 if bad else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ls")
    s.add_argument("file")
    s.add_argument("prefix", nargs="?", default="")
    s.set_defaults(fn=cmd_ls)
    s = sub.add_parser("cat")
    s.add_argument("file")
    s.add_argument("msbt")
    s.set_defaults(fn=cmd_cat)
    s = sub.add_parser("set")
    s.add_argument("file")
    s.add_argument("out")
    s.add_argument("edits", nargs="+")
    s.set_defaults(fn=cmd_set)
    s = sub.add_parser("check")
    s.add_argument("file")
    s.set_defaults(fn=cmd_check)
    for x in sub.choices.values():
        x.add_argument("--dict", help="the game's Pack/ZsDic.pack.zs")
        x.add_argument("--level", type=int, default=19, help="zstd level when recompressing (default 19)")
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
