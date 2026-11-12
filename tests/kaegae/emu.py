"""A small stand-in for the game's process, for the KaeGae module tests: Unicorn runs the real
AArch64 modules, and this file does what the game's rtld and the system do around them.

  load      puts a module (an NSO, or an ELF for the fakes) in memory
  link      relocates every module and resolves its imports against the others, by name
  call      runs a function to its return
  svc       debug output is collected in `log`; memory queries answer from what is mapped
"""
import struct

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_INTR
from unicorn.arm64_const import *

PAGE = 0x1000
STACK_TOP, STACK_SIZE = 0x60000000, 0x100000
RETURN_AT = 0x50000000
DT_PLTRELSZ, DT_HASH, DT_STRTAB, DT_SYMTAB, DT_RELA, DT_RELASZ, DT_INIT, DT_JMPREL = 2, 4, 5, 6, 7, 8, 12, 23
R_ABS64, R_GLOB_DAT, R_JUMP_SLOT, R_RELATIVE = 257, 1025, 1026, 1027


def elf_segments(elf):
    """[(vaddr, bytes, memsz)] of an ELF's PT_LOAD segments."""
    phoff, = struct.unpack_from("<Q", elf, 0x20)
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x36)
    out = []
    for i in range(phnum):
        p_type, _, offset, vaddr, _, filesz, memsz, _ = struct.unpack_from("<IIQQQQQQ", elf, phoff + i * phentsize)
        if p_type == 1:
            out.append((vaddr, elf[offset:offset + filesz], memsz))
    return out


def nso_segments(nso):
    """[(vaddr, bytes, memsz)] of an uncompressed NSO, as tools/mknso.py writes them."""
    assert nso[:4] == b"NSO0"
    out = []
    for i in range(3):
        offset, vaddr, size, extra = struct.unpack_from("<IIII", nso, 0x10 + 0x10 * i)
        out.append((vaddr, nso[offset:offset + size], size + (extra if i == 2 else 0)))
    return out


class Module:
    def __init__(self, name, base, size):
        self.name, self.base, self.size = name, base, size
        self.exports = {}


class Process:
    def __init__(self):
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.uc.reg_write(UC_ARM64_REG_CPACR_EL1, 0x300000)   # floating point on
        self.uc.mem_map(STACK_TOP - STACK_SIZE, STACK_SIZE)
        self.uc.mem_map(RETURN_AT, PAGE)
        self.uc.hook_add(UC_HOOK_INTR, self._interrupt)
        self.modules = []        # in the order rtld would search them
        self.log = []
        self.unresolved = []
        self.ticks = 0

    # ---- memory ----
    def read(self, address, size):
        return bytes(self.uc.mem_read(address, size))

    def write(self, address, data):
        self.uc.mem_write(address, bytes(data))

    def u32(self, address):
        return struct.unpack("<I", self.read(address, 4))[0]

    def u64(self, address):
        return struct.unpack("<Q", self.read(address, 8))[0]

    def mapped(self, address):
        return any(start <= address <= end for start, end, _ in self.uc.mem_regions())

    # ---- loading ----
    def load(self, name, base, segments, size=None):
        end = max(vaddr + memsz for vaddr, _, memsz in segments)
        size = (size or end + PAGE - 1) & ~(PAGE - 1)
        self.uc.mem_map(base, size)
        for vaddr, data, _ in segments:
            self.write(base + vaddr, data)
        module = Module(name, base, size)
        self.modules.append(module)
        return module

    def _dynamic(self, m):
        mod0 = m.base + self.u32(m.base + 4)
        assert self.read(mod0, 4) == b"MOD0", f"{m.name}: no MOD0"
        at = mod0 + struct.unpack("<i", self.read(mod0 + 4, 4))[0]
        tags = {}
        while True:
            tag, value = struct.unpack("<qQ", self.read(at, 16))
            if tag == 0:
                return tags
            tags[tag] = value
            at += 16

    def _symbol(self, m, tags, index):
        name, info, _, section, value, _ = struct.unpack("<IBBHQQ", self.read(m.base + tags[DT_SYMTAB] + 24 * index, 24))
        at = m.base + tags[DT_STRTAB] + name
        text = self.read(at, 256).split(b"\0")[0].decode()
        return text, info >> 4, section, value

    def link(self, lazy=()):
        """Relocate every module. Imports of the modules named in `lazy` that go through the PLT
        are left unbound, pointing back into the module, as rtld leaves them until the first call."""
        dynamics = {m.name: self._dynamic(m) for m in self.modules}
        for m in self.modules:
            tags = dynamics[m.name]
            count = self.u32(m.base + tags[DT_HASH] + 4)       # nchain: the number of symbols
            for i in range(1, count):
                name, bind, section, value = self._symbol(m, tags, i)
                if section and bind in (1, 2) and name:
                    m.exports[name] = m.base + value
            m.init = m.base + tags[DT_INIT] if DT_INIT in tags else 0
        for m in self.modules:
            tags = dynamics[m.name]
            for table, size in ((DT_RELA, DT_RELASZ), (DT_JMPREL, DT_PLTRELSZ)):
                for k in range(0, tags.get(size, 0) if table in tags else 0, 24):
                    where, info, addend = struct.unpack("<QQq", self.read(m.base + tags[table] + k, 24))
                    kind, index = info & 0xFFFFFFFF, info >> 32
                    if kind == R_RELATIVE:
                        target = m.base + addend
                    elif kind in (R_ABS64, R_GLOB_DAT, R_JUMP_SLOT):
                        name, bind, section, value = self._symbol(m, tags, index)
                        if kind == R_JUMP_SLOT and m.name in lazy and not section:
                            target = m.base + self.u64(m.base + where)      # still pointing at the PLT
                        elif section:
                            target = m.base + value + addend
                        else:
                            found = next((o.exports[name] for o in self.modules if name in o.exports), None)
                            if found is None:
                                if bind != 2:                                # not weak
                                    self.unresolved.append((m.name, name))
                                found = -addend
                            target = found + addend
                    else:
                        raise AssertionError(f"{m.name}: relocation type {kind} isn't handled")
                    self.write(m.base + where, struct.pack("<Q", target))

    # ---- running ----
    def call(self, address, *args, d10=None):
        for i, value in enumerate(args):
            self.uc.reg_write(UC_ARM64_REG_X0 + i, value)
        if d10 is not None:
            self.uc.reg_write(UC_ARM64_REG_D10, d10)
        self.uc.reg_write(UC_ARM64_REG_SP, STACK_TOP - 0x100)
        self.uc.reg_write(UC_ARM64_REG_X30, RETURN_AT)
        self.uc.emu_start(address, RETURN_AT, count=20_000_000)
        assert self.uc.reg_read(UC_ARM64_REG_PC) == RETURN_AT, "the call didn't return"
        assert self.uc.reg_read(UC_ARM64_REG_SP) == STACK_TOP - 0x100, "the stack pointer moved"
        return self.uc.reg_read(UC_ARM64_REG_X0)

    def _interrupt(self, uc, number, _):
        pc = uc.reg_read(UC_ARM64_REG_PC)
        word = self.u32(pc - 4)
        assert word & 0xFFE0001F == 0xD4000001, f"unexpected exception {number} at {pc:#x}"
        svc = (word >> 5) & 0xFFFF
        if svc == 0x27:      # OutputDebugString(text, length)
            text = self.read(uc.reg_read(UC_ARM64_REG_X0), uc.reg_read(UC_ARM64_REG_X1))
            self.log.append(text.decode())
            uc.reg_write(UC_ARM64_REG_X0, 0)
        elif svc == 0x6:     # QueryMemory(info, _, address)
            out, address = uc.reg_read(UC_ARM64_REG_X0), uc.reg_read(UC_ARM64_REG_X2)
            region = next(((s, e) for s, e, _ in uc.mem_regions() if s <= address <= e), None)
            if region:
                info = struct.pack("<QQIIIIII", region[0], region[1] - region[0] + 1, 3, 0, 3, 0, 0, 0)
            else:
                info = struct.pack("<QQIIIIII", address & ~(PAGE - 1), PAGE, 0, 0, 0, 0, 0, 0)
            self.write(out, info)
            uc.reg_write(UC_ARM64_REG_X0, 0)
        elif svc == 0xB:     # SleepThread(ns): time doesn't pass here
            uc.reg_write(UC_ARM64_REG_X0, 0)
        elif svc == 0x1E:    # GetSystemTick: 2 ms a call, so nothing Core caches is seen twice
            self.ticks += 38400
            uc.reg_write(UC_ARM64_REG_X0, self.ticks)
        elif svc == 0x29:    # GetInfo: nothing to tell
            uc.reg_write(UC_ARM64_REG_X0, 0xE401)
        else:
            raise AssertionError(f"svc {svc:#x} isn't handled")
