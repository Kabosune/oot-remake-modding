"""Build exefs IPS32 patches for main from an assembly source.

The source is assembled with clang and linked with ld.lld at the cave address, against the
addresses in symbols/<build>.ld. Every hook site is checked against the original instruction,
in a real main if one is given, so a patch can't silently land on a different game build.

build() takes one assembly file and one cave. build_regions() takes several sources (.S or .c)
and spreads their sections over several free gaps of the cave, and can split the code of a C file
over the compiler's padding between functions (see split_into_slots), for mods that don't fit.

Needs: clang, ld.lld, llvm-objcopy, llvm-nm (LLVM 15+).
"""
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

BASE = 0x80020000          # module base used by every address in this repo (same as Hookshot)
NSO_HEADER_SIZE = 0x100    # Lichii / yuzu-style IPS offsets count the NSO header
TEXT_END = 0x3C461D0       # end of .text; the zero padding up to 0x3C47000 is executable
CAVE_LIMIT = 0x3C47000
REPO = Path(__file__).resolve().parent.parent


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def b_word(at, to):
    """b <to> placed at <at> (both addresses)"""
    delta = (to - at) // 4
    assert -(1 << 25) <= delta < (1 << 25), "branch out of range"
    return 0x14000000 | (delta & 0x3FFFFFF)


def assemble(source, symbols, cave, defines, workdir):
    """Assemble and link source at cave (module offset). Returns (code bytes, {symbol: address})."""
    workdir = Path(workdir)
    params = workdir / "params.inc"
    params.write_text("".join(f"#define {k} {v}\n" for k, v in defines.items()))
    obj, elf, binf = workdir / "cave.o", workdir / "cave.elf", workdir / "cave.bin"
    run("clang", "--target=aarch64-none-elf", "-march=armv8.2-a", "-c", "-x", "assembler-with-cpp",
        "-I", workdir, source, "-o", obj)
    script = workdir / "link.ld"
    script.write_text(f'INCLUDE "{Path(symbols).resolve()}"\n'
                      f"SECTIONS {{ . = {BASE + cave:#x}; .text : {{ *(.text) }} }}\n")
    run("ld.lld", "-e", "0", "-T", script, obj, "-o", elf)
    run("llvm-objcopy", "-O", "binary", "-j", ".text", elf, binf)
    nm = subprocess.run(["llvm-nm", str(elf)], check=True, capture_output=True, text=True).stdout
    syms = {}
    for line in nm.splitlines():
        parts = line.split()
        if len(parts) == 3:
            syms[parts[2]] = int(parts[0], 16)
    return binf.read_bytes(), syms


def build(source, symbols, cave, hooks, defines):
    """hooks: [(site address, original word, entry symbol)]. Returns [(module offset, bytes, original)]."""
    with tempfile.TemporaryDirectory() as tmp:
        code, syms = assemble(source, symbols, cave, defines, tmp)
    assert cave >= TEXT_END and cave + len(code) <= CAVE_LIMIT, f"cave overflows ({len(code)} bytes)"
    records = []
    for site, original, entry in hooks:
        records.append((site - BASE, struct.pack("<I", b_word(site, syms[entry])), struct.pack("<I", original)))
    records.append((cave, code, bytes(len(code))))
    return records, len(code)


C_FLAGS = ["-Oz", "-ffast-math", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
           "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-ffunction-sections",
           "-fdata-sections", "-mno-outline-atomics", "-std=c11", "-Wall", "-Werror"]


def load_slots(path):
    """Padding slots from a list like symbols/e0f3ccfa-slots.txt: [(address, length)]."""
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            a, n = line.split()
            out.append((int(a, 0), int(n)))
    return out


TERMINATORS = {"ret", "retab", "b", "br", "braa", "brab"}


def split_into_slots(asm, slots):
    """Spread the code of a clang -S listing over padding slots.

    Each slot holds whole instructions and, unless its last instruction already ends the flow
    (ret, b, br), a final `b` to the next slot. Data sections pass through unchanged. Labels stay
    on the instruction they belong to, so branches inside the code are resolved by the assembler
    and linker as usual: the slots must lie within the shortest branch range (tbz: 32 KB).
    Returns (new listing, number of slots used)."""
    out, pending = [], []
    state = {"slot": -1, "used": 0, "cap": 0, "last_term": True}

    def open_slot():
        if state["slot"] >= 0 and not state["last_term"]:
            out.append(f"\tb\t.Lslot_{state['slot'] + 1}")
        state["slot"] += 1
        assert state["slot"] < len(slots), f"code doesn't fit in {len(slots)} slots"
        state["used"], state["cap"], state["last_term"] = 0, slots[state["slot"]][1] // 4, True
        out.append(f'\t.section\t.text.slot.{state["slot"]},"ax",@progbits')
        out.append(f".Lslot_{state['slot']}:")

    in_code = False
    for raw in asm.splitlines():
        line = raw.split("//")[0].rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith((".section", ".text", ".data", ".bss")):
            name = stripped.split()[1].split(",")[0] if stripped.startswith(".section") else stripped.split()[0]
            in_code = name.startswith(".text")
            if not in_code:
                out.append(line)
            elif state["slot"] >= 0:   # back from data: carry on in the current slot
                out.append(f'\t.section\t.text.slot.{state["slot"]},"ax",@progbits')
            continue
        if not in_code:
            out.append(line)
            continue
        if stripped.endswith(":"):
            pending.append(stripped)
            continue
        if stripped.startswith("."):
            if stripped.startswith((".globl", ".type", ".hidden", ".local", ".weak")):
                out.append(line)
            continue   # .p2align, .size, .cfi_*: not meaningful once the code is split
        op = stripped.split()[0]
        term = op in TERMINATORS
        room = state["cap"] - state["used"]
        if state["slot"] < 0 or not (room >= 2 or (room == 1 and term)):
            open_slot()
        out.extend(pending)
        pending = []
        out.append("\t" + stripped)
        state["used"] += 1
        state["last_term"] = term
    if pending:   # end-of-function labels after the last instruction
        out.append(f'\t.section\t.text.slot.{state["slot"]},"ax",@progbits')
        out.extend(pending)
    assert state["last_term"], "the code must not fall off the end of its last slot"
    return "\n".join(out) + "\n", state["slot"] + 1


def build_regions(sources, symbols, regions, hooks, defines, slots=None):
    """Compile sources (.S / .c) and link their sections into cave regions and padding slots.

    regions: [(start, end, [input section patterns])], module offsets inside the cave.
    slots: [(address, length)] padding slots; when given, the code of every .c source is split
    across them (see split_into_slots) and its data still goes to the regions.
    hooks: [(site address, original word, entry symbol)].
    Returns ([(module offset, bytes, original)], {region start: bytes used}, slots used).
    Any section not placed somewhere (code, data, bss) is an error, so nothing is left out."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "params.inc").write_text("".join(f"#define {k} {v}\n" for k, v in defines.items()))
        objs, nslots = [], 0
        c_sources = [s for s in sources if str(s).endswith(".c")]
        assert not slots or len(c_sources) <= 1, "slots take the code of one .c file"
        for i, src in enumerate(sources):
            obj = tmp / f"{i}.o"
            common = ["clang", "--target=aarch64-none-elf", "-march=armv8.2-a", "-I", tmp]
            if str(src).endswith(".c") and slots:
                listing = tmp / f"{i}.s"
                run(*common, *C_FLAGS, "-fno-jump-tables", "-S", src, "-o", listing)
                split, nslots = split_into_slots(listing.read_text(), slots)
                (tmp / f"{i}.split.s").write_text(split)
                run(*common, "-c", tmp / f"{i}.split.s", "-o", obj)
            elif str(src).endswith(".c"):
                run(*common, *C_FLAGS, "-c", src, "-o", obj)
            else:
                run(*common, "-c", "-x", "assembler-with-cpp", src, "-o", obj)
            objs.append(obj)
        places = []
        for start, end, patterns in regions:
            assert TEXT_END <= start < end <= CAVE_LIMIT, f"region {start:#x}..{end:#x} is outside the cave"
            places.append((start, end, patterns))
        for n in range(nslots):
            address, length = slots[n]
            assert address - BASE < TEXT_END, f"slot {address:#x} isn't in .text"
            places.append((address - BASE, address - BASE + length, [f".text.slot.{n}"]))
        order = sorted(range(len(places)), key=lambda n: places[n][0])   # lld wants rising addresses
        lines = [f'INCLUDE "{Path(symbols).resolve()}"', "SECTIONS {"]
        for n in order:
            start, end, patterns = places[n]
            lines.append(f"  .r{n} {BASE + start:#x} : {{ " + " ".join(f"*({p})" for p in patterns) + " }")
        lines += ["  .symtab 0 : { *(.symtab) }", "  .strtab 0 : { *(.strtab) }", "  .shstrtab 0 : { *(.shstrtab) }",
                  "  /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) }", "}"]
        script = tmp / "link.ld"
        script.write_text("\n".join(lines) + "\n")
        elf = tmp / "cave.elf"
        run("ld.lld", "-e", "0", "--orphan-handling=error", "-T", script, *objs, "-o", elf)
        nm = subprocess.run(["llvm-nm", str(elf)], check=True, capture_output=True, text=True).stdout
        syms = {p[2]: int(p[0], 16) for p in (l.split() for l in nm.splitlines()) if len(p) == 3}
        records, used = [], {}
        for n, (start, end, _) in enumerate(places):
            out = tmp / f"r{n}.bin"
            run("llvm-objcopy", "-O", "binary", "-j", f".r{n}", elf, out)
            code = out.read_bytes() if out.exists() else b""
            assert len(code) <= end - start, f"region {start:#x}..{end:#x}: {len(code)} bytes don't fit"
            if n < len(regions):
                used[start] = len(code)
            if code:
                records.append((start, code, bytes(len(code))))
    for site, original, entry in hooks:
        records.append((site - BASE, struct.pack("<I", b_word(site, syms[entry])), struct.pack("<I", original)))
    return records, used, nslots


def is_terminator(word):
    """ret / retab / b / br: an instruction after which execution never falls through."""
    return word in (0xD65F03C0, 0xD65F0FFF) or word >> 26 == 0x05 or word & 0xFFFFFC1F == 0xD61F0000


def verify_slots(slots, main_image):
    """Each slot must still be zero padding right after an instruction that ends the flow."""
    img = Path(main_image).read_bytes()
    for address, length in slots:
        off = address - BASE
        assert img[off:off + length] == bytes(length), f"slot {address:#x} isn't zero padding"
        assert is_terminator(struct.unpack_from("<I", img, off - 4)[0]), f"slot {address:#x}: code falls into it"


def verify(records, main_image):
    """main_image: flat module image (module offset 0 = byte 0). Checks the bytes each record replaces."""
    img = Path(main_image).read_bytes()
    for off, new, original in records:
        found = img[off:off + len(original)]
        assert found == original, f"main+{off:#x}: expected {original.hex()}, found {found.hex()}"


def ips32(records):
    out = bytearray(b"IPS32")
    for off, data, _ in sorted(records):
        for k in range(0, len(data), 0xFFFF):
            chunk = data[k:k + 0xFFFF]
            out += struct.pack(">IH", off + k + NSO_HEADER_SIZE, len(chunk)) + chunk
    return bytes(out + b"EEOF")


def write_zip(path, title_id, mod_name, build_id, patch, readme=None, manifest=None):
    """manifest: the mod's mod.toml (a path), put in the mod folder so `kaepora check` knows the mod."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name, data):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))   # fixed date: same input, same zip
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
        add(f"{title_id}/{mod_name}/exefs/{build_id}.ips", patch)
        if readme:
            add(f"{title_id}/{mod_name}/README.txt", readme)
        if manifest and Path(manifest).exists():
            add(f"{title_id}/{mod_name}/mod.toml", Path(manifest).read_bytes())
