"""Kaepora Core and core mods, end to end, without the game: the modules are built exactly as
they ship (tools/kaemod.py), loaded and linked by a small stand-in for the game's rtld, and run
in Unicorn against a fake game and a fake system module (tests/kaepora/).

    python3 tests/test_kaepora_modules.py

What this can show: Core's own logic on real AArch64 code, the module format, and that mods work
as their own modules or linked into Core's, whichever module starts first. What it can't show is
how the real rtld, emulator or console behave: that takes the in-game test in api/README.md.

Needs clang, ld.lld, llvm-nm, llvm-objcopy, Python 3.11+ and Unicorn 2. No game files.
"""
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HERE = REPO / "tests" / "kaepora"
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))
import emu  # noqa: E402
import kaemod  # noqa: E402
import kaepora_symbols  # noqa: E402

PACK = kaepora_symbols.load_packs()[0]
MAIN_BASE, SDK_BASE, CORE_BASE, MOD_BASE = 0x8052F000, 0x70000000, 0x90000000, 0x91000000
MOVE_UPDATE = 0x2C215E0
FAKE_FLAGS = ["--target=aarch64-none-elf", "-O1", "-fPIC", "-ffreestanding", "-fno-builtin", "-fvisibility=hidden",
              "-fno-stack-protector", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-Wall", "-Wextra",
              "-Werror", "-std=c11"]
MAIN_LD = """
PHDRS {{ code PT_LOAD FLAGS(5); nnmain PT_LOAD FLAGS(5); move PT_LOAD FLAGS(5); ro PT_LOAD FLAGS(4);
        rw PT_LOAD FLAGS(6); dyn PT_DYNAMIC; }}
SECTIONS {{
  . = 0;
  .text : {{ KEEP(*(.text.header)) *(.text .text.*) }} :code
  .plt  : {{ *(.plt .plt.*) }} :code
  . = {nnmain:#x};
  .text_nnmain : {{ KEEP(*(.text_nnmain)) }} :nnmain
  . = {move:#x};
  .text_move : {{ KEEP(*(.text_move)) }} :move
  . = {mod0:#x};
  .rodata   : {{ KEEP(*(.rodata.mod0)) *(.rodata .rodata.*) }} :ro
  .hash     : {{ *(.hash) }} :ro
  .gnu.hash : {{ *(.gnu.hash) }} :ro
  .dynsym   : {{ *(.dynsym) }} :ro
  .dynstr   : {{ *(.dynstr) }} :ro
  .rela.dyn : {{ *(.rela.dyn) }} :ro
  .rela.plt : {{ *(.rela.plt) }} :ro
  .eh_frame_hdr : {{ HIDDEN(__kp_eh_hdr_start = .); *(.eh_frame_hdr) HIDDEN(__kp_eh_hdr_end = .); }} :ro
  . = ALIGN(0x1000);
  .data     : {{ *(.data .data.*) }} :rw
  .dynamic  : {{ HIDDEN(__kp_dynamic = .); *(.dynamic) }} :rw :dyn
  .got      : {{ *(.got) }} :rw
  .got.plt  : {{ *(.got.plt) }} :rw
  .bss (NOLOAD) : {{ HIDDEN(__kp_bss_start = .); *(.bss.rtld_object) *(.bss .bss.*) *(COMMON) HIDDEN(__kp_bss_end = .); }} :rw
  /DISCARD/ : {{ *(.interp) *(.comment) *(.note*) *(.ARM.attributes) }}
}}
"""


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def build_fakes(work, nnmain=None):
    """The fake main (with nnMain where the pack says, or elsewhere) and the two fake sdk modules."""
    objs = []
    for src in (kaemod.CORE / "crt0.S", HERE / "fake_main.c", HERE / "fake_main_move.S"):
        obj = work / (src.name + ".o")
        run("clang", *FAKE_FLAGS, "-c", src, "-o", obj)
        objs.append(obj)
    script = work / "main.ld"
    script.write_text(MAIN_LD.format(nnmain=nnmain or PACK["detect"]["nnmain"], move=MOVE_UPDATE, mod0=PACK["detect"]["mod0"]))
    main = work / "main.elf"
    run("ld.lld", "-shared", "-Bsymbolic", "--hash-style=both", "-z", "norelro", "-z", "max-page-size=4096",
        "-T", script, "-o", main, *objs)
    sdks = {}
    for name, flags in (("sdk", []), ("old-sdk", ["-DOLD_SDK"])):
        obj = work / f"{name}.o"
        run("clang", *FAKE_FLAGS, *flags, "-c", HERE / "fake_sdk.c", "-o", obj)
        elf = work / f"{name}.elf"
        run("ld.lld", "-shared", "-Bsymbolic", "--hash-style=both", "--build-id=sha1", "-z", "norelro",
            "-z", "max-page-size=4096", "-T", kaemod.CORE / "module.ld", "-o", elf, objs[0], obj)
        sdks[name] = elf.read_bytes()
    return main.read_bytes(), sdks


def apply_ips(p, ips):
    """Core's patch to main, checking that it replaces the instruction it expects to."""
    _, records = kaemod.hook_patch()
    for offset, new, original in records:
        found = p.read(MAIN_BASE + offset, len(original))
        assert found == original, f"main+{offset:#x}: the patch expects {original.hex()}, the fake main has {found.hex()}"
    at = 5
    assert ips[:5] == b"IPS32"
    while ips[at:at + 4] != b"EEOF":
        offset, size = struct.unpack_from(">IH", ips, at)
        p.write(MAIN_BASE + offset - 0x100, ips[at + 6:at + 6 + size])
        at += 6 + size


class Game:
    """A process with the fake game in it and the built modules loaded, linked and started."""

    def __init__(self, fakes, files, order="core-first", lazy=True, patched=True, sdk="sdk", with_core=True,
                 other_hook=False):
        main_elf, sdks = fakes
        p = self.p = emu.Process()
        self.main = p.load("main", MAIN_BASE, emu.elf_segments(main_elf), size=PACK["detect"]["size"])
        if patched:
            apply_ips(p, files[f"exefs/{kaemod.HOOK_BUILD_ID}.ips"])
        added = []
        slots = sorted(name for name in files if name.startswith("exefs/subsdk"))
        for n, name in enumerate(slots):
            if name.endswith(kaemod.CORE_SLOT) and not with_core:
                continue
            base = CORE_BASE if name.endswith(kaemod.CORE_SLOT) else MOD_BASE + n * 0x1000000
            added.append(p.load(name.split("/")[1], base, emu.nso_segments(files[name])))
        self.sdk = p.load("sdk", SDK_BASE, emu.elf_segments(sdks[sdk]))
        p.link(lazy=("main",) if lazy else ())
        if other_hook:   # another module got to main's slot first
            assert not lazy, "other_hook needs main's imports bound (lazy=False)"
            start = MAIN_BASE + (PACK["detect"]["mod0"] & ~0xFFF) + 0x1000      # main's data, after its read-only part
            at = p.read(start, 0x10000).find(struct.pack("<Q", self.sdk.exports["nvnBootstrapLoader"]))
            assert at >= 0 and at % 8 == 0, "main's slot for nvnBootstrapLoader wasn't found"
            slot = start + at
            p.write(slot, struct.pack("<Q", self.sdk.exports["sdk_other_hook"]))
        for m in (added if order == "core-first" else added[::-1]):
            if m.init:
                p.call(m.init)

    def game(self, name, *args, **kw):
        return self.p.call(self.main.exports[name], *args, **kw)

    def sdk_int(self, name):
        return struct.unpack("<i", self.p.read(self.sdk.exports[name], 4))[0]

    def set_controller(self, buttons, lx=0, ly=0, rx=0, ry=0):
        self.p.write(self.sdk.exports["sdk_buttons"], struct.pack("<Q", buttons))
        for name, v in (("sdk_lx", lx), ("sdk_ly", ly), ("sdk_rx", rx), ("sdk_ry", ry)):
            self.p.write(self.sdk.exports[name], struct.pack("<i", v))

    def states(self, controller):
        """[(buttons, lx, ly, rx, ry)] the game was handed for player 1 (0) or the handheld (1)."""
        count = struct.unpack("<i", self.p.read(self.main.exports["game_state_count"] + 4 * controller, 4))[0]
        raw = self.p.read(self.main.exports["game_states"] + controller * 4 * 0x28, count * 0x28)
        return [struct.unpack_from("<Qiiii", raw, 8 + i * 0x28) for i in range(count)]

    def rects(self):
        count = self.sdk_int("sdk_rect_count")
        raw = self.p.read(self.sdk.exports["sdk_rects"], count * 20)
        return [struct.unpack_from("<iiiiI", raw, i * 20) for i in range(count)]

    def frame(self, actor=0xABC000, style_set=1):
        self.game("game_poll", style_set)
        self.game("game_read_motion")
        d10 = 0x400921FB54442D18
        self.game("game_move", actor, d10=d10)
        assert self.p.uc.reg_read(emu.UC_ARM64_REG_D10) == d10, "the movement update lost d10"
        self.game("game_present", 0)

    def logged(self, part):
        return [line for line in self.p.log if part in line]

    def expect(self, *parts):
        for part in parts:
            assert self.logged(part), f"no log line with {part!r}. The log:\n  " + "\n  ".join(self.p.log)


LAST_LOG = []
HELLO = REPO / "api" / "examples" / "hello"
PROBE = HERE / "probe"


def check_full_run(g, style_set=1):
    """Hello and the probe mod on a known game with everything in place."""
    p = g.p
    assert not p.unresolved, p.unresolved
    g.expect("kaepora: Core 0.2 loaded, game 1.1.1, main at 0x8052f000", "hook point in place: Actor.MoveUpdate")
    assert not g.logged("started"), "a mod started before the game ran"
    g.game("game_boot")
    g.expect("kaepora: mod kaepora.hello 0.2.0 started", "kaepora: mod kaepora.test-probe 1.2.3 started")
    base = MAIN_BASE
    g.expect(f"kaepora [kaepora.test-probe]: start: api 2 game 1.1.1 build {PACK['build']} base {base:#x}",
             f"start: sym {base + 0x6B2530:#x} alias {base + 0x6B2530:#x} vtable {base + 0x4B25E18:#x} field 796 unknown 0x0 -1",
             "start: has 1111110", "start: alloc 1 readable 10", "start: subscribed 0 0 0 0",
             "kaepora [kaepora.hello]: hello from its own start. Core API 0.2, game 1.1.1",
             "event.actor_move: yes", f"CctChangePosition at {base + 0x6B2530:#x}, Actor.position at +0x31c")
    A, B, X, Y = 1, 2, 4, 8
    g.set_controller(A | B | Y, lx=1000, ly=2000, rx=-3000, ry=4000)
    for _ in range(3):
        g.frame(style_set=style_set)
    # input: the probe hid B, pressed X because A is held, and took the left stick, in every state
    for controller in (0, 1):
        states = g.states(controller)
        assert len(states) == 3 and all(s == (A | X | Y, 111, -222, -3000, 4000) for s in states), states
    g.set_controller(B)
    g.game("game_poll", style_set)
    assert g.states(0)[0] == (0, 111, -222, 0, 0), g.states(0)
    # the movement update still did its own work, and the mods saw the actor
    assert struct.unpack("<Qi", p.read(g.main.exports["game_moved_actor"], 12)) == (0xABC000, 3)
    # drawing: hello's two squares, then the probe's (priority 10), flipped for a lower-left origin
    unit = 720 // 90
    assert g.rects() == [(unit * 2 - 2, 720 - (unit * 2 - 2) - (unit * 3 + 4), unit * 3 + 4, unit * 3 + 4, 0x000000),
                         (unit * 2, 720 - unit * 2 - unit * 3, unit * 3, unit * 3, 0x40E060),   # green: A was held
                         (10, 720 - 20 - 40, 30, 40, 0x112233), (0, 0, 15, 20, 0xFFFFFF)], g.rects()
    assert g.sdk_int("sdk_presents") == 3 and g.sdk_int("sdk_submits") == 3
    # one frame per poll (the probe counts them), two controller reads per poll
    g.expect("report: frames 3 inputs 6 moves 3 draws 3 actor 0xabc000 size 1280x720",
             "report: motion 3 0.5 8.5 mouse 1 640,360")
    g.expect("kaepora [kaepora.hello]: alive: 1 frames, 0 controller reads, 0 actor moves")
    LAST_LOG[:] = p.log


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fakes = build_fakes(tmp)
        mods = [kaemod.Mod(HELLO), kaemod.Mod(PROBE)]
        separate = kaemod.build(mods, False, tmp / "separate")
        bundle = kaemod.build(mods, True, tmp / "bundle")
        assert sorted(separate) == ["exefs/E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348.ips", "exefs/subsdk1",
                                    "exefs/subsdk2", "exefs/subsdk3"]
        assert sorted(bundle) == ["exefs/E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348.ips", "exefs/subsdk1"]

        for files, how in ((separate, "each mod its own module"), (bundle, "mods linked into Core's module")):
            for order in ("core-first", "core-last"):
                for lazy in (True, False):
                    g = Game(fakes, files, order=order, lazy=lazy)
                    check_full_run(g)
                    started = [line.split()[2] for line in g.logged(" started")]
                    if files is separate:   # mods start in the order their modules registered
                        assert started == (["kaepora.hello", "kaepora.test-probe"] if order == "core-first"
                                           else ["kaepora.test-probe", "kaepora.hello"]), started
            print(f"{how}: ok (Core started first or last, main's imports bound or not)")

        g = Game(fakes, separate, sdk="old-sdk")
        # the fake main imports the missing ones too (and never calls them); Core's are weak
        assert {m for m, _ in g.p.unresolved} == {"main"}, g.p.unresolved
        g.p.unresolved.clear()
        g.expect("input: 3 of 5 controller styles hooked, frames from GetNpadStates")
        check_full_run(g, style_set=0)
        print("a system without three of the hoped-for functions: ok (those styles unhooked, frames from the states)")

        g = Game(fakes, separate, patched=False)
        g.expect("hook points off: main isn't patched")
        g.game("game_boot")
        g.expect("event.actor_move: no", "start: has 1110110", "start: subscribed 0 0 -3 0",
                 "mod kaepora.hello 0.2.0 started", "mod kaepora.test-probe 1.2.3 started")
        for _ in range(3):
            g.frame()
        g.expect("report: frames 3 inputs 6 moves 0 draws 3")
        print("without Core's patch to main: ok (actor_move off, everything else on)")

        g = Game(fakes, separate, lazy=False, other_hook=True)
        check_full_run(g)
        assert g.sdk_int("sdk_other_hook_calls") > 0
        print("another module's hook already on main's import: ok (Core calls it on)")

        g = Game(fakes, separate, with_core=False, lazy=False)   # nothing wraps main's imports here
        assert g.p.unresolved == [], g.p.unresolved      # a mod's imports from Core are all weak
        assert len(g.logged("Kaepora Core isn't loaded")) == 2
        g.game("game_boot")
        for _ in range(2):
            g.frame()
        assert g.sdk_int("sdk_presents") == 2 and g.rects() == []
        print("mods without Core: ok (they say so and do nothing)")

        other = build_fakes(tmp, nnmain=PACK["detect"]["nnmain"] + 0x40)
        g = Game(other, separate, order="core-last", patched=False, lazy=False)
        g.expect("Core 0.2: unknown game build, doing nothing",
                 "mod kaepora.hello 0.2.0 is off: this build of the game isn't known to Core",
                 "mod kaepora.test-probe 1.2.3 is off: this build of the game isn't known to Core")
        g.game("game_boot")
        g.set_controller(3)
        for _ in range(2):
            g.frame()
        assert g.states(0)[0][0] == 3 and g.rects() == [] and not g.logged("start:")
        g = Game(other, bundle, patched=False, lazy=False)
        g.expect("unknown game build", "mod kaepora.hello 0.2.0 is off", "mod kaepora.test-probe 1.2.3 is off")
        print("a game build Core doesn't know: ok (nothing hooked, each mod reported off)")
        # Mouse Grab, the first real mod on Core: it loads, starts, draws its cursor at the (fake) mouse
        # and gets every actor's movement update. Grabbing itself needs the game.
        grab = kaemod.Mod(REPO / "mods" / "mouse-grab")
        for bundled in (True, False):
            g = Game(fakes, kaemod.build([kaemod.Mod(HELLO), grab], bundled, tmp / f"grab-{bundled}"))
            g.p.uc.mem_map(0x40000000, 0x10000)          # an actor that isn't Link: zeroed memory
            g.game("game_boot")
            g.expect("kaepora [kabosune.mouse-grab]: mouse grab: build", "mod kabosune.mouse-grab 0.2.0 started",
                     "mod kaepora.hello 0.2.0 started")
            for _ in range(3):
                g.frame(actor=0x40000000)
            rects = g.rects()
            assert len(rects) > 20 and (640, 720 - 360 - 1, 1, 1, 0) in rects, rects[:6]   # the arrow's tip
            assert not g.p.unresolved, g.p.unresolved
        print("Mouse Grab on Core, bundled and as its own module: ok (starts, draws its cursor, sees actors)")
    if "--log" in sys.argv:
        print("\nThe log of the last full run:\n  " + "\n  ".join(LAST_LOG))
    print("all module tests passed")


if __name__ == "__main__":
    main()
