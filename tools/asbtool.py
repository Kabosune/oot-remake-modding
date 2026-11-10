#!/usr/bin/env python3
"""Read and check the game's animation graphs (AS/*.root.asb, version 0x41B). See docs/asb.md.

    python3 tools/asbtool.py ls    <file.asb>        commands, elements, animation names, FrameController rates
    python3 tools/asbtool.py refs  <file.asb>        which element each plug points to
    python3 tools/asbtool.py check <file.asb> ...    test files against layout rules every ASB in the game follows

Takes decompressed files (tools/zstool.py x decompresses .zs). Run check on any hand-edited ASB
before trying it in game. Read-only.
"""
import struct
import sys

TYPES = {1: "FloatSelector", 2: "StringSelector", 3: "SkeletalAnimation", 4: "State", 6: "Blend1D",
         7: "Sequential", 8: "IntSelector", 9: "Simultaneous", 10: "Event", 11: "MaterialAnimation",
         12: "FrameController", 13: "Dummy", 14: "RandomSelector", 16: "PreviousTagSelector",
         17: "BonePositionSelector", 18: "BoneAnimation", 19: "InitialFrame", 20: "BoneBlend",
         21: "BoolSelector", 22: "Alert", 23: "SubtractAnimation", 24: "ShapeAnimation", 26: "Blend2D"}
ELEMENT = 0x24
COMMAND = 0x30
PLUG_HEADER = {3: 0x20, 4: 0x00, 7: 0x18, 12: 0x78}    # where the plug header sits in the param block, by type
PLUGS = ["state", "unknown", "child", "transition", "event", "frame"]
HEADER_POINTERS = (4, 6, 8, 10, 12, 13, 14, 15, 16, 17, 18, 21, 23, 25, 26, 27, 28, 31)   # header words


class Asb:
    def __init__(self, data):
        self.b = data
        if data[:4] != b"ASB " or self.u32(4) != 0x41B:
            raise ValueError("not an ASB version 0x41B")
        self.n_commands, self.commands = self.u32(0x0C), self.u32(0x10)
        self.n_elements, self.elements = self.u32(0x14), self.u32(0x18)
        self.strings = self.u32(0x3C)

    def u16(self, o): return struct.unpack_from("<H", self.b, o)[0]
    def u32(self, o): return struct.unpack_from("<I", self.b, o)[0]
    def f32(self, o): return struct.unpack_from("<f", self.b, o)[0]

    def string(self, off):
        o = self.strings + off
        return self.b[o:self.b.index(b"\0", o)].decode()

    def element(self, i):
        o = self.elements + i * ELEMENT
        return {"type": self.u16(o), "attachments": self.b[o + 2], "flags": self.b[o + 3], "tag": self.u32(o + 4),
                "param": self.u32(o + 8), "calc_start": self.u16(o + 0xC), "calc_count": self.u16(o + 0xE),
                "attachment_start": self.u16(o + 0x10)}

    def plugs(self, i):
        """[(plug name, target)] for element i; the target is an element index (an event index for 'event')."""
        e = self.element(i)
        if e["type"] not in PLUG_HEADER:
            return []
        q = e["param"] + PLUG_HEADER[e["type"]]
        out = []
        for k, name in enumerate(PLUGS):
            count, first = self.b[q + 2 * k], self.b[q + 2 * k + 1]
            for j in range(count):
                at = self.u32(q + 12 + 4 * (first + j))
                out.append((name, self.u32(at + (4 if name == "transition" else 0))))
        return out

    def value(self, o, kind):
        """A property: flags u32 + value. Bit 31 of the flags means the value comes from elsewhere."""
        if self.u32(o) & 0x80000000:
            return f"<indirect {self.u32(o):#x}>"
        return f"{self.f32(o + 4):g}" if kind == "f" else self.string(self.u32(o + 4))


def ls(a):
    print(f"commands {a.n_commands}, elements {a.n_elements}")
    for i in range(a.n_commands):
        o = a.commands + i * COMMAND
        print(f"  command {i:3} {a.string(a.u32(o)):40} frames {a.value(o + 8, 'f'):6} element {a.u16(o + 0x2C)}")
    for i in range(a.n_elements):
        e = a.element(i); p = e["param"]; extra = ""
        if e["type"] == 3:
            extra = a.value(p, "s")
        elif e["type"] == 12:
            extra = f"rate {a.value(p, 'f')}  start {a.value(p + 8, 'f')}  count {a.value(p + 0x10, 'f')}  end {a.value(p + 0x54, 'f')}"
        print(f"  element {i:3} {TYPES.get(e['type'], e['type']):20} param {p:#07x}  {extra}")


def refs(a):
    for i in range(a.n_elements):
        for name, target in a.plugs(i):
            print(f"  element {i:3} {TYPES.get(a.element(i)['type'], '?'):20} {name:10} -> {target}")


def check(a):
    bad = []
    pointers = [a.u32(w * 4) for w in HEADER_POINTERS if a.u32(w * 4)]
    if max(pointers) != a.strings:
        bad.append("the string pool is not the last section")
    if a.strings + a.u32(0x60) != len(a.b):
        bad.append("string pool size (header 0x60) doesn't reach the end of the file")
    calc = attachments = previous = events = 0
    for i in range(a.n_elements):
        e = a.element(i)
        if e["calc_start"] != calc:
            bad.append(f"element {i}: calc controller start {e['calc_start']}, should be {calc}")
        if e["attachment_start"] != attachments:
            bad.append(f"element {i}: attachment start {e['attachment_start']}, should be {attachments}")
        calc += e["calc_count"]; attachments += e["attachments"]
        if e["param"] <= previous:
            bad.append(f"element {i}: its param block isn't after the previous element's")
        previous = e["param"]; events += e["type"] == 10
        if e["type"] in (3, 12):
            for name, target in a.plugs(i):
                if name != "event" and target >= a.n_elements:
                    bad.append(f"element {i}: {name} plug points to element {target} of {a.n_elements}")
                elif name == "frame" and a.element(target)["type"] not in (12, 19):
                    bad.append(f"element {i}: frame plug points to a {TYPES.get(a.element(target)['type'])}")
    if events != a.u32(0x1C):
        bad.append("event count (header 0x1C) isn't the number of Event elements")
    return bad


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("ls", "refs", "check"):
        sys.exit(__doc__)
    failed = 0
    for path in sys.argv[2:]:
        a = Asb(open(path, "rb").read())
        if sys.argv[1] == "ls":
            ls(a)
        elif sys.argv[1] == "refs":
            refs(a)
        else:
            bad = check(a); failed += bool(bad)
            if bad or len(sys.argv) == 3:
                print(path, "OK" if not bad else "")
                for line in bad:
                    print("   ", line)
    if sys.argv[1] == "check":
        print(f"{len(sys.argv) - 2} files, {failed} with problems")
        sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
