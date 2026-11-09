"""Run the FPV Drone hooks on a patched main in Unicorn, with a fake controller, timer and camera.

    python3 tests/test_fpv_drone.py <flat main image> <fpv-drone zip>

The controller reads go through the game's real GetNpadStates import stubs (their GOT slots point
at a fake nn::hid), so the stub patch, npad_wrap and fpv_input all run as they would in game. The
view hook runs from its site. Checks: the toggle, take-off from the game camera, hiding the
controller from the game, hover, Angle / Acro / Simple flight, + and - leaving the drone, standing by
when the gameplay view stops, and that every register the game relies on comes back unchanged.
"""
import math
import struct
import sys
import zipfile

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INSN, UC_HOOK_INTR
from unicorn.arm64_const import *

BASE = 0x80020000
HEAP = 0x10000000
STACK = 0x20000000
FAKE_HID = 0x30000000
VT_VIEW, CAMMGR_SLOT, DRONE = 0x84C18A88, 0x84CA6BC0, 0x84EBFD00
STUBS = {  # style: (PLT stub, GOT slot)
    "joydual": (0x83C627F0, 0x84CDF5C0), "fullkey": (0x83C62800, 0x84CDF5C8),
    "joyleft": (0x83C62810, 0x84CDF5D0), "joyright": (0x83C62820, 0x84CDF5D8),
    "handheld": (0x83C62830, 0x84CDF5E0),
}
SITE, SITE_RET, SITE_TAKEN = 0x804E506C, 0x804E5070, 0x804E5B78
FREQ = 19_200_000
A, B, X, Y, L3, R3, L, R, ZL, ZR, PLUS, MINUS = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
FREE, ANGLE, ACRO, SIMPLE = 0, 1, 2, 3
VT_ACTOR, VT_PLAYER, VT_CCT = 0x84B45E18, 0x84B6C460, 0x84C54F10
MOVE, MOVE_RET, CHANGE_POSITION = 0x82C415E0, 0x82C415E4, 0x806D2530
FULL = 32767


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
        u.reg_write(UC_ARM64_REG_CPACR_EL1, 0x300000)   # FP/SIMD on
        self.tick = 1_000_000
        self.pads = {}            # (style, npad id) -> (buttons, lx, ly, rx, ry)
        self.history = 16
        for i, (style, (_, got)) in enumerate(STUBS.items()):
            fn = FAKE_HID + 0x10 * i
            self.q(got, fn)
            u.hook_add(UC_HOOK_CODE, self._hid, style, fn, fn)
        u.hook_add(UC_HOOK_INTR, self._svc)
        u.hook_add(UC_HOOK_INSN, self._mrs, None, 1, 0, UC_ARM64_INS_MRS)
        self.svcs = []
        # camera manager -> camera 0 -> gameplay view
        self.view, self.camera = HEAP + 0x1000, HEAP + 0x3000
        mgr_ptr, mgr, cams, cam0 = HEAP + 0x100, HEAP + 0x200, HEAP + 0x300, HEAP + 0x400
        self.q(CAMMGR_SLOT, mgr_ptr); self.q(mgr_ptr, mgr); self.d(mgr + 0x20, 1); self.q(mgr + 0x28, cams)
        self.q(cams, cam0); self.q(cam0 + 0x78, self.view); self.q(self.view, VT_VIEW)
        self.other_view = HEAP + 0x5000
        self.q(self.other_view, VT_VIEW)
        self.buf, self.idp = HEAP + 0x8000, HEAP + 0x9000
        # Link: actor -> components -> movement (in the player object at +0x1d50) -> "Player",
        # and components -> +80 -> +32 -> +16 -> +8 = his character controller.
        self.link = self.make_actor(HEAP + 0x40000, b"Player\0")
        self.other = self.make_actor(HEAP + 0x80000, b"Enemy\0")
        self.moves = []
        u.hook_add(UC_HOOK_CODE, self._change_position, None, CHANGE_POSITION, CHANGE_POSITION)

    def make_actor(self, base, name):
        actor, comps, player, res = base, base + 0x1000, base + 0x2000, base + 0x8000
        c1, c2, c3, cct = base + 0x9000, base + 0x9100, base + 0x9200, base + 0x9300
        self.q(actor, VT_ACTOR); self.q(actor + 0x270, comps)
        self.q(comps + 0x320, player + 0x1D50); self.q(player + 0x1D50 + 0x18, actor)
        self.q(player, VT_PLAYER); self.q(player + 0x10, res); self.u.mem_write(res + 0x58, name)
        self.q(comps + 80, c1); self.q(c1 + 32, c2); self.q(c2 + 16, c3); self.q(c3 + 8, cct)
        self.q(cct, VT_CCT)
        return actor, cct

    def _change_position(self, u, addr, size, _):
        cct = u.reg_read(UC_ARM64_REG_X0)
        self.moves.append((cct, struct.unpack("<4f", u.mem_read(u.reg_read(UC_ARM64_REG_X1), 16))))
        for r in range(UC_ARM64_REG_X0, UC_ARM64_REG_X0 + 18):
            u.reg_write(r, 0xDEAD0000 + r)
        for r in range(UC_ARM64_REG_Q0, UC_ARM64_REG_Q0 + 8):
            u.reg_write(r, 0xBAD)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def actor_update(self, actor):
        """The game's call into the movement update, from its first instruction to its second."""
        u = self.u
        self._sentinels()
        u.reg_write(UC_ARM64_REG_X0, actor)
        u.emu_start(MOVE, MOVE_RET, count=20000)
        assert u.reg_read(UC_ARM64_REG_PC) == MOVE_RET
        assert u.reg_read(UC_ARM64_REG_SP) == STACK and u.reg_read(UC_ARM64_REG_X30) == 0x7777
        for k in range(29):
            if 9 <= k <= 18:
                continue   # caller-saved and not arguments: free at a function's first instruction
            want = actor if k == 0 else 0x5000 + k
            assert u.reg_read(UC_ARM64_REG_X0 + k) == want, f"x{k} changed (actor hook)"
        for k in list(range(8)) + list(range(8, 16)):
            got = u.reg_read(UC_ARM64_REG_Q0 + k)
            want = 0x1111 * (k + 1)
            assert (got if k < 8 else got & 0xFFFFFFFFFFFFFFFF) == want, f"q{k} changed (actor hook)"

    def q(self, a, v): self.u.mem_write(a, struct.pack("<Q", v))
    def d(self, a, v): self.u.mem_write(a, struct.pack("<I", v))
    def f(self, a, *v): self.u.mem_write(a, struct.pack("<%df" % len(v), *v))
    def rf(self, a, n=1): return struct.unpack("<%df" % n, self.u.mem_read(a, 4 * n))

    def _svc(self, u, intno, _):
        pc = u.reg_read(UC_ARM64_REG_PC)          # the instruction after the svc
        word = struct.unpack("<I", u.mem_read(pc - 4, 4))[0]
        assert word & 0xFFE0001F == 0xD4000001, f"exception {intno} at {pc - 4:#x}, not an svc"
        num = (word >> 5) & 0xFFFF
        self.svcs.append(num)
        assert num == 0x1E, f"svc {num:#x}"       # GetSystemTick: x0 = ticks, nothing else changes
        u.reg_write(UC_ARM64_REG_X0, self.tick)

    def _mrs(self, u, reg, cp, _):
        # Lichii's CPU emulator stops on system registers it doesn't know (cntvct_el0, cntfrq_el0),
        # so the patch must not read any. The flags (NZCV) are fine: First Person uses them too.
        if (cp.op0, cp.op1, cp.crn, cp.crm, cp.op2) == (3, 3, 4, 2, 0):
            return False   # not handled here: Unicorn reads NZCV itself
        raise AssertionError(f"mrs of a system register at {u.reg_read(UC_ARM64_REG_PC):#x}")

    def _hid(self, u, addr, size, style):
        out, count = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1)
        npad = struct.unpack("<I", u.mem_read(u.reg_read(UC_ARM64_REG_X2), 4))[0]
        assert count == 16
        pad = self.pads.get((style, npad))
        n = self.history if pad else 1
        for i in range(n):
            b, lx, ly, rx, ry = pad or (0, 0, 0, 0, 0)
            u.mem_write(out + 0x28 * i, struct.pack("<qQiiiiII", 100 - i, b, lx, ly, rx, ry, 1 if pad else 0, 0))
        for r in range(UC_ARM64_REG_X1, UC_ARM64_REG_X0 + 18):   # clobber caller-saved like real code
            u.reg_write(r, 0xDEAD0000 + r)
        for r in range(UC_ARM64_REG_Q0, UC_ARM64_REG_Q0 + 8):
            u.reg_write(r, 0xBAD)
        u.reg_write(UC_ARM64_REG_X0, n)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def _sentinels(self):
        u = self.u
        for k in range(29):
            u.reg_write(UC_ARM64_REG_X0 + k, 0x5000 + k)
        for k in range(32):
            u.reg_write(UC_ARM64_REG_Q0 + k, 0x1111 * (k + 1))
        u.reg_write(UC_ARM64_REG_SP, STACK)
        u.reg_write(UC_ARM64_REG_X30, 0x7777)
        u.reg_write(UC_ARM64_REG_NZCV, 0x60000000)

    def read_pad(self, style="fullkey", npad=0):
        """The game's call: GetNpadStates(buf, 16, id) through the import stub."""
        u = self.u
        self._sentinels()
        self.d(self.idp, npad)
        u.reg_write(UC_ARM64_REG_X0, self.buf)
        u.reg_write(UC_ARM64_REG_X1, 16)
        u.reg_write(UC_ARM64_REG_X2, self.idp)
        u.reg_write(UC_ARM64_REG_X30, 0x7770)
        u.emu_start(STUBS[style][0], 0x7770, count=200000)
        assert u.reg_read(UC_ARM64_REG_PC) == 0x7770
        assert u.reg_read(UC_ARM64_REG_SP) == STACK, "sp"
        for k in range(19, 29):
            assert u.reg_read(UC_ARM64_REG_X0 + k) == 0x5000 + k, f"x{k} changed (npad_wrap)"
        for k in range(8, 16):   # d8-d15 (low halves) must survive a call
            got = u.reg_read(UC_ARM64_REG_Q0 + k) & 0xFFFFFFFFFFFFFFFF
            assert got == 0x1111 * (k + 1), f"d{k} changed (npad_wrap)"
        n = u.reg_read(UC_ARM64_REG_X0)
        states = [struct.unpack("<qQiiiiII", u.mem_read(self.buf + 0x28 * i, 0x28)) for i in range(n)]
        return n, states

    def game_view(self, eye, yaw, pitch=0.0, view=None):
        """Write a game camera matrix the way the game does, then run the view hook."""
        view = view or self.view
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        back = (sy * cp, -sp, cy * cp)         # camera looks along -back
        right = (cy, 0.0, -sy)
        up = (back[1] * right[2] - back[2] * right[1], back[2] * right[0] - back[0] * right[2],
              back[0] * right[1] - back[1] * right[0])
        for r, axis in enumerate((right, up, back)):
            self.f(view + 8 + r * 16, *axis, -sum(a * e for a, e in zip(axis, eye)))
        self.f(view + 0x38, *eye)
        u = self.u
        self._sentinels()
        u.reg_write(UC_ARM64_REG_X19, self.camera)
        u.reg_write(UC_ARM64_REG_X20, view)
        u.reg_write(UC_ARM64_REG_X8, 0x1234)
        u.emu_start(SITE, SITE_RET, count=2000)
        assert u.reg_read(UC_ARM64_REG_PC) == SITE_RET
        assert u.reg_read(UC_ARM64_REG_SP) == STACK
        assert u.reg_read(UC_ARM64_REG_NZCV) == 0x60000000, "flags changed (view hook)"
        for k in range(29):
            want = {8: 0x1234, 19: self.camera, 20: view}.get(k, 0x5000 + k)
            assert u.reg_read(UC_ARM64_REG_X0 + k) == want, f"x{k} changed (view hook)"
        for k in range(32):
            assert u.reg_read(UC_ARM64_REG_Q0 + k) == 0x1111 * (k + 1), f"q{k} changed (view hook)"
        return self.view_pose(view)

    def view_pose(self, view=None):
        rows = [self.rf((view or self.view) + 8 + r * 16, 4) for r in range(3)]
        eye = tuple(-sum(rows[r][i] * rows[r][3] for r in range(3)) for i in range(3))
        return eye, [row[:3] for row in rows]

    def drone(self):
        on, mode = struct.unpack("<II", self.u.mem_read(DRONE, 8))
        p = self.rf(DRONE + 0x68, 3)
        v = self.rf(DRONE + 0x74, 3)
        r = [self.rf(DRONE + 0x80 + 12 * i, 3) for i in range(3)]
        return on, mode, p, v, r

    def frame(self, buttons=0, lx=0, ly=0, rx=0, ry=0, dt=1 / 60, style="fullkey", npad=0,
              eye=(0.0, 5.0, 10.0), yaw=0.0):
        """One game frame: controller read, then the gameplay view."""
        self.tick += int(dt * FREQ)
        self.pads = {(style, npad): (buttons, lx, ly, rx, ry)}
        n, states = self.read_pad(style, npad)
        pose = self.game_view(eye, yaw)
        return states, pose


def close(a, b, eps=1e-3):
    return all(abs(x - y) < eps for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def main():
    g = Game(load(sys.argv[1], sys.argv[2]))
    game_eye, game_yaw = (3.0, 5.0, 10.0), math.radians(30)

    def fly(seconds, **kw):
        kw.setdefault("eye", game_eye)
        kw.setdefault("yaw", game_yaw)
        for _ in range(int(round(seconds * 60))):
            out = g.frame(**kw)
        return out

    # Off: the game sees the controller as it is, and its own camera.
    states, (eye, _) = g.frame(buttons=1 << B, lx=1000, ly=-2000, eye=game_eye, yaw=game_yaw)
    assert len(states) == 16 and all(s[1] == 1 << B and s[2] == 1000 and s[3] == -2000 for s in states)
    assert close(eye, game_eye) and g.drone()[0] == 0
    print("off: controller passes through, game camera unchanged")

    # L3: on, at the game camera, level, same heading, in Free fly (the mode at boot).
    states, (eye, rows) = g.frame(buttons=1 << L3, eye=game_eye, yaw=game_yaw)
    on, mode, p, v, r = g.drone()
    assert on == 1 and mode == FREE, (on, mode)
    assert all(s[1] == 0 for s in states), states[:2]
    assert close(eye, game_eye, 2e-2), eye
    want_back = (math.sin(game_yaw), 0.0, math.cos(game_yaw))
    assert close(r[2], want_back, 1e-3) and close(r[1], (0, 1, 0), 1e-3), r
    assert close(rows[2], want_back, 1e-3), rows[2]   # Free fly: no camera uptilt
    print("L3: on in Free fly (the boot default) at the game camera, level, heading kept")
    states, (eye, rows) = g.frame(buttons=1 << Y | 1 << R3, lx=FULL, ly=-FULL, rx=123, ry=-456, eye=game_eye, yaw=game_yaw)
    assert all(s[1] == 0 and s[2:6] == (0, 0, 0, 0) for s in states), states[:2]
    print("flying: all 16 states the game reads have no buttons and centred sticks")
    assert g.drone()[1] == ANGLE
    g.frame(buttons=1 << A, eye=game_eye, yaw=game_yaw)
    _, (eye, rows) = g.frame(eye=game_eye, yaw=game_yaw)
    up20 = math.radians(20)
    assert abs(dot(rows[2], want_back) - math.cos(up20)) < 2e-3, rows[2]   # camera tilted up 20 deg
    assert rows[2][1] < 0, "camera should look up a little (back axis points down)"
    print("Y: Angle mode, camera tilted up 20 deg from the drone")

    g.frame(buttons=1 << A, eye=game_eye, yaw=game_yaw)
    fly(0.5)   # let go of the sticks
    states, (eye, rows) = fly(2.0)
    on, mode, p, v, r = g.drone()
    assert abs(p[1] - game_eye[1]) < 0.6 and abs(v[1]) < 0.2, (p, v)
    assert abs(r[1][1] - 1.0) < 1e-3, r
    print("hover: centred sticks hold height (y %.2f, vy %.2f)" % (p[1], v[1]))
    g.frame(buttons=1 << A, eye=game_eye, yaw=game_yaw)
    p0 = g.drone()[2]
    assert close(p0, game_eye, 0.05), p0
    print("A: back to the game camera")

    fly(1.0, ly=FULL)
    on, mode, p, v, r = g.drone()
    assert p[1] - game_eye[1] > 5 and v[1] > 8, (p, v)
    print("full throttle 1 s: climbed %.1f m, %.1f m/s up" % (p[1] - game_eye[1], v[1]))

    g.frame(buttons=1 << A, eye=game_eye, yaw=game_yaw)
    fly(2.0, ry=FULL)
    on, mode, p, v, r = g.drone()
    fwd0 = (-math.sin(game_yaw), 0.0, -math.cos(game_yaw))
    tilt = math.degrees(math.asin(r[2][1]))
    assert 45 < tilt < 52, tilt
    moved = tuple(a - b for a, b in zip(p, game_eye))
    assert dot(moved, fwd0) > 5, moved
    print("Angle, pitch stick forward 2 s: nose down %.0f deg, %.1f m forward" % (tilt, dot(moved, fwd0)))

    fly(2.0)
    on, mode, p, v, r = g.drone()
    assert abs(r[2][1]) < 0.02 and abs(r[0][1]) < 0.02, r
    print("Angle, sticks centred: levels itself")

    g.frame(buttons=1 << A, eye=game_eye, yaw=game_yaw)
    fly(0.25, lx=FULL)
    on, mode, p, v, r = g.drone()
    fwd = (-r[2][0], -r[2][1], -r[2][2])
    right0 = (math.cos(game_yaw), 0.0, -math.sin(game_yaw))
    turned = math.degrees(math.atan2(dot(fwd, right0), dot(fwd, fwd0)))
    assert 65 < turned < 80, turned
    print("yaw stick right 0.25 s: nose turned %.0f deg right" % turned)

    # Acro: X. Full right roll for 1 s should roll about 670 deg, frame stays orthonormal.
    g.frame(buttons=1 << A, eye=game_eye, yaw=game_yaw)
    g.frame(buttons=1 << X, eye=game_eye, yaw=game_yaw)
    assert g.drone()[1] == ACRO
    g.frame(rx=FULL, eye=game_eye, yaw=game_yaw)
    r = g.drone()[4]
    assert r[0][1] < 0, "roll right: right side goes down"
    total, prev = 0.0, g.drone()[4][0]
    for _ in range(59):
        g.frame(rx=FULL, eye=game_eye, yaw=game_yaw)
        cur = g.drone()[4][0]
        total += math.degrees(math.acos(max(-1.0, min(1.0, dot(prev, cur)))))
        prev = cur
    assert 600 < total < 720, total
    r = g.drone()[4]
    for i in range(3):
        for j in range(3):
            assert abs(dot(r[i], r[j]) - (i == j)) < 1e-3, r
    print("Acro, full roll 1 s: rolled %.0f deg, frame still orthonormal" % total)
    fly(0.5)
    r2 = g.drone()[4]
    assert abs(r2[0][1] - r[0][1]) < 0.05, "Acro doesn't level"
    print("Acro, sticks centred: holds the attitude (no levelling)")
    g.frame(buttons=1 << A, eye=game_eye, yaw=game_yaw)
    g.frame(ry=-FULL, eye=game_eye, yaw=game_yaw)
    assert g.drone()[4][2][1] < 0, "pitch back: nose up"
    print("Acro, pitch stick back: nose up")

    # Simple: B. Throttle up = climb at ~4 m/s, let go = stops.
    g.frame(buttons=1 << B, eye=game_eye, yaw=game_yaw)
    on, mode, p, v, r = g.drone()
    assert mode == SIMPLE and abs(r[1][1] - 1) < 1e-3, (mode, r)
    print("B: Simple mode, starts level")
    fly(2.0, ly=FULL)
    vy = g.drone()[3][1]
    assert abs(vy - 4.0) < 0.3, vy
    fly(2.0)
    v = g.drone()[3]
    assert abs(v[1]) < 0.2, v
    fly(2.0, ry=FULL)
    fly(3.0)
    v = g.drone()[3]
    assert math.sqrt(dot(v, v)) < 1.0, v
    print("Simple: climbs at %.1f m/s, holds height, stops by itself" % vy)

    # Other controllers and players: hidden while flying too.
    g.tick += FREQ // 60
    g.pads = {("handheld", 0x20): (1 << A, 500, 0, 0, 0)}
    n, states = g.read_pad("handheld", 0x20)
    assert all(s[1] == 0 and s[2] == 0 for s in states)
    g.pads = {("fullkey", 1): (1 << A, 500, 0, 0, 0)}
    n, states = g.read_pad("fullkey", 1)
    assert all(s[1] == 0 and s[2] == 0 for s in states)
    print("handheld and player 2: hidden from the game while flying")

    # + keeps working and leaves the drone.
    states, (eye, _) = g.frame(buttons=1 << PLUS, eye=game_eye, yaw=game_yaw)
    assert states[0][1] == 1 << PLUS and g.drone()[0] == 0
    states, (eye, _) = g.frame(buttons=1 << Y, eye=game_eye, yaw=game_yaw)
    assert close(eye, game_eye) and states[0][1] == 1 << Y
    print("+: passes through, leaves the drone, game camera and controls back")

    # Handheld can fly too.
    g.frame(buttons=1 << L3, style="handheld", npad=0x20, eye=game_eye, yaw=game_yaw)
    assert g.drone()[0] == 1
    g.frame(buttons=1 << MINUS, style="handheld", npad=0x20, eye=game_eye, yaw=game_yaw)
    assert g.drone()[0] == 0
    print("handheld: L3 on, - off")

    # Stand by when the gameplay view isn't built (menu, loading): controller passes through.
    g.frame(buttons=1 << L3, eye=game_eye, yaw=game_yaw)
    assert g.drone()[0] == 1
    for _ in range(12):
        g.tick += FREQ // 60
        g.pads = {("fullkey", 0): (1 << A, 0, FULL, 0, 0)}
        n, states = g.read_pad()
    assert states[0][1] == 1 << A and states[0][3] == FULL
    p_before = g.drone()[2]
    fly(0.02)
    assert close(g.drone()[2], p_before, 0.05) and g.drone()[0] == 1
    print("no gameplay view for 12 reads: stands by and lets the controller through; resumes after")

    # Other views are left alone; the matrix is only replaced on the gameplay view.
    g.game_view((50.0, 50.0, 50.0), 0.0, view=g.other_view)
    eye, _ = g.view_pose(g.other_view)
    assert close(eye, (50.0, 50.0, 50.0))
    print("other views: untouched")

    # The replaced cbz: taken when x8 == 0.
    u = g.u
    g._sentinels()
    u.reg_write(UC_ARM64_REG_X20, g.view)
    u.reg_write(UC_ARM64_REG_X8, 0)
    u.emu_start(SITE, SITE_TAKEN, count=2000)
    assert u.reg_read(UC_ARM64_REG_PC) == SITE_TAKEN
    print("replaced cbz x8: still branches when x8 == 0")
    assert g.svcs and set(g.svcs) == {0x1E}
    print("timer: svcGetSystemTick only, no system-register reads")
    # Free fly: L. Level, no uptilt; left stick moves where you look, right stick looks, ZR up.
    g.frame(buttons=1 << PLUS, eye=game_eye, yaw=game_yaw)   # off, whatever came before
    g.frame(eye=game_eye, yaw=game_yaw)
    g.frame(buttons=1 << L3, eye=game_eye, yaw=game_yaw)
    assert g.drone()[0] == 1
    g.frame(buttons=1 << L, eye=game_eye, yaw=game_yaw)
    on, mode, p, v, r = g.drone()
    assert mode == FREE and abs(r[1][1] - 1) < 1e-3
    _, (eye, rows) = g.frame(eye=game_eye, yaw=game_yaw)
    assert abs(rows[2][1]) < 1e-3, "Free fly: camera not tilted up"
    p0 = g.drone()[2]
    fly(1.0, ly=FULL)
    p1 = g.drone()[2]
    moved = tuple(a - b for a, b in zip(p1, p0))
    fwd0 = (-math.sin(game_yaw), 0.0, -math.cos(game_yaw))
    assert abs(dot(moved, fwd0) - 8.0) < 0.6 and abs(moved[1]) < 0.05, moved
    print("Free fly: left stick forward 1 s: %.1f m along the view, level" % dot(moved, fwd0))
    fly(0.5, ry=FULL)
    look_up = math.degrees(math.asin(-g.drone()[4][2][1]))
    assert 50 < look_up < 70, look_up
    fly(2.0, ry=FULL)
    look_up = math.degrees(math.asin(-g.drone()[4][2][1]))
    assert 70 < look_up < 80, look_up
    r = g.drone()[4]
    assert abs(r[0][1]) < 1e-3, "no roll"
    print("Free fly: right stick up looks up (%.0f deg after 2.5 s, stops short of straight up), no roll" % look_up)
    p0 = g.drone()[2]
    fly(1.0, ly=FULL)
    moved = tuple(a - b for a, b in zip(g.drone()[2], p0))
    assert moved[1] > 7.0, moved
    print("Free fly: moving while looking up climbs (%.1f m)" % moved[1])
    p0 = g.drone()[2]
    fly(1.0, buttons=1 << ZR)
    assert abs(g.drone()[2][1] - p0[1] - 8.0) < 0.6
    fly(0.5, buttons=1 << ZL)
    print("Free fly: ZR up 8 m/s, ZL down")
    fly(0.5, rx=FULL)
    assert abs(g.drone()[4][0][1]) < 1e-3
    p0 = g.drone()[2]
    fly(1.0)
    assert close(g.drone()[2], p0, 1e-4)
    print("Free fly: turning keeps it level, sticks centred stops dead")

    # Carry Link: R. His controller is moved in his movement update: feet at camera height,
    # 1 m behind the camera along its level back axis.
    def carry_point():
        p, r = g.drone()[2], g.drone()[4]
        h = math.hypot(r[2][0], r[2][2])
        return (p[0] + r[2][0] / h, p[1], p[2] + r[2][2] / h, 0.0)
    g.moves.clear()
    g.actor_update(g.link[0])
    assert not g.moves
    g.frame(buttons=1 << R, eye=game_eye, yaw=game_yaw)
    g.actor_update(g.other[0])
    assert not g.moves, "only Link is carried"
    g.actor_update(g.link[0])
    assert len(g.moves) == 1 and g.moves[0][0] == g.link[1], g.moves
    want = carry_point()
    assert close(g.moves[0][1], want, 1e-4), (g.moves, want)
    eye, rows = g.view_pose()
    assert abs(g.moves[0][1][1] - eye[1]) < 1e-3, "feet at camera height"
    h = math.hypot(rows[2][0], rows[2][2])
    behind = dot(tuple(a - b for a, b in zip(g.moves[0][1][:3], eye)), (rows[2][0] / h, 0.0, rows[2][2] / h))
    assert abs(behind - 1.0) < 1e-3, "1 m behind the camera"   # (back axis = away from where it looks)
    print("R: carrying; Link's feet at camera height, 1 m behind it: %s" % (tuple(round(x, 2) for x in g.moves[0][1][:3]),))
    fly(1.0, ly=FULL)
    g.actor_update(g.link[0])
    assert close(g.moves[-1][1], carry_point(), 1e-4)
    fly(0.3, rx=FULL)
    g.actor_update(g.link[0])
    assert close(g.moves[-1][1], carry_point(), 1e-4)
    print("carried Link follows the camera and stays behind it as it turns")
    g.frame(buttons=1 << R, eye=game_eye, yaw=game_yaw)
    n = len(g.moves)
    g.actor_update(g.link[0])
    assert len(g.moves) == n
    print("R again: drops him")
    g.frame(buttons=1 << R, eye=game_eye, yaw=game_yaw)
    g.frame(buttons=1 << L3, eye=game_eye, yaw=game_yaw)
    n = len(g.moves)
    g.actor_update(g.link[0])
    assert g.drone()[0] == 0 and len(g.moves) == n
    print("drone off while carrying: Link is let go")
    print("all checks passed")


if __name__ == "__main__":
    main()
