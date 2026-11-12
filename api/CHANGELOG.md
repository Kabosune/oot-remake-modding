# KaeGae changelog

Until API 1.0 anything here may still change, and Core only runs mods built against exactly its
own API version.

## Core 0.5.1 (11 November 2026)

Same API (0.5), a fix in Core only: mods need no rebuild.

- **The game could hang** (freeze for good, no crash) a few seconds after an area loaded, with
  Core 0.5, Sloped Up Sloperina and Mouse Grab on. Core's locks only spun while waiting; the game
  runs threads of different priorities on one core, so a thread spinning on a lock held by a
  lower-priority one kept it from ever running again. 0.5 takes these locks far more often (it
  looks at every actor's movement update to find Link), so it hit this often. Locks now spin
  briefly and then sleep between tries. Tested in the game: no hang in 7 minutes of play with area
  loads, levitate, and Link ragdolled and thrown six times.
- The start line in the log says `Core 0.5 loaded (build 0.5.1, locks sleep)`.

## Draft 0.9, API 0.5 (11 November 2026; tested in the game the same day, with Core 0.5.1)

Link, from Core.

- **`player_move`** (`kae_on_player_move`): Link's own movement update, with a `KaePlayer` (his
  actor, player object, character controller, its physics body, his position). This is the event
  the design called `player_update`.
- **`kae_player_of(actor)`** for an `actor_move` function that needs to tell Link from other actors.
- **`kae_player_move`**, **`kae_player_velocity`**, **`kae_player_set_velocity`**: the game's own
  character controller move, and its body's velocity. `kae_has("player")`,
  `kae_has("event.player_move")`.
- The walk from an actor to Link, which Sloped Up Sloperina, Mouse Grab and FPV Drone each wrote
  out with their own offsets, is now in Core once (`core/player.c`), and its offsets are fields of
  the symbol pack (`Actor.components`, `Player.movement`, `Cct.body` ...), so a pack for 1.0.0 covers
  every mod at once. New pack entries: `vtable.CctBody` and those fields. `CctBody.velocity`
  (`+0xE0`) is from sloperinaGZ's write-up and has not been checked against main by us; Core
  refuses values that can't be a speed.
- **Sloped Up Sloperina 0.2.0** uses these and has no game offset left in it. Levitate now takes
  away Link's falling speed every update he is held up (0.1.0 only lifted him, and gravity won).
- Mouse Grab is rebuilt for API 0.5 from the same source (it still finds Link itself).
- API 0.5: mods built for 0.4 need a rebuild.

## Draft 0.8: the new names (11 November 2026)

No change in behaviour. The standard **Kaepora** is now **KaeGae**, Kaepora Core is **KaeGae Core**,
and Super Sloperina is **Sloped Up Sloperina**. Older entries below use the new names too.

- Mod ids: `kaepora.core` → `kaegae.core`, `kaepora.hello` → `kaegae.hello`, `kaepora.built` →
  `kaegae.built`, `kabosune.super-sloperina` → `kabosune.sloped-up-sloperina`. A manifest that
  requires `kaepora.core` must say `kaegae.core` now.
- Files: `tools/kaegae.py` (was `kaepora.py`) and `tools/kaegae_*.py`, `api/include/kaegae.h` (was
  `kaepora.h`: change the `#include`), `tests/test_kaegae_*.py`, `mods/sloped-up-sloperina/`.
- Release zips: `kaegae-test.zip`, `kaegae-hello-without-core.zip`, `sloped-up-sloperina.zip`.
- The log prefix is `kaegae:`; environment variables `KAEGAE_TARGET`, `KAEGAE_LOAD_DIR`.
- Kept: the `kae_*` functions, `KAE_*` names and `Kae*` types, so a mod's code only needs the new
  `#include`. Modules built before the rename still link to the new Core.

## Draft 0.7: the tools for levels 1 and 2 (11 November 2026)

No change to Core or its API. Everything here runs on a PC.

- **`tools/kaegae.py`**: `check` (which installed mods can't be on together, and why), `install`
  (check first, then copy), `remove`, `list`, `inspect` (what a patch writes and whose space that
  is), `init` (write a `mod.toml` for an existing mod), `registry`, `targets`.
- **The manifest is specified**: [MANIFEST.md](MANIFEST.md). Changes from the draft example: the
  ranges a patch fills are `code` (was `cave`, since padding slots count too); `[modules]` names
  each `exefs/subsdkN`; `[relations] requires` takes a version (`"kaegae.core==0.3"`); romfs files
  need no listing.
- **The registry exists**: `registry/e0f3ccfa.toml` for 1.1.1, with the free spaces and every known
  claim, including mods outside the standard and the emulators' built-in patches.
  `registry/33fa6c2c.toml` for 1.0.0 holds the one claim known there.
- First Person and FPV Drone have manifests, and their zips carry them (the patches are byte for
  byte the same). `tools/kaemod.py` writes a manifest into every folder it builds.
- **A mod without Core in its folder**: `tools/kaemod.py <mod> --no-core`. `kaegae install` gives
  such a mod a free module slot. Not tried in the game yet.
- **`kaegae build`** makes one resource size table from the requests in every mod's manifest
  (`[[romfs-patch]] kind = "size-table"`), from the player's own dump, as a mod folder of its own.
  On a real dump it reproduces the table Slow King Zora v4 was given by hand.
- The emulator's folder is no longer assumed to be `%APPDATA%\eden`: Fritchii v5.8 moved to
  `%APPDATA%\fritchii`. The tools take `--target` or `--load-dir`; the docs name both.
- Found by the first real `check`: Fritchii v5.8.3's built-in "Water ripples at any frame rate"
  patch uses `main+0x3C46E00`, inside First Person's range. With First Person on, Fritchii leaves
  its fix out (its log says so). Recorded in the registry and the memory map; not resolved.

## Draft 0.6, API 0.4 (10 November 2026; tested in the game on 11 November)

The Mods menu runs inside Core.

- **The Mods menu** ([MODS-MENU.md](MODS-MENU.md)) opens with - and + together. It lists every mod
  with its version, switches a mod off and on with X (a mod that is off gets no events), and shows
  a mod's page of settings. While it is open the game sees no buttons or sticks, whatever a mod's
  input function does.
- **`kae_settings(name, items, count)`** gives the calling mod its page: toggles, choices, numbers,
  button bindings and actions (`KaeItem`). The mod reads `value` / `binding` from its own array;
  Core calls `changed` after the player changes one. **`kae_menu_open()`**, `kae_has("menu")`, and
  the button names `KAE_A` ... `KAE_DOWN`.
- The menu's code is `menu/kae_menu.c`, the same file the host tests build; inside Core it draws
  with `kae_draw_rect` and `kae_draw_text` instead of its own picture renderer.
- Not yet: settings aren't saved between runs, and the reminder line on the game's pause menu.
- API 0.4: mods built for 0.3 need a rebuild.

## Draft 0.5, API 0.3 (10 November 2026; tested in the game)

Text and small pictures.

- **`kae_draw_text`, `kae_text_width`, `kae_text_height`**: text in a built-in 8 x 16 font
  ([Spleen](https://github.com/fcambus/spleen) by Frederic Cambus, BSD 2-Clause, in
  `core/font/`), at whole-number scales. UTF-8; the font carries ASCII and Latin-1.
- **`kae_draw_image`**: a picture of 0xAARRGGBB pixels at a whole-number scale. A pixel is drawn
  solid or left out (alpha below 0x80): made for pixel art such as cursors and icons.
- In the game (Fritchii v5.7, 1.1.1): Hello's text and picture show; NVN reports free command
  memory; 131 rectangles took 9028 bytes of command memory, about 69 bytes each.
- Both are drawn as rectangles, the one kind of drawing proven in the game, so nothing new is asked
  of the game's graphics library. Smooth text in the game's own font and pictures blended over the
  game are a later step behind the same functions.
- Core now takes up to 8192 rectangles a frame (128 before). It keeps to the amount of command
  memory per rectangle that is proven in the game, asks NVN how much room is left beyond that, and
  leaves rectangles out instead of overrunning. If the game's heap won't give the larger drawing
  memory (2.5 MB), Core falls back to the old amount. The log says how many command bytes the
  fullest frame took.
- The pack for 1.1.1 gains 38 symbols contributed by gleedgleed (the pouch, GameData, EventFlow,
  event requests, dungeon items, actor position and transform, the framework's frame function).
- `tests/test_kaegae_symbols.py` checks that a pack and its linker file agree, and fails when the
  linker file has a vtable, function or global the pack lacks.
- API 0.3: mods built for 0.2 need a rebuild (0.x versions don't mix).

## Draft 0.4, API 0.2 (10 November 2026)

Core is now its own module with a public API, instead of a skeleton compiled together with one mod.

- **API 0.2** (`include/kaegae.h`): `KAE_MOD`, `kae_register`; events `kae_on_frame`,
  `kae_on_input`, `kae_on_draw`, `kae_on_actor_move`, each with any number of subscribers in
  priority order; `kae_draw_rect`; `kae_sym`, `kae_field`, `kae_game_base`, `kae_game_version`,
  `kae_game_build`; `kae_has`, `kae_api_version`; `kae_motion_direction`; `kae_logf` / `KAE_LOG`;
  `kae_alloc` / `kae_free`; `kae_readable`.
- **Two ways to load a mod**, from the same source: its own module (`subsdk2` to `subsdk8`), or
  linked into Core's (`--bundle`). `tools/kaemod.py` builds both.
- **Symbol packs** exist: `symbols/<build>.toml`, compiled into Core. They also tell Core how to
  recognise each build. The pack for 1.1.1 has the first functions, vtables and fields.
- **Input without a patch**: Core wraps main's `GetNpadStates` and `GetNpadStyleSet` imports by
  name. That gives the `frame` and `input` events.
- A mod's imports from Core are weak, so a mod without Core loads and does nothing.
- Design changes: a mod's `start` runs at the first call from the game rather than "after every
  module is loaded" being detected some other way; the hook-point event for the movement update is
  called `actor_move` (it runs for every actor, not only Link); 0.x versions don't mix.
- Not yet: `kae_hook` and the hook-point generator, input bindings, config, text drawing, the
  `view` / `player_update` / `scene_change` / `pause_change` events, a pack for 1.0.0.

## Draft 0.3 (9 November 2026)

Both game versions, 1.0.0 and 1.1.1, are supported by the design.

## Draft 0.2

1.1.1 taken as the final game version.

## Draft 0.1

The first design: three levels, the manifest, the registry, Core. The Mods menu's code and tests.
