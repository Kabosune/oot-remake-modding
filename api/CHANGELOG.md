# Kaepora changelog

Until API 1.0 anything here may still change, and Core only runs mods built against exactly its
own API version.

## Draft 0.7: the tools for levels 1 and 2 (11 November 2026; on the branch `kaepora-tools`)

No change to Core or its API. Everything here runs on a PC.

- **`tools/kaepora.py`**: `check` (which installed mods can't be on together, and why), `install`
  (check first, then copy), `remove`, `list`, `inspect` (what a patch writes and whose space that
  is), `init` (write a `mod.toml` for an existing mod), `registry`, `targets`.
- **The manifest is specified**: [MANIFEST.md](MANIFEST.md). Changes from the draft example: the
  ranges a patch fills are `code` (was `cave`, since padding slots count too); `[modules]` names
  each `exefs/subsdkN`; `[relations] requires` takes a version (`"kaepora.core==0.3"`); romfs files
  need no listing.
- **The registry exists**: `registry/e0f3ccfa.toml` for 1.1.1, with the free spaces and every known
  claim, including mods outside the standard and the emulators' built-in patches.
  `registry/33fa6c2c.toml` for 1.0.0 holds the one claim known there.
- First Person and FPV Drone have manifests, and their zips carry them (the patches are byte for
  byte the same). `tools/kaemod.py` writes a manifest into every folder it builds.
- **A mod without Core in its folder**: `tools/kaemod.py <mod> --no-core`. `kaepora install` gives
  such a mod a free module slot. Not tried in the game yet.
- The emulator's folder is no longer assumed to be `%APPDATA%\eden`: Fritchii v5.8 moved to
  `%APPDATA%\fritchii`. The tools take `--target` or `--load-dir`; the docs name both.
- Found by the first real `check`: Fritchii v5.8.3's built-in "Water ripples at any frame rate"
  patch uses `main+0x3C46E00`, inside First Person's range. With First Person on, Fritchii leaves
  its fix out (its log says so). Recorded in the registry and the memory map; not resolved.

## Draft 0.5, API 0.3 (10 November 2026; on the branch `kaepora-draw-text`, not tested in the game yet)

Text and small pictures.

- **`kae_draw_text`, `kae_text_width`, `kae_text_height`**: text in a built-in 8 x 16 font
  ([Spleen](https://github.com/fcambus/spleen) by Frederic Cambus, BSD 2-Clause, in
  `core/font/`), at whole-number scales. UTF-8; the font carries ASCII and Latin-1.
- **`kae_draw_image`**: a picture of 0xAARRGGBB pixels at a whole-number scale. A pixel is drawn
  solid or left out (alpha below 0x80): made for pixel art such as cursors and icons.
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
- `tests/test_kaepora_symbols.py` checks that a pack and its linker file agree, and fails when the
  linker file has a vtable, function or global the pack lacks.
- API 0.3: mods built for 0.2 need a rebuild (0.x versions don't mix).

## Draft 0.4, API 0.2 (10 November 2026)

Core is now its own module with a public API, instead of a skeleton compiled together with one mod.

- **API 0.2** (`include/kaepora.h`): `KAE_MOD`, `kae_register`; events `kae_on_frame`,
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
