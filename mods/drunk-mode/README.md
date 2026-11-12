# Drunk Mode

The controls go wrong on purpose, for the Ocarina of Time remake, running on
[KaeGae Core](../../api/README.md). The movement stick's direction sways back and forth, and
sticks and buttons can be mirrored, flipped or swapped.

**Status, 11 November 2026: version 0.1.0, works in Fritchii (KaeGae Core 0.6, game 1.1.1).** It also passes the module
tests (`tests/test_kaegae_modules.py`). It doesn't need anything of the game beyond the
controllers, so it should run wherever Core runs.

## Settings

| Setting | Default | What it does |
|---|---|---|
| Wobble (%) | 40 | How far the stick's direction sways; 100 is a quarter turn each way, 0 is off |
| Wobble speed | 3 | 1 to 10 |
| Wobble the camera too | off | The right stick sways the other way |
| Mirror movement | off | Left on the stick is right |
| Flip movement | off | Up on the stick is down |
| Mirror camera | off | |
| Flip camera | off | |
| Swap sticks | off | Move with the right stick, look with the left |
| Swap A and B | off | |

All on the mod's page in the Mods menu (- and + together). The Mods menu itself is never affected,
and Drunk Mode can be switched off there in one press. Settings are saved between runs by Core.

## How it works

One C file, [drunk_mode.c](drunk_mode.c), on the public API only: it changes what the game is
handed in the input event (`kae_on_input`). The wobble turns the stick without changing how far
it's pushed, so a stick at rest stays at rest. It mixes two sways at different speeds so it
doesn't feel like a metronome.

## Install

```
python3 tools/kaegae.py install releases/kaegae-core.zip releases/drunk-mode.zip
```

## Credits

- KaboWabo/Kabosune (me :3): idea, direction, in-game testing
- AI assistance (Claude Opus 5.5)
