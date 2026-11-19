# World Tools

The time of day, the weather and the wind for the Ocarina of Time remake, running on
[KaeGae Core](../../api/README.md): a clock on screen, set the time (or jump to day / night),
pick any of the game's 12 weathers, and set the wind.

**Status, 18 November 2026: version 0.1.0 works in Fritchii on game 1.1.1** (the clock, Set time,
the weathers and the wind; run on KaeGae Core 0.9.0, which has its names). **0.1.1 (18 November)
works too and fixes "Keep after loading"**: 0.1.0 never noticed a new area (it watched Link's
actor, which the game keeps across areas); 0.1.1 watches WorldMgr's state object. The area's own
weather still shows for about a second after you arrive, then yours comes back. It asks Core for
the game by name, so it should run on 1.0.0 too (not tried).

**Needs KaeGae Core 0.8.6 or later** (the first Core with the names it asks for). The
[kaegae-core.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/kaegae-core.zip)
download is 0.9.0 (18 November), which has them. On an older Core World Tools loads, says in the
log that this Core doesn't know the world's names, and does nothing.

Download: [world-tools.zip](https://github.com/Kabosune/oot-remake-modding/raw/main/releases/world-tools.zip).

## Settings

| Setting | Default | What it does |
|---|---|---|
| Show clock | on | The time of day on screen, hours:minutes (24 hours) |
| Clock corner | Top right | Where it sits |
| Clock size | 2 | Text size, 1 to 4 |
| Show weather number | off | The game's own number for the current weather next to the clock: 0 clear, 1 rain, 2 snow, 3 thunderstorm, 4 cloudy (the area kinds count as their family: Kokiri and Zora's Domain 0, the rains 1, the storms and Ganon rain 3, Ash and Ganon clouds 4) |
| Hour, Minute | 12:00 | For Set time |
| Set time | | Sets the time of day to the hour and minute above |
| Jump to day / Jump to night / One hour later | unbound | Bindings: 12:00, 0:00, an hour on |
| Weather | Rain | Clear, Cloudy, Rain, Thunderstorm, Snow, and the area kinds the game has: Kokiri (damp), Ash clouds, Graveyard rain, Graveyard storm, Ganon clouds, Ganon rain, Zora's Domain |
| Change speed | 5 | How fast the weather changes, for Set weather and Area's own weather: 0 = a slow fade, 3 = fast, 5 = at once (what the game itself uses for an instant change) |
| Set weather / Area's own weather | | Change it / give it back to the area |
| Wind direction, elevation, strength | 0°, 0°, 8 | Degrees, degrees, and the strength in the units the game's areas use (0.5 to 10) |
| Wind changes at once | on | Off: it blends over |
| Set wind / Area's own wind | | Change it / give it back to the area |
| Keep after loading | off | Sets your weather and wind again a second after each new area loads (areas pick their own), then checks the weather for ten seconds and sets it again if the area changed it |

All on the mod's page in the Mods menu (- and + together). Settings are saved between runs by Core.

## Good to know

- Indoors and in dungeons the look doesn't follow the clock (those areas have a fixed palette),
  and dungeons stop the clock. Set the time outdoors, e.g. Hyrule Field.
- Each area picks its own weather (some by story progress, like Kakariko's storm). A weather you
  set is probably replaced when you go to another area: that's what Keep after loading is for.

## How it works

One C file, [world_tools.c](world_tools.c), on the public API only. It calls the same functions
the game's own event actions call (`ExecuteWmSetTime`, `OneShotWmSetWeatherForFlowchart`,
`ExecuteWmSetWindForFlowchart` and their resets), and reads the time and weather the way the
game's `QueryWorldGetCurrentTime` / `QueryWeather` nodes do. Core gives it their addresses by name
(`WorldMgrPtr`, `WmSetTime`, `WmSetWeather`, `WmResetWeather`, `WmSetWind`, `WmResetWind`,
`WorldMgr.state`, `WorldState.time_slot`, `WorldState.weather_slot`). Those functions queue a
request that the game's world manager applies on its next update; the mod calls them from Core's
frame event. "Keep after loading" notices a new area by WorldMgr's state object changing (the
game makes a new one with each area's `WorldParam`), then compares the game's weather number
(0 clear, 1 rain, 2 snow, 3 thunderstorm, 4 cloudy) with the one it chose.

Stopping the clock or changing its speed isn't in yet: the running clock itself hasn't been found
in the game's code.

## Install

```
python3 tools/kaegae.py install releases/kaegae-core.zip world-tools.zip
```

or copy both folders into the emulator's mod folder for the game by hand (if another mod already
uses `subsdk2`, rename this one's `exefs/subsdk2` to a free `subsdk3` ... `subsdk9`).

## Credits

- KaboWabo/Kabosune (me :3): idea, direction, in-game testing
- AI assistance (Claude Opus 5.5)
