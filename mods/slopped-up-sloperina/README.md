# Slopped Up Sloperina

[sloperinaGZ](https://github.com/PracticeROM/sloperina), PracticeROM's gz-style practice menu for the
Ocarina of Time remake, running as a mod on [KaeGae Core](../../api/README.md). It's their code
(release 0.0.4.2), ported: KaeGae Core starts it, runs it every frame, hands it the controller and
draws for it, so it sits next to other KaeGae mods instead of taking the game's hooks for itself.

**Licence: GPL-3.0-or-later** ([LICENSE](LICENSE)), because sloperinaGZ is. This folder is the only
part of the repository under the GPL; KaeGae Core and the other mods stay MIT.

**Status, 11 November 2026: version 0.3.0, the first port. Works in the real game** (Fritchii
v5.8.4, game 1.1.1, on KaeGae Core 0.6: KaboWabo, 20:46 PT), and its PC emulator test passes (it
starts on game 1.1.1, opens and draws its menu, hides the controller from the game while the menu is
open). Game version 1.1.1 for now: the mod keeps sloperinaGZ's
offsets for 1.0.0 too, but KaeGae Core doesn't start mods on a game version it has no symbol pack for,
and it has none for 1.0.0 yet.

## What it does

What sloperinaGZ does; its [manual](https://github.com/PracticeROM/sloperina/blob/master/docs/MANUAL.md)
describes every menu. In short: warps to any map and entrance, inventory, equipment, quest items and
upgrades, story flags and dungeon items, cheats, Link's age, save / load position, levitate, watches
(position, speed, timers, any memory address), the input display, frame advance, a memory viewer,
the air walls and enemies' health shown in the world, the dive tests, translations of the menu.

- **Open the menu:** R + right stick down (gz's R + C-down). Same again to close it; B goes back.
- **Move:** D-pad up / down; change a value: D-pad left / right; **select: L**. The prompts under the
  menu show select, return and close as they're bound now. On a keyboard (from
  0.4.0, in an emulator): the arrow keys, Enter to select, Backspace to go back.
- **Rebind its shortcuts, or give them keyboard keys** (from 0.4.0): KaeGae Core's Mods menu (- and
  + together) → Slopped Up Sloperina. Twelve of them: open / close the menu, back, save / load
  position (R + D-up / down), levitate (L3), frame advance (L) and run (L + L3), the timer, the lag
  counter, the jump height and showing the watches.
- KaeGae Core's own Mods menu (- and + together) lists it and can switch it off; while that menu is
  open this one holds still.

## What's different from sloperinaGZ

- **Drawn by KaeGae Core in gz's style**, with Core's 8 x 16 font: the menu, watches, log and input
  display as panels of text, the air walls and enemy health bars as rectangles. sloperinaGZ's own
  look (the game's font, buttons, pictures and see-through backdrop, drawn with the game's UI shader)
  isn't there, so the settings menu has no "style" option. A background opacity of 0% means none;
  anything else is drawn solid, since Core can't blend yet.
- **No X / Y / Z locks.** They need sloperinaGZ's patch to main (stubs for the game's stores of Link's
  position), which this mod doesn't have.
- **Runs at a different moment of the frame:** Core's frame event (when the game reads the
  controllers), not sloperinaGZ's hook on the game's GameData unlock. Everything that changes the game
  goes through the same functions as in sloperinaGZ; whether all of them are as happy to be called
  from here is the main thing the first test in the game has to show.
- **Its own folder on the SD card:** `SloppedUpSloperina/` (settings, log, translations). If it has no
  settings yet it reads sloperinaGZ's `sloperinaGZ/settings.ini`, so yours carry over.
- The input display shows the sticks as two boxes instead of a drawing of the controller; items have
  no pictures.

## Install

Needs KaeGae Core 0.7 or later (0.3.0 needed 0.5.2), installed once from its own download. Install both:

```
python3 tools/kaegae.py install releases/kaegae-core.zip releases/slopped-up-sloperina.zip
```

or copy both zips' folders into the emulator's mod folder for the game by hand (in Fritchii,
`%APPDATA%\fritchii\load\0400486024DEC000\`). **Turn sloperinaGZ itself off** while this one is on:
they're the same menu on the same buttons. It needs no `.ips` of its own.

## Changes to sloperinaGZ's sources

The GPL asks that changes are marked. `src/` is sloperinaGZ's `src/ootgz/` at release 0.0.4.2
(commit `0cc9c8f`), with:

- **Left out:** `nvn.c`, `gpuui.c`, `nativeui.c`, `overlayui.c`, `uishader.c`, `scenedepth.c`,
  `gamefont.c`, `gameimage.c`, `gamefile.c`, `astc.c`, `zstd.c`, `font.c`, `got.c`, `crt0.S` and
  `third_party/` (their drawing, their GOT hooks and module start).
- **New:** `kaedraw.c` / `kaedraw.h` (drawing the published panels and rectangles with Core),
  `platform_extra.c` (`sqrtf`, and `gameimage_lost` for the left-out pictures), `build_info.h`
  (versions, made by their Makefile there).
- **Changed:** `ootgz.c` (start and frame from Core's events; no patch checks), `input.c` / `input.h`
  (the game's copy of the controller edited in Core's input event instead of through main's GOT;
  gz's shortcuts as bindings on Core's page, with keys, and the keyboard in the menu),
  `position.c` / `levitate.c` / `watches.c` (the shortcuts read as those bindings),
  `lock.c` (locks off), `gfx.c` / `settings.c` / `menus.c` (gz's style only; the text size choices),
  `sdfs.h` (the SD card folder), `menus.c` / `settings.c` / `sys.c` / `memview.c` (the mod's name in
  titles and the log).

## How it's built

`python3 tools/kaemod.py mods/slopped-up-sloperina --no-core` (clang, as every KaeGae mod). sloperinaGZ's
game offsets for both versions stay its own table (`src/z64hd_builds.h`), found from `nnMain` as it
always did, rather than Core's symbol pack. The module test in `tests/test_kaegae_modules.py` runs
it against the fake game.

## Credits

- **sloperinaGZ** by PracticeROM: Kieran Monaghan, with Yves, FantaTanked, Ec1ipse, Tom Lube,
  waze3174, Meta // Cam, simonMettler2000, Volvagia ([their contributors](CONTRIBUTORS-sloperinaGZ.md)
  and [thanks](THANKS-sloperinaGZ.md)). All of the practice menu is their work.
- KaboWabo/Kabosune (me :3): the port's idea, direction, in-game testing
- AI assistance (Claude Opus 5.5): the port to KaeGae Core
