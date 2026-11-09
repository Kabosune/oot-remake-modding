# OoT Remake Modding

Research notes, an address map and patch tooling for **The Legend of Zelda: Ocarina of Time** on
Nintendo Switch 2 (the 2026 remake), plus mods built with them.

Everything here targets one build of the game:

| | |
|---|---|
| Title ID | `0400486024DEC000` |
| Update | v131072 ("1.1.1") |
| main build ID | `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348` |

Other builds will need their addresses found again. The build scripts check every patched
instruction, so a mismatch fails loudly at build time instead of crashing the game.

**No game files are in this repository**: no executables, keys, dumps or extracted assets.
Mods are distributed as IPS32 patches that contain only new code. You need your own dump.

## Mods

| Mod | What it does | Status |
|---|---|---|
| [First Person](mods/first-person/README.md) | R3 toggles a first-person view. Right stick looks, left stick walks. | v0.1, testing |

Mods install like any exefs mod: copy the zip's `0400486024DEC000` folder into the emulator's
`load` folder (Lichii / Fritchii / Eden: `%APPDATA%\eden\load\`), then restart the game.

## Docs

- [Getting started](docs/getting-started.md): from your dump to a flat `main` image you can read and patch.
- [Address map](docs/address-map.md): functions, globals, vtables and imports we know about.
- [Structures](docs/structures.md): field layouts (camera view, camera manager, Link, controller state).
- [Memory map](docs/memory-map.md): which code cave and free memory each mod uses, so mods don't collide.
- [Writing a patch](docs/writing-a-patch.md): how `tools/nxpatch.py` works and the rules for hooks.

## Layout

```
symbols/e0f3ccfa.ld        addresses for build E0F3CCFA, shared by every mod (a linker script)
tools/nxpatch.py           assemble + link at the cave + IPS32 + verify against your main
tools/flatten_nso.py       uncompressed main -> flat module image
mods/<mod>/                source (.S), build.py, README
tests/                     Unicorn tests that run the hooks on a patched main with fake game objects
releases/                  built zips
```

Addresses use a module base of `0x80020000`, the same as Hookshot, so `f_XXXXXXXX` names
match between the two projects. `main offset = address - 0x80020000`.

## Contributing

New findings go in the docs with a note on how they were found, so others can check them.
New mods take their cave and memory from [docs/memory-map.md](docs/memory-map.md) and add
themselves to it.

## Credits

- KaboWabo/Kabosune (me :3)
- AI assistance (Claude Opus 5.5)
- [NotRexed/Hookshot](https://github.com/NotRexed/Hookshot): the gameplay camera, view and player
  findings that the first-person mod is built on, and the NUP / ZBIC tools used to get `main` out
  of a dump.
- [craftycorvid/oot-mod](https://github.com/craftycorvid/oot-mod): the IPS32 conventions for this
  build and the first use of the `.text` padding as a cave.

An unofficial fan project, not affiliated with or endorsed by Nintendo. The Legend of Zelda and
Ocarina of Time are trademarks of Nintendo.
