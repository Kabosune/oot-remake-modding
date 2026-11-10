# Kaepora (draft)

A proposed shared standard for Ocarina of Time remake mods: one package format, one registry of
who patches what, and a small core module that mods call instead of patching the game themselves.

- [DESIGN.md](DESIGN.md): the design, its reasons, the roadmap and the open questions.
- [include/kaepora.h](include/kaepora.h): the Core API (0.2). A mod includes only this.
- [core/](core/): Kaepora Core, the module that goes in `exefs/subsdk1`.
- [sdk/](sdk/): what the build adds to a mod (its module start, four C library functions).
- [examples/hello/](examples/hello/): the smallest core mod, also Core's in-game test.
- [examples/mod.toml](examples/mod.toml): a manifest for a mod that patches `main` itself (levels 1 and 2).
- [MODS-MENU.md](MODS-MENU.md): the shared in-game Mods menu (settings, button mapping), with menu code and host tests in `menu/`. Not connected to Core yet.
- [CHANGELOG.md](CHANGELOG.md): what changed between drafts and API versions.

## Status (10 November 2026)

| Part | State |
|---|---|
| Core 0.2: mods register and start, events (`frame`, `input`, `draw`, `actor_move`), symbols by name, log, memory pool, motion | Written. Passes its tests on a PC, including the real AArch64 modules run in an emulator against a fake game. **The new parts haven't run in the game yet** |
| Drawing, the motion sensor, the `Actor.MoveUpdate` hook point | Tested in the game (Fritchii v5.6, game 1.1.1) as part of Mouse Grab, before Core was split out |
| A mod as its own module (`subsdk2`+) finding Core through rtld | Built; whether the game's rtld links one added module to another is open question 1, answered by the test below |
| `kaepora check / install / build`, the registry, romfs patches (levels 1 and 2) | Design only |
| Generic hook points (`kae_hook`), input bindings, config, the Mods menu in game | Design only |
| Game version 1.0.0 | No symbol pack yet: Core does nothing there and says so |

## Writing a mod

```c
#include <kaepora.h>

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

What a mod can rely on:

- `start` runs once, after every module is loaded, the first time the game calls into Core (early,
  while the game sets up its graphics). Returning non-zero switches the mod off and takes back
  whatever it subscribed to.
- A subscribed function can be called as soon as it is subscribed. `frame`, `input` and
  `actor_move` come on the game's thread, `draw` on its render thread.
- If Core is missing, the build of the game is unknown, or the mod was built for another API
  version, the mod doesn't run and the log says why. Nothing crashes on its behalf.
- Core's log lines start `kaepora:`, a mod's `kaepora [its.id]:`. In Fritchii they are in
  `eden_log.txt` as `Debug.Emulated <Info>`.

## Tests

```
python3 tests/test_kaepora_unit.py       # Core's logic, built for the PC
python3 tests/test_kaepora_modules.py    # the shipped modules in Unicorn with a fake game and system
python3 tests/test_kaepora_hooks.py main.bin releases/kaepora-test.zip    # the hook stub on your real main
```

The first two need no game files. `--log` on the second prints the log of a full run.

## The in-game test (open questions 1, 2 and 4)

`releases/kaepora-test.zip` is Core in `subsdk1` and Hello in `subsdk2`, plus Core's `.ips`.

1. Turn off any other mod folder that has an `exefs/subsdk1` (older Mouse Grab builds).
2. Copy the zip's `0400486024DEC000` folder into the emulator's `load` folder, close and reopen
   the emulator, start the game.
3. What should happen: a small blue square near the top left corner, which turns green while A is
   held. In the log, `kaepora: Core 0.2 loaded`, then `kaepora [kaepora.hello]: hello from its own
   start` and a list of what works, then an `alive:` line every 300 frames with rising counts.

What each outcome means:

| You see | It means |
|---|---|
| The square and Hello's log lines | rtld links an added module to another one. Mods can be separate modules (question 1: yes) |
| `Core 0.2 loaded` but `kaepora mod: Kaepora Core isn't loaded` and no square | rtld loaded both but didn't link them (question 1: no). Mods get bundled into Core's module instead: `--bundle` |
| The game doesn't start | Something in the new Core stops it. Try `releases/mouse-grab-on-core-0.2.zip` (Core and Mouse Grab in one module): if that starts, the second module is the problem; if not, look first at Core's new input hooks |
| `input: 0 of 5 controller styles hooked` | The system's names for the controller functions aren't the ones Core guessed; the log line says which part is missing |

The order of `Core 0.2 loaded` and the mod's first line also answers question 2 (who starts
first); either order works.
