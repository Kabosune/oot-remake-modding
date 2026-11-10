"""Run the mouse probe's wrappers on a patched main in Unicorn, with a fake nn::hid.

    python3 tests/test_mouse_probe.py <flat main image> <mouse-probe zip>

The calls go through the game's real import stubs (their GOT slots point at fake functions), so
the stub patches, the wrappers and the C code all run as they would in game. Checks: x16 / x17
reach the real function as the stub set them (rtld's lazy binding needs them), return values
and callee-saved registers come back unchanged, the game's own mouse reads are counted, a line
goes out twice a second and holds the mouse and motion values that the fake functions returned.
"""
import struct
import sys
import zipfile

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm64_const import *

BASE, HEAP, STACK, FAKE_HID = 0x80020000, 0x10000000, 0x20000000, 0x30000000
STYLE = (0x83C627E0, 0x84CDF5B8)   # PLT stub, GOT slot
SIX = (0x83C628A0, 0x84CDF618)
MOUSE = (0x83C64800, 0x84CE05C8)
GAME_MOUSE_READ_RET = 0x83B487B0
STATE = 0x84EBFB00
FREQ = 19_200_000


def load(image_path, zip_path):
    img = bytearray(open(image_path, "rb").read())
    z = zipfile.ZipFile(zip_path)
    b = z.read(next(n for n in z.namelist() if n.endswith(".ips")))
    pos = 5
    while b[pos:pos + 4] != b"EEOF":
        o, s = struct.unpack_from(">IH", b, pos)
        img[o - 0x100:o - 0x100 + s] = b[pos + 6:pos + 6 + s]
        pos += 6 + s
    return img


class Game:
    def __init__(self, img):
        u = self.u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        u.mem_map(BASE, (len(img) + 0xFFFF) & ~0xFFFF)
        u.mem_write(BASE, bytes(img))
        u.mem_map(HEAP, 0x100000)
        u.mem_map(STACK - 0x10000, 0x20000)
        u.mem_map(FAKE_HID, 0x1000)
        u.reg_write(UC_ARM64_REG_CPACR_EL1, 0x300000)
        self.tick, self.lines, self.mouse_calls = 1_000_000, [], []
        self.mouse = (7, 640, 360, 3, -2, 0, 0, 1, 2)          # sampling, x, y, dx, dy, wheel x2, buttons, attributes
        self.motion = [float(i) + 0.5 for i in range(18)]
        for i, (name, (_, got)) in enumerate({"style": STYLE, "six": SIX, "mouse": MOUSE}.items()):
            fn = FAKE_HID + 0x10 * i
            u.mem_write(got, struct.pack("<Q", fn))
            u.hook_add(UC_HOOK_CODE, self._hid, (name, got), fn, fn)
        u.hook_add(UC_HOOK_INTR, self._svc)

    def _hid(self, u, addr, size, key):
        # Imports are bound lazily: on a first call this would be rtld's resolver, which needs x16
        # (the GOT slot's address) and x17 exactly as the import stub set them.
        name, got = key
        assert u.reg_read(UC_ARM64_REG_X16) == got, f"{name}: x16 isn't the GOT slot"
        assert u.reg_read(UC_ARM64_REG_X17) == addr, f"{name}: x17 changed"
        x0, x1 = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1)
        if name == "style":
            ret = 0x21
        elif name == "six":
            for i in range(x1):
                u.mem_write(x0 + 0x60 * i, struct.pack("<Qq18fII", 5, 50 - i, *self.motion, 1, 0))
            ret = x1
        else:
            self.mouse_calls.append(x1)
            for i in range(x1):
                u.mem_write(x0 + 0x28 * i, struct.pack("<q6iII", *self.mouse))
            ret = x1
        for r in range(UC_ARM64_REG_X1, UC_ARM64_REG_X1 + 17):   # a real callee may trash x1-x17
            u.reg_write(r, 0xDEAD0000 + r)
        u.reg_write(UC_ARM64_REG_X0, ret)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def _svc(self, u, intno, _):
        pc = u.reg_read(UC_ARM64_REG_PC)
        word = struct.unpack("<I", u.mem_read(pc - 4, 4))[0]
        assert word & 0xFFE0001F == 0xD4000001, f"exception {intno} at {pc - 4:#x}, not an svc"
        num = (word >> 5) & 0xFFFF
        if num == 0x1E:
            u.reg_write(UC_ARM64_REG_X0, self.tick)
        elif num == 0x27:
            self.lines.append(bytes(u.mem_read(u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1))).decode())
            u.reg_write(UC_ARM64_REG_X0, 0)
        else:
            raise AssertionError(f"svc {num:#x}")

    def call(self, stub, x0, x1=0, x2=0, lr=0x7777):
        u = self.u
        for k in range(19, 29):
            u.reg_write(UC_ARM64_REG_X0 + k, 0x5000 + k)
        u.reg_write(UC_ARM64_REG_X29, 0x5029)
        for r, v in ((UC_ARM64_REG_X0, x0), (UC_ARM64_REG_X1, x1), (UC_ARM64_REG_X2, x2),
                     (UC_ARM64_REG_X30, lr), (UC_ARM64_REG_SP, STACK)):
            u.reg_write(r, v)
        u.emu_start(stub, lr, count=100000)
        assert u.reg_read(UC_ARM64_REG_PC) == lr and u.reg_read(UC_ARM64_REG_SP) == STACK
        for k in range(19, 29):
            assert u.reg_read(UC_ARM64_REG_X0 + k) == 0x5000 + k, f"x{k} changed"
        assert u.reg_read(UC_ARM64_REG_X29) == 0x5029, "x29 changed"
        return u.reg_read(UC_ARM64_REG_X0)

    def words(self, n):
        return struct.unpack(f"<{n}I", self.u.mem_read(STATE + 8, 4 * n))


def main():
    g = Game(load(sys.argv[1], sys.argv[2]))
    buf = HEAP + 0x1000

    # one poll: a line at once (the state starts zeroed), with the mouse the fake returned
    assert g.call(STYLE[0], HEAP) == 0x21
    assert len(g.lines) == 1 and g.mouse_calls == [1]
    parts = g.lines[0].split(" ")
    assert parts[0] == "MGP" and len(parts) == 33 and len(g.lines[0]) == 3 + 32 * 9
    w = [int(x, 16) for x in parts[1:]]
    assert w[:4] == [1, 0, 0, 1], w[:4]
    assert struct.pack("<10I", *w[4:14]) == struct.pack("<q6iII", *g.mouse)
    assert w[14:] == [0] * 18
    print("first line:", g.lines[0][:60], "...")

    # more polls inside the same half second: no new line, the count goes up
    for _ in range(20):
        g.tick += FREQ // 100
        g.call(STYLE[0], HEAP)
    assert len(g.lines) == 1 and g.words(1)[0] == 21

    # the game's own mouse read is counted; a read from elsewhere isn't
    assert g.call(MOUSE[0], buf, 16, lr=GAME_MOUSE_READ_RET) == 16
    assert g.call(MOUSE[0], buf, 16) == 16
    assert g.words(2)[1] == 1
    assert bytes(g.u.mem_read(buf + 0x28, 0x28)) == struct.pack("<q6iII", *g.mouse)

    # motion: the newest state is kept; an empty read changes nothing
    assert g.call(SIX[0], buf, 0, HEAP) == 0
    assert g.words(3)[2] == 0
    assert g.call(SIX[0], buf, 2, HEAP) == 2
    assert g.words(3)[2] == 1

    # half a second later: a second line with all of it
    g.tick += FREQ // 2
    g.mouse = (8, 100, 700, -5, 9, 0, 0, 3, 2)
    g.call(STYLE[0], HEAP)
    assert len(g.lines) == 2
    w = [int(x, 16) for x in g.lines[1].split(" ")[1:]]
    assert w[:4] == [22, 1, 1, 1], w[:4]
    assert struct.pack("<10I", *w[4:14]) == struct.pack("<q6iII", *g.mouse)
    assert list(struct.unpack("<18f", struct.pack("<18I", *w[14:]))) == g.motion
    print("second line motion ok; all checks passed")


if __name__ == "__main__":
    main()
