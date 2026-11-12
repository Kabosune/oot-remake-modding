# Moon Jump

Low gravity, bigger jumps and a hold-to-fly button for the Ocarina of Time remake, running on
[KaeGae Core](../../api/README.md).

**Status, 11 November 2026: version 0.1.0, works in Fritchii (KaeGae Core 0.6, game 1.1.1).** It also passes the module
tests (`tests/test_kaegae_modules.py`). Game version 1.1.1 only (Core has no 1.0 symbol pack yet).

## What it does

| Setting | Default | What it does |
|---|---|---|
| Gravity (%) | 40 | How hard Link falls. 100 is the game's own. |
| Jump boost (%) | 130 | How much faster a jump starts going up. 100 is the game's own. |
| Moon jump (hold) | L + A | Link flies straight up while held. The game doesn't see the combination. |
| Moon jump speed | 6 | Metres a second upward while held. |
| Top falling speed | 0 | Metres a second; 0 leaves it to the game. |

Everything is on the mod's page in the Mods menu (- and + together), and the mod can be switched
off there. Settings are saved between runs by Core.

## How it works

One C file, [moon_jump.c](moon_jump.c), on the public API only. Every one of Link's movement
updates (`kae_on_player_move`) it reads his velocity (`kae_player_velocity`). It doesn't know the
game's gravity: it looks at how much his upward speed dropped since the last update and lets only
part of that drop through (`kae_player_set_velocity`). A rise of more than 2 m/s in one update is
taken as a jump starting and boosted. Other rises (a ledge hop, landing) pass through as they are.

Fall damage is the game's: a long low-gravity fall still ends in a hard landing if he lands fast,
and the moon jump can carry him high enough to get hurt when he's let go. Use Top falling speed
to soften that.

## Install

```
python3 tools/kaegae.py install releases/kaegae-core.zip releases/moon-jump.zip
```

or copy both zips' folders into the emulator's mod folder for the game by hand (if another mod
already uses `subsdk2`, rename this one's `exefs/subsdk2` to a free `subsdk3` ... `subsdk8`).

## Credits

- KaboWabo/Kabosune (me :3): idea, direction, in-game testing
- AI assistance (Claude Opus 5.5)
