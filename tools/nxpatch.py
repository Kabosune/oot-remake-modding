"""Build exefs IPS32 patches for main from an assembly source.

The source is assembled with clang and linked with ld.lld at the cave address, against the
addresses in symbols/<build>.ld. Every hook site is checked against the original instruction,
in a real main if one is given, so a patch can't silently land on a different game build.

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


def write_zip(path, title_id, mod_name, build_id, patch, readme=None):
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
