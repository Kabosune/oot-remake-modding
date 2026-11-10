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
| [First Person](mods/first-person/README.md) | R3 toggles a first-person view (right stick looks, left stick walks). Link is hidden by default. Keyboard: `,` `.` eye height, `;` show / hide Link. | Works in Lichii / Fritchii |
| [FPV Drone](mods/fpv-drone/README.md) | L3 launches a noclip Free fly camera (L) or an FPV quadcopter with Mode 2 sticks: Angle (Y), Acro (X), Simple (B). R carries Link along behind the camera. | Drone modes tried in Fritchii; Free fly and carry tested in Unicorn only |

Mods install like any exefs mod: copy the zip's `0400486024DEC000` folder into the emulator's
`load` folder (Lichii / Fritchii / Eden: `%APPDATA%\eden\load\`), then restart the game.

## A shared modding standard (draft)

[Kaepora](api/README.md) is a proposal for how mods for this game can be packaged, checked for
conflicts and, later, built on one shared core module so they survive game updates and work
together. It is a design draft: read [api/DESIGN.md](api/DESIGN.md) and say what's wrong with it.

## Docs

- [Getting started](docs/getting-started.md): from your dump to a flat `main` image you can read and patch.
- [The engine](docs/engine.md): what the Tears of the Kingdom engine (ModuleSystem) means for modding this game.
- [romfs](docs/romfs.md): what's in the game's 26 GB of data, its compression, how to look inside, and the resource size table.
- [Animation graphs](docs/asb.md): the ASB format (version 0x41B), how a playback rate is attached, rules for editing by hand.
- [Camera](docs/camera.md): the camera's parameter files, FOV, distances, and Link's heights.
- [Script commands](docs/script-commands.md): all ~5,200 AI / logic commands mapped to their code in `main`.
- [Address map](docs/address-map.md): functions, globals, vtables and imports we know about.
- [Structures](docs/structures.md): field layouts (camera view, camera manager, Link, controller state).
- [Memory map](docs/memory-map.md): which code cave and free memory each mod uses, so mods don't collide.
- [Writing a patch](docs/writing-a-patch.md): how `tools/nxpatch.py` works and the rules for hooks.
- [What sloperinaGZ found](docs/sloperina-findings.md): a summary of the practice menu's findings (save fields, pausing, physics controller, actors) in this repo's addresses, and what they open up for the mods here.
- [Community projects](docs/community.md): emulators, recomps, other mods and tools.

## Layout

```
symbols/e0f3ccfa.ld        addresses for build E0F3CCFA, shared by every mod (a linker script)
symbols/e0f3ccfa-commands.csv   every script command and its code (tools/gen_commands.py makes it)
symbols/e0f3ccfa-slots.txt the compiler's padding between functions that mods can fill (tools/find_slots.py)
tools/nxpatch.py           assemble / compile C + link into the cave and padding slots + IPS32 + verify against your main
tools/find_slots.py        find padding slots in a flat main
tools/flatten_nso.py       uncompressed main -> flat module image
tools/zstool.py            look inside romfs files: .zs (with the game's dictionaries), SARC, BYML
tools/asbtool.py           read and check animation graphs (AS/*.root.asb)
tools/rstb_set.py          raise entries in the resource size table for romfs mods whose files grew
tools/gen_commands.py      regenerate the script-command table from a flat main
tools/ghidra_label_commands.py  name those functions in Ghidra
api/                       Kaepora, the proposed modding standard (design draft)
mods/<mod>/                source (.S, .c), build.py, README
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
- AI assistance (Claude Opus 5.5, Claude Fable 5.2)
- [NotRexed/Hookshot](https://github.com/NotRexed/Hookshot): the gameplay camera, view and player
  findings that the first-person mod is built on, and the NUP / ZBIC tools used to get `main` out
  of a dump.
- [craftycorvid/oot-mod](https://github.com/craftycorvid/oot-mod): the IPS32 conventions for this
  build and the first use of the `.text` padding as a cave.
- [PracticeROM/sloperina](https://github.com/PracticeROM/sloperina): its findings document, summarised in
  [docs/sloperina-findings.md](docs/sloperina-findings.md).

An unofficial fan project, not affiliated with or endorsed by Nintendo. The Legend of Zelda and
Ocarina of Time are trademarks of Nintendo.
