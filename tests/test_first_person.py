"""Run the First Person hooks on a patched main in Unicorn, with fake camera / Link / controller objects.

    python3 tests/test_first_person.py <flat main image> <first-person zip>

Checks: the R3 toggle, the measured eye height, the view translation, the staleness pause, hiding
Link, keeping the pitch through R3's camera recenter, and that every register the game uses comes
back unchanged.
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
KEY_SEMI, KEY_COMMA, KEY_PERIOD, KEY_SLASH = 0x33, 0x36, 0x37, 0x38


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
        self.stick_y = {"fullkey": 0, "joydual": 0, "handheld": 0}   # right stick
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
        self.model = HEAP + 0x40000
        self.q(comps + 0x260, self.model)
        self.set_model(1, 0)

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
        mine = (npad == 0x20) == (kind == "handheld")
        b, ry = (self.buttons[kind], self.stick_y[kind]) if mine else (0, 0)
        u.mem_write(out, struct.pack("<qQiiiiI4x", 1, b, 0, 0, 0, ry, 1))
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

    def set_model(self, visible, flags):
        self.u.mem_write(self.model + 0xE5, bytes([visible]))
        self.d(self.model + 0x120, flags)

    def model_state(self):
        return self.u.mem_read(self.model + 0xE5, 1)[0], struct.unpack("<I", self.u.mem_read(self.model + 0x120, 4))[0]

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

    def view_frame(self, yaw, eye, target, pitch=0.0):
        """Write a camera matrix the way the game does (rows: right, up, back; t = -axis.eye).
        pitch > 0: the back axis points up, so the camera looks down."""
        rows = rotation(yaw, pitch)
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


def rotation(yaw, pitch):
    sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
    return [(cy, 0, -sy), (-sp * sy, cp, -sp * cy), (sy * cp, sp, cy * cp)]


def view_angles(rows):
    """(yaw, pitch) of a view's rotation, and how far it is from orthonormal."""
    back = rows[2][:3]
    err = max(abs(sum(a * b for a, b in zip(rows[i][:3], rows[j][:3])) - (i == j)) for i in range(3) for j in range(3))
    return math.atan2(back[0], back[2]), math.asin(max(-1.0, min(1.0, back[1]))), err


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
    assert g.model_state() == (0, 0x800), g.model_state()
    print("Link hidden by default once first person is on (visible byte 0, model told to update)")

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

    assert g.model_state()[0] == 0, g.model_state()
    g.set_model(1, 0)        # the game shows him again (say, an event): hidden again next update
    key_frame()
    assert g.model_state() == (0, 0x800), g.model_state()
    print("hiding holds against the game showing him")
    key_frame(KEY_SEMI)
    key_frame()   # the actor update after the toggle applies it
    assert g.model_state()[0] == 1, g.model_state()
    print("';': Link shown")
    g.buttons["fullkey"] = 1 << 5; key_frame(); g.buttons["fullkey"] = 0; key_frame()   # R3 off
    g.buttons["fullkey"] = 1 << 5; key_frame(); g.buttons["fullkey"] = 0; key_frame()   # R3 on
    assert g.state()[0] == 1 and g.model_state()[0] == 1, g.model_state()
    print("R3 off / on: still shown (toggle remembered)")
    key_frame(KEY_SEMI); key_frame()
    assert g.model_state()[0] == 0
    print("';' again: hidden")
    g.buttons["fullkey"] = 1 << 5; key_frame(); g.buttons["fullkey"] = 0; key_frame()   # R3 off
    assert g.state()[0] == 0 and g.model_state()[0] == 1, g.model_state()
    print("R3 off: Link visible again")
    g.buttons["fullkey"] = 1 << 5; key_frame(); g.buttons["fullkey"] = 0; key_frame()   # R3 on
    assert g.model_state()[0] == 0
    print("R3 on: hidden again")
    key_frame(KEY_SEMI); key_frame()    # show him
    assert g.model_state()[0] == 1
    g.set_model(0, 0)        # the game itself had him hidden: we must not show him when we stop
    key_frame(KEY_SEMI); key_frame()
    key_frame(KEY_SEMI); key_frame()
    assert g.model_state()[0] == 0, g.model_state()
    print("game-hidden Link stays hidden after our hide stops")
    g.set_model(1, 0)

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

    check_pitch(img)
    print("all checks passed")


def check_pitch(img):
    """R3 is also the game's camera recenter: in first person the yaw swing shows, the pitch doesn't."""
    g = Game(img)
    deg = math.radians
    link, eye3, target = (10.0, 2.0, -5.0), (10.0, 3.5, -1.0), (10.0, 3.4, -5.0)

    def frame(yaw, pitch, r3=False, stick=0):
        g.buttons["fullkey"] = 1 << 5 if r3 else 0
        g.stick_y["fullkey"] = stick
        g.actor_update(link)
        eye, rows = g.view_frame(yaw, eye3, target, deg(pitch))
        y, p, err = view_angles(rows)
        assert err < 1e-4, err
        return eye, math.degrees(y), math.degrees(p)

    for _ in range(3):
        _, y, p = frame(0.3, 25)
    assert abs(p - 25) < 1e-3 and abs(y - math.degrees(0.3)) < 1e-3, (y, p)
    print("pitch: mode off, view untouched (25 deg down)")
    _, y, p = frame(0.0, 22, r3=True)          # the recenter already took one step on the press
    assert g.state()[0] == 1 and abs(p - 25) < 1e-3 and abs(y) < 1e-3, (y, p)
    for pitch in (17, 12, 8, 5):
        eye, y, p = frame(0.0, pitch)
        assert abs(p - 25) < 1e-3 and abs(y) < 1e-3, (pitch, p)
    print("R3 on: the recenter swings the yaw behind Link, the pitch stays at 25 deg")
    for _ in range(8):
        eye, y, p = frame(0.0, 5)
    h = target[1] - link[1]
    assert close(eye, (link[0], link[1] + h, link[2] - 0.15)), eye   # eye placement unchanged
    eye, y, p = frame(0.0, 15)                  # game pitch moves again (right stick): followed
    assert abs(p - 35) < 1e-3, p
    eye, y, p = frame(0.0, -20)
    assert abs(p) < 1e-3, p
    print("after the recenter: the game's pitch changes are followed (+10, -35 deg)")
    eye, y, p = frame(0.0, 70)                  # 90 + offset 20 would pass straight up: clamped
    assert abs(p - 85) < 1e-2, p
    print("pitch clamped at 85 deg")
    frame(0.0, 70, r3=True)                     # off
    assert g.state()[0] == 0
    _, y, p = frame(0.0, 40)
    assert abs(p - 40) < 1e-3
    print("R3 off: the game's camera again")

    frame(0.0, 30)
    frame(0.0, 27, r3=True)                     # on from 30
    _, y, p = frame(0.0, 22)
    assert abs(p - 30) < 1e-3, p
    _, y, p = frame(0.0, 20, stick=20000)       # right stick used: follow from here on
    assert abs(p - 28) < 1e-3, p
    _, y, p = frame(0.0, 15)
    assert abs(p - 23) < 1e-3, p
    print("right stick during the recenter: following resumes at once")
    g.stick_y["fullkey"] = 0
    frame(0.0, 15, r3=True)                     # off
    frame(0.0, 10)
    frame(0.0, 10, r3=True)                     # on from 10
    for k in range(70):                         # the game keeps drifting the pitch: after HOLD_MAX views it's followed
        _, y, p = frame(0.0, 10 - 0.5 * (k + 1))
    assert abs(p - (10 - 0.5 * 10)) < 1e-2, p   # ignored for 60 views, then the last 10 steps followed
    print("a pitch that never settles is followed again after 60 views")


if __name__ == "__main__":
    main()
