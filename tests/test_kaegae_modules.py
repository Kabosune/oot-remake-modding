"""KaeGae Core and core mods, end to end, without the game: the modules are built exactly as
they ship (tools/kaemod.py), loaded and linked by a small stand-in for the game's rtld, and run
in Unicorn against a fake game and a fake system module (tests/kaegae/).

    python3 tests/test_kaegae_modules.py

What this can show: Core's own logic on real AArch64 code, the module format, and that mods work
as their own modules or linked into Core's, whichever module starts first. What it can't show is
how the real rtld, emulator or console behave: that takes the in-game test in api/README.md.

Needs clang, ld.lld, llvm-nm, llvm-objcopy, Python 3.11+ and Unicorn 2. No game files.
"""
import math
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HERE = REPO / "tests" / "kaegae"
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))
import emu  # noqa: E402
import kaemod  # noqa: E402
import kaegae_font  # noqa: E402
import kaegae_symbols  # noqa: E402

PACKS = {pack["version"]: pack for pack in kaegae_symbols.load_packs()}
PACK = PACKS["1.1.1"]      # the fake game's version: main() runs every test once per version (sets this)
CORE_VERSION = kaemod.core_version()
MAIN_BASE, SDK_BASE, CORE_BASE, MOD_BASE = 0x8052F000, 0x70000000, 0x90000000, 0x91000000
VIEW_LEAD = 0x168          # fake_main_view.S: from the start of view_update to its hook point site
FAKE_FLAGS = ["--target=aarch64-none-elf", "-O1", "-fPIC", "-ffreestanding", "-fno-builtin", "-fvisibility=hidden",
              "-fno-stack-protector", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-Wall", "-Wextra",
              "-Werror", "-std=c11"]
MAIN_LD = """
PHDRS {{ code PT_LOAD FLAGS(5); view PT_LOAD FLAGS(5); nnmain PT_LOAD FLAGS(5); move PT_LOAD FLAGS(5); ro PT_LOAD FLAGS(4);
        rw PT_LOAD FLAGS(6); dyn PT_DYNAMIC; }}
SECTIONS {{
  . = 0;
  .text : {{ KEEP(*(.text.header)) *(.text .text.*) }} :code
  .plt  : {{ *(.plt .plt.*) }} :code
  . = {view:#x};
  .text_view : {{ KEEP(*(.text_view)) }} :view
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


def build_fakes(work, nnmain=None, pack=None):
    """The fake main (with nnMain where the pack says, or elsewhere) and the two fake sdk modules,
    laid out as the pack's game build (its hook point sites, nnMain and MOD0 where the pack says)."""
    pack = pack or PACK
    work.mkdir(parents=True, exist_ok=True)
    objs = []
    for src in (kaemod.CORE / "crt0.S", HERE / "fake_main.c", HERE / "fake_main_move.S", HERE / "fake_main_view.S"):
        obj = work / (src.name + ".o")
        run("clang", *FAKE_FLAGS, "-c", src, "-o", obj)
        objs.append(obj)
    script = work / "main.ld"
    script.write_text(MAIN_LD.format(nnmain=nnmain or pack["detect"]["nnmain"], mod0=pack["detect"]["mod0"],
                                     view=pack["hookpoint"]["Camera.View"]["site"] - VIEW_LEAD,
                                     move=pack["hookpoint"]["Actor.MoveUpdate"]["site"] - 4))
    main = work / "main.elf"
    run("ld.lld", "-shared", "-Bsymbolic", "--hash-style=both", "-z", "norelro", "-z", "max-page-size=4096",
        "-T", script, "-o", main, *objs)
    sdks = {}
    for name, flags in (("sdk", []), ("old-sdk", ["-DOLD_SDK"])):
        obj, libc = work / f"{name}.o", work / f"{name}-libc.o"
        run("clang", *FAKE_FLAGS, *flags, "-c", HERE / "fake_sdk.c", "-o", obj)
        run("clang", *FAKE_FLAGS, *flags, "-c", HERE / "fake_libc.c", "-o", libc)
        elf = work / f"{name}.elf"
        run("ld.lld", "-shared", "-Bsymbolic", "--hash-style=both", "--build-id=sha1", "-z", "norelro",
            "-z", "max-page-size=4096", "-T", kaemod.CORE / "module.ld", "-o", elf, objs[0], obj, libc)
        sdks[name] = elf.read_bytes()
    return main.read_bytes(), sdks


def fake_pouch(pack):
    """{module offset: code} for the fake pouch functions at the pack's offsets (0.9): PouchEquip
    (returns 7 when it runs; its second instruction is the real one's, Core's hook point),
    PouchIsEquipped (1 for a name starting with "E"), PouchUnequip (stores the name's first 8
    bytes at pouch+0x200), and a caller inside the hook point's menu range."""
    ret = 0xD65F03C0
    equip = pack["function"]["PouchEquip"]["offset"]
    menu = int(pack["hookpoint"]["Pouch.Equip"]["menu"].split("..")[0], 16)
    bl = 0x94000000 | (((equip - (menu + 4)) >> 2) & 0x3FFFFFF)
    return {
        equip: (0xD503237F, 0xD10603FF, 0x910603FF, 0x528000E0, 0xD50323FF, ret),   # pacibsp, sub/add sp, mov w0 #7, autibsp
        pack["function"]["PouchIsEquipped"]["offset"]: (0xF9400028, 0x39400108, 0x7101151F, 0x1A9F17E0, ret),
        pack["function"]["PouchUnequip"]["offset"]: (0xF9400028, 0xF9400109, 0xF9010009, ret),
        menu: (0xA9BF7BFD, bl, 0xA8C17BFD, ret),                                       # stp, bl PouchEquip, ldp, ret
    }


def write_fake_pouch(p, pack):
    for offset, words in fake_pouch(pack).items():
        p.write(MAIN_BASE + offset, struct.pack(f"<{len(words)}I", *words))


def apply_ips(p, ips, build=kaemod.HOOK_BUILD_ID):
    """Core's patch to main, checking that it replaces the instruction it expects to."""
    _, records = kaemod.hook_patch(build=build)
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
                 other_hook=False, pack=None):
        pack = pack or PACK
        main_elf, sdks = fakes
        p = self.p = emu.Process()
        self.main = p.load("main", MAIN_BASE, emu.elf_segments(main_elf), size=pack["detect"]["size"])
        write_fake_pouch(p, pack)
        if patched:
            apply_ips(p, files[f"exefs/{pack['build']}.ips"], pack["build"])
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


def sdk_rect_total(g):
    """Every rectangle Core drew in the newest frame (sdk_rects keeps only the first 1024)."""
    return g.sdk_int("sdk_rect_count")


def check_full_run(g, style_set=1):
    """Hello and the probe mod on a known game with everything in place."""
    p = g.p
    assert not p.unresolved, p.unresolved
    g.expect(f"kaegae: Core {CORE_VERSION} loaded, game {PACK['version']}, main at 0x8052f000", "hook point in place: Actor.MoveUpdate")
    assert not g.logged("started"), "a mod started before the game ran"
    g.game("game_boot")
    g.expect("kaegae: mod kaegae.hello 0.5.0 started", "kaegae: mod kaegae.test-probe 1.2.3 started")
    base = MAIN_BASE
    sym, vtable = base + PACK["function"]["CctChangePosition"]["offset"], base + PACK["vtable"]["Actor"]["offset"]
    alias = sym if PACK["version"] == "1.1.1" else 0     # the probe asks for 1.1.1's alias, f_806d2530: aliases are per build
    g.expect(f"kaegae [kaegae.test-probe]: start: api {kaemod.api_version()[1]} game {PACK['version']} build {PACK['build']} base {base:#x}",
             f"start: sym {sym:#x} alias {alias:#x} vtable {vtable:#x} field 796 unknown 0x0 -1",
             "start: has 1111110", "start: alloc 1 readable 10", "start: subscribed 0 0 0 0",
             f"kaegae [kaegae.hello]: hello from its own start. Core API 0.{kaemod.api_version()[1]}, game {PACK['version']}",
             "event.actor_move: yes", f"CctChangePosition at {sym:#x}, Actor.position at +0x31c")
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
    rects = g.rects()
    assert rects[:2] == [(unit * 2 - 2, 720 - (unit * 2 - 2) - (unit * 3 + 4), unit * 3 + 4, unit * 3 + 4, 0x000000),
                         (unit * 2, 720 - unit * 2 - unit * 3, unit * 3, unit * 3, 0x40E060)], rects[:2]   # green: A was held
    assert rects[-2:] == [(10, 720 - 20 - 40, 30, 40, 0x112233), (0, 0, 15, 20, 0xFFFFFF)], (len(rects), rects[-2:])
    assert g.sdk_int("sdk_overruns") == 0
    # between them hello's text plate, its text (f"KaeGae Core 0.{kaemod.api_version()[1]}: A is held", white, at its
    # default size 2) and its picture
    text_x, text_y, size, chars = unit * 7, unit * 2, 2, len(f"KaeGae Core 0.{kaemod.api_version()[1]}: A is held")
    plate, text = rects[2], [r for r in rects[3:-2] if r[4] == 0xFFFFFF and r[0] < text_x + chars * 8 * size]
    assert plate[4] == 0x101820 and plate[0] == text_x - 4 and plate[1] == 720 - (text_y - 4) - plate[3], plate
    assert all(text_x <= r[0] and r[0] + r[2] <= text_x + chars * 8 * size and
               text_y <= 720 - r[1] - r[3] and 720 - r[1] <= text_y + 16 * size for r in text), "text outside its line"
    # the first glyph's cell, painted from the rectangles (flipped back), is the font's "K"
    cell = [[0] * 8 for _ in range(16)]
    for x, y, w, h, _ in text:
        for yy in range(720 - y - h, 720 - y):
            for xx in range(x, x + w):
                if text_x <= xx < text_x + 8 * size:
                    cell[(yy - text_y) // size][(xx - text_x) // size] = 1
    assert [sum(bit << (7 - i) for i, bit in enumerate(row)) for row in cell] == kaegae_font.read_bdf()[ord("K")]
    picture = [r for r in rects[3:-2] if r[4] in (0xFFD040,) ]
    assert len(text) > 60 and len(picture) >= 6, (len(text), len(picture))
    assert g.sdk_int("sdk_presents") == 3 and g.sdk_int("sdk_submits") == 3
    # one frame per poll (the probe counts them), two controller reads per poll
    g.expect("report: frames 3 inputs 6 moves 3 draws 3 actor 0xabc000 size 1280x720",
             "report: motion 3 0.5 8.5 mouse 1 640,360")
    g.expect("kaegae [kaegae.hello]: alive: 1 frames, 0 controller reads, 0 actor moves")
    LAST_LOG[:] = p.log


# Core's patch, one per game build with a symbol pack (1.0.0 and 1.1.1)
IPS = sorted(f"exefs/{build}.ips" for build in kaemod.hook_builds())


def suite():
    assert len(IPS) == 2, IPS
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fakes = build_fakes(tmp)
        mods = [kaemod.Mod(HELLO), kaemod.Mod(PROBE)]
        separate = kaemod.build(mods, False, tmp / "separate")
        bundle = kaemod.build(mods, True, tmp / "bundle")
        assert sorted(separate) == [*IPS, "exefs/subsdk1",
                                    "exefs/subsdk2", "exefs/subsdk3"]
        assert sorted(bundle) == [*IPS, "exefs/subsdk1"]

        for files, how in ((separate, "each mod its own module"), (bundle, "mods linked into Core's module")):
            for order in ("core-first", "core-last"):
                for lazy in (True, False):
                    g = Game(fakes, files, order=order, lazy=lazy)
                    check_full_run(g)
                    started = [line.split()[2] for line in g.logged(" started")]
                    if files is separate:   # mods start in the order their modules registered
                        assert started == (["kaegae.hello", "kaegae.test-probe"] if order == "core-first"
                                           else ["kaegae.test-probe", "kaegae.hello"]), started
            print(f"{how}: ok (Core started first or last, main's imports bound or not)")

        # game version 1.0.0: the same modules on a fake main laid out as 1.0.0 (its pack's hook
        # point sites, nnMain and MOD0), patched with Core's 1.0.0 .ips
        old = PACKS["1.0.0"]
        g = Game(build_fakes(tmp / "v1.0.0", pack=old), separate, pack=old)
        assert not g.p.unresolved, g.p.unresolved
        g.expect(f"kaegae: Core {CORE_VERSION} loaded, game 1.0.0, main at 0x8052f000",
                 "hook point in place: Actor.MoveUpdate", "hook point in place: Camera.View")
        g.game("game_boot")
        sym, vt = MAIN_BASE + old["function"]["CctChangePosition"]["offset"], MAIN_BASE + old["vtable"]["Actor"]["offset"]
        g.expect("kaegae: mod kaegae.hello 0.5.0 started", "kaegae: mod kaegae.test-probe 1.2.3 started",
                 f"start: api {kaemod.api_version()[1]} game 1.0.0 build {old['build']} base {MAIN_BASE:#x}",
                 # the probe asks for 1.1.1's Hookshot-style alias, f_806d2530: those name an address,
                 # so they differ per build (1.0.0's is f_806f7730) and only plain names port
                 f"start: sym {sym:#x} alias 0x0 vtable {vt:#x} field 796 unknown 0x0 -1",
                 f"Core API 0.{kaemod.api_version()[1]}, game 1.0.0", f"CctChangePosition at {sym:#x}, Actor.position at +0x31c")
        g.frame(style_set=1)
        print("game version 1.0.0: ok (Core finds the build, both hook points in place, the same mods start)")

        g = Game(fakes, separate, sdk="old-sdk")
        # the fake main imports the missing ones too (and never calls them); Core's are weak
        assert {m for m, _ in g.p.unresolved} == {"main"}, g.p.unresolved
        g.p.unresolved.clear()
        g.expect("input: 3 of 5 controller styles hooked, frames from GetNpadStates")
        check_full_run(g, style_set=0)
        g.expect("settings off: the system's file functions weren't found")
        print("a system without three of the hoped-for functions: ok (those styles unhooked, frames from the states)")

        # a game whose heap won't give Core the larger drawing memory: Core takes the small amount.
        # With an NVN that reports free memory everything still fits; without, Core stops at the
        # number of rectangles it is sure of and never writes past its memory.
        for sdk, drawn in (("sdk", "all"), ("old-sdk", 128)):
            g = Game(fakes, separate, sdk=sdk)
            g.p.unresolved.clear()
            g.p.write(g.main.exports["game_heap_limit"], struct.pack("<Q", 0x100000))
            g.game("game_boot")
            g.set_controller(1)   # A held
            g.frame(style_set=1 if sdk == "sdk" else 0)
            g.expect("the game's heap is short, taking the small amount of memory", "drawing ready")
            count = g.sdk_int("sdk_rect_count")
            assert g.sdk_int("sdk_overruns") == 0 and (count > 128 if drawn == "all" else count == 128), count
            assert bool(g.logged("out of command memory")) == (drawn != "all")
        print("a game short of memory: ok (small drawing memory; rectangles past it are left out, nothing overruns)")

        # the Mods menu: - and + together open it; while it is open the game sees no buttons, the
        # menu is drawn over the mods' drawing, and X switches the selected mod off
        g = Game(fakes, separate)
        g.game("game_boot")
        MINUS, PLUS, X_BUTTON, B_BUTTON = 1 << 11, 1 << 10, 1 << 2, 1 << 1

        def frames(buttons, count=1):
            g.set_controller(buttons)
            for _ in range(count):
                g.frame()
            return g.states(0)[-1][0]
        frames(0, 2)
        before = g.sdk_int("sdk_rect_count")
        assert frames(MINUS | PLUS, 3) == 0 and g.logged("Mods menu opened")
        assert frames(0, 2) == 0
        opened = g.rects()
        assert len(opened) > before + 100, (before, len(opened))            # the panel and its text
        panel = [r for r in opened if r[4] == 0x16211C]
        assert panel and panel[0][2] == 1260 * 720 // 1080, panel[:1]
        assert frames(1, 2) == 0, "the game saw A while the menu was open"   # A opens the first mod's page
        frames(0, 2)
        frames(B_BUTTON, 1)
        frames(0, 2)
        frames(X_BUTTON, 1)                                                  # back in the list: switch Hello off
        frames(0, 2)
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        assert g.logged("Mods menu closed")
        closed = g.rects()
        assert not [r for r in closed if r[4] == 0x101820], "Hello still draws after being switched off"
        assert (10, 720 - 20 - 40, 30, 40, 0x112233) in closed               # the probe is still on
        assert frames(1, 2) & 1                                              # and the game has its buttons back
        print("the Mods menu: ok (opens on - and +, hides input from the game, switches a mod off)")

        # a lone + (the game's own pause menu) reaches the game as one press, never two: its
        # first frame used to slip through before the menu held it back, then came again
        def game_presses(sequence, button=PLUS):
            held, presses = 0, 0
            for buttons in sequence:
                now = frames(buttons) & button
                presses += bool(now and not held)
                held = now
            return presses
        frames(0, 3)
        assert game_presses([PLUS] * 8 + [0] * 4) == 1, "a held + reached the game twice"
        assert game_presses([PLUS] * 2 + [0] * 4) == 1, "a tapped + reached the game twice"
        assert game_presses([MINUS] * 8 + [0] * 4, MINUS) == 1, "a held - reached the game twice"
        assert game_presses([MINUS | PLUS] * 3 + [0] * 3, MINUS | PLUS) == 0, "the chord reached the game"
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        print("a lone + or -: ok (one press for the game, the chord's first frame hidden too)")

        # Instant + (Core 0.8.3, on Core's own page): a lone + reaches the game on its first frame;
        # - held first, then +, still opens the menu, and the game sees neither
        saved_g = g
        g = Game(fakes, separate)
        text = "[kaegae.core]\nInstant + = 1\n"
        g.p.write(g.sdk.exports["sdk_file"], text.encode())
        g.p.write(g.sdk.exports["sdk_file_len"], struct.pack("<i", len(text)))
        g.game("game_boot")
        frames(0, 3)
        assert frames(PLUS) & PLUS, "Instant +: the first frame of + was held back"
        assert frames(PLUS, 6) & PLUS and frames(0) == 0
        frames(0, 3)
        assert game_presses([PLUS] * 2 + [0] * 4) == 1, "Instant +: a tapped + reached the game twice"
        assert game_presses([MINUS] * 2 + [MINUS | PLUS] * 3 + [0] * 3, MINUS | PLUS) == 0, "Instant +: the chord reached the game"
        assert g.logged("Mods menu opened")
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        assert g.logged("Mods menu closed")
        g = saved_g
        print("Instant +: ok (+ reaches the game at once; - then + still opens the Mods menu)")

        # settings kept between runs: the menu's close wrote the file on the (fake) SD card
        def sd_file(g):
            n = g.sdk_int("sdk_file_len")
            return g.p.read(g.sdk.exports["sdk_file"], n).decode() if n >= 0 else None
        saved = sd_file(g)
        assert saved and "[kaegae.hello]\n(on) = 0\n" in saved and "Text size = 2\n" in saved, saved
        assert "Flash the diamond = 0x10\n" in saved and "Write a line" not in saved, saved   # actions aren't saved
        assert "[kaegae.test-probe]\n(on) = 1\n" in saved, saved
        assert g.sdk_int("sdk_auto_abort") == 1, "Core left nn::fs auto-abort off"
        g.expect("settings: no file yet", "settings: saved to kaegae/settings.txt")
        writes = g.sdk_int("sdk_writes")
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        assert g.sdk_int("sdk_writes") == writes, "the file was written again with nothing changed"

        # the next run: the file is read on the first frame, before anything is drawn
        g = Game(fakes, separate)
        text = ("# by hand\n[kaegae.hello]\r\n(on) = 0\nText size = 9\nText colour = 1\nFlash the diamond = 0x3\n"
                "Show the square = nonsense\n\n[someone.else]\nx = 1\n")
        g.p.write(g.sdk.exports["sdk_file"], text.encode())
        g.p.write(g.sdk.exports["sdk_file_len"], struct.pack("<i", len(text)))
        g.game("game_boot")
        frames(0, 3)
        g.expect("settings: 4 loaded from kaegae/settings.txt")
        assert not [r for r in g.rects() if r[4] == 0x101820], "Hello draws although the file switched it off"
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        frames(X_BUTTON, 1)   # switch Hello back on
        frames(0, 2)
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        saved = sd_file(g)
        assert "[kaegae.hello]\n(on) = 1\n" in saved, saved
        assert "Text size = 4\n" in saved and "Text colour = 1\n" in saved and "Flash the diamond = 0x3\n" in saved, saved
        assert "Show the square = 1\n" in saved, saved                       # a bad value leaves the default
        assert "[someone.else]\nx = 1\n" in saved, saved                     # a mod that isn't installed keeps its lines
        assert g.sdk_int("sdk_auto_abort") == 1
        print("settings between runs: ok (written when the menu closes after a change, read on the first frame, "
              "values clamped, other mods' lines kept)")

        g = Game(fakes, separate)
        g.p.write(g.sdk.exports["sdk_mount_result"], struct.pack("<i", 0x7D402))
        g.game("game_boot")
        frames(0, 2)
        g.expect("settings off: the SD card couldn't be opened (result 0x7d402)")
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        assert sd_file(g) is None and g.sdk_int("sdk_auto_abort") == 1
        print("settings with no SD card: ok (off, said once, the menu works)")

        g = Game(fakes, separate, patched=False)
        g.expect("hook point Actor.MoveUpdate off: main isn't patched")
        g.game("game_boot")
        g.expect("event.actor_move: no", "start: has 1110110", "start: subscribed 0 0 -3 0",
                 "mod kaegae.hello 0.5.0 started", "mod kaegae.test-probe 1.2.3 started")
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
        assert len(g.logged("KaeGae Core isn't loaded")) == 2
        g.game("game_boot")
        for _ in range(2):
            g.frame()
        assert g.sdk_int("sdk_presents") == 2 and g.rects() == []
        print("mods without Core: ok (they say so and do nothing)")

        other = build_fakes(tmp, nnmain=PACK["detect"]["nnmain"] + 0x40)
        g = Game(other, separate, order="core-last", patched=False, lazy=False)
        g.expect(f"Core {CORE_VERSION}: unknown game build, doing nothing",
                 "mod kaegae.hello 0.5.0 is off: this build of the game isn't known to Core",
                 "mod kaegae.test-probe 1.2.3 is off: this build of the game isn't known to Core")
        g.game("game_boot")
        g.set_controller(3)
        for _ in range(2):
            g.frame()
        assert g.states(0)[0][0] == 3 and g.rects() == [] and not g.logged("start:")
        g = Game(other, bundle, patched=False, lazy=False)
        g.expect("unknown game build", "mod kaegae.hello 0.5.0 is off", "mod kaegae.test-probe 1.2.3 is off")
        print("a game build Core doesn't know: ok (nothing hooked, each mod reported off)")
        # Mouse Grab, the first real mod on Core: it loads, starts, draws its cursor at the (fake) mouse
        # and gets every actor's movement update. Grabbing itself needs the game.
        grab = kaemod.Mod(REPO / "mods" / "mouse-grab")
        for bundled in (True, False):
            g = Game(fakes, kaemod.build([kaemod.Mod(HELLO), grab], bundled, tmp / f"grab-{bundled}"))
            g.p.uc.mem_map(0x40000000, 0x10000)          # an actor that isn't Link: zeroed memory
            g.game("game_boot")
            g.expect(f"kaegae [kabosune.mouse-grab]: mouse grab {grab.manifest['version']} on game {PACK['version']} (KaeGae Core's names)",
                     f"mod kabosune.mouse-grab {grab.manifest['version']} started",
                     "mod kaegae.hello 0.5.0 started")
            for _ in range(3):
                g.frame(actor=0x40000000)
            rects = g.rects()
            assert len(rects) > 20 and (640, 720 - 360 - 1, 1, 1, 0) in rects, rects[:6]   # the arrow's tip
            assert not g.p.unresolved, g.p.unresolved
            assert not g.logged("  actor: "), "Mouse Grab's research log is on by default"
            for buttons in (MINUS | PLUS, 0, MINUS | PLUS, 0):   # open and close the Mods menu: the close writes the file
                g.set_controller(buttons)
                for _ in range(3):
                    g.frame(actor=0x40000000)
            saved = sd_file(g)
            assert "[kabosune.mouse-grab]\n(on) = 1\nGyro depth speed = 100\n" in saved and "Debug log = 0\n" in saved, saved
        print("Mouse Grab on Core, bundled and as its own module: ok (finds all its names, starts, draws its cursor, sees actors, "
              "has its settings page)")
        # mods built for API 0.5 and released before 0.6, unchanged, on this Core (0.6 and later run them):
        # tests/kaegae/old-mods holds the zips as they were released
        old = {}
        for zip_name, slot in (("slopped-up-sloperina-0.2.1-api0.5.zip", "subsdk2"), ("mouse-grab-0.2.0-api0.5.zip", "subsdk3")):
            with zipfile.ZipFile(HERE / "old-mods" / zip_name) as z:
                (module,) = [n for n in z.namelist() if "/exefs/subsdk" in n]
                assert 'api = "0.5"' in z.read(next(n for n in z.namelist() if n.endswith("mod.toml"))).decode()
                old[f"exefs/{slot}"] = z.read(module)
        core_only = kaemod.build([], False, tmp / "core-only")
        g = Game(fakes, {**core_only, **old})
        g.p.uc.mem_map(0x40000000, 0x10000)
        g.game("game_boot")
        for _ in range(3):
            g.frame(actor=0x40000000)
        g.expect(f"Core {CORE_VERSION} loaded", "mod kabosune.slopped-up-sloperina 0.2.1 started", "mod kabosune.mouse-grab 0.2.0 started")
        assert not g.logged(" is off"), g.logged(" is off")
        print("mods built for API 0.5 on Core 0.8: ok (the released Slopped Up Sloperina and Mouse Grab start)")

        # keys (0.7): bindings get a keyboard key in the Mods menu, kept in the settings file. A 0.7 mod
        # reads them with kae_binding_held / kae_binding_pressed; for older mods (Hello, 0.5) Core adds
        # the binding's buttons to their input while its key is held, and keeps them from the game.
        keys_files = kaemod.build([kaemod.Mod(HELLO), kaemod.Mod(HERE / "keys-test")], False, tmp / "keys")
        F5, SPACE, ZR, L3 = 62, 44, 1 << 9, 1 << 4

        def set_keys(*codes):
            words = [0, 0, 0, 0]
            for code in codes:
                words[code >> 6] |= 1 << (code & 63)
            g.p.write(g.sdk.exports["sdk_keys"], struct.pack("<4Q", *words))

        def keyboard():
            return g.sdk_int("sdk_keyboard_inits"), g.sdk_int("sdk_keyboard_early_reads")

        def keys_line():
            return [line.split("keys: ")[1] for line in g.logged("keys: held")][-1]

        def diamond_area():
            return sum(r[2] * r[3] for r in g.rects() if r[4] == 0xFFD040)

        def with_file(text):
            game = Game(fakes, keys_files)
            game.p.write(game.sdk.exports["sdk_file"], text.encode())
            game.p.write(game.sdk.exports["sdk_file_len"], struct.pack("<i", len(text)))
            return game

        g = Game(fakes, keys_files)
        g.game("game_boot")
        frames(0, 3)
        assert keyboard() == (0, 0), keyboard()                       # no key bound: never set up or read
        assert keys_line() == "held 0 presses 0 saw 0x0 keyboard 1", keys_line()
        frames(ZR)
        assert keys_line().startswith("held 1 presses 1"), keys_line()  # the controller, as before
        frames(ZR, 2)
        assert keys_line().startswith("held 1 presses 1"), keys_line()  # one press, however long it's held
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        assert keyboard() == (1, 0), keyboard()                       # the open menu reads keys: set up first
        assert keys_line().startswith("held 0"), keys_line()          # nothing is held while it's open
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        saved = sd_file(g)
        assert "[kaegae.core]\n(on) = 1\nKeyboard = 1\n" in saved and "(key)" not in saved, saved

        g = with_file("[kaegae.hello]\nFlash the diamond (key) = F5\n[kaegae.keys-test]\nJump (key) = space\n")
        g.game("game_boot")
        frames(0, 2)
        g.expect("settings: 2 loaded")
        small = diamond_area()
        set_keys(F5)
        assert not frames(0) & L3, "the game saw the buttons of a key"
        assert diamond_area() > small, "Hello didn't get L3 for its key"
        set_keys()
        frames(0)
        assert diamond_area() == small
        set_keys(SPACE)
        assert not frames(0) & ZR
        line = keys_line()
        assert line.startswith("held 1 presses 1") and "saw 0x0" in keys_line(), line   # held by its key; no buttons
        set_keys(SPACE, F5)
        frames(0, 2)                                                  # (the mod logs the last frame's input)
        assert keys_line().startswith("held 1 presses 1"), keys_line()
        assert keys_line().split()[5] == hex(L3), keys_line()         # other mods see an older mod's buttons
        set_keys()
        frames(0)
        set_keys(SPACE)
        frames(0)
        assert keys_line().startswith("held 1 presses 2"), keys_line()
        assert keyboard() == (1, 0), keyboard()
        set_keys()
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        saved = sd_file(g)
        assert "Flash the diamond = 0x10\nFlash the diamond (key) = F5\n" in saved, saved
        assert "Jump = 0x200\nJump (key) = Space\n" in saved, saved

        g = with_file("[kaegae.core]\nKeyboard = 0\n[kaegae.keys-test]\nJump (key) = Space\n")   # switched off
        g.game("game_boot")
        set_keys(SPACE)
        frames(0, 3)
        assert keys_line() == "held 0 presses 0 saw 0x0 keyboard 0", keys_line()
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        assert keyboard() == (0, 0), keyboard()                       # never set up, even with the menu open

        g = Game(fakes, keys_files, sdk="old-sdk")
        g.p.unresolved.clear()
        g.game("game_boot")
        g.expect("keyboard: the system has no keyboard functions")
        g.frame(style_set=0)
        assert keys_line().endswith("keyboard 0"), keys_line()
        print("keys: ok (none bound: never read; the menu sets the keyboard up before reading; 0.7 mods hold and "
              "press by key; older mods get their buttons, the game doesn't; saved as \"(key)\" lines; the switch)")
        # Core's player_move event under the player test mod (Slopped Up Sloperina 0.2, the first mod
        # written against the public API only). A Link is built in memory the way the game lays him out (actor -> components
        # -> movement inside the player object, whose resource is "Player"; components -> ... ->
        # character controller -> body), and main gets stand-ins: ChangePosition copies the position
        # it is given into the controller at +0x100, BodySetLinearVelocity the velocity into the
        # body at +0x200.
        sloperina = kaemod.Mod(HERE / "player-test")
        g = Game(fakes, kaemod.build([kaemod.Mod(HELLO), sloperina], False, tmp / "sloperina"))
        LINK, COMPONENTS, C1, C2, C3, CCT, RESOURCE, BODY, PLAYER = (0x40000000 + i * 0x1000 for i in range(9))
        MOVEMENT = PLAYER + 0x1D50
        g.p.uc.mem_map(0x40000000, 0x10000)
        for at, value in ((LINK, MAIN_BASE + PACK["vtable"]["Actor"]["offset"]), (LINK + 0x270, COMPONENTS),
                          (COMPONENTS + 0x320, MOVEMENT), (MOVEMENT + 0x18, LINK),
                          (PLAYER, MAIN_BASE + PACK["vtable"]["Player"]["offset"]), (PLAYER + 0x10, RESOURCE),
                          (COMPONENTS + 0x50, C1), (C1 + 0x20, C2), (C2 + 0x10, C3), (C3 + 0x08, CCT),
                          (CCT, MAIN_BASE + PACK["vtable"]["Cct"]["offset"]), (CCT + 0x20, BODY),
                          (BODY, MAIN_BASE + PACK["vtable"]["CctBody"]["offset"])):
            g.p.write(at, struct.pack("<Q", value))
        g.p.write(RESOURCE + 0x58, b"Player\0")
        # ldr q0, [x1] ; str q0, [x0, #0x100] ; ret
        g.p.write(MAIN_BASE + PACK["function"]["CctChangePosition"]["offset"], struct.pack("<3I", 0x3DC00020, 0x3D804000, 0xD65F03C0))
        # ldr q0, [x1] ; str q0, [x0, #0x200] ; ret
        g.p.write(MAIN_BASE + PACK["function"]["BodySetLinearVelocity"]["offset"], struct.pack("<3I", 0x3DC00020, 0x3D808000, 0xD65F03C0))
        position = LINK + PACK["field"]["Actor.position"]["offset"]
        velocity = BODY + PACK["field"]["CctBody.velocity"]["offset"]
        set_velocity = lambda: struct.unpack("<3f", g.p.read(BODY + 0x200, 12))      # noqa: E731

        def link_frame(buttons, at=None):
            if at:
                g.p.write(position, struct.pack("<3f", *at))
            g.set_controller(buttons)
            g.frame(actor=LINK)
            return g.states(0)[-1][0], struct.unpack("<3f", g.p.read(CCT + 0x100, 12))
        L, LEFT, UP, RIGHT = 1 << 6, 1 << 12, 1 << 13, 1 << 14
        g.game("game_boot")
        g.expect("mod kaegae.player-test 1.0.0 started")
        assert link_frame(0, (1.0, 2.0, 3.0)) == (0, (0.0, 0.0, 0.0))               # nothing asked: Link isn't moved
        assert link_frame(L | LEFT)[0] == 0, "the game saw the save combination"    # saved at (1, 2, 3)
        link_frame(0, (50.0, 60.0, 70.0))
        seen, moved = link_frame(L | RIGHT)
        assert seen == 0 and moved == (1.0, 2.0, 3.0), (seen, moved)                # loaded
        seen, moved = link_frame(L | UP, (5.0, 6.0, 7.0))
        assert seen == 0 and moved[0] == 5.0 and abs(moved[1] - 6.1) < 1e-5 and moved[2] == 7.0, moved   # levitate: 10 cm
        assert set_velocity() == (0.0, 0.0, 0.0)                                    # he wasn't falling
        g.p.write(velocity, struct.pack("<3f", 1.5, -9.0, 2.5))                     # falling while walking
        link_frame(L | UP)
        assert set_velocity() == (1.5, 0.0, 2.5), set_velocity()                    # the fall is gone, the walk stays
        g.p.write(velocity, struct.pack("<3f", 1.5, 4.0, 2.5))                      # rising: left alone
        link_frame(L | UP)
        assert set_velocity() == (1.5, 4.0, 2.5), set_velocity()
        g.p.write(BODY + 0x200, bytes(12))
        link_frame(0)
        assert set_velocity() == (0.0, 0.0, 0.0)                                    # not levitating: velocity untouched
        g.expect("levitate: holding Link's falling speed at zero")
        g.p.write(CCT + 0x20, struct.pack("<Q", 0))                                 # a Link whose body isn't found
        seen, moved = link_frame(L | UP, (5.0, 6.0, 7.0))
        assert abs(moved[1] - 6.1) < 1e-5 and set_velocity() == (0.0, 0.0, 0.0), moved   # still lifted, nothing called
        g.expect("levitate: Link's velocity is out of reach here")
        g.p.write(CCT + 0x20, struct.pack("<Q", BODY))
        assert link_frame(1)[0] & 1                                                 # other buttons reach the game
        g.frame(actor=0xABC000)                                                     # an actor that isn't Link
        hud = [r for r in g.rects() if r[4] == 0x101820 and r[0] == 720 // 45]
        assert len(hud) == 1 and hud[0][1] == 720 // 45, hud                        # bottom left (origin lower left)
        assert not g.p.unresolved, g.p.unresolved
        print("player_move: ok (Core finds Link, the test mod saves / loads his position, levitates without falling, hides its combinations, draws its display)")

        # Slopped Up Sloperina: sloperinaGZ's code as a Core mod. The fake game has nothing in it (no
        # GameData, no Link), so this shows that the module loads and links, finds the 1.1.1 build from
        # nnMain, runs its frames on Core's frame event, opens its menu with R + right stick down, draws
        # it through Core, hides the controller from the game while it's open, and closes it again.
        slopped = kaemod.Mod(REPO / "mods" / "slopped-up-sloperina")
        g = Game(fakes, kaemod.build([slopped], False, tmp / "slopped"))
        g.game("game_boot")
        g.expect(f"mod kabosune.slopped-up-sloperina {slopped.manifest['version']} started", f"sloperinaGZ 0.0.4.2 on game {PACK['version']}")
        A, R, RS_DOWN = 1 << 0, 1 << 7, 1 << 23
        BACKGROUND = 0x181820

        def slopped_frame(buttons):
            g.set_controller(buttons)
            g.frame()
            return g.states(0)[-1][0], [r for r in g.rects() if r[4] == BACKGROUND]
        for _ in range(3):
            slopped_frame(0)
        g.expect(f"running on game {PACK['version']} (on KaeGae Core")
        assert slopped_frame(A)[0] & A                                               # menu closed: the game sees A
        slopped_frame(R | RS_DOWN)                                                   # gz's combination opens the menu
        seen, panels = slopped_frame(0)
        menu = [r for r in panels if r[0] == 1280 * 35 // 1000]
        assert menu and menu[0][3] > 100, panels                                     # the menu's panel, under the D-pad
        assert sdk_rect_total(g) > 200, sdk_rect_total(g)                            # ... with its text
        assert [r for r in g.rects() if r[4] == 0xE0E0E0], "no button prompts (key caps) under the menu"
        assert slopped_frame(A)[0] == 0, "the game saw A while the menu was open"
        slopped_frame(R | RS_DOWN)                                                   # the same again closes it
        slopped_frame(0)
        seen, panels = slopped_frame(A)
        assert seen & A and not [r for r in panels if r[0] == 1280 * 35 // 1000], panels
        assert not g.p.unresolved, g.p.unresolved
        print(f"Slopped Up Sloperina: ok (starts on {PACK['version']}, opens and draws its menu through Core, hides the controller "
              f"from the game while it's open; {sdk_rect_total(g)} rectangles in its last frame)")

        # its shortcuts are bindings on Core's page (0.4.0): saved with their buttons, and with a key
        # from the settings file F1 opens its menu, Backspace closes it (fixed keys inside the menu)
        text = "[kabosune.slopped-up-sloperina]\nOpen / close the menu (key) = F1\nSave position (key) = F5\n"
        g = Game(fakes, kaemod.build([slopped], False, tmp / "slopped"))
        g.p.write(g.sdk.exports["sdk_file"], text.encode())
        g.p.write(g.sdk.exports["sdk_file_len"], struct.pack("<i", len(text)))
        g.game("game_boot")
        for _ in range(3):
            slopped_frame(0)
        g.expect("settings: 2 loaded")
        F1, BACKSPACE = 58, 42

        def press_key(code):
            g.p.write(g.sdk.exports["sdk_keys"], struct.pack("<4Q", *[(1 << (code & 63)) if i == code >> 6 else 0 for i in range(4)]))
            seen, panels = slopped_frame(0)
            g.p.write(g.sdk.exports["sdk_keys"], bytes(32))
            slopped_frame(0)
            return seen, [r for r in g.rects() if r[4] == BACKGROUND and r[0] == 1280 * 35 // 1000]
        seen, menu = press_key(F1)
        assert menu, "F1 didn't open the menu"
        assert slopped_frame(A)[0] == 0, "the game saw A while the menu was open"
        seen, menu = press_key(BACKSPACE)
        assert not menu, "Backspace didn't close the menu at its top level"
        assert slopped_frame(A)[0] & A
        assert g.sdk_int("sdk_keyboard_early_reads") == 0
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        frames(MINUS | PLUS, 3)
        frames(0, 3)
        saved = sd_file(g)
        assert "Open / close the menu = 0x800080\nOpen / close the menu (key) = F1\n" in saved, saved
        assert "Save position = 0x2080\nSave position (key) = F5\n" in saved and "Watches: show / hide = 0x4080\n" in saved, saved
        print("Slopped Up Sloperina's shortcuts on Core's page: ok (saved with their buttons and keys; F1 opens its menu, "
              "Backspace closes it)")
        # The showcase mods: Moon Jump, Speedometer and Drunk Mode, three modules next to Core, on the
        # same Link as above.
        showcase = [kaemod.Mod(REPO / "mods" / name) for name in ("moon-jump", "speedometer", "drunk-mode")]
        g = Game(fakes, kaemod.build(showcase, False, tmp / "showcase"))
        g.p.uc.mem_map(0x40000000, 0x10000)
        for at, value in ((LINK, MAIN_BASE + PACK["vtable"]["Actor"]["offset"]), (LINK + 0x270, COMPONENTS),
                          (COMPONENTS + 0x320, MOVEMENT), (MOVEMENT + 0x18, LINK),
                          (PLAYER, MAIN_BASE + PACK["vtable"]["Player"]["offset"]), (PLAYER + 0x10, RESOURCE),
                          (COMPONENTS + 0x50, C1), (C1 + 0x20, C2), (C2 + 0x10, C3), (C3 + 0x08, CCT),
                          (CCT, MAIN_BASE + PACK["vtable"]["Cct"]["offset"]), (CCT + 0x20, BODY),
                          (BODY, MAIN_BASE + PACK["vtable"]["CctBody"]["offset"])):
            g.p.write(at, struct.pack("<Q", value))
        g.p.write(RESOURCE + 0x58, b"Player\0")
        g.p.write(MAIN_BASE + PACK["function"]["CctChangePosition"]["offset"], struct.pack("<3I", 0x3DC00020, 0x3D804000, 0xD65F03C0))
        g.p.write(MAIN_BASE + PACK["function"]["BodySetLinearVelocity"]["offset"], struct.pack("<3I", 0x3DC00020, 0x3D808000, 0xD65F03C0))
        g.game("game_boot")
        g.expect("mod kabosune.moon-jump 0.1.0 started", "mod kabosune.speedometer 0.1.0 started",
                 "mod kabosune.drunk-mode 0.1.0 started")
        UNSET = (123.0, 456.0, 789.0)

        def step(v, at=(0.0, 0.0, 0.0), buttons=0, lx=0, ly=0):
            g.p.write(BODY + 0x200, struct.pack("<3f", *UNSET))
            g.p.write(velocity, struct.pack("<3f", *v))
            g.p.write(position, struct.pack("<3f", *at))
            g.set_controller(buttons, lx, ly)
            g.frame(actor=LINK)
            return set_velocity(), g.states(0)[-1]
        close = lambda a, b: all(abs(x - y) < 1e-4 for x, y in zip(a, b))     # noqa: E731
        # Moon Jump, gravity 40 %: the first update only looks; after that a drop of 1 m/s becomes 0.4
        assert step((1.0, -1.0, 2.0))[0] == UNSET
        assert close(step((1.0, -2.0, 2.0))[0], (1.0, -1.4, 2.0)), set_velocity()
        # a jump's kick (more than 2 m/s up in one update) is boosted 130 %
        assert close(step((1.0, 5.0, 2.0))[0], (1.0, 6.5, 2.0)), set_velocity()
        # a rise that isn't a kick passes through untouched
        assert step((1.0, 7.0, 2.0))[0] == UNSET
        # hold L + A: he flies up at 6 m/s and the game doesn't see the combination
        L, A = 1 << 6, 1 << 0
        moved, seen = step((1.0, -3.0, 2.0), buttons=L | A)
        assert close(moved, (1.0, 6.0, 2.0)) and seen[0] == 0, (moved, seen)
        print("Moon Jump: ok (lower gravity, boosted jump kick, moon jump hides its combination)")
        # Drunk Mode, wobble 40 %: a pushed stick is turned but keeps its length; a centred one stays
        # centred; buttons other than the moon jump's pass through
        turned = []
        for _ in range(40):
            seen = step((0.0, 0.0, 0.0), lx=0, ly=20000, buttons=A)[1]
            assert seen[0] == A and abs((seen[1] ** 2 + seen[2] ** 2) ** 0.5 - 20000) < 40, seen
            turned.append(seen[1])
        assert max(abs(x) for x in turned) > 1000, turned
        assert step((0.0, 0.0, 0.0))[1][1:3] == (0, 0)
        print("Drunk Mode: ok (the stick wobbles and keeps its length, a centred stick stays centred)")
        # Speedometer: 0.2 m an update along the ground is 6 m/s; the display sits bottom right
        for i in range(30):
            step((0.0, 0.0, 0.0), at=(0.2 * i, 0.0, 0.0))
        g.frame(actor=0xABC000)
        plate = [r for r in g.rects() if r[4] == 0x101820]
        width = 14 * 8 * 2 + 2 * 12
        assert any(r[0] == 1280 - 720 // 45 - width and r[1] == 720 // 45 and r[2] == width for r in plate), plate
        assert any(r[4] != 0x101820 and r[4] != 0x2A3530 and r[3] == 16 for r in g.rects()), "no bar fill"
        assert not g.p.unresolved, g.p.unresolved
        print("Speedometer: ok (measures Link's speed, draws its display bottom right with a filled bar)")

        # World Tools (0.1.1): a fake WorldMgr behind the pack's names. Its state object answers the
        # time (13:25) and the weather (2) through its vtable; the fake setters store their arguments
        # in the WorldMgr, so the test can read what the mod asked for.
        world = kaemod.Mod(REPO / "mods" / "world-tools")
        g = Game(fakes, kaemod.build([world], False, tmp / "world"))
        WM, STATE, VT, CODE = 0x42000000, 0x42001000, 0x42002000, 0x42003000
        g.p.uc.mem_map(WM, 0x4000)
        ret = 0xD65F03C0
        code = struct.pack("<8I", 0xB9400800, ret, 0xB9400C00, ret, 0, 0, 0, 0)       # ldr w0, [x0, #8] / #12
        g.p.write(CODE, code)
        g.p.write(MAIN_BASE + PACK["global"]["WorldMgrPtr"]["offset"], struct.pack("<Q", WM))
        g.p.write(WM + PACK["field"]["WorldMgr.state"]["offset"], struct.pack("<Q", STATE))
        g.p.write(STATE, struct.pack("<QII", VT, 13 * 3600 + 25 * 60 + 7, 2))
        g.p.write(VT + PACK["field"]["WorldState.time_slot"]["offset"], struct.pack("<Q", CODE))
        g.p.write(VT + PACK["field"]["WorldState.weather_slot"]["offset"], struct.pack("<Q", CODE + 8))
        for name, words in (("WmSetTime", (0xB9010001, ret)),                                  # str w1, [x0, #0x100]
                            ("WmSetWeather", (0xF9400021, 0xF9008401, 0xB9011002, ret)),       # the name, the speed
                            ("WmSetWind", (0xB9011801, 0xBD011C00, 0xBD012001, 0xBD012402, ret)),
                            ("WmResetWeather", (0xB9012801, ret)), ("WmResetWind", (0xB9012C01, ret))):
            g.p.write(MAIN_BASE + PACK["function"][name]["offset"], struct.pack(f"<{len(words)}I", *words))
        text = "[kabosune.world-tools]\nJump to night = 0x1\nOne hour later = 0x2\nShow weather number = 1\n"
        g.p.write(g.sdk.exports["sdk_file"], text.encode())
        g.p.write(g.sdk.exports["sdk_file_len"], struct.pack("<i", len(text)))
        g.game("game_boot")
        g.expect("mod kabosune.world-tools 0.1.1 started", f"world tools 0.1.1: clock, time of day, weather, wind (game {PACK['version']})")
        set_time = lambda: struct.unpack("<i", g.p.read(WM + 0x100, 4))[0]               # noqa: E731
        g.p.write(WM + 0x100, struct.pack("<i", -5))
        for _ in range(3):
            g.set_controller(0)
            g.frame()
        g.expect("world tools: WorldMgr at")
        assert set_time() == -5, "the time was set without asking"
        # the clock, top right: "13:25  weather 2" at size 2 on its plate (the recorded rectangles
        # count y from the bottom, as Speedometer's check above shows)
        label = "13:25  weather 2"
        width, height = len(label) * 8 * 2 + 2 * 8, 16 * 2 + 2 * 8
        plate = [r for r in g.rects() if r[4] == 0x101820]
        assert any(r[0] == 1280 - 720 // 45 - width and r[1] == 720 - 720 // 45 - height and r[2] == width
                   and r[3] == height for r in plate), plate
        # Jump to night (A): 0:00; One hour later (B): 14:25 from the reported 13:25
        g.set_controller(1 << 0)
        g.frame()
        assert set_time() == 0, set_time()
        g.set_controller(0)
        g.frame()
        g.set_controller(1 << 1)
        g.frame()
        assert set_time() == 14 * 3600 + 25 * 60 + 7, set_time()
        g.expect("world tools: time set to 0:00", "world tools: time set to 14:25")
        assert not g.p.unresolved, g.p.unresolved
        print("World Tools: ok (reads the time and weather through the state's vtable, draws the clock top right, "
              "Jump to night and One hour later call WmSetTime)")

        # World Tools' Keep after loading (0.1.1): Set weather (Rain) from its Mods menu page, then a new
        # area (WorldMgr gets a new state object, which reports clear weather): a second later the
        # mod sets Rain again, and again when its check still sees the wrong weather number. With the
        # setting off, a new area changes nothing.
        def world_game(keep):
            g = Game(fakes, kaemod.build([world], False, tmp / f"world-keep-{keep}"))
            g.p.uc.mem_map(WM, 0x8000)
            g.p.write(CODE, code)
            g.p.write(MAIN_BASE + PACK["global"]["WorldMgrPtr"]["offset"], struct.pack("<Q", WM))
            g.p.write(WM + PACK["field"]["WorldMgr.state"]["offset"], struct.pack("<Q", STATE))
            g.p.write(STATE, struct.pack("<QII", VT, 13 * 3600, 0))
            g.p.write(VT + PACK["field"]["WorldState.time_slot"]["offset"], struct.pack("<Q", CODE))
            g.p.write(VT + PACK["field"]["WorldState.weather_slot"]["offset"], struct.pack("<Q", CODE + 8))
            for name, words in (("WmSetTime", (0xB9010001, ret)), ("WmSetWeather", (0xF9400021, 0xF9008401, 0xB9011002, ret)),
                                ("WmSetWind", (0xB9011801, 0xBD011C00, 0xBD012001, 0xBD012402, ret)),
                                ("WmResetWeather", (0xB9012801, ret)), ("WmResetWind", (0xB9012C01, ret))):
                g.p.write(MAIN_BASE + PACK["function"][name]["offset"], struct.pack(f"<{len(words)}I", *words))
            text = f"[kabosune.world-tools]\nKeep after loading = {keep}\n"
            g.p.write(g.sdk.exports["sdk_file"], text.encode())
            g.p.write(g.sdk.exports["sdk_file_len"], struct.pack("<i", len(text)))
            g.game("game_boot")
            return g
        MINUS, PLUS, A_BUTTON, DOWN = 1 << 11, 1 << 10, 1 << 0, 1 << 15
        for keep in (1, 0):
            g = world_game(keep)

            def frames(buttons, count=1):
                g.set_controller(buttons)
                for _ in range(count):
                    g.frame()
            frames(0, 3)
            frames(MINUS | PLUS, 3)
            frames(0, 2)
            frames(A_BUTTON)                       # the first page: World Tools
            frames(0, 2)
            for _ in range(12):                    # down to Set weather (Weather's default: Rain)
                frames(DOWN)
                frames(0, 2)
            frames(A_BUTTON)
            frames(0, 2)
            frames(MINUS | PLUS, 3)
            frames(0, 3)
            weather_sets = lambda: len(g.logged("world tools: weather set to Rainy"))   # noqa: E731
            assert weather_sets() == 1, g.p.log[-10:]
            g.p.write(WM + 0x108, struct.pack("<Q", 0))
            g.p.write(STATE + 0x1000, struct.pack("<QII", VT, 14 * 3600, 0))        # the new area's state: clear
            g.p.write(WM + PACK["field"]["WorldMgr.state"]["offset"], struct.pack("<Q", STATE + 0x1000))
            frames(0, 59)
            assert weather_sets() == 1, "Keep after loading set the weather before the area settled"
            frames(0, 2)
            if keep:
                g.expect("world tools: new area: setting the chosen weather and wind again")
                assert weather_sets() == 2
                name = struct.unpack("<Q", g.p.read(WM + 0x108, 8))[0]
                assert g.p.read(name, 6) == b"Rainy\0"
                frames(0, 61)
                g.expect("world tools: the area changed the weather (0): setting it again")
                assert weather_sets() == 3
            else:
                frames(0, 120)
                assert weather_sets() == 1 and not g.logged("new area"), "Keep after loading is off, but the mod set the weather"
        print("World Tools' Keep after loading: ok (a new state object = a new area: Rain set again after a second, "
              "and again when the weather number is wrong; nothing with the setting off)")

        # the pouch_equip event (0.9): the fake PouchEquip (7 = it ran) called from the fake menu
        # caller and from outside it; the test mod takes an item picked again in the menu off
        g = Game(fakes, kaemod.build([kaemod.Mod(HERE / "pouch-test")], False, tmp / "pouch"))
        POUCH = 0x43000000
        g.p.uc.mem_map(POUCH, 0x1000)
        g.p.write(MAIN_BASE + PACK["global"]["PouchMgrPtr"]["offset"], struct.pack("<Q", POUCH))
        g.game("game_boot")
        g.expect("hook point in place: Pouch.Equip", "pouch: has 1 1")
        equip_at = MAIN_BASE + PACK["function"]["PouchEquip"]["offset"]
        menu_at = MAIN_BASE + int(PACK["hookpoint"]["Pouch.Equip"]["menu"].split("..")[0], 16)

        def equip(fn, text):
            g.p.write(POUCH + 0x500, text.encode() + b"\0")
            g.p.write(POUCH + 0x400, struct.pack("<Qi", POUCH + 0x500, 0x40))
            return g.p.call(fn, POUCH, POUCH + 0x400, 3, 0)

        assert equip(menu_at, "Equip_Sword") == POUCH, "picked again in the menu: the game's equip should be skipped"
        assert g.p.read(POUCH + 0x200, 8) == b"Equip_Sw", "the mod's kae_pouch_unequip didn't reach PouchUnequip"
        assert equip(equip_at, "Equip_Sword") == 7, "the game's own call (not the menu) must go ahead"
        assert equip(menu_at, "Weapon_Bow") == 7, "a new item picked in the menu must be equipped"
        g.expect("pouch: Equip_Sword menu 1 equipped 1 mode 3 handled 0", "pouch: unequip 0, still equipped 1",
                 "pouch: Equip_Sword menu 0 equipped 1 mode 3", "pouch: Weapon_Bow menu 1 equipped 0")
        assert not g.p.unresolved, g.p.unresolved
        print("pouch_equip: ok (menu vs game calls told apart, a handled equip is skipped, kae_pouch_unequip reaches the game)")

        # Equip Anything 1.0 (0.9): a fake pause-menu table behind PouchMgrPtr (one page, two
        # buttons: the Kokiri Tunic's, with one item only for a child and one only for an adult,
        # and one with an adult-only item); the mod opens an item to an age only where its button
        # has no item of that age's own (1.0.1), puts them back when switched off, and takes an
        # item picked again off
        equip_mod = kaemod.Mod(REPO / "mods" / "equip-anything")
        g = Game(fakes, kaemod.build([equip_mod], False, tmp / "equip"))
        F = PACK["field"]
        POUCH, UI, TABLE, BUTTON, ITEMS, NAMES = (0x44000000 + i * 0x1000 for i in range(6))
        BUTTON2 = BUTTON + 0x400
        g.p.uc.mem_map(POUCH, 0x6000)
        g.p.write(MAIN_BASE + PACK["global"]["PouchMgrPtr"]["offset"], struct.pack("<Q", POUCH))
        g.p.write(POUCH + F["PouchMgr.ui"]["offset"], struct.pack("<Q", UI))
        g.p.write(UI + F["PouchUi.table"]["offset"], struct.pack("<Q", TABLE))
        page = TABLE + F["PouchTable.pages"]["offset"]                      # the first page
        g.p.write(page, struct.pack("<QIIQ", 0, 2, 2, TABLE + 0x800))         # count 2, elements at +0x800
        g.p.write(TABLE + 0x800, struct.pack("<QQ", BUTTON, BUTTON2))
        g.p.write(BUTTON + F["PouchButton.items"]["offset"], struct.pack("<QIIQ", 0, 2, 2, BUTTON + 0x800))
        g.p.write(BUTTON + 0x800, struct.pack("<QQ", ITEMS, ITEMS + 0x100))
        g.p.write(BUTTON2 + F["PouchButton.items"]["offset"], struct.pack("<QIIQ", 0, 1, 1, BUTTON2 + 0x200))
        g.p.write(BUTTON2 + 0x200, struct.pack("<Q", ITEMS + 0x200))
        child_at, adult_at = F["PouchItem.usable_child"]["offset"], F["PouchItem.usable_adult"]["offset"]
        for n, (name, child, adult) in enumerate((("Obj_Armor_Child_Normal", 1, 0), ("Armor_Adult_Normal", 0, 1),
                                                  ("Weapon_Sword_Master", 0, 1))):
            g.p.write(NAMES + n * 0x40, name.encode() + b"\0")
            g.p.write(ITEMS + n * 0x100 + F["PouchItem.name"]["offset"], struct.pack("<Q", NAMES + n * 0x40))
            g.p.write(ITEMS + n * 0x100 + child_at, bytes((child, adult, 0, child, adult)))   # values, then "set here"
        flags = lambda n: tuple(g.p.read(ITEMS + n * 0x100 + child_at, 5))   # noqa: E731
        g.game("game_boot")
        g.expect("equip anything 1.0.1", "any age ready", "take off ready")
        g.set_controller(0)
        g.frame()
        assert flags(0) == (1, 0, 0, 1, 0) and flags(1) == (0, 1, 0, 0, 1), \
            ("the Kokiri Tunic's button has an item for each age: leave it alone", flags(0), flags(1))
        assert flags(2) == (1, 1, 0, 1, 1), ("an adult-only button: open to a child", flags(2))
        g.expect("equip anything: every age can use 1 more items")
        # picked again in the menu: taken off (the fake unequip stores the name at pouch+0x200), skipped
        g.p.write(NAMES + 0x200, b"Equip_Shield\0")
        g.p.write(NAMES + 0x300, struct.pack("<Qi", NAMES + 0x200, 0x40))
        menu_at = MAIN_BASE + int(PACK["hookpoint"]["Pouch.Equip"]["menu"].split("..")[0], 16)
        assert g.p.call(menu_at, POUCH, NAMES + 0x300, 3, 0) == POUCH
        assert g.p.read(POUCH + 0x200, 8) == b"Equip_Sh"
        g.expect("equip anything: took off Equip_Shield (0)")
        assert not g.p.unresolved, g.p.unresolved
        print("Equip Anything: ok (items opened to the ages their button lacks, the Kokiri Tunic's pair left alone, an item picked again taken off)")
        # Adventure Log: reads the game's play log (1.1.1 only) through main's recorder pointer
        check_adventure_log(fakes, tmp)

        # the view event (0.8) and the two mods on it: First Person 2 and FPV Drone 2. The fake view
        # update fills the registers, passes Core's hook point and stores them: they must come back.
        cams = [kaemod.Mod(REPO / "mods" / "first-person" / "core"), kaemod.Mod(REPO / "mods" / "fpv-drone" / "core")]
        cam_files = kaemod.build(cams, False, tmp / "cams")
        VIEW, CAMERA, MGR, CAMERAS, CAM0, CELL, OUT = (0x41000000 + i * 0x1000 for i in range(7))
        TAN25, ASPECT = 0.46630765815, 16 / 9
        R3, L3, A_, L_, ZR_ = 1 << 5, 1 << 4, 1 << 0, 1 << 6, 1 << 9

        def camera_game(text=None):
            g = Game(fakes, cam_files)
            if text:
                g.p.write(g.sdk.exports["sdk_file"], text.encode())
                g.p.write(g.sdk.exports["sdk_file_len"], struct.pack("<i", len(text)))
            g.p.uc.mem_map(0x40000000, 0x10000)
            g.p.uc.mem_map(0x41000000, 0x10000)
            for at, value in ((LINK, MAIN_BASE + PACK["vtable"]["Actor"]["offset"]), (LINK + 0x270, COMPONENTS),
                              (COMPONENTS + 0x320, MOVEMENT), (MOVEMENT + 0x18, LINK),
                              (PLAYER, MAIN_BASE + PACK["vtable"]["Player"]["offset"]), (PLAYER + 0x10, RESOURCE),
                              (COMPONENTS + 0x50, C1), (C1 + 0x20, C2), (C2 + 0x10, C3), (C3 + 0x08, CCT),
                              (CCT, MAIN_BASE + PACK["vtable"]["Cct"]["offset"]), (CCT + 0x20, BODY),
                              (BODY, MAIN_BASE + PACK["vtable"]["CctBody"]["offset"]),
                              (COMPONENTS + 0x260, BODY + 0x400),                         # his model
                              (VIEW, MAIN_BASE + PACK["vtable"]["View"]["offset"]), (CAMERA + 0x20, 1),
                              (MAIN_BASE + PACK["global"]["CameraManagerSlot"]["offset"], CELL), (CELL, MGR),
                              (MGR + 0x20, 1), (MGR + 0x28, CAMERAS), (CAMERAS, CAM0), (CAM0 + 0x78, VIEW)):
                g.p.write(at, struct.pack("<Q", value))
            g.p.write(RESOURCE + 0x58, b"Player\0")
            g.p.write(BODY + 0x400 + 0xE5, b"\1")                                      # visible
            g.p.write(MAIN_BASE + PACK["function"]["CctChangePosition"]["offset"], struct.pack("<3I", 0x3DC00020, 0x3D804000, 0xD65F03C0))
            g.game("game_boot")
            return g

        def set_view(g, eye=(0.0, 1.0, 10.0), look=(0.0, 3.68, 5.0)):
            # looking along -z: right (1, 0, 0), up (0, 1, 0), back (0, 0, 1); t = -(row . eye)
            m = (1, 0, 0, -eye[0], 0, 1, 0, -eye[1], 0, 0, 1, -eye[2])
            g.p.write(VIEW + 0x08, struct.pack("<12f", *m))
            g.p.write(VIEW + 0x38, struct.pack("<6f", *eye, *look))
            g.p.write(VIEW + 0x98, b"\0\0")
            g.p.write(VIEW + 0x9C, struct.pack("<f", 1 / (TAN25 * ASPECT)))
            g.p.write(VIEW + 0xB0, struct.pack("<f", 1 / TAN25))
            g.p.write(VIEW + 0x130, struct.pack("<5f", 0.87266463, 0.42261826, 0.90630779, TAN25, ASPECT))
            g.p.write(CAMERA + 0x13C, struct.pack("<2f", 0.87266463, ASPECT))   # the camera's own: the game copies it later

        def cam_frame(g, buttons=0, at=(1.0, 2.0, 3.0), lx=0, ly=0, rx=0, ry=0):
            g.p.write(LINK + PACK["field"]["Actor.position"]["offset"], struct.pack("<3f", *at))
            g.set_controller(buttons, lx, ly, rx, ry)
            g.frame(actor=LINK)
            set_view(g)
            g.p.write(OUT, bytes(0xb0))
            g.game("game_view", CAMERA, VIEW, OUT)
            regs = struct.unpack("<16Q4d2Q", g.p.read(OUT, 0xb0))
            want = (0x1000, 0x1001, 0x1003, 0x1004, 0x1005, 0x1006, 0x1007, 0x1009, 0x100a, 0x100b, 0x100c, 0x100d,
                    0x100e, 0x100f, 0x1010, 0x1011, 1.0, 7.0, 16.0, 31.0, 1, 1)
            assert regs == want, f"the view hook point changed registers: {regs}"
            return struct.unpack("<12f", g.p.read(VIEW + 0x08, 48)), struct.unpack("<f", g.p.read(CAMERA + 0x13C, 4))[0]

        g = camera_game()
        g.expect("hook point in place: Camera.View", "mod kabosune.first-person 2.0.1 started",
                 "mod kabosune.fpv-drone 2.0.0 started", "first person 2.0.1 on Core: field of view can change")
        game_view = (1, 0, 0, 0, 0, 1, 0, -1, 0, 0, 1, -10)
        for _ in range(3):
            matrix, fovy = cam_frame(g)
            assert matrix == game_view and abs(fovy - 0.87266463) < 1e-6, (matrix, fovy)   # both mods off: untouched
        g.p.write(OUT, bytes(0xb0))
        g.game("game_view", CAMERA, VIEW + 0x800, OUT)                                   # another view: left alone
        matrix, fovy = cam_frame(g, R3)                                                  # R3: first person on
        close = lambda a, b: all(abs(x - y) < 1e-4 for x, y in zip(a, b))     # noqa: E731
        # eye = Link (1, 2, 3) + measured 1.68 up, 0.15 forward (along -back = -z)
        assert close(matrix, (1, 0, 0, -1, 0, 1, 0, -3.68, 0, 0, 1, -2.85)), matrix
        assert abs(fovy - 0.87266463) < 1e-6, fovy                                      # FOV "the game's"
        g.expect("first person on", "first person: eye height 1.68 m")
        assert g.p.read(BODY + 0x400 + 0xE5, 1) == b"\0", "Link wasn't hidden"
        cam_frame(g, rx=10000)
        assert g.states(0)[-1][3] == 10000                                               # look speed 100 %
        cam_frame(g, R3)                                                                 # off again
        assert cam_frame(g)[0] == game_view
        assert g.p.read(BODY + 0x400 + 0xE5, 1) == b"\1", "Link wasn't shown again"
        print("view event: ok (only the gameplay view, every register kept); First Person 2: ok (Link's eyes, hides him, R3 on / off)")

        # settings from the file: FOV 90 (index 3), eye 10 cm higher, look speed 200 %; and the drone
        g = camera_game("[kabosune.first-person]\nField of view = 3\nEye height (cm) = 10\nLook speed (%) = 50\n"
                        "[kabosune.fpv-drone]\nField of view = 5\nFree fly speed (m/s) = 20\n")
        cam_frame(g)
        matrix, fovy = cam_frame(g, R3)
        want_fovy = 2 * math.atan(math.tan(math.radians(45)) / ASPECT)
        assert close(matrix, (1, 0, 0, -1, 0, 1, 0, -3.78, 0, 0, 1, -2.85)), matrix
        assert abs(fovy - want_fovy) < 1e-4, (fovy, want_fovy)
        assert abs(struct.unpack("<f", g.p.read(VIEW + 0x130, 4))[0] - 0.87266463) < 1e-6     # the projection is the game's to fill
        cam_frame(g, rx=10000)
        assert g.states(0)[-1][3] == 5000                                                # look speed 50 %
        cam_frame(g, R3)
        # FPV Drone: L3 takes off from the view as it is, in Free fly; the game sees nothing
        cam_frame(g)
        matrix, fovy = cam_frame(g, L3)
        g.expect("fpv drone on")
        assert g.states(0)[-1][0] == 0, "the game saw L3 while the drone flies"
        assert close(matrix, game_view), matrix                                           # starts at the game camera
        assert abs(fovy - 2 * math.atan(math.tan(math.radians(55)) / ASPECT)) < 1e-4, fovy   # FOV 110
        for _ in range(5):
            matrix, _ = cam_frame(g, ZR_, ly=32767)                                       # forward and up
        seen = g.states(0)[-1]
        assert seen[0] == 0 and seen[1:] == (0, 0, 0, 0), seen
        eye = [-(matrix[i] * matrix[3] + matrix[4 + i] * matrix[7] + matrix[8 + i] * matrix[11]) for i in range(3)]
        assert eye[2] < 10 - 0.5 and eye[1] > 1.2 and abs(eye[0]) < 1e-3, eye            # moved along -z and up
        cam_frame(g, 1 << 7)                                                              # R: carry Link
        cam_frame(g)
        carried = struct.unpack("<3f", g.p.read(CCT + 0x100, 12))
        assert abs(carried[2] - (eye[2] + 1.0)) < 0.6 and abs(carried[1] - eye[1]) < 0.6, (carried, eye)
        cam_frame(g, L3)
        assert cam_frame(g, A_)[0] == game_view and g.states(0)[-1][0] & A_            # off: the game has it all back
        assert not g.p.unresolved, g.p.unresolved
        print("FPV Drone 2: ok (takes off from the view, free fly with its settings, FOV, carries Link, hides the controller)")
    if "--log" in sys.argv:
        print("\nThe log of the last full run:\n  " + "\n  ".join(LAST_LOG))
    print("all module tests passed")


def murmur3(text, seed=0):
    key, h, n = text.encode(), seed, len(text.encode())
    rot = lambda x, r: ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF      # noqa: E731
    for i in range(0, n // 4 * 4, 4):
        k = rot(int.from_bytes(key[i:i + 4], "little") * 0xCC9E2D51 & 0xFFFFFFFF, 15) * 0x1B873593 & 0xFFFFFFFF
        h = (rot(h ^ k, 13) * 5 + 0xE6546B64) & 0xFFFFFFFF
    if n % 4:
        h ^= rot(int.from_bytes(key[n // 4 * 4:], "little") * 0xCC9E2D51 & 0xFFFFFFFF, 15) * 0x1B873593 & 0xFFFFFFFF
    h ^= n
    h ^= h >> 16
    h = h * 0x85EBCA6B & 0xFFFFFFFF
    h ^= h >> 13
    h = h * 0xC2B2AE35 & 0xFFFFFFFF
    return h ^ (h >> 16)


def check_adventure_log(fakes, tmp):
    """Adventure Log next to Core: on 1.1.1 it follows the recorder main points to (entries of 24
    bytes, next slot and count at +0x6000) and logs and shows new entries by name; on 1.0.0 it
    does nothing."""
    import zlib
    g = Game(fakes, kaemod.build([kaemod.Mod(REPO / "mods" / "adventure-log")], False, tmp / "adventure-log"))
    g.game("game_boot")
    if PACK is not PACKS["1.1.1"]:
        g.frame()
        g.expect("only 1.1.1 does): doing nothing")
        print("Adventure Log: ok (does nothing on a game without the play log)")
        return
    g.expect("adventure log 0.3.1 on game 1.1.1")
    g.frame()                                       # no recorder yet: waits
    assert not g.logged("recorder is at")
    REC = 0x43000000
    g.p.uc.mem_map(REC, 0x7000)
    entry = lambda t, kind, a=0, b=0, v1=0, v2=0: struct.pack("<IIIIii", t, kind, a, b, v1, v2)  # noqa: E731
    stalchild, link = zlib.crc32(b"Enemy_Stalchild"), zlib.crc32(b"Player_Child")
    g.p.write(REC, entry(100, 3, link, stalchild, 2, 2) + entry(101, 37, stalchild))
    g.p.write(REC + 0x6000, struct.pack("<II", 2, 2))
    g.p.write(MAIN_BASE + 0x4E6B718, struct.pack("<Q", REC))
    g.frame()
    g.expect("recorder is at", "the game's log has 2 entries, next slot 2")
    assert not g.logged("kind 3 ")                  # what was there already isn't new
    # one new entry: an area change, the scene names are MurmurHash3
    g.p.write(REC + 2 * 24, entry(102, 25, murmur3("HyruleField_Child"), murmur3("Market_Child"), 7, 8))
    g.p.write(REC + 0x6000, struct.pack("<II", 3, 3))
    g.frame()
    g.expect("t=102 kind 25 (area change) HyruleField_Child Market_Child 7 8")
    # wrapping around the end of the 1,024 slots
    g.p.write(REC + 1023 * 24, entry(103, 11, zlib.crc32(b"Obj_Rupee_Green")))
    g.p.write(REC + 0, entry(104, 99, 0x12345678, zlib.crc32(b"Obj_Armor_Child_Normal")))   # an item name from main's strings
    g.p.write(REC + 0x6000, struct.pack("<II", 1023, 1024))
    g.frame()
    g.expect("1020 entries at once")                # a jump of ~1,000: read back from a save, not counted
    g.p.write(REC + 0x6000, struct.pack("<II", 1, 1024))
    g.frame()
    g.expect("t=103 kind 11 (picked up) Obj_Rupee_Green -", "t=104 kind 99 (?) 12345678 Obj_Armor_Child_Normal")
    plate = [r for r in g.rects() if r[4] == 0x101820]
    x, y, w, h, _ = plate[0]                         # the rectangles' origin is the lower left
    assert x == 1280 // 60 and y + h == 720 - 720 // 30 and w == 112 * 8 + 16, plate
    # the totals: a fake GameData manager with three Int64 fields (block at +0x850, records 0x30
    # apart, value at +0x20, a {hash, index} map with open addressing from hash % size)
    MGR, RECS, MAP = 0x44000000, 0x44010000, 0x44020000
    g.p.uc.mem_map(MGR, 0x30000)
    hashes = {0xA6454431: 10, 0x4AC3FF5D: 20, 0x2A24450A: 30}     # jumps, rolls, sword swings
    size, table = 7, [None] * 7
    for index, h in enumerate(hashes):
        i = h % size
        while table[i] is not None:
            i = (i + 1) % size
        table[i] = (h, index)
    g.p.write(MAP, b"".join(struct.pack("<II", *(e or (0, 0))) for e in table))

    def set_totals(values):
        for index, v in enumerate(values):
            g.p.write(RECS + index * 0x30, struct.pack("<Q", 0x4E000000))     # the records' class
            g.p.write(RECS + index * 0x30 + 0x20, struct.pack("<qq", v, v))
    set_totals((0, 0, 0))                           # the title screen: no file loaded yet
    g.p.write(MGR + 0x850, struct.pack("<I", 3))
    g.p.write(MGR + 0x858, struct.pack("<QQ", RECS, MAP))
    g.p.write(MGR + 0x86C, struct.pack("<I", size))
    g.p.write(MAIN_BASE + PACK["global"]["GameDataMgrPtr"]["offset"], struct.pack("<Q", MGR))
    for _ in range(10):
        g.frame()
    assert not g.logged("totals:"), "all-zero totals (the title screen) were taken as a reading"
    set_totals(hashes.values())
    for _ in range(10):
        g.frame()
    g.expect("totals: 10 jumps, 20 rolls, 30 sword swings")
    set_totals((14, 26, 35))                        # 4 jumps, 6 rolls, 5 swings
    for _ in range(10):
        g.frame()
    g.expect("jumps 14 (was 10)", "rolls 26 (was 20)", "sword swings 35 (was 30)")
    # a broken log (count over 1,024) is left alone
    g.p.write(REC + 0x6000, struct.pack("<II", 5, 5000))
    g.frame()
    g.expect("the log looks wrong")
    assert not g.p.unresolved, g.p.unresolved
    print("Adventure Log: ok (follows the game's log through main's pointer, names entries, wraps, "
          "skips a read-back, reads the jump / roll / swing totals from GameData, leaves a broken log alone)")


def main():
    """Every test once per game version: the fake game laid out as that version's build."""
    global PACK
    for version in ("1.1.1", "1.0.0"):
        PACK = PACKS[version]
        print(f"--- game version {version} ---")
        suite()


if __name__ == "__main__":
    main()
