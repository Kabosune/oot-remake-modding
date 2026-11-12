# Speedometer

How fast Link is going, for the Ocarina of Time remake, running on
[KaeGae Core](../../api/README.md): a big number, a bar that goes from green to red, his top speed,
and how fast he is rising or falling.

**Status, 11 November 2026: version 0.1.0, works in Fritchii (KaeGae Core 0.6, game 1.1.1).** It also passes the module
tests (`tests/test_kaegae_modules.py`). Game version 1.1.1 only.

## Settings

| Setting | Default | What it does |
|---|---|---|
| Units | km/h | m/s, km/h or mph |
| Corner | Bottom right | Where it sits on the screen |
| Size | 2 | Text size, 1 to 4 |
| Bar full at (m/s) | 12 | The speed that fills the bar |
| Count falling | off | Off: only speed along the ground. On: falling counts too |
| Show top speed | on | The fastest since the last reset (gold while he's at it) |
| Show rise / fall | on | `^` going up, `v` coming down (blue) |
| Reset top speed | | Sets the top speed back to 0 |

All on the mod's page in the Mods menu (- and + together). Settings are saved between runs by Core.

## How it works

One C file, [speedometer.c](speedometer.c), on the public API only. Each of Link's movement
updates (`kae_on_player_move`) it measures how far he moved since the last one and multiplies by
30, the game's updates a second (the same rate Slopped Up Sloperina's position watch uses, not
measured by this mod). A move of more than 50 m in one update is a warp or a reload and is left
out. The number is lightly smoothed so it doesn't flicker. It shows `--` when Link isn't moving
in the world (cutscenes, loading).

It fits next to Slopped Up Sloperina: Sloperina's display is bottom left, this one bottom right.

## Install

```
python3 tools/kaegae.py install releases/kaegae-core.zip releases/speedometer.zip
```

## Credits

- KaboWabo/Kabosune (me :3): idea, direction, in-game testing
- AI assistance (Claude Opus 5.5)
