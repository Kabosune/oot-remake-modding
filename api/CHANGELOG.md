# Kaepora changelog

Until API 1.0 anything here may still change, and Core only runs mods built against exactly its
own API version.

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
