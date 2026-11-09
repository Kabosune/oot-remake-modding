# Getting started

From your own dump of the game to a flat image of `main` that you can disassemble, and that the
build scripts can check patches against.

You need:

- Your dump as a `.nup` with update v131072 (or `exefs/` + `romfs/` folders).
- Python 3.10+.
- [Hookshot](https://github.com/NotRexed/Hookshot)'s `nx2/` tools, for reading the `.nup` and
  undoing Switch 2's ZBIC compression. They need `pip install lz4 zstandard`, plus clang to build
  their small ZBIC decompressor on first use.
- To build mods: LLVM (clang, ld.lld, llvm-objcopy, llvm-nm). On Windows, the LLVM installer from
  <https://github.com/llvm/llvm-project/releases> includes all four.

## 1. Get the tools

Run these one at a time, pressing Enter after each:

```
git clone --depth 1 https://github.com/NotRexed/Hookshot.git
```

```
pip install lz4 zstandard capstone unicorn
```

## 2. Extract `main` from the dump

This writes only the exefs (about 40 MB), not the 26 GB romfs.

```
python Hookshot/nx2/nup.py "The Legend of Zelda Ocarina of Time [0400486024DEC000][v131072].nup" --extract work --only exefs
```

`work/exefs/main` is now there, still ZBIC-compressed.

## 3. Decompress it

`unpack.py` rewrites ZBIC NSOs in place, so run it on a copy:

```
xcopy work\exefs work\plain\ /E /I
```

```
python Hookshot/nx2/unpack.py work/plain
```

(On Linux or macOS, use `cp -r work/exefs work/plain` instead of `xcopy`.)

## 4. Flatten it

```
python tools/flatten_nso.py work/plain/main work/main.bin
```

It prints the build ID. It must be `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`.

`work/main.bin` is the module laid out as it sits in memory: byte N is module offset N. Load it
in Ghidra or IDA as raw AArch64 at base `0x80020000` and the addresses in this repo line up.
Keep it out of git: it's the game's code.

## 5. Build and check a mod

```
python mods/first-person/build.py --verify-main work/main.bin
```

```
python tests/test_first_person.py work/main.bin releases/first-person.zip
```

The first builds the zip and checks every replaced instruction against your `main`. The second
runs the patched code in an emulated CPU with fake game objects.
