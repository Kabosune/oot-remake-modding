# The world: time of day, weather, wind

What the game's world manager (WorldMgr) does with the time of day, the weather and the wind, and
the functions [World Tools](../mods/world-tools/README.md) calls. Found 17 November 2026 by
reading `main` and the romfs; addresses are module offsets of `main` (1.1.1 build E0F3CCFA unless
said otherwise), the same as `symbols/*.toml`. Research by KaboWabo/Kabosune (me :3) with AI
assistance (Claude Opus 5.5).

**Labels:** **checked** = read in `main`'s code or the romfs files (17 Nov); **guess** = not confirmed, says why it's likely. Nothing here has been tried in the game yet.

## Where the world state lives

- **WorldMgr** (checked): one object, 0x40D8 bytes, made by `0xF93A70` and kept in the pointer variable **`0x4E7EAB0`** (1.0.0: `0x4E0E668`, ported by `tools/port_pack.py`, 37 of 40 references agree). `[0x4E7EAB0]` = the WorldMgr. The game's event nodes reach it through the GOT entry `0x4C7E898`, which points at that variable.
- **Its read-only face** (checked): `[wm+0x578]` is an object whose virtual functions answer questions: slot `+0x30` returns the **world time in seconds** (the game takes it mod 86,400 for the time of day: hour = s / 3600, minute = s % 3600 / 60; so the value may count days too), slot `+0xF0` returns the **current weather** as a number 0–4 (what each number means: not checked; the game's `QueryWeather` node returns it).
- **Requests** (checked): the setters below don't change the world at once; they lock a mutex at `wm+0x490` and write a request into one of two 0x11A0-byte blocks at `wm+0xDE8` (`wm+0x3128` picks the block), with flag bits at the block's start. WorldMgr applies them on its next update. So they are made to be called from anywhere at any time (guess from the lock and the double buffer; that a mod can call them from Core's `frame` event is not tested).
- **Time in the save** (checked): on load, WorldMgr reads the time from unnamed GameData fields: **UInt64 `0xEF10B80F`** (low 32 bits = the seconds passed to the time setter, high 32 bits = its last argument), UInt `0x3F8D9D86` and Float `0x46920F1B` (`0x345DF40`, `0x345DEE0`, called from `0x3425090`). No GameData field with a readable name holds the time (checked: every string in `main` hashed with MurmurHash3, and sloperinaGZ's 7,161 recovered names: no match). So the live time is WorldMgr's, and the save only matters at load.

## Time of day

- **Setting it (checked):** the event action `ExecuteWmSetTime` (inputs `TimeHour`, `TimeMin`) does exactly `WmSetTime(wm, hour * 3600 + min * 60)`, **`0x34522D0`** (1.0.0 `0x33F1580`). That one is 5 instructions: it calls the time object at `[wm+0x510]` with `0xEEE640(timeobj, seconds, 1, -1)`, which stores the target time at `+0x48` and sets request bits at `+0x08`. The same action is very likely what the Sun's Song and the "wait until night" events use (guess: not traced which flowcharts call it).
- **Reading it (checked):** `[[wm+0x578]]` slot `+0x30`, see above. The game's `QueryWorldGetCurrentTime` (outputs `Hour`, `Minute`) and the sequence query `SeqQueryGetCurrentTime` both do exactly this.
- **Day / night:** there's no separate switch; it's the time. The area's `WorldParam` (romfs `WorldMgr/WorldParam/*.bgyml`, checked) sets sunrise / sunset (`SunriseHoure` 4, `SunsetHoure` 18 for the fixed fields; child Hyrule Field differs), whether the sun and moon move (`IsSolarMotion`), and the palettes per time (`ResEnvPaletteTimeTable`, in `Pack/EnvPalette.pack`). Indoor areas use `IndoorFixedEnvPalette` (a fixed look), so changing the time there likely shows nothing (guess). Night spawns (Stalchildren etc.) and NPC schedules follow the time in the original; whether they switch at once after a jump is a guess.
- **Stopping the clock / time speed:** the game has three built-in ways (all checked as data / names, none traced to the live clock):
  - the scene's `GameBancParam.IsEnableTimerCounting` (false in dungeons: the clock doesn't run there),
  - an event's `IsWorldTimeStop` (event setting, field `+0x4B` of the event param struct, parsed in `0x2BD5290`),
  - `ExecuteWmSetTimeTransitionForTimeline` → **`WmSetTimeRateForEvent` `0x3454AA0`** (1.0.0 `0x33F3D50`): start time, end time, a float rate and a flag, written as a request (block `+0x10E4..+0x10F8`, flag bit 25). That's the cutscene time-lapse.
  - **Not found:** where the running clock and its "is counting" flag / speed sit in the time object. Time object fields seen: `+0x08` flags, `+0x48` / `+0x4C` the set-time request, `+0x6C` time at load, `+0x74` / `+0x78` two floats set to 1.0 at load (a speed is a guess). Finding the clock needs either more code reading or one probe build that logs these fields while time passes (the cheaper way).
  - Fallback that needs nothing new: hold the time by calling `WmSetTime` again whenever it drifts (e.g. once per game minute). Side effects unknown: each call also builds a ~4 KB notification in `0xEEE640` (what listens is not traced; NPC schedules or palette fades may restart).

## Weather

- **Setting it (checked):** `OneShotWmSetWeatherForFlowchart` (inputs `Weather`, `IsImmTrans`, `ChangeSpeed`) calls **`WmSetWeather(wm, &name, speed)` `0x3454FB0`** (1.0.0 `0x33F4260`), with `speed = 5` when `IsImmTrans`. `name` is a pointer to a `const char *`; the callee keeps the part after the last `/` and builds `Work/WorldMgr/ResWeatherInfluenceParam/%s.game__wm__ResWeatherInfluenceParam.gyml` (`0x1177030`), so a short name like `"Rainy"` is enough.
- **Back to the area's own (checked):** `OneShotWmResetWeatherForFlowchart` → **`WmResetWeather(wm, speed)` `0x3455120`** (1.0.0 `0x33F43D0`).
- **The 12 weathers** (checked, `Pack/EnvPalette.pack`, `WorldMgr/ResWeatherInfluenceParam`): `Default` (clear), `Cloudy`, `Rainy` (`IsRain`), `Thunderstorm` (rain, `FogDensity` 5, darker), `Snowy` (wind 5.5), and area variants `Cloudy_Ash`, `GanonCloudy`, `GanonRainy`, `Kokiri`, `Rainy_Graveyard`, `Thunderstorm_Graveyard`, `ZoraDomain`. Each sets fog density, colour, cloud alpha, rain exposure (wet look), the palette family (`SelectTimePaletteType`) and the effect (`WeatherEffect`: rain / snow particles). That pack is in the romfs as one file the game likely keeps loaded (guess).
- **How areas pick weather (checked):** each `WorldParam` has `WeatherData.WeatherFileName` plus an optional `WeatherWorldSetting` list of (GameData condition → weather), e.g. adult Kakariko: `Cloudy`, `Thunderstorm` after `HavePlayedEvent.Dm_Kakariko_0030`, clear after the Shadow Sage. No area uses `Rainy` by default: rain comes from the Song of Storms (`SongOfTheStormDurationFrame`, `SongOfTheStormRandomTime` in `main`) and events. So a chosen weather is likely replaced on the next area change (guess), and the mod would set it again after each load.
- **Fog / sky:** no separate setter used yet. Fog comes with the weather (`FogDensity`; Thunderstorm is the foggy one) and the palettes. `ExecuteWmSetEnvPaletteForFlowchart` (inputs `EnvPaletteName`, `EnvTimeTableName`, `ChangeSpeed`; 191 palettes in the pack) could set a whole look by name, but it goes through another manager (`0x2890150`, not traced). Lightning on its own: `OneShotWmThunderOneShot` (input `PatternKey`) needs the calling actor's context, harder; Thunderstorm weather brings lightning anyway (guess).

## Wind (checked)

`ExecuteWmSetWindForFlowchart` (inputs `Azimuth`, `Elevation`, `Speed`, `IsImmTrans`) → **`WmSetWind(wm, imm, azimuth, elevation, speed)` `0x3455190`** (1.0.0 `0x33F4440`); `ExecuteWmResetWindForFlowchart` → **`WmResetWind(wm, imm)` `0x3455250`** (1.0.0 `0x33F4500`). Areas set `MinWindSpeed` / `MaxWindSpeed` (1.5–5.5) in `WorldParam`; what visibly follows the wind (grass, cloth, clouds, fog noise `WindScale`) is a guess.

## Also seen, not followed

`ExecuteWmSetLunarAgeForTimeline` (moon phase), `ExecuteWmSetCloudShape`, `ExecuteWmSetSunMoonModelInvisibleForTimeline`, `ExecuteWmSetDisableLensFlare`, `WmThunderMgr`, `game__wm__WmGlobalParam` (`RainFullWetTime` 30, `FullDryTime` 40, lightning curves, fishing prime times), `IsWorldTimeStop`, `QueryTimeDivision` (morning / day / ... as a number).

## The pack names (Core 0.8.6)

All 1.1.1 offsets above ported to 1.0.0 with `tools/port_pack.py` (8 of 8 matched uniquely, 17 Nov). New pack names (a Core release, third number): global `WorldMgrPtr`; functions `WmSetTime`, `WmSetWeather`, `WmResetWeather`, `WmSetWind`, `WmResetWind` (and later `WmSetTimeRateForEvent` if speed goes that way); fields `WorldMgr.state` (`0x578`) and the two virtual slots (`WorldState.time` `0x30`, `WorldState.weather` `0xF0`). Field offsets are the same in both builds as far as the ported functions show (their code matched with offsets unmasked).

## How it was found (for redoing it)

Strings in `main` (`strings -n 4`) → the event-node classes (`ExecuteWm*`, `OneShotWm*`, `QueryWorld*`): each node's vtable has a name getter (slot 12, `adrp`+`add`+`ret`), the input binder (slot 21, names its inputs) and the execute function (slot 22, or slot 32 for `OneShot` nodes). The execute functions call the WorldMgr functions directly. Tools: a numpy `adrp` cross-reference finder, a data-pointer finder and capstone (scratch, PC shell `$HOME/tools`). Romfs: `tools/zstool.py cat` / `x` on `WorldMgr/WorldParam`, `GameParameter/WmGlobalParam`, `Pack/EnvPalette.pack.zs` (the extracted 1.1.1 romfs next to the `.nup`).
