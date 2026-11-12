"""Run KaeGae's hook point stubs (Core's .ips) on a patched main in Unicorn.

    python3 tests/test_kaegae_hooks.py <flat main image> <any zip built by tools/kaemod.py>

With the slot empty and with a function in it (one that trashes every caller-saved register), the
movement update's second instruction must still do its work (d10 stored, sp down 0x80) and come
back to the third with the arguments, x29 and x30 as they were.
"""
import struct
import sys
import zipfile

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import *

BASE, SLOT, SITE, AFTER, FN, STACK = 0x80020000, 0x84EBFB00, 0x82C415E4, 0x82C415E8, 0x30000000, 0x20000000


def main():
    img = bytearray(open(sys.argv[1], "rb").read())
    z = zipfile.ZipFile(sys.argv[2])
    b = z.read(next(n for n in z.namelist() if n.endswith(".ips")))
    pos = 5
    while b[pos:pos + 4] != b"EEOF":
        o, s = struct.unpack_from(">IH", b, pos)
        img[o - 0x100:o - 0x100 + s] = b[pos + 6:pos + 6 + s]
        pos += 6 + s
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    u.mem_map(BASE, (len(img) + 0xFFFF) & ~0xFFFF)
    u.mem_write(BASE, bytes(img))
    u.mem_map(STACK - 0x10000, 0x20000)
    u.mem_map(FN, 0x1000)
    u.reg_write(UC_ARM64_REG_CPACR_EL1, 0x300000)
    calls = []

    def fake(uc, *_):
        calls.append(uc.reg_read(UC_ARM64_REG_X0))
        for r in range(UC_ARM64_REG_X0, UC_ARM64_REG_X0 + 18):
            uc.reg_write(r, 0xDEAD)
        for r in range(UC_ARM64_REG_Q0, UC_ARM64_REG_Q0 + 8):
            uc.reg_write(r, 0xBAD)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    u.hook_add(UC_HOOK_CODE, fake, None, FN, FN)
    for fn in (0, FN):
        u.mem_write(SLOT, struct.pack("<Q", fn))
        for k in range(9):
            u.reg_write(UC_ARM64_REG_X0 + k, 0x1000 + k)
        for k in range(8):
            u.reg_write(UC_ARM64_REG_Q0 + k, 0x2000 + k)
        u.reg_write(UC_ARM64_REG_X30, 0x7777)
        u.reg_write(UC_ARM64_REG_X29, 0x2929)
        u.reg_write(UC_ARM64_REG_D10, 0x3FF0000000000000)
        u.reg_write(UC_ARM64_REG_SP, STACK)
        u.emu_start(SITE, AFTER, count=200)
        assert u.reg_read(UC_ARM64_REG_PC) == AFTER
        assert u.reg_read(UC_ARM64_REG_SP) == STACK - 0x80
        assert struct.unpack("<Q", u.mem_read(STACK - 0x80, 8))[0] == 0x3FF0000000000000
        for k in range(9):
            assert u.reg_read(UC_ARM64_REG_X0 + k) == 0x1000 + k, f"x{k}"
        for k in range(8):
            assert u.reg_read(UC_ARM64_REG_Q0 + k) == 0x2000 + k, f"q{k}"
        assert u.reg_read(UC_ARM64_REG_X30) == 0x7777 and u.reg_read(UC_ARM64_REG_X29) == 0x2929
    assert calls == [0x1000], calls
    print("hook point stub: ok (empty slot and called slot)")


if __name__ == "__main__":
    main()
