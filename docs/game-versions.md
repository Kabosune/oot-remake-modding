# Game versions 1.0.0 and 1.1.1

The game shipped as 1.0.0 (main build `33FA6C2C23848282A77E8B88A0A93F4887C55920`) and got one
update, 1.1.1 (`E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`), the day before launch: Zelda Notes
support and fixes. KaeGae supports both. This page says what differs, how the 1.0.0 symbol pack
was made (17 November 2026), and how to add to it.

## What carries over and what doesn't

- **Anything that patches `main` at an address works on one build only.** The update rebuilt
  `main`: functions moved by different amounts (from 2.8 MB earlier to 0.4 MB later), some
  swapped order, `.text` grew by 0x5F980 bytes. Read-only data moved in a few blocks (+0x649xx to
  +0x65C08), data and `.bss` in two (+0x65CA8, +0x70460). No single offset converts one build's
  addresses to the other's. So the 1.x First Person / FPV Drone zips (IPS patches) are 1.1.1 only;
  on 1.0.0 the emulator skips their patch (it is named for the 1.1.1 build).
- **Core mods carry over unchanged.** They ask Core for names (`kae_sym`, `kae_field`), and Core
  answers from the pack of the build it runs in. From Core 0.8.4 both packs exist and Core's zip
  holds its patch for both builds.
- **The code itself barely changed.** Of 3,000 function starts sampled in 1.1.1, 47 (1.6 %) have
  no match in 1.0.0 with addresses masked; the rest are the same instructions with the same struct
  offsets. Where checked (the camera view function, the actor chain in `ActorHolder`,
  `CctChangePosition`), field offsets are the same.
- **What really changed** among the pack's names: `PouchAddContent` (in 1.0.0 the item event
  returns from it without the separate notification 1.1.1 has, per sloperinaGZ) and the dungeon
  item setters `DungeonSetMap` / `DungeonSetCompass` / `DungeonSetBossKey` (1.0.0's only set the
  flag; 1.1.1's make one more call when the value is true). The movement update (hook point
  `Actor.MoveUpdate`) was recompiled with a different stack layout; its first two instructions,
  where Core hooks it, are the same.
- **Tested 17 November (Fritchii v5.8.4):** Core 0.8.4 on 1.0.0 finds the build and Link, its
  Mods menu and Slopped Up Sloperina work. Fritchii shows 1.0.0 as a black picture with or without
  mods (an emulator problem). Mouse Grab 0.3.0 crashes there: it calls 1.1.1's `ActorHolder`
  address itself instead of asking Core.
- Hookshot-style aliases (`f_806d2530`) name an address, so each build has its own: a mod asking
  for 1.1.1's alias gets 0 on 1.0.0. Use the plain names.
- **Not checked yet:** romfs. The update ships the whole romfs again (186,583 files against
  1.0.0's 185,994); whether the files the data mods change differ between the versions isn't
  known. Fritchii's built-in patches (Dynamic FPS, Max Resolution) exist for 1.1.1 only.

## Getting a plain 1.0.0 `main`

Switch 2 dumps hold `main` ZBIC-compressed. The simplest way to a plain copy is the emulator:
Fritchii (Lichii, Eden) has **Configure → Filesystem → Patch Manager → Dump Decompressed NSOs**.
Turn the 1.1.1 update off for the game (Configure Game → Add-Ons), start it to the title screen,
and `dump/0400486024DEC000/nso/main-33FA6C2C….nso` appears in the emulator's data folder. Turn
both back afterwards.

That file is the NSO header (0x100 bytes, still the compressed one's, flags 0xFF) followed by the
whole module image, `.bss` included (0x4E30000 bytes for 1.0.0). The flat `main.bin` the tools
take is the file from offset 0x100 on; `tools/flatten_nso.py` refuses it because of the header
flags. A dump of 1.1.1 made the same way is byte for byte the same as an unpacked 1.1.1 `main`
laid out by `flatten_nso.py`, so the method gives the plain game code, with no mod patches in it.

## The port: `tools/port_pack.py`

    python3 tools/port_pack.py symbols/e0f3ccfa.toml main-1.1.1.bin main-1.0.0.bin --version 1.0.0 --out draft.toml

- **Functions and hook points**: the first 12 to 64 instructions of the 1.1.1 entry, with every
  address in them masked (branch targets, adrp pages, literal loads, and the low 12 bits of an add
  / ldr / str right after an adrp), searched in 1.0.0's `.text`. One match is the answer. Struct
  offsets are not masked, so a match also means the code uses the same fields. No match or
  several: through the function's callers (each caller matched, then its `bl` / `b` read). A hook
  point's instruction must be the same word in both builds.
- **Globals**: the code that loads them (adrp + add / ldr) is matched and the address read from
  1.0.0's copy of it. Every reference agreed for all four (34 to 36 votes each).
- **Vtables**: their function pointers are ported and the sequence looked for in 1.0.0's data
  (pointers in `main`'s data are stored in place; its relocations are RELR).
- **Fields**: copied, marked "not checked".

The draft for 1.0.0 found 53 of 55 entries. Checked against sloperinaGZ's own 1.0.0 addresses
(found independently): every one that overlaps is the same, and `vtable.Actor` is its
`vt_linkobj`. The two left (`DungeonSetMap`, `DungeonSetCompass`) were found by hand next to
`DungeonSetBossKey`, by the GameData flag hash each one sets. Core's hook slots and stubs went in
space surveyed for the [1.0.0 registry](../registry/33fa6c2c.toml): the last reference into
`.bss` is 0x4E2A060, and `.text`'s zero padding runs from 0x3BE6850 to 0x3BE7000.

## Adding a name

Find it on 1.1.1 and add it to `symbols/e0f3ccfa.toml` as usual, then rerun `port_pack.py` and
copy its entry into `symbols/33fa6c2c.toml` (and both `.ld` files if it has an `ld` name). If the
draft can't find it, find it by hand or leave it out: a mod that needs it still builds, says in
its README.txt which version it won't run on, and gets 0 from `kae_sym` there, so its `start`
should return an error when a name it needs is missing. `tests/test_kaegae_symbols.py` checks
each pack against its `.ld` file; `tests/test_kaegae_unit.py` checks that both packs have the same
number of names; `tests/test_kaegae_hooks.py <main.bin> <core zip>` runs Core's stub on either
build's real code.
