# KaeGae (draft)

A proposed shared standard for Ocarina of Time remake mods: one package format, one registry of
who patches what, and a small core module that mods call instead of patching the game themselves.

- [DESIGN.md](DESIGN.md): the design, its reasons, the roadmap and the open questions.
- [include/kaegae.h](include/kaegae.h): the Core API (0.8). A mod includes only this.
- [core/](core/): KaeGae Core, the module that goes in `exefs/subsdk1`.
- [sdk/](sdk/): what the build adds to a mod (its module start, four C library functions).
- [examples/hello/](examples/hello/): the smallest core mod, also Core's in-game test.
- [examples/mod.toml](examples/mod.toml): a manifest for a mod that patches `main` itself (levels 1 and 2).
- [MODS-MENU.md](MODS-MENU.md): the shared in-game Mods menu (settings, button mapping), with menu code and host tests in `menu/`. Built into Core from API 0.4.
- [MANIFEST.md](MANIFEST.md): the package format, `mod.toml`, the registry, and what `kaegae check` and
  `kaegae install` do (levels 1 and 2). The registry itself is [`registry/`](../registry/).
- [CHANGELOG.md](CHANGELOG.md): what changed between drafts and API versions.

## Status (12 November 2026)

| Part | State |
|---|---|
| Core 0.2: mods register and start, events (`frame`, `input`, `draw`, `actor_move`), symbols by name, log, memory pool, motion | Written and tested in the game (10 November, Fritchii, game 1.1.1): Hello registered, started, drew and reacted to the A button. Also passes its tests on a PC, including the real AArch64 modules run in an emulator against a fake game |
| API 0.3: text (`kae_draw_text`) and small pictures (`kae_draw_image`) | Tested in the game (10 November, Fritchii v5.7, game 1.1.1) |
| API 0.4: the Mods menu and mods' settings (`kae_settings`) | Tested in the game (11 November, Fritchii v5.8.3, game 1.1.1): the menu opens with - and +, blocks the game's input, switches mods off, settings and rebinding work, with three added modules loaded at once (Core, Hello, Slopped Up Sloperina) |
| API 0.5: Link from Core (`player_move`, `kae_player_of`, `kae_player_move`, his velocity) | Tested in the game (11 November, Fritchii v5.8.4, game 1.1.1) with Core 0.5.1: Core finds Link and his body, Slopped Up Sloperina levitates. Core 0.5 itself could hang the game (its locks only spun), fixed in 0.5.1 |
| Core 0.5.2: the Mods menu's settings saved between runs (`kaegae/settings.txt` on the SD card, through the system's `nn::fs`) | Tested in the game (11 November, Fritchii v5.8.4, game 1.1.1): changes survive closing and reopening the emulator |
| Core 0.6: newer Cores run older mods (back to 0.5), `kae_settings_sized` | Tested in the game (11 November, Fritchii v5.8.4): five mods built for 0.5 start and work on Core 0.6 |
| Core 0.7: keyboard keys for every binding, `kae_binding_held` / `_pressed`, sticks in bindings | Tested in the game (12 November, Fritchii v5.8.4, game 1.1.1): works, with Slopped Up Sloperina 0.4.0 using its new bindings and keys |
| Drawing, the motion sensor, the `Actor.MoveUpdate` hook point | Tested in the game (Fritchii v5.6, game 1.1.1) as part of Mouse Grab, before Core was split out |
| A mod as its own module (`subsdk2`+) finding Core through rtld | Works in the game: Hello in `subsdk2` found Core in `subsdk1` (open question 1: yes) |
| `kaegae check / install / list / init`, the manifest, the registry for 1.1.1 (levels 1 and 2) | Written, pass their tests on a PC, and `check` was run on a real Fritchii mod folder (11 November). Needs no game. [MANIFEST.md](MANIFEST.md) |
| A core mod in its own folder, apart from Core's (`kaemod.py --no-core`) | Tested in the game (11 November, Fritchii v5.8.3): Core, Hello and Slopped Up Sloperina from three folders load, link and start |
| `kaegae build`: one resource size table from every mod's requests | Written, passes its tests, and gives the same table as the hand-made one from a real dump (11 November). The other romfs patch kinds are design only |
| Core 0.8: the camera view event (`kae_on_view`, matrix and field of view), the `Camera.View` hook point | Works in the game (12 November, Fritchii): hook points in place, First Person 2.0 and FPV Drone 2.0 run on it. The FOV did nothing in 0.8.0; 0.8.1 changes the camera's own FOV instead (not tested in the game yet) |
| Generic hook points (`kae_hook`), config | Design only |
| Game version 1.0.0 | No symbol pack yet: Core does nothing there and says so |

## Writing a mod

```c
#include <kaegae.h>

static void draw(const KaeFrame *frame, void *user) {
    kae_draw_rect(20, 20, 40, 40, 0x40C0FF);
}

static int start(void) {
    KAE_LOG("hello, game version %s", kae_game_version());
    return kae_on_draw(draw, 0, 0);
}

KAE_MOD("author.mod-name", "1.0.0", start, 0);
```

Next to it, a `mod.toml` with a `[core]` table ([the example's](examples/hello/mod.toml)): the API
version, the source files, and any system function the mod imports itself. Then:

```
python3 tools/kaemod.py path/to/my-mod              # Core in subsdk1, the mod in subsdk2
python3 tools/kaemod.py path/to/my-mod --bundle     # both linked into subsdk1
python3 tools/kaemod.py mod-a mod-b --name "My Pack"
```

The build refuses a mod that uses a `kae_` function Core doesn't export, imports a system function
it didn't declare, or asks for a symbol that some game version's pack doesn't have.

Beyond drawing, Core gives a mod text and small pictures, a page of settings and rebindable
controls in the Mods menu, saved between runs (`kae_settings`; `kae_binding_held` /
`kae_binding_pressed` read a binding from its buttons or its keyboard key), Link and his
velocity (`kae_player_*`), the motion sensor, symbols by name and a memory pool.
[include/kaegae.h](include/kaegae.h) lists every function; the mods in [`mods/`](../mods/) that
need Core are working examples.

What a mod can rely on:

- `start` runs once, after every module is loaded, the first time the game calls into Core (early,
  while the game sets up its graphics). Returning non-zero switches the mod off and takes back
  whatever it subscribed to.
- A subscribed function can be called as soon as it is subscribed. `frame`, `input` and
  `actor_move` come on the game's thread, `draw` on its render thread.
- If Core is missing, the build of the game is unknown, or the mod was built for another API
  version, the mod doesn't run and the log says why. Nothing crashes on its behalf.
- Core's log lines start `kaegae:`, a mod's `kaegae [its.id]:`. In Fritchii they are in
  `log\eden_log.txt` in its data folder (`%APPDATA%\fritchii` from v5.8, `%APPDATA%\eden` before) as
  `Debug.Emulated <Info>`.

## Checking and installing mods

```
python3 tools/kaegae.py check                     # the mods that are on in the emulator: can they run together?
python3 tools/kaegae.py check my-mod.zip --with-installed
python3 tools/kaegae.py install my-mod.zip        # check first, then copy; gives a core mod a free module slot
python3 tools/kaegae.py list
python3 tools/kaegae.py init "My Mod" --id me.my-mod   # write a mod.toml for an existing mod
```

It reads mods with and without a manifest, compares their patches byte by byte, and knows from
the registry whose space a patch is in. [MANIFEST.md](MANIFEST.md) has the format and every finding
it can report.

A folder built by `tools/kaemod.py` carries a `mod.toml` that names its modules.

**Core goes in its own folder, each mod in its own** (tested in the game on 11 November: Core,
Hello and Slopped Up Sloperina from three folders, all linked and started). Core is
`releases/kaegae-core.zip` (`python3 tools/kaemod.py` with no mod); a mod is built with
`--no-core`; up to seven mods sit next to Core, each in a free `subsdk2` ... `subsdk8`, which
`kaegae install` picks. Without `--no-core`, Core is linked into the mod's folder: it installs by
hand in one step, but two such folders can't be on together (both bring `subsdk1`).

## Tests

```
python3 tests/test_kaegae_tools.py      # the manifest reader, the registry, check / install / init
python3 tests/test_kaegae_unit.py       # Core's logic, built for the PC
python3 tests/test_kaegae_modules.py    # the shipped modules in Unicorn with a fake game and system
python3 tests/test_kaegae_symbols.py    # the symbol pack and symbols/<build>.ld agree
python3 tests/test_kaegae_hooks.py main.bin releases/kaegae-test.zip    # the hook stub on your real main
```

The first four need no game files. `--log` on the second prints the log of a full run.

## Checking that Core runs

Install `releases/kaegae-core.zip` and any mod built on it (Moon Jump or Speedometer show
something right away), close and reopen the emulator, start the game. Core's
log starts with `kaegae: Core 0.7 loaded, game 1.1.1, main at ...`, then each mod's own lines
(`kaegae [its.id]: ...`); while the emulator runs, the log is `eden_log.busy.txt`. The Mods menu (- and + together) lists every mod Core found, with the
reason next to any it switched off. Close the emulator before changing mod folders: it locks a
mod's exefs files while it runs.

## The first in-game tests (10 November 2026)

What these settled (Fritchii, game 1.1.1, Core 0.2); the status table above has everything
tested since.

- **One added module can call another (open question 1: yes).** Hello in `subsdk2` found Core in
  `subsdk1` through the game's rtld: its square appeared and turned green while A was held. So
  mods can be separate modules, and `--bundle` is only needed if a setup ever refuses that.
- **Several added modules run at once (question 4).** Mouse Grab (Core and the mod in one
  module) ran in the same session with First Person and FPV Drone (patches to `main`) on. Its log
  had `input: 5 of 5 controller styles hooked` (Core's guess at the controller functions' names
  was right) and `hook point in place: Actor.MoveUpdate`.
- **A mod without Core does no harm (question 6).** With only Hello's module installed, the game
  ran as normal and the log said `kaegae mod: KaeGae Core isn't loaded (or this module wasn't
  linked to it); doing nothing`: the game's rtld leaves a missing weak import empty.
- **Who starts first (question 2)** is still unmeasured (that run's log was overwritten); either
  order works.

`releases/kaegae-test.zip` (Core with Hello in its own module) and
`releases/kaegae-hello-without-core.zip` are the builds from those tests, kept as they were.
