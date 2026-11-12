#!/usr/bin/env python3
"""Tests for the manifest reader, the registry and `kaegae check / install / init`.

    python3 tests/test_kaegae_tools.py

Needs no game files. It builds small mod folders in a temporary place and checks that each kind
of conflict is reported, that the registry agrees with the released patches and with the mods'
own manifests, and that installing assigns module slots and refuses a set of mods with errors.
"""
import contextlib
import io
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import kaegae  # noqa: E402
import kaegae_check as kc  # noqa: E402
import kaegae_manifest as km  # noqa: E402
import nxpatch  # noqa: E402

B111 = "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"
TITLE = "0400486024DEC000"
count = 0


def ok(condition, what):
    global count
    assert condition, what
    count += 1


def make(root, name, manifest=None, records=None, exefs=None, romfs=None, build=B111):
    """A mod folder: records are (module offset, bytes) for an IPS32 patch to main."""
    folder = Path(root) / name
    (folder / "exefs").mkdir(parents=True)
    if manifest is not None:
        (folder / "mod.toml").write_text(manifest)
    if records is not None:
        (folder / "exefs" / f"{build}.ips").write_bytes(nxpatch.ips32([(o, b, b"") for o, b in records]))
    for file, blob in (exefs or {}).items():
        (folder / "exefs" / file).write_bytes(blob)
    for file, blob in (romfs or {}).items():
        path = folder / "romfs" / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    return folder


def manifest(mod_id, extra="", version="1.0.0"):
    return (f'manifest = 1\nid = "{mod_id}"\nname = "{mod_id}"\nversion = "{version}"\nauthors = ["t"]\nlicense = "MIT"\n'
            f'[game]\ntitle = "{TITLE}"\n{extra}')


def codes(problems, level=None):
    return {p.code for p in problems if level is None or p.level == level}


def check(*folders, **kw):
    return kc.check([km.load_folder(f) for f in folders], kw.pop("registries", {}), **kw)


def run(*argv):
    """The command line tool: (exit code, what it printed)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = kaegae.main([str(a) for a in argv])
    return code, out.getvalue()


def test_values():
    ok(km.parse_range("0x10..0x20", "t") == (16, 32), "range")
    for bad in ("0x20..0x10", "0x10", 5, "a..b"):
        try:
            km.parse_range(bad, "t")
            ok(False, f"{bad!r} should not parse as a range")
        except ValueError:
            ok(True, "")
    ok(km.parse_binding("Left+L") == km.parse_binding("l+left") == "L+Left", "chords compare equal in any order")
    ok(km.parse_binding("key:F5") == "key:f5" and km.parse_binding("mouse:left") == "mouse:left", "keys and mouse")
    for bad in ("+", "Q", "L+L", "key:", "mouse:nose"):
        try:
            km.parse_binding(bad)
            ok(False, f"{bad!r} should not be a binding")
        except ValueError:
            ok(True, "")
    ok(km.parse_relation("kaegae.core>=0.3") == ("kaegae.core", ">=", "0.3"), "relation")
    ok(km.relation_holds(">=", "0.3", "0.3.1") and not km.relation_holds("==", "0.3", "0.4"), "versions compare by number")
    ok(km.relation_holds("==", "0.3", "0.3.0") and km.relation_holds("<", "1.10", "1.9"), "0.3 is 0.3.0; 1.9 is below 1.10")


def test_ips():
    records = [(0x3C46B00, bytes(range(40))), (0x4C5068, b"\x01\x02\x03\x04")]
    ok(sorted(km.read_ips(nxpatch.ips32([(o, b, b"") for o, b in records]))) == sorted(records), "IPS32 round trip")
    classic = b"PATCH" + (0x100 + 0x20).to_bytes(3, "big") + b"\x00\x02" + b"\xAA\xBB" + b"EOF"
    ok(km.read_ips(classic) == [(0x20, b"\xAA\xBB")], "classic IPS, NSO header taken off")
    rle = b"IPS32" + (0x100 + 0x40).to_bytes(4, "big") + b"\x00\x00" + b"\x00\x08" + b"\x7F" + b"EEOF"
    ok(km.read_ips(rle) == [(0x40, b"\x7F" * 8)], "run-length record")
    for bad in (b"hello", b"IPS32" + b"\x00\x00\x01\x00\x00\x10" + b"ab", b"IPS32" + b"\x00\x00\x00\x10\x00\x01\x00EEOF"):
        try:
            km.read_ips(bad)
            ok(False, "a broken patch should be refused")
        except ValueError:
            ok(True, "")
    ok(km.runs([(0x10, b"ab"), (0x12, b"cd"), (0x20, b"e")]) == [(0x10, 0x14), (0x20, 0x21)], "adjacent records merge")


def test_registry():
    registries = kc.load_registries()
    ok(B111 in registries, "a registry for 1.1.1")
    for reg in registries.values():
        faults = kc.registry_problems(reg)
        ok(not faults, f"{reg.path.name}: {faults}")
    reg = registries[B111]
    # every mod in this repo that patches main: its manifest and the registry say the same thing
    for path in sorted(REPO.glob("mods/*/mod.toml")):
        m = km.load_manifest(path)
        ok(not [p for p in m.problems if p.level == "error"], f"{path}: {[str(p) for p in m.problems]}")
        if B111 not in m.builds:
            continue
        claim, mine = reg.claim_of(m.id), m.builds[B111]
        ok(claim is not None, f"{m.id} patches main but has no claim in {reg.path.name}")
        ok((sorted(claim.code), sorted(claim.memory), sorted(claim.hooks)) == (sorted(mine.code), sorted(mine.memory), sorted(mine.hooks)),
           f"{m.id}: mod.toml and {reg.path.name} disagree")
    # the released patches stay inside what their owners registered
    seen = set()
    with tempfile.TemporaryDirectory() as work:
        for n, release in enumerate(sorted((REPO / "releases").glob("*.zip"))):
            for root in kaegae.unpack(release, Path(work) / str(n)):
                mod = km.load_folder(root)
                ok(not codes(mod.problems, "error"), f"{release.name}: {[str(p) for p in mod.problems]}")
                if B111 not in mod.patches or "probe" in release.name or "diagnostic" in release.name:
                    continue
                claim = kc.recognise(reg, km.runs(mod.patches[B111]))
                ok(claim is not None, f"{release.name}: its patch writes outside every claim in {reg.path.name}")
                ok(mod.id in (None, claim.owner) or kc.CORE_ID == claim.owner, f"{release.name}: recognised as {claim.owner}")
                seen.add(claim.owner)
    ok({"kabosune.first-person", "kabosune.fpv-drone", "kaegae.core"} <= seen, f"releases recognised: {seen}")
    for example in ("api/examples/mod.toml", "api/examples/hello/mod.toml"):
        m = km.load_manifest(REPO / example)
        ok(not m.problems, f"{example}: {[str(p) for p in m.problems]}")


def test_manifest_against_files(work):
    good = manifest("a.good", f'[build.{B111}]\ncode = ["0x3C46B00..0x3C46B40"]\nhooks = ["0x4C5068"]\nmemory = ["0x4E9F000..0x4E9F010"]\n')
    records = [(0x3C46B00, b"\x11" * 0x30), (0x4C5068, b"\x01\x00\x00\x14")]
    ok(not km.load_folder(make(work, "good", good, records)).problems, "a truthful manifest has no problems")
    mod = km.load_folder(make(work, "liar", good, records + [(0x100000, b"\x00\x00\x00\x14")]))
    ok("undeclared-write" in codes(mod.problems, "error"), "a write the manifest doesn't claim")
    mod = km.load_folder(make(work, "nohook", good, records[:1]))
    ok("hook-not-written" in codes(mod.problems, "error"), "a hook the patch doesn't write")
    mod = km.load_folder(make(work, "nobuild", manifest("a.nobuild"), records))
    ok("undeclared-patch" in codes(mod.problems, "error"), "a patch with no [build] table")
    mod = km.load_folder(make(work, "module", manifest("a.module", '[modules]\nsubsdk2 = "a.module@1.0.0"\n'), exefs={"subsdk3": b"x"}))
    ok({"module-missing", "undeclared-module"} <= codes(mod.problems, "error"), "modules that aren't the files in exefs")
    bad = 'manifest = 2\nid = "Bad Id"\nversion = "one"\n[game]\ntitle = "xyz"\n[input]\ngo = "Q"\n[relations]\nrequires = ["nope"]\n[[romfs-patch]]\nkind = "magic"\n'
    found = codes(km.load_folder(make(work, "bad", bad)).problems, "error")
    ok({"manifest-version", "id", "name", "version", "authors", "title", "input", "relation", "romfs-patch"} <= found, f"each fault is named: {found}")
    table = manifest("a.table") + '[[romfs-patch]]\nkind = "size-table"\npath = "AS/X.asb"\nat-least = 6368\n'
    mod = km.load_folder(make(work, "table", table, romfs={"System/Resource/ResourceSizeTable.Product.111.rsizetable.zs": b"x"}))
    ok(mod.manifest.size_table == {"AS/X.asb": 6368} and "ships-size-table" in codes(mod.problems, "warning"), "size table requests")
    (Path(work) / "broken").mkdir()
    (Path(work) / "broken" / "mod.toml").write_text("this is = not toml [")
    ok("manifest-unreadable" in codes(km.load_folder(Path(work) / "broken").problems), "an unreadable manifest is reported, not raised")


def test_conflicts(work):
    registries = kc.load_registries()
    a = make(work, "A", records=[(0x3C46B00, b"\x11" * 16), (0x4C5068, b"\x01\x00\x00\x14")])
    b = make(work, "B", records=[(0x3C46B08, b"\x22" * 16)])
    ok("byte-overlap" in codes(check(a, b), "error"), "different bytes at the same place")
    twin = make(work, "A2", records=[(0x3C46B00, b"\x11" * 16)])
    found = check(a, twin)
    ok("same-bytes" in codes(found, "warning") and "byte-overlap" not in codes(found), "the same bytes twice is a warning")
    ok(not codes(check(a, make(work, "C", records=[(0x3C46B10, b"\x33" * 4)])), "error"), "neighbours don't clash")

    def level2(mod_id, code, hook, mem):
        return manifest(mod_id, f'[build.{B111}]\ncode = ["{code}"]\nhooks = ["{hook}"]\nmemory = ["{mem}"]\n')
    m1 = make(work, "M1", level2("x.one", "0x3C46000..0x3C46020", "0x4C5068", "0x4E9F000..0x4E9F010"),
              [(0x3C46000, b"\x01" * 8), (0x4C5068, b"\x01\x00\x00\x14")])
    m2 = make(work, "M2", level2("x.two", "0x3C46010..0x3C46040", "0x4C5068", "0x4E9F008..0x4E9F020"),
              [(0x3C46030, b"\x02" * 8), (0x4C5068, b"\x02\x00\x00\x14")])
    found = codes(check(m1, m2), "error")
    ok({"hook-clash", "code-clash", "memory-clash", "byte-overlap"} <= found, f"claims clash even where no byte does yet: {found}")

    ok("exefs-clash" in codes(check(make(work, "E1", exefs={"subsdk1": b"a"}), make(work, "E2", exefs={"subsdk1": b"b"})), "error"),
       "two folders with the same module slot")
    ok("romfs-clash" in codes(check(make(work, "R1", romfs={"AS/a.asb.zs": b"a"}), make(work, "R2", romfs={"AS/a.asb.zs": b"b"})), "error"),
       "two folders with the same romfs file")
    i1 = make(work, "I1", manifest("x.i1", '[input]\ntoggle = "L3"\n'))
    i2 = make(work, "I2", manifest("x.i2", '[input]\nlevitate = "L3"\nother = "L3+R3"\n'))
    found = check(i1, i2)
    ok("input-clash" in codes(found, "warning") and not codes(found, "error"), "the same default button is a warning")
    ok("duplicate-id" in codes(check(make(work, "D1", manifest("x.dup")), make(work, "D2", manifest("x.dup", version="2.0.0"))), "error"),
       "one id in two folders")

    need = make(work, "N", manifest("x.need", '[relations]\nrequires = ["x.lib>=2.0"]\nconflicts = ["x.enemy"]\n'))
    ok("requires" in codes(check(need), "error"), "a requirement nobody meets")
    ok("requires" in codes(check(need, make(work, "L1", manifest("x.lib", version="1.5.0"))), "error"), "a requirement met by too old a version")
    ok(not codes(check(need, make(work, "L2", manifest("x.lib", version="2.1.0"))), "error"), "a requirement met")
    ok("conflicts" in codes(check(need, make(work, "L3", manifest("x.lib", version="2.1.0")), make(work, "En", manifest("x.enemy"))), "error"),
       "a declared conflict")

    core = make(work, "Core", manifest("kaegae.core", '[modules]\nsubsdk1 = "kaegae.core@0.3"\n', version="0.3"), exefs={"subsdk1": b"c"})
    def core_mod(name, api, slot="subsdk2"):
        return make(work, name, manifest(f"x.{name.lower()}", f'[modules]\n{slot} = "x.{name.lower()}@1.0.0"\n[core]\napi = "{api}"\n'), exefs={slot: b"m"})
    ok(not codes(check(core, core_mod("Fits", "0.3")), "error"), "a core mod with its Core")
    ok("api-mismatch" in codes(check(core, core_mod("Old", "0.2")), "error"), "a core mod built for another API version")
    ok("no-core" in codes(check(core_mod("Alone", "0.3")), "error"), "a core mod without Core")

    # against the registry
    fp = make(work, "Intruder", records=[(0x3C46B10, b"\x44" * 8)])
    found = check(fp, registries=registries)
    ok("registered-to-other" in codes(found, "note") or "recognised" in codes(found), "space registered to someone else is said")
    drone = make(work, "Somewhere", manifest("x.unreg", f'[build.{B111}]\ncode = ["0x3C461D0..0x3C461E0"]\n'), [(0x3C461D0, b"\x55" * 8)])
    ok("unregistered" in codes(check(drone, registries=registries), "warning"), "a level 2 mod with no claim in the registry")
    ripple = make(work, "Ripple", records=[(0x3C46E00, b"\x66" * 4)])
    ok("builtin-clash" in codes(check(ripple, registries=registries, target="fritchii"), "warning"), "an emulator's built-in patch, on that emulator")
    ok("builtin-clash" in codes(check(ripple, registries=registries, target=None), "note"), "the same, as a note elsewhere")

    image = bytearray(0x3C47000)
    image[0x3C46B00:0x3C46B04] = b"\x1f\x20\x03\xd5"
    hit = check(a, registries=registries, main_image=bytes(image))
    ok("overwrites-game" in codes(hit, "error"), "with main at hand: code that lands on bytes that aren't padding")
    ok("overwrites-game" not in codes(check(b, registries=registries, main_image=bytes(image))), "and code on padding is fine")


def test_install(work):
    load = Path(work) / "emu" / "load"
    (load.parent / "config").mkdir(parents=True)
    (load.parent / "config" / "qt-config.ini").write_text(
        "[Other]\nx=1\n\n[DisabledAddOns]\nsize=2\n1\\title_id=1\n1\\disabled\\size=1\n1\\disabled\\1\\d=Nope\n"
        f"2\\title_id={int(TITLE, 16)}\n2\\disabled\\size=2\n2\\disabled\\1\\d=Off Mod\n2\\disabled\\2\\d=Max Resolution (built-in)\n"
        "2\\disabled\\3\\d=Stale Entry\n\n[UI]\ny=2\n")
    ok(kaegae.read_disabled(load.parent / "config" / "qt-config.ini", TITLE) == {"Off Mod", "Max Resolution (built-in)"},
       "the emulator's Add-Ons list: this title's entries, up to its size")
    src = Path(work) / "src"
    core = make(src, "KaeGae Core", manifest("kaegae.core", '[modules]\nsubsdk1 = "kaegae.core@0.3"\n', version="0.3"), exefs={"subsdk1": b"c"})
    def core_mod(name):
        ident = "x." + name.lower()
        return make(src, name, manifest(ident, f'[modules]\nsubsdk2 = "{ident}@1.0.0"\n[core]\napi = "0.3"\n[relations]\nrequires = ["kaegae.core==0.3"]\n'),
                    exefs={"subsdk2": name.encode()})
    one, two = core_mod("One"), core_mod("Two")
    code, text = run("install", one, "--load-dir", load)
    ok(code == 1 and not (load / TITLE / "One").exists(), f"a mod whose requirement is missing is not installed: {text}")
    code, text = run("install", core, one, two, "--load-dir", load, "--dry-run")
    ok(code == 0 and not (load / TITLE).exists(), f"a dry run copies nothing: {text}")
    code, text = run("install", core, one, two, "--load-dir", load)
    ok(code == 0, text)
    ok((load / TITLE / "One" / "exefs" / "subsdk2").read_bytes() == b"One", "the first mod keeps its slot")
    ok((load / TITLE / "Two" / "exefs" / "subsdk3").read_bytes() == b"Two", "the second is moved to the next free slot")
    ok(km.load_folder(load / TITLE / "Two").manifest.modules == {"subsdk3": [("x.two", "1.0.0")]}, "and its manifest says so")
    ok((two / "exefs" / "subsdk2").exists(), "the source folder is left as it was")
    code, text = run("check", "--load-dir", load)
    ok(code == 0 and "no problems found" in text, f"what was installed passes the check: {text}")
    code, text = run("install", two, "--load-dir", load)
    ok(code == 0 and (load / TITLE / "Two" / "exefs" / "subsdk3").exists(), f"installing again replaces, in a free slot: {text}")
    off = make(load / TITLE, "Off Mod", exefs={"subsdk1": b"second core"})
    code, text = run("check", "--load-dir", load)
    ok(code == 0 and "switched off" in text, f"a mod switched off in the emulator is left out: {text}")
    code, text = run("check", "--load-dir", load, "--all")
    ok(code == 1 and "exefs-clash" in text, "and counted with --all")
    code, text = run("list", "--load-dir", load)
    ok("off Off Mod" in text and "on  One  [x.one 1.0.0]" in text, f"list shows on and off: {text}")
    import os
    locked = load / TITLE / "One" / "exefs"
    os.chmod(locked, 0o500)                   # a folder whose files can't be removed, as when the emulator runs
    try:
        code, text = run("install", one, "--load-dir", load)
    finally:
        os.chmod(locked, 0o700)
    if os.geteuid() != 0:                     # root ignores the permission, so the lock can't be shown
        ok(code == 2 and "Nothing in the load folder was changed" in text, f"a locked folder stops the install: {text}")
    ok(not any(p.name.startswith(".") for p in (load / TITLE).iterdir()), "no temporary folder is ever left in the game's folder")
    ok((load / TITLE / "One" / "exefs" / "subsdk2").read_bytes() == b"One", "and the installed mod is untouched")
    code, text = run("remove", "Off Mod", "--load-dir", load)
    ok(code == 0 and not off.exists(), "remove deletes the folder")
    code, text = run("remove", "../src", "--load-dir", load)
    ok(code == 2 and src.exists(), "remove only takes a folder name inside the load folder")

    # zips: the layouts people ship, and one that tries to write outside
    z = Path(work) / "titled.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr(f"{TITLE}/Zipped/exefs/{B111}.ips", nxpatch.ips32([(0x3C461D0, b"\x01" * 4, b"")]))
    ok([r.name for r in kaegae.unpack(z, Path(work) / "u1")] == ["Zipped"], "a zip with <title id>/<mod>/")
    z2 = Path(work) / "Flat Mod.zip"
    with zipfile.ZipFile(z2, "w") as f:
        f.writestr("romfs/a.txt", "x")
    ok([r.name for r in kaegae.unpack(z2, Path(work) / "u2")] == ["Flat Mod"], "a zip that is the mod folder itself takes the zip's name")
    evil = Path(work) / "evil.zip"
    with zipfile.ZipFile(evil, "w") as f:
        f.writestr("../outside/exefs/x", "x")
    code, text = run("install", evil, "--load-dir", load)
    ok(code == 2 and "refusing" in text, "a zip that points outside itself is refused")


def test_init(work):
    folder = make(work, "Old Mod", records=[(0x3C461D0, b"\x01" * 8), (0x3C461E0, b"\x02" * 8), (0x100000, b"\x01\x00\x00\x14")])
    code, text = run("init", folder, "--id", "me.old-mod", "--author", "Me", "--license", "MIT")
    ok(code == 0, text)
    mod = km.load_folder(folder)
    ok(mod.manifest.id == "me.old-mod" and not codes(mod.problems, "error"), f"init writes a manifest that agrees with the patch: {text}")
    claims = mod.manifest.builds[B111]
    ok(claims.hooks == [0x100000] and claims.code == [(0x3C461D0, 0x3C461E8)], f"hooks and code are told apart: {claims}")
    code, _ = run("init", folder, "--id", "me.old-mod")
    ok(code == 2, "init doesn't write over a manifest")
    code, text = run("inspect", folder)
    ok(code == 0 and "hook" in text and "[cave]" in text, f"inspect: {text}")
    code, text = run("registry")
    ok(code == 0 and "kabosune.first-person" in text, "registry prints")


def test_built_package(work):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        print("  (no clang / ld.lld here: the built package's manifest was not checked)")
        return
    import kaemod
    out = Path(work) / "built"
    for name, argv in (("core", []), ("hello", [REPO / "api/examples/hello", "--no-core"]), ("both", [REPO / "api/examples/hello"]),
                       ("bundle", [REPO / "api/examples/hello", "--bundle"])):
        with contextlib.redirect_stdout(io.StringIO()):
            kaemod.main([str(a) for a in argv] + ["--out", str(out / f"{name}.zip")])
    def one(name):
        return km.load_folder(kaegae.unpack(out / f"{name}.zip", Path(work) / "unz" / name)[0])
    core, hello, both, bundle = one("core"), one("hello"), one("both"), one("bundle")
    for mod in (core, hello, both, bundle):
        ok(not mod.problems, f"{mod.name}: a built folder's manifest agrees with its files: {[str(p) for p in mod.problems]}")
    ok(core.id == kc.CORE_ID and "subsdk1" in core.manifest.modules and B111 in core.patches, "Core alone")
    ok(list(hello.exefs) == ["subsdk2"] and hello.manifest.requires[0][0] == kc.CORE_ID, "a mod without Core asks for it")
    ok(len(bundle.manifest.modules["subsdk1"]) == 2 and list(bundle.exefs) == ["subsdk1"], "a bundle names everything in its one module")
    registries = kc.load_registries()
    ok(not codes(kc.check([core, hello], registries), "error"), "Core and a mod from separate folders pass the check")
    ok("requires" in codes(kc.check([hello], registries), "error"), "the mod alone doesn't")
    ok("duplicate-id" in codes(kc.check([both, core], registries), "error"), "two folders with Core are an error")


def fake_table(sizes, named=()):
    """A RESTBL version 1 table: {path: size} as hashed entries, then (path, size) named entries."""
    import struct
    import zlib
    rows = sorted((zlib.crc32(p.encode()), s) for p, s in sizes.items())
    out = b"RESTBL" + struct.pack("<IIII", 1, 160, len(rows), len(named)) + b"".join(struct.pack("<II", h, s) for h, s in rows)
    return out + b"".join(p.encode().ljust(160, b"\0") + struct.pack("<I", s) for p, s in named)


def test_build(work):
    try:
        import zstandard  # noqa: F401
    except ImportError:
        print("  (no zstandard here: `kaegae build` was not tested)")
        return
    import kaegae_build as kb
    game = fake_table({"AS/King.asb": 5344, "AS/Other.asb": 800, "Model/Big.bfres": 1 << 20}, [("Named/File.bin", 64)])
    merged, changes, missing = kb.merge(game, {"AS/King.asb": 6361, "AS/Other.asb": 100, "Named/File.bin": 100, "Not/There.x": 5})
    ok(changes == [("AS/King.asb", 5344, 6368), ("AS/Other.asb", 800, 800), ("Named/File.bin", 64, 104)] and missing == ["Not/There.x"],
       f"raised to a multiple of 8, never lowered, named entries too, unknown paths reported: {changes} {missing}")
    ok(kb.size_of(merged, "AS/King.asb") == 6368 and kb.size_of(merged, "Model/Big.bfres") == 1 << 20 and len(merged) == len(game),
       "other entries and the table's size stay as they were")
    for bad in (b"nope", game[:-4]):
        try:
            kb.unpack(bad)
            ok(False, "a broken table should be refused")
        except kb.TableError:
            ok(True, "")

    load = Path(work) / "emu" / "load"
    table_file = Path(work) / "ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs"
    table_file.write_bytes(kb.pack(game))
    def asker(name, size):
        return make(load / TITLE, name, manifest("x." + name.lower()) + f'[[romfs-patch]]\nkind = "size-table"\npath = "AS/King.asb"\nat-least = {size}\n',
                    romfs={f"AS/{name}.txt": b"x"})
    asker("Small", 6000)
    code, text = run("check", "--load-dir", load)
    ok(code == 0 and "size-table-not-built" in text, f"a request with no built table is a warning: {text}")
    code, text = run("build", "--load-dir", load)
    ok(code == 2 and "--game-table" in text, "build says what it needs")
    code, text = run("build", "--load-dir", load, "--game-table", table_file, "--dry-run")
    ok(code == 0 and "5344 -> 6000" in text and not (load / TITLE / kb.BUILT_NAME).exists(), f"a dry run writes nothing: {text}")
    code, text = run("build", "--load-dir", load, "--game-table", table_file)
    built = km.load_folder(load / TITLE / kb.BUILT_NAME)
    ok(code == 0 and built.id == kb.BUILT_ID and not built.problems, f"build writes a folder the checker accepts: {text} {[str(p) for p in built.problems]}")
    ok(kb.size_of(kb.built_table(built), "AS/King.asb") == 6000, "with the entry raised")
    code, text = run("check", "--load-dir", load)
    ok(code == 0 and "size-table" not in text, f"then the check is quiet: {text}")
    asker("Large", 7000)
    code, text = run("check", "--load-dir", load)
    ok(code == 1 and "size-table-stale" in text, "a new, larger request makes the built table stale: an error")
    code, text = run("build", "--load-dir", load, "--game-table", table_file)
    ok(code == 0 and kb.size_of(kb.built_table(km.load_folder(load / TITLE / kb.BUILT_NAME)), "AS/King.asb") == 7000,
       f"building again merges both, the largest wins: {text}")
    ok(run("check", "--load-dir", load)[0] == 0, "and the check passes again")
    shipper = make(load / TITLE, "Shipper", romfs={"System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs": b"x"})
    code, text = run("check", "--load-dir", load)
    ok(code == 1 and "romfs-clash" in text, "a mod that ships its own table clashes with the built one")
    shutil.rmtree(shipper)


def main():
    test_values()
    test_ips()
    test_registry()
    for test in (test_manifest_against_files, test_conflicts, test_install, test_init, test_build, test_built_package):
        with tempfile.TemporaryDirectory() as work:
            test(work)
    print(f"all kaegae tool tests passed ({count} checks)")


if __name__ == "__main__":
    main()
