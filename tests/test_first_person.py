"""Run the First Person hooks on a patched main in Unicorn, with fake camera / Link / controller objects.

    python3 tests/test_first_person.py <flat main image> <first-person zip>

Checks: the R3 toggle, the measured eye height, the view translation, the staleness pause, and that
every register the game uses comes back unchanged.
"""
import math
import struct
import sys
import zipfile

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UcError
from unicorn.arm64_const import *

BASE = 0x80020000
HEAP = 0x10000000
STACK = 0x20000000
VT_VIEW, VT_ACTOR, VT_PLAYER = 0x84C18A88, 0x84B45E18, 0x84B6C460
CAMMGR_SLOT, FP_STATE = 0x84CA6BC0, 0x84EBFC00
PLT = {0x83C627F0: "joydual", 0x83C62800: "fullkey", 0x83C62830: "handheld"}
PLT_KEYBOARD = 0x83C64810
KEY_COMMA, KEY_PERIOD, KEY_SLASH = 0x36, 0x37, 0x38


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
        size = (len(img) + 0xFFFF) & ~0xFFFF
        u.mem_map(BASE, size)
        u.mem_write(BASE, bytes(img))
        u.mem_map(HEAP, 0x100000)
        u.mem_map(STACK - 0x10000, 0x20000)
        u.reg_write(UC_ARM64_REG_CPACR_EL1, 0x300000)   # FP/SIMD on
        self.buttons = {"fullkey": 0, "joydual": 0, "handheld": 0}
        self.calls = []
        self.keys = set()
        u.hook_add(UC_HOOK_CODE, self._plt, begin=0x83C627F0, end=0x83C62840)
        u.hook_add(UC_HOOK_CODE, self._keyboard, begin=PLT_KEYBOARD, end=PLT_KEYBOARD)
        # camera manager chain -> camera 0 -> view
        self.view, self.camera = HEAP + 0x1000, HEAP + 0x3000
        mgr_ptr, mgr, cams, cam0 = HEAP + 0x100, HEAP + 0x200, HEAP + 0x300, HEAP + 0x400
        self.q(CAMMGR_SLOT, mgr_ptr); self.q(mgr_ptr, mgr); self.d(mgr + 0x20, 1); self.q(mgr + 0x28, cams)
        self.q(cams, cam0); self.q(cam0 + 0x78, self.view); self.q(self.view, VT_VIEW)
        self.q(self.camera + 0x20, 0x1234)   # what the replaced ldr x8, [x19, #0x20] reads
        # Link: actor -> components -> movement (inside the player object at +0x1d50) -> resource "Player"
        self.actor, comps, self.player, res = HEAP + 0x8000, HEAP + 0x9000, HEAP + 0x20000, HEAP + 0x30000
        movement = self.player + 0x1D50
        self.q(self.actor, VT_ACTOR); self.q(self.actor + 0x270, comps); self.q(comps + 0x320, movement)
        self.q(movement + 0x18, self.actor); self.q(self.player, VT_PLAYER); self.q(self.player + 0x10, res)
        u.mem_write(res + 0x58, b"Player\0")

    def q(self, a, v): self.u.mem_write(a, struct.pack("<Q", v))
    def d(self, a, v): self.u.mem_write(a, struct.pack("<I", v))
    def f(self, a, *v): self.u.mem_write(a, struct.pack("<%df" % len(v), *v))
    def rf(self, a, n=1): return struct.unpack("<%df" % n, self.u.mem_read(a, 4 * n))
    def state(self): return struct.unpack("<5I4f", self.u.mem_read(FP_STATE, 0x24))

    def _plt(self, u, addr, size, _):
        kind = PLT.get(addr)
        if not kind:
            return
        out, count = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1)
        npad = struct.unpack("<I", u.mem_read(u.reg_read(UC_ARM64_REG_X2), 4))[0]
        self.calls.append((kind, count, npad))
        b = self.buttons[kind] if (npad == 0x20) == (kind == "handheld") else 0
        u.mem_write(out, struct.pack("<qQiiiiI4x", 1, b, 0, 0, 0, 0, 1))
        for r in range(UC_ARM64_REG_X0, UC_ARM64_REG_X0 + 18):   # clobber caller-saved like real code would
            if r != UC_ARM64_REG_X0:
                u.reg_write(r, 0xDEAD0000 + r)
        for r in range(UC_ARM64_REG_Q0, UC_ARM64_REG_Q0 + 8):
            u.reg_write(r, 0xBAD)
        u.reg_write(UC_ARM64_REG_X0, 1)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def _keyboard(self, u, addr, size, _):
        bits = 0
        for k in self.keys:
            bits |= 1 << k
        out = u.reg_read(UC_ARM64_REG_X0)
        u.mem_write(out, struct.pack("<qII", 1, 0, 1) + bits.to_bytes(32, "little"))
        for r in range(UC_ARM64_REG_X1, UC_ARM64_REG_X0 + 18):
            u.reg_write(r, 0xDEAD0000 + r)
        for r in range(UC_ARM64_REG_Q0, UC_ARM64_REG_Q0 + 8):
            u.reg_write(r, 0xBAD)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def offset(self):
        return struct.unpack("<f", self.u.mem_read(FP_STATE + 0x24, 4))[0]

    def run(self, start, stop, regs):
        u = self.u
        sentinel = {}
        for k in range(29):
            v = 0x5000 + k
            sentinel[k] = v
            u.reg_write(UC_ARM64_REG_X0 + k, v)
        for k in range(32):
            u.reg_write(UC_ARM64_REG_Q0 + k, 0x1111 * (k + 1))
        for k, v in regs.items():
            u.reg_write(UC_ARM64_REG_X0 + k, v)
            sentinel[k] = v
        u.reg_write(UC_ARM64_REG_SP, STACK)
        u.reg_write(UC_ARM64_REG_X30, 0x7777)
        u.reg_write(UC_ARM64_REG_NZCV, 0x60000000)
        u.emu_start(start, stop, count=4000)
        assert u.reg_read(UC_ARM64_REG_PC) == stop, hex(u.reg_read(UC_ARM64_REG_PC))
        assert u.reg_read(UC_ARM64_REG_SP) == STACK
        assert u.reg_read(UC_ARM64_REG_X30) == 0x7777
        assert u.reg_read(UC_ARM64_REG_NZCV) == 0x60000000
        for k in range(32):
            assert u.reg_read(UC_ARM64_REG_Q0 + k) == 0x1111 * (k + 1), f"q{k} changed"
        return sentinel

    def actor_update(self, pos):
        self.f(self.actor + 0x31C, *pos)
        s = self.run(0x82C41720, 0x82C41724, {19: self.actor})
        assert self.u.reg_read(UC_ARM64_REG_X23) == self.actor + 0x328
        for k in range(29):
            if k != 23:
                assert self.u.reg_read(UC_ARM64_REG_X0 + k) == s[k], f"x{k} changed (actor hook)"

    def view_frame(self, yaw, eye, target):
        """Write a camera matrix the way the game does (rows: right, up, back; t = -axis.eye)."""
        sy, cy = math.sin(yaw), math.cos(yaw)
        rows = [(cy, 0, -sy), (0, 1, 0), (sy, 0, cy)]
        for r, axis in enumerate(rows):
            t = -sum(a * e for a, e in zip(axis, eye))
            self.f(self.view + 8 + r * 16, *axis, t)
        self.u.mem_write(self.view + 0x60, struct.pack("<3d", *eye))
        self.u.mem_write(self.view + 0x78, struct.pack("<3d", *target))
        s = self.run(0x804E5068, 0x804E506C, {19: self.camera, 20: self.view})
        assert self.u.reg_read(UC_ARM64_REG_X8) == 0x1234
        for k in range(29):
            if k != 8:
                assert self.u.reg_read(UC_ARM64_REG_X0 + k) == s[k], f"x{k} changed (view hook)"
        rows_out = [self.rf(self.view + 8 + r * 16, 4) for r in range(3)]
        # recover the eye from the matrix: eye = -R^T t
        return tuple(-sum(rows_out[r][i] * rows_out[r][3] for r in range(3)) for i in range(3)), rows_out


def close(a, b, eps=1e-3):
    return all(abs(x - y) < eps for x, y in zip(a, b))


def main():
    img = load(sys.argv[1], sys.argv[2])
    g = Game(img)
    link = (10.0, 2.0, -5.0)
    orbit_eye, target = (10.0, 3.5, -1.0), (10.0, 3.4, -5.0)   # behind Link, looking down -z
    yaw = 0.0

    g.actor_update(link)
    st = g.state()
    assert st[2] == 1 and close(st[5:8], link), st
    print("actor hook: Link found, position copied")

    eye, _ = g.view_frame(yaw, orbit_eye, target)
    assert close(eye, orbit_eye) and g.state()[0] == 0
    assert {c[0] for c in g.calls} == {"fullkey", "joydual", "handheld"}, g.calls
    print("view hook, mode off: view unchanged, all three pads read")

    g.buttons["fullkey"] = 1 << 5
    g.actor_update(link)
    eye, rows = g.view_frame(yaw, orbit_eye, target)
    st = g.state()
    h = target[1] - link[1]
    assert st[0] == 1 and abs(st[8] - h) < 1e-4, st
    want = (link[0], link[1] + h, link[2] - 0.15)   # pushed 0.15 forward (-z)
    assert close(eye, want), (eye, want)
    assert close([r[0] for r in rows[:3]], (1, 0, 0))   # rotation untouched
    print("R3: on, eye height measured %.2f, eye at %s" % (st[8], tuple(round(x, 3) for x in eye)))

    g.actor_update(link)
    eye, _ = g.view_frame(yaw, orbit_eye, target)   # R3 still held: no second toggle
    assert g.state()[0] == 1 and close(eye, want)
    print("R3 held: stays on")

    yaw = math.radians(90)
    g.actor_update((12.0, 2.0, -5.0))
    eye, _ = g.view_frame(yaw, (14.0, 3.5, -5.0), (12.0, 3.4, -5.0))   # camera turned: looking down -x
    want = (12.0 - 0.15, 2.0 + h, -5.0)
    assert close(eye, want), (eye, want)
    print("camera turned 90 deg, Link moved: eye follows, forward push turns with the view")

    for _ in range(31):
        eye, _ = g.view_frame(yaw, (14.0, 3.5, -5.0), (12.0, 3.4, -5.0))
    diag = "diagnostic" in sys.argv[2]
    if diag:
        assert close(eye, (12.0, 3.4, -5.0)), eye
        print("no Link update for 31 views: diagnostic build puts the eye on the look-at point")
    else:
        assert close(eye, (14.0, 3.5, -5.0)), eye
        print("no Link update for 31 views: back to the game's camera")
    g.actor_update((12.0, 2.0, -5.0))
    eye, _ = g.view_frame(yaw, (14.0, 3.5, -5.0), (12.0, 3.4, -5.0))
    assert close(eye, (12.0 - 0.15, 2.0 + h, -5.0)), eye
    print("Link updates again: first person resumes")

    g.buttons["fullkey"] = 0
    cam = ((14.0, 3.5, -5.0), (12.0, 3.4, -5.0))
    base = (12.0 - 0.15, 2.0 + h, -5.0)

    def key_frame(*keys):
        g.keys = set(keys)
        g.actor_update((12.0, 2.0, -5.0))
        return g.view_frame(yaw, *cam)[0]

    for _ in range(3):
        key_frame(KEY_PERIOD)
        key_frame()
    eye = key_frame(KEY_COMMA)
    for _ in range(5):
        eye = key_frame(KEY_COMMA)   # held: no repeat
    assert abs(g.offset() - 0.04) < 1e-5, g.offset()
    assert close(eye, (base[0], base[1] + 0.04, base[2])), eye
    print("keys: '.' x3, ',' x1 (held) -> eye +4 cm, no repeat while held")

    g.buttons["fullkey"] = 1 << 5; key_frame(); g.buttons["fullkey"] = 0; key_frame()   # off
    assert g.state()[0] == 0
    g.buttons["fullkey"] = 1 << 5; eye = key_frame(); g.buttons["fullkey"] = 0
    assert g.state()[0] == 1 and close(eye, (base[0], base[1] + 0.04, base[2])), eye
    print("offset kept across R3 off / on")
    key_frame(KEY_SLASH)
    eye = key_frame()
    assert g.offset() == 0 and close(eye, base), eye
    print("'/' resets the offset")

    g.view_frame(yaw, (14.0, 3.5, -5.0), (12.0, 3.4, -5.0))
    g.buttons["handheld"] = 1 << 5
    g.actor_update((12.0, 2.0, -5.0))
    eye, _ = g.view_frame(yaw, (14.0, 3.5, -5.0), (12.0, 3.4, -5.0))
    assert g.state()[0] == 0 and close(eye, (14.0, 3.5, -5.0))
    print("R3 on handheld: off again, game camera back")

    g.q(g.player + 0x10, 0)   # some other actor using the same movement code: ignored
    before = g.state()[2]
    g.actor_update((99.0, 99.0, 99.0))
    assert g.state()[2] == before and close(g.state()[5:8], (12.0, 2.0, -5.0))
    print("other actors: ignored")
    print("all checks passed")


if __name__ == "__main__":
    main()
