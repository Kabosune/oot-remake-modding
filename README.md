# OoT Remake Modding

Research notes, an address map and patch tooling for **The Legend of Zelda: Ocarina of Time** on
Nintendo Switch 2 (the 2026 remake), plus mods built with them.

Everything here was made on game version 1.1.1. **Mods built on KaeGae Core also run on 1.0.0**
(from Core 0.8.4: Core carries the addresses for both, the mods stay the same). The standalone
patches (the 1.x downloads) and the romfs mods are 1.1.1 only for now; see
[game versions](docs/game-versions.md).

| | 1.1.1 | 1.0.0 |
|---|---|---|
| Title ID | `0400486024DEC000` | `0400486024DEC000` |
| Version | v131072 (the update) | v65536 (the base game, no update) |
| main build ID | `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348` | `33FA6C2C23848282A77E8B88A0A93F4887C55920` |

Other builds will need their addresses found again (`tools/port_pack.py` does most of it). The build scripts check every patched
instruction, so a mismatch fails loudly at build time instead of crashing the game.

**No game files are in this repository**: no executables, keys, dumps or extracted assets.
Mods are distributed as IPS32 patches that contain only new code. You need your own dump.

## Mods

**Install [KaeGae Core](api/README.md) first** ([download `kaegae-core.zip`](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/kaegae-core.zip)),
in its own folder, before any of the mods below. All of them run on it and
do nothing without it. Kaegae has its own mod menu and button mapping system. activate its menu by pressing + and -. On a real Switch 2, KaeGae
Core may not run yet properly ([issue #2](https://github.com/Kabosune/oot-remake-modding/issues/2))

| Mod | Download | What it does | Needs KaeGae Core | Status |
|---|---|---|---|---|
| [Adventure Log](mods/adventure-log/README.md) | [adventure-log.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/adventure-log.zip) | The play log the game keeps for Zelda Notes, on screen. A simple panel with your hearts, rupees and Gold Skulltulas, today's enemies, chests, areas and songs, jumps, rolls, sword swings and km on foot (this session and all time) and the newest highlights; or a detailed panel with every count and the raw log. Works offline, without Zelda Notes. | Yes (Core 0.8) | 0.4.0 works in Fritchii on 1.1.1 (KaeGae Core 0.9.0, 19 Nov); 0.4.1 fixes what counts as distance. **1.1.1 only** (1.0.0 has no play log) |
| [Equip Anything](mods/equip-anything/README.md) | [equip-anything.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/equip-anything.zip) | Child and adult Link can equip every item (child with the Master Sword, adult with the masks, ...); pick an equipped sword, shield or tunic again to take it off. Both are switches on the Mods menu. | Yes (Core 0.9) | 1.0.1 works in Fritchii on 1.1.1 (KaeGae Core 0.9.0, 18 Nov); 1.0.0 not tried |
| [First Person](mods/first-person/README.md) | [first-person.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/first-person.zip) | R3 toggles a first-person view (right stick looks, left stick walks). Link is hidden by default. Settings page: FOV, eye height and forward, look speed, show Link, rebindable toggle. | Yes (Core 0.8) | 2.0.1 works in Fritchii (KaeGae Core 0.8, 12 Nov). The old 1.x without Core is on [its page](mods/first-person/README.md) |
| [Flashlight & Lantern](mods/flashlight-lantern/README.md) | [flashlight-lantern.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/flashlight-lantern.zip) | Real dynamic lights that follow Link, made with the game's own lighting: a lantern that glows all around him like Navi, and a flashlight beam where he faces (or where the camera looks). Brightness, colour, size, beam width, glow style, and a switch to turn Navi's own light off. | Yes (Core 0.8) | 0.1.2 works in Fritchii on 1.1.1 (KaeGae Core 0.9.0, 22 Nov); 1.0.0 not tried |
| [FPV Drone](mods/fpv-drone/README.md) | [fpv-drone.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/fpv-drone.zip) | L3 launches a noclip Free fly camera (L) or an FPV quadcopter with Mode 2 sticks: Angle (Y), Acro (X), Simple (B). R carries Link along behind the camera. Every button rebindable (and keys); FOV, speeds, rates, tilt, thrust on its settings page. | Yes (Core 0.8) | 2.0.0 works in Fritchii (KaeGae Core 0.8, 12 Nov). The old 1.x without Core is on [its page](mods/fpv-drone/README.md) |
| [Mouse Grab](mods/mouse-grab/README.md) | [mouse-grab.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/mouse-grab.zip) | A mouse cursor that grabs Link (and other characters) as a ragdoll, to move and throw him. Settings for the gyro depth, throw strength and more. | Yes (Core 0.8.5) | 0.4.0 works in Fritchii on 1.0.0 and 1.1.1 (KaeGae Core 0.8.5, 17 Nov) |
| [Slopped Up Sloperina](mods/slopped-up-sloperina/README.md) | [slopped-up-sloperina.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/slopped-up-sloperina.zip) | PracticeROM's sloperinaGZ practice menu ported onto KaeGae Core: warps, inventory, flags, cheats, watches, levitate, frame advance, memory viewer and more. **GPL-3.0**, unlike the rest of the repo. | Yes | 0.4.0 works in Fritchii (KaeGae Core 0.7, 12 Nov): shortcuts rebindable on Core's page, with keyboard keys. Needs Core 0.7 |
| [World Tools](mods/world-tools/README.md) | [world-tools.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/world-tools.zip) | A clock on screen, set the time of day (or jump to day / night, an hour on), any of the game's 12 weathers (rain, thunderstorm, snow, ...) and the wind, all from its settings page. | Yes (Core 0.8.6 or later) | 0.1.1 works in Fritchii on 1.1.1 (KaeGae Core 0.9.0, 18 Nov); 1.0.0 not tried |

### Extra mods

Small, just-for-fun mods. Moon Jump, Speedometer and Drunk Mode are built on KaeGae Core, need it,
have their settings on the Mods menu, and work in Fritchii (KaeGae Core 0.6, game 1.1.1, 11 Nov).
Dark Deku Tree is a romfs mod without Core.

| Mod | Download | What it does |
|---|---|---|
| [Moon Jump](mods/moon-jump/README.md) | [moon-jump.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/moon-jump.zip) | Low gravity, boosted jumps, hold L + A to fly up. |
| [Speedometer](mods/speedometer/README.md) | [speedometer.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/speedometer.zip) | Link's speed as a big number and a bar, with his top speed and rise / fall. m/s, km/h or mph. |
| [Drunk Mode](mods/drunk-mode/README.md) | [drunk-mode.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/drunk-mode.zip) | The movement stick wobbles; sticks and A / B can be mirrored, flipped or swapped. |
| [Dark Deku Tree](mods/dark-deku-tree/README.md) | [dark-deku-tree.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/dark-deku-tree.zip) | Inside the Deku Tree with no baked light, ambient light or fog: pitch dark, for Flashlight & Lantern. **No Core needed**, but its files are built from your own dump with `python3 tools/kaegae.py build --romfs <dump>` (see its page). Works in Fritchii on 1.1.1 (22 Nov). |

Mods install like any exefs mod: copy the zip's `0400486024DEC000` folder into the emulator's
`load` folder (Fritchii v5.8 and later: `%APPDATA%\fritchii\load\`; Lichii, Eden and older
Fritchii: `%APPDATA%\eden\load\`), then close and reopen the emulator (Fritchii v6.1 lists new mod folders switched off: switch them on in the game's Add-Ons). Do this for
`kaegae-core.zip` first, then for each mod; each one gets its own folder. Every mod zip has its
module as `exefs/subsdk2`, so when you copy more than one by hand, rename the file in each extra
mod to a free number (`subsdk3`, `subsdk4`, ... up to `subsdk8`), or only one of them loads. Or let the tool do it,
with a check for conflicts first (it also tells you when a mod needs Core and Core is missing or
switched off): `python3 tools/kaegae.py install releases/kaegae-core.zip releases/mouse-grab.zip`
([api/MANIFEST.md](api/MANIFEST.md)).

## A shared modding standard (draft)

[KaeGae](api/README.md) is a proposal for how mods for this game can be packaged, checked for
conflicts and, later, built on one shared core module so they survive game updates (if those ever evenget dumped lol) and work
together. The core runs in the game and the conflict checker works on today's mods
(`python3 tools/kaegae.py check`); it is still a draft: read [api/DESIGN.md](api/DESIGN.md) and
say what's wrong with it.

## Docs

- [Getting started](docs/getting-started.md): from your dump to a flat `main` image you can read and patch.
- [Game versions](docs/game-versions.md): 1.0.0 and 1.1.1, what differs, how KaeGae Core runs the same mods on both.
- [The engine](docs/engine.md): what the Tears of the Kingdom engine (ModuleSystem) means for modding this game.
- [romfs](docs/romfs.md): what's in the game's 26 GB of data, its compression, how to look inside, and the resource size table.
- [Scenes, scene changes and spawn points](docs/warps.md): how doors / exits name their destination, and all 465 spawn points with coordinates.
- [Custom maps](docs/custom-maps.md): every file a scene is made of (Inside the Deku Tree as the example), format versions, and the ways in.
- [Field enemy spawning](docs/enemy-spawning.md): Stalchildren, Leevers and Guay come from ten loose data files (counts, intervals, strong versions).
- [Event flows](docs/event-flow.md): the 914 cutscene and dialogue scripts (BFEVFL), what actions and flag checks they use, and a table of all 2,423 story flags.
- [Tuning data](docs/tuning.md): Link's movement, damage, healing, Epona, songs and the scene / item tables as data files; the script node catalogue; leftover debug modes; how enum hashes work.
- [Animation graphs](docs/asb.md): the ASB format (version 0x41B), how a playback rate is attached, rules for editing by hand.
- [Dynamic lights](docs/lights.md): the LocationalLight manager (point, spot and Navi's lights), a light's fields, making one at run time, how far lights reach, and Navi's glow.
- [Camera](docs/camera.md): the camera's parameter files, FOV, distances, and Link's heights.
- [Script commands](docs/script-commands.md): all ~5,200 AI / logic commands mapped to their code in `main`.
- [Address map](docs/address-map.md): functions, globals, vtables and imports we know about.
- [Structures](docs/structures.md): field layouts (camera view, camera manager, Link, controller state).
- [Memory map](docs/memory-map.md): which code cave and free memory each mod uses, so mods don't collide.
- [Writing a patch](docs/writing-a-patch.md): how `tools/nxpatch.py` works and the rules for hooks.
- [Modules](docs/modules.md): mods as their own `subsdk` module (KaeGae Core), hooking from a module, drawing, mouse and motion input.
- [Ragdoll, faces and voices](docs/ragdoll-and-animation.md): starting and ending Link's ragdoll, moving its bodies, playing AS commands.
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
tools/zsmod.py             change numbers in those files and write a .zs the game loads (tuning mods, no code)
tools/evflags.py           list the story flags the event scripts set and check (needs `pip install evfl`)
tools/msbtmod.py           read and change dialogue / menu text (MSBT in the Mals packs) and write a .zs
tools/asbtool.py           read and check animation graphs (AS/*.root.asb)
tools/rstb_set.py          raise entries in the resource size table for romfs mods whose files grew
tools/gen_commands.py      regenerate the script-command table from a flat main
tools/ghidra_label_commands.py  name those functions in Ghidra
api/                       KaeGae, the proposed modding standard: the design, Core (api/core), its API (api/include)
tools/kaemod.py            build KaeGae Core and core mods into exefs modules
tools/kaegae_symbols.py   symbol packs (symbols/<build>.toml) -> the table compiled into Core
tools/mknso.py             pack a linked module into an NSO
mods/<mod>/                source (.S, .c), build.py, README
tests/                     Unicorn tests that run the hooks on a patched main with fake game objects;
                           KaeGae's tests (test_kaegae_unit.py, test_kaegae_modules.py, test_kaegae_symbols.py) need no game files
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
- AI assistance (Claude Opus 5.5, Claude Fable 5.2, Claude Sonnet 5.5)
- [NotRexed/Hookshot](https://github.com/NotRexed/Hookshot): the gameplay camera, view and player
  findings that the first-person mod is built on, and the NUP / ZBIC tools used to get `main` out
  of a dump.
- [craftycorvid/oot-mod](https://github.com/craftycorvid/oot-mod): the IPS32 conventions for this
  build and the first use of the `.text` padding as a cave.
- [PracticeROM/sloperina](https://github.com/PracticeROM/sloperina): its findings document, summarised in
  [docs/sloperina-findings.md](docs/sloperina-findings.md), and sloperinaGZ itself, which
  [Slopped Up Sloperina](mods/slopped-up-sloperina/README.md) is a port of.

Licences: MIT ([LICENSE](LICENSE)), except `mods/slopped-up-sloperina/`, which is sloperinaGZ's code
and stays GPL-3.0 ([its LICENSE](mods/slopped-up-sloperina/LICENSE)).

An unofficial fan project, not affiliated with or endorsed by Nintendo. The Legend of Zelda and
Ocarina of Time are trademarks of Nintendo.
