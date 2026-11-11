# Scenes, scene changes and spawn points

Read from the romfs of build 1.1.1 (11 November 2026). **Nothing here has been tried in game**; what a field does is
inferred from its name and from how the data fits together, unless said otherwise. How to look inside these files:
[romfs.md](romfs.md).

## The pieces

| Piece | File | What it holds |
|---|---|---|
| Scene list | `RSDB/GameBancInfo.Product.111.rstbl.byml.zs` | 81 rows: `__RowId` (scene name), `BancMain` (`Work/Banc/Scene/<Area>/<Scene>.bcett.json`), `SoundSceneryName` (Japanese area name) |
| Scene settings | `Banc/GameBancParam/<Scene>.game__banc__GameBancParam.bgyml` (80) | `AreaIndex`, `Banc.Main`, `DungeonParam`, `IsChildWhenChangeBanc`, `IsForceSwitchChildOrAdult`, `OptimizeChangeBancUnits`, light / bake / sound / world-map settings. Many files inherit through `$parent` (Adult → Child; boss stages → their dungeon; see [tuning.md](tuning.md)) |
| Placement | `Banc/<Area>/<Scene>_Static.bcett.byml.zs`, `..._Dynamic...` | `Actors`: every actor in the scene (`Gyaml` = actor name, `Translate` / `Rotate` / `Scale`, `Dynamic` = per-instance parameters, `Links`, `Presence` = a game-data flag that decides if it exists) |
| Spawn points | `AoC1/Banc/BancBasedResource/StartPos.byml.zs` | `<Scene>` → `<start position name>` → `Trans` (x, y, z) and `Rot` (x, y, z radians). 92 scenes, 465 positions (table below) |

Scene names: areas come as `_Child` / `_Adult` pairs (plus `KakarikoVillage_Adult_Alternative`,
`ZoraDomain_Adult_Alternative`), dungeons are single scenes with an `_MQ` twin (Master Quest; 12 in `StartPos.byml`), and
`DreamWorld` holds the boss / enemy rematch stages. `StartPos.byml` has one key per scene, `_MQ` ones included, so
the MQ twins are complete scenes with their own spawn points.

## How a scene change is placed: `FieldAndDungeonEntranceEventRequestActor`

167 placements in the `Banc/` files (161 with a destination). The destination is in the actor's `Dynamic`:

| Field | Count | Meaning (from values) |
|---|---|---|
| `NextBancParamNameAdult` / `NextBancParamNameChild` | 161 | the scene to load, by `GameBancParam` name, for adult / child Link. They differ in 131 of 161 (the `_Adult` / `_Child` pair), are equal for dungeons and similar |
| `NextStartPosName` | 161 | a start position name. **All 161 are found in `StartPos.byml` under the destination scene's key** (adult or child; none missing) |
| `FirstEventName` | 161 | event played when leaving (20 distinct; `Dm_SY_BancChangeGo` for 99, `..._LostWood` 18, `..._UnderWater` 7, ...) |
| `NextEventName` | 161 | event played on arrival (62 distinct; `Dm_SY_BancChangeArrive` 38, `..._Kokiri` 18, special ones like `Get_StoneOfFire_ArriveFromGoronCity`) |
| `InitEventName` + `InitEventFlag` | 53 | an extra first-time event (e.g. `Goto_FireTemple` with flag `HavePlayedEvent.Goto_FireTemple`) |
| `AddEventName` + `AddEventFlag` | 16 | another conditional event |
| `IsAlternativeGameDataBool` | 14 | a game-data bool that picks the `_Alternative` scene (e.g. `Sequence_IsAlternative_KakarikoAdult`) |
| `IsNoDisplayMapIcon` 23, `IsChangableAirPos` 19, `IsEventStarterCandidate` 1 | | flags |

Example, from `BottomOfTheWell_Static`, actor `Well_KakarikoSide`: leave with `Dm_SY_BancChangeGo_KakarikoVillage`,
go to `KakarikoVillage_Adult` / `KakarikoVillage_Child` at start position `Kakariko_WellSide`, play
`Dm_SY_BancChangeArrive`.

So **a warp is a pair: scene name + start position name**; coordinates come from `StartPos.byml` (table below).
Whether the game also needs the events to run (cutscene state, fade) when a module requests the change is not known.

Related actors in the same files: `AbilityChangeAreaForSceneChange` (173 areas), `ChangeBancBeforehandAnchor` (174;
its placement name reads "the anchor that serves as reference coordinate for pre-loading"),
`ForbidSetWarpPointArea` (6; areas where a warp point can't be set), `FixedEnvPaletteChangeArea`,
`EnvPaletteTimeTableChangeArea`, `IndoorAreaBox`, `CameraChangeAreaBox`.

### In `GameBancParam`

- `AreaIndex`: a number per area (the Adult / Child twins share one; the boss and rematch stages seen have 0; e.g. Kokiri Forest
  20, Death Mountain Trail 4, Fire Temple 7).
- `OptimizeChangeBancUnits` (78 of 80 scenes): a list of neighbouring scenes, each with `BancParamName`,
  `BancResourcePath`, `BasePos` (two vectors), `HasMQ` and `LoadRadius` (70 for the Deku Tree entry in Kokiri
  Forest). Looks like the preload list for the next scenes (compare `ChangeBancBeforehandAnchor`); not verified.
- `IsChildWhenChangeBanc` / `IsChildWhenInitializingScene` (30 scenes, mostly `False`) and `IsForceSwitchChildOrAdult`
  (20): age handling on scene change; values not tabulated.

## Spawn points (`StartPos.byml`)

465 rows. `x y z` = `Trans`, `yaw` = `Rot` y in radians. Names starting with `StartPos_SubEvent_AllBossBattle` (26) are the
boss-rush entries, `StartPos_SageOf...` (13) the sage rooms, `ReturnFromDream...` (12) the way back from a rematch
stage, `StartPos_Get_StoneOf...` and `StartPos_Defeat_...` follow story events; most of the rest are named for the door or the
side of an area they come from (`Kakariko_WellSide`, `GoronCity_CraterSide`).

| scene | start position | x | y | z | yaw |
|---|---|---|---|---|---|
| BarinadeStage | BarinadeStage | 42.4 | 102.0 | -98.1 | -0.01 |
| BarinadeStage | StartPos_SubEvent_AllBossBattle | 42.4 | 102.0 | -98.2 | -0.05 |
| BigOctoStage | BigOctoStage | -26.7 | 84.9 | -89.8 | -1.57 |
| BigOctoStage | StartPos_SubEvent_AllBossBattle | -30.1 | 84.9 | -99.8 | 0.79 |
| BongoBongoStage | BongoBongoStage | -138.3 | -11.5 | 22.0 | -0.00 |
| BongoBongoStage | StartPos_SageOfShadow | -138.3 | -11.5 | 22.0 | -0.00 |
| BongoBongoStage | StartPos_SubEvent_AllBossBattle | -138.3 | -11.5 | 22.1 | -0.00 |
| BossRushIntervalRoom | BossRush | 0.0 | 0.0 | 4.3 | -0.00 |
| BossRushIntervalRoom | StartPos_SubEvent_AllBossBattle | 0.0 | 0.0 | 4.2 | -0.00 |
| BottomOfTheWell |  | -0.0 | 106.0 | 40.4 | 0.00 |
| BottomOfTheWell | EntrancePos | -0.0 | 106.0 | 42.4 | -0.00 |
| BottomOfTheWell | StartPos_SubEvent_GetStormSong | 3.6 | 92.4 | -97.2 | -0.00 |
| BottomOfTheWell | StartPos_SubEvent_GetStormSong_BeforeBossRoom | 0.1 | 102.2 | -93.0 | -0.00 |
| BottomOfTheWell | Well_KakarikoSide | -0.0 | 106.0 | 45.5 | -0.00 |
| BottomOfTheWell_MQ |  | -0.0 | 106.0 | 40.4 | 0.00 |
| BottomOfTheWell_MQ | EntrancePos | -0.0 | 106.0 | 42.4 | -0.00 |
| BottomOfTheWell_MQ | Well_KakarikoSide | -0.0 | 106.0 | 45.5 | -0.00 |
| CrumblingGanonCastle |  | -6.3 | 230.3 | 0.0 | -1.49 |
| CrumblingGanonCastle | BackEntrance | -95.4 | 166.8 | -0.0 | 1.57 |
| CrumblingGanonCastle | CrumblingGanonCastle_StartPos | -6.6 | 230.3 | -0.0 | -1.54 |
| CrumblingGanonCastle | EntrancePos | -95.4 | 166.8 | -0.0 | 1.57 |
| CrumblingGanonCastle | RestartPos1 | 12.2 | 213.7 | 0.0 | -1.51 |
| CrumblingGanonCastle | RestartPos2 | -26.7 | 193.0 | -26.2 | 0.70 |
| CrumblingGanonCastle | RestartPos3 | -0.1 | 191.9 | -4.1 | -0.00 |
| CrumblingGanonCastle | RestartPos4 | 0.1 | 191.9 | 15.7 | -0.00 |
| CrumblingGanonCastle | RestartPos5 | 34.8 | 180.6 | 10.7 | 0.41 |
| CrumblingGanonCastle | RestartPos6 | -0.2 | 173.1 | 25.0 | -0.01 |
| CrumblingGanonCastle | RestartPos7 | -74.5 | 167.0 | -0.0 | -1.56 |
| CrumblingGanonCastle | RestartPos_Ganondorf_BossBattle | -5.1 | 230.3 | 0.3 | -1.57 |
| CrumblingGanonCastle | StartPos_Defeat_Ganon | -15.9 | 230.0 | 0.0 | -1.57 |
| DarkLinkStage | DarkLinkStage | -77.9 | 125.5 | -75.8 | -0.00 |
| DarkLinkStage | StartPos_SubEvent_AllBossBattle | -77.9 | 125.5 | -75.8 | 0.00 |
| DeadHandStage | DeadHandStage | -0.0 | 92.4 | -104.4 | -0.00 |
| DeadHandStage | StartPos_SubEvent_AllBossBattle | -0.0 | 92.4 | -104.4 | -0.00 |
| DeathMountainCrater_Adult |  | 16.5 | 131.9 | 59.4 | -0.52 |
| DeathMountainCrater_Adult | Crater_GoronCitySide | -55.5 | 120.4 | -19.8 | 1.12 |
| DeathMountainCrater_Adult | Crater_MountainTrailSide | 16.5 | 131.9 | 59.4 | -0.56 |
| DeathMountainCrater_Adult | EntrancePos_FireTemple | 0.6 | 113.0 | -30.7 | -0.00 |
| DeathMountainCrater_Adult | EntrancePos_GoronCity | -55.5 | 120.4 | -19.8 | 1.12 |
| DeathMountainCrater_Adult | EntrancePos_MountainTrail | 16.5 | 131.9 | 59.4 | -0.56 |
| DeathMountainCrater_Adult | FireBolero | 0.4 | 111.7 | -8.7 | 0.00 |
| DeathMountainCrater_Adult | OutsideOfFireTemple | 0.6 | 113.0 | -30.7 | -0.00 |
| DeathMountainCrater_Child |  | 16.5 | 131.9 | 59.4 | -0.52 |
| DeathMountainCrater_Child | Crater_GoronCitySide | -55.5 | 120.4 | -19.8 | 1.12 |
| DeathMountainCrater_Child | Crater_MountainTrailSide | 16.5 | 131.9 | 59.4 | -0.56 |
| DeathMountainCrater_Child | EntrancePos_FireTemple | 0.6 | 113.0 | -30.7 | -0.00 |
| DeathMountainCrater_Child | EntrancePos_GoronCity | -55.5 | 120.4 | -19.8 | 1.12 |
| DeathMountainCrater_Child | EntrancePos_MountainTrail | 16.5 | 131.9 | 59.4 | -0.56 |
| DeathMountainCrater_Child | FireBolero | 0.4 | 111.7 | -8.7 | 0.00 |
| DeathMountainCrater_Child | OutsideOfFireTemple | 0.6 | 113.0 | -30.7 | -0.00 |
| DeathMountainTrail_Adult |  | -31.3 | 90.4 | 65.4 | -0.81 |
| DeathMountainTrail_Adult | DodongoCavernFront | -42.2 | 110.8 | -3.9 | -0.00 |
| DeathMountainTrail_Adult | EntrancePos | -31.4 | 90.5 | 65.3 | -0.92 |
| DeathMountainTrail_Adult | MountainTrail_CraterSide | -0.1 | 206.4 | -154.5 | 0.02 |
| DeathMountainTrail_Adult | MountainTrail_DodongoCavernSide | -44.3 | 109.7 | -17.6 | 0.37 |
| DeathMountainTrail_Adult | MountainTrail_GoronCitySide | -10.6 | 118.1 | -53.2 | 0.00 |
| DeathMountainTrail_Adult | MountainTrail_KakarikoSide | -31.4 | 90.5 | 65.3 | -1.05 |
| DeathMountainTrail_Child |  | -31.3 | 90.4 | 65.4 | -0.81 |
| DeathMountainTrail_Child | DodongoCavernFront | -42.2 | 110.8 | -3.9 | -0.00 |
| DeathMountainTrail_Child | EntrancePos | -31.4 | 90.5 | 65.3 | -0.92 |
| DeathMountainTrail_Child | MountainTrail_CraterSide | -0.1 | 206.4 | -154.5 | 0.02 |
| DeathMountainTrail_Child | MountainTrail_DodongoCavernSide | -44.3 | 109.7 | -17.6 | 0.37 |
| DeathMountainTrail_Child | MountainTrail_GoronCitySide | -10.6 | 118.1 | -53.2 | 0.00 |
| DeathMountainTrail_Child | MountainTrail_KakarikoSide | -31.4 | 90.5 | 65.3 | -1.05 |
| Demo_ShootingLocation_Tapestry_ED |  | 0.1 | 0.2 | 0.1 | -0.00 |
| Demo_ShootingLocation_Tapestry_ED | Ending | 0.1 | 0.2 | 0.1 | -0.00 |
| DesertColossus_Adult |  | -3.0 | 100.1 | -0.0 | -1.51 |
| DesertColossus_Adult | DesertColossus_FromHountedWasteland | -3.0 | 100.1 | -0.0 | -1.51 |
| DesertColossus_Adult | DesertColossus_FromSpiritTempleEntrance | -159.3 | 96.2 | 10.3 | 1.55 |
| DesertColossus_Adult | DesertColossus_FromSpiritTempleLeftHand | -164.5 | 112.7 | -11.8 | 0.00 |
| DesertColossus_Adult | DesertColossus_FromSpiritTempleRightHand | -164.5 | 112.7 | 32.5 | 0.00 |
| DesertColossus_Adult | EntrancePos | 19.3 | 100.0 | -0.1 | 1.51 |
| DesertColossus_Adult | SpiritRequiem | -126.0 | 94.4 | 10.5 | -1.57 |
| DesertColossus_Child |  | -3.0 | 100.1 | -0.0 | -1.51 |
| DesertColossus_Child | DesertColossus_FromHountedWasteland | -3.0 | 100.1 | -0.0 | -1.51 |
| DesertColossus_Child | DesertColossus_FromSpiritTempleEntrance | -159.3 | 96.2 | 10.3 | 1.55 |
| DesertColossus_Child | DesertColossus_FromSpiritTempleLeftHand | -164.5 | 112.7 | -11.8 | 0.00 |
| DesertColossus_Child | DesertColossus_FromSpiritTempleRightHand | -164.5 | 112.7 | 32.5 | 0.00 |
| DesertColossus_Child | EntrancePos | 19.3 | 100.0 | -0.1 | 1.51 |
| DesertColossus_Child | SpiritRequiem | -126.0 | 94.4 | 10.5 | -1.57 |
| DinolfosStage | DinolfosStage | -54.6 | 70.8 | 1.5 | -1.27 |
| DinolfosStage | StartPos_SubEvent_AllBossBattle | -54.6 | 70.8 | 1.5 | -1.27 |
| DodongoCavern |  | 0.0 | 102.4 | 41.0 | -0.00 |
| DodongoCavern | DodongoCavern_MountainTrailSide | 0.0 | 102.4 | 41.0 | -0.00 |
| DodongoCavern | EntrancePos | 0.0 | 102.4 | 41.0 | -0.00 |
| DodongoCavern | StartPos_Get_StoneOfFire | 24.0 | 73.4 | -77.6 | 1.57 |
| DodongoCavern_MQ |  | 0.0 | 102.4 | 41.0 | -0.00 |
| DodongoCavern_MQ | DodongoCavern_MountainTrailSide | 0.0 | 102.4 | 41.0 | -0.00 |
| DodongoCavern_MQ | EntrancePos | 0.0 | 102.4 | 41.0 | -0.00 |
| DodongoCavern_MQ | StartPos_Get_StoneOfFire | 24.0 | 73.4 | -77.6 | 1.57 |
| DodongoStage | DodongoStage | 24.0 | 73.4 | -77.5 | 1.57 |
| DodongoStage | StartPos_Get_StoneOfFire | 24.0 | 73.4 | -77.6 | 1.57 |
| DodongoStage | StartPos_SubEvent_AllBossBattle | 24.0 | 73.4 | -77.5 | 1.57 |
| EnemyMuseum | EnemyMusuem | 0.0 | 0.0 | 0.0 | 0.52 |
| FinalBattleField | FinalBattleField_Entrance | 28.2 | 100.0 | -0.8 | -1.57 |
| FinalBattleField | RestartPos_Ganondorf_BossBattle | 28.2 | 100.0 | -0.8 | -1.57 |
| FinalBattleField | StartPos_Defeat_Ganon | 28.2 | 100.0 | -0.8 | -1.57 |
| FinalBattleField | StartPos_Defeat_Ganon_InBattle | 11.7 | 100.0 | -0.1 | -1.57 |
| FireTemple |  | 0.0 | 100.0 | 23.7 | -0.00 |
| FireTemple | BossDefeat | -71.2 | 102.5 | 0.0 | -1.57 |
| FireTemple | EntrancePos | 0.0 | 100.0 | 24.5 | -0.00 |
| FireTemple | FireTemple | 0.0 | 100.0 | 24.7 | -0.00 |
| FireTemple | StartPos_SageOfFire | -64.5 | 102.5 | 0.0 | -1.57 |
| FireTemple_MQ |  | 0.0 | 100.0 | 22.5 | -0.00 |
| FireTemple_MQ | BossDefeat | -71.2 | 102.5 | 0.0 | -1.57 |
| FireTemple_MQ | EntrancePos | 0.0 | 100.0 | 23.3 | -0.00 |
| FireTemple_MQ | FireTemple | 0.0 | 100.0 | 23.5 | -0.00 |
| FireTemple_MQ | StartPos_SageOfFire | -64.5 | 102.5 | 0.0 | -1.57 |
| FlareDancerStage | FlareDancerStage | -66.6 | 148.0 | -3.9 | -0.79 |
| FlareDancerStage | StartPos_SubEvent_AllBossBattle | -66.6 | 148.0 | -3.9 | -0.79 |
| ForestTemple | EntrancePos | 0.0 | 101.5 | 78.4 | -0.00 |
| ForestTemple | ForestTemple | 0.0 | 101.5 | 78.4 | -0.00 |
| ForestTemple | StartPos_SageOfForest | -6.0 | 74.7 | -66.0 | 1.05 |
| ForestTemple | StartPos_SageOfForest_Step06 | -0.1 | 103.5 | 17.9 | -0.00 |
| ForestTemple_MQ | EntrancePos | 0.0 | 101.5 | 76.4 | -0.00 |
| ForestTemple_MQ | ForestTemple | 0.0 | 101.5 | 76.4 | -0.00 |
| ForestTemple_MQ | StartPos_SageOfForest | -5.4 | 74.7 | -65.6 | 1.05 |
| ForestTemple_MQ | StartPos_SageOfForest_Step06 | -0.1 | 103.5 | 17.9 | -0.00 |
| GanonCastle |  | 61.2 | 82.5 | 367.7 | 0.03 |
| GanonCastle | EntrancePos | 38.4 | 98.6 | 208.1 | -0.19 |
| GanonCastle | GanonCastleEntrance | 61.2 | 82.5 | 367.3 | 0.22 |
| GanonCastle | GanonCastleEntrance_FromInside | 42.3 | 98.7 | 228.6 | 0.20 |
| GanonStage | GanonStage | 11.8 | 100.1 | -1.1 | -1.57 |
| GanonStage | RestartPos_Ganondorf_BossBattle | 28.2 | 100.0 | -0.8 | -1.57 |
| GanonStage | StartPos_SubEvent_AllBossBattle | 11.7 | 100.0 | -0.1 | -1.56 |
| GanondorfStage | GanondorfStage | 0.0 | 171.0 | -11.3 | -0.00 |
| GanondorfStage | StartPos_SubEvent_AllBossBattle | 0.0 | 171.0 | -11.3 | -0.00 |
| GerudoFortress_Adult |  | -26.5 | 106.6 | -23.2 | 0.60 |
| GerudoFortress_Adult | EntrancePos | 7.8 | 110.3 | 0.1 | 0.53 |
| GerudoFortress_Adult | GerudoFortress_FromGerudoTrainingGround | 7.8 | 110.3 | 0.1 | 0.53 |
| GerudoFortress_Adult | GerudoFortress_FromGerudoValley | -26.5 | 106.6 | -23.2 | 0.63 |
| GerudoFortress_Adult | GerudoFortress_FromHountedWasteland | -31.3 | 104.9 | -105.1 | 0.72 |
| GerudoThiefStage | GerudoThiefStage | 24.5 | 102.5 | -75.1 | -0.00 |
| GerudoThiefStage | StartPos_SubEvent_AllBossBattle | 24.5 | 102.5 | -75.1 | -0.00 |
| GerudoTrainingGround | EntrancePos | -1.8 | 99.3 | -1.5 | -0.00 |
| GerudoTrainingGround | GerudoTrainingGround_FromGerudoFortress | -1.8 | 103.0 | 11.9 | -0.00 |
| GerudoTrainingGround | GerudoTrainingGround_FromGerudoFortress_Air | -1.7 | 103.0 | 11.9 | 0.00 |
| GerudoTrainingGround_MQ | EntrancePos | -1.8 | 103.0 | 11.9 | -0.00 |
| GerudoTrainingGround_MQ | GerudoTrainingGround_FromGerudoFortress | -1.8 | 103.0 | 11.9 | -0.00 |
| GerudoValley_Adult |  | 72.6 | 94.3 | 16.6 | -1.02 |
| GerudoValley_Adult | EntrancePos | 72.6 | 94.3 | 16.7 | -1.00 |
| GerudoValley_Adult | GerudoValley_Entrance | 72.6 | 94.3 | 16.6 | -1.00 |
| GerudoValley_Adult | GerudoValley_FromGerudoFortress | -62.4 | 102.6 | -6.5 | 1.52 |
| GerudoValley_Adult | GerudoValley_FromLakeHylia | 8.2 | 10.3 | 64.3 | -0.10 |
| GerudoValley_Adult | GerudoValley_FromLakeHylia_Air | 8.4 | 14.5 | 64.3 | -0.10 |
| GerudoValley_Adult | ReturnFromDreamWorld | -39.9 | 101.2 | -24.7 | 0.60 |
| GerudoValley_Adult | RunningRace_pos | -37.0 | 101.2 | -18.0 | -1.53 |
| GerudoValley_Child |  | 72.6 | 94.3 | 16.6 | -1.02 |
| GerudoValley_Child | EntrancePos | 72.6 | 94.3 | 16.7 | -1.00 |
| GerudoValley_Child | GerudoValley_Entrance | 72.6 | 94.3 | 16.6 | -1.00 |
| GerudoValley_Child | GerudoValley_FromLakeHylia | 8.2 | 10.3 | 64.3 | -0.10 |
| GerudoValley_Child | GerudoValley_FromLakeHylia_Air | 8.4 | 14.5 | 64.3 | -0.10 |
| GerudoValley_Child | ReturnFromDreamWorld | -39.9 | 101.2 | -24.7 | 0.60 |
| GohmaStage | DefeatBoss | 11.5 | 47.0 | 67.6 | 1.57 |
| GohmaStage | GohmaStage | 6.7 | 47.0 | 67.6 | 1.57 |
| GohmaStage | StartPos_Get_StoneOfForest | 6.7 | 47.0 | 67.6 | 1.57 |
| GohmaStage | StartPos_SubEvent_AllBossBattle | 4.5 | 47.0 | 67.7 | 1.45 |
| GoronCity_Adult |  | 1.7 | 116.0 | 35.2 | 0.03 |
| GoronCity_Adult | EntrancePos | 15.2 | 104.9 | -1.4 | -1.40 |
| GoronCity_Adult | GoronCity_CraterSide | -0.2 | 98.5 | -47.3 | -0.00 |
| GoronCity_Adult | GoronCity_LostWoodSide_after | 15.2 | 104.9 | -1.4 | -1.40 |
| GoronCity_Adult | GoronCity_LostWoodSide_before | 21.7 | 104.9 | -2.5 | -1.40 |
| GoronCity_Adult | GoronCity_MountainTrailSide | 1.7 | 116.0 | 35.2 | -0.03 |
| GoronCity_Adult | ReturnFromDreamWorld | 3.0 | 103.4 | 24.6 | -1.29 |
| GoronCity_Child |  | 1.7 | 116.0 | 35.2 | 0.03 |
| GoronCity_Child | EntrancePos | 15.2 | 104.9 | -1.4 | -1.40 |
| GoronCity_Child | GoronCity_CraterSide | -0.2 | 98.5 | -47.3 | -0.00 |
| GoronCity_Child | GoronCity_LostWoodSide_after | 15.2 | 104.9 | -1.4 | -1.40 |
| GoronCity_Child | GoronCity_LostWoodSide_before | 21.7 | 104.9 | -2.5 | -1.40 |
| GoronCity_Child | GoronCity_MountainTrailSide | 1.7 | 116.0 | 35.2 | -0.03 |
| GoronCity_Child | ReturnFromDreamWorld | 3.0 | 103.4 | 24.6 | -1.29 |
| Graveyard_Adult | 4 | 22.2 | 78.6 | -10.9 | 1.57 |
| Graveyard_Adult | 5 | 24.4 | 78.6 | -10.9 | 1.57 |
| Graveyard_Adult | 6 | 23.3 | 78.6 | -10.9 | 1.57 |
| Graveyard_Adult | EntrancePos | -36.5 | 101.1 | 8.4 | 1.31 |
| Graveyard_Adult | GraveYard_KakarikoSide | -36.5 | 98.0 | 8.5 | 1.55 |
| Graveyard_Adult | GraveYard_KakarikoWindmillSide | -28.5 | 87.7 | 77.6 | 1.57 |
| Graveyard_Adult | GraveYard_ShadowTempleSide | 72.8 | 108.5 | 2.6 | -1.57 |
| Graveyard_Adult | ShadowNocturne | 64.6 | 109.0 | 2.5 | 1.57 |
| Graveyard_Child | EntrancePos | -36.5 | 101.1 | 8.4 | 1.31 |
| Graveyard_Child | Front | -17.3 | 100.0 | 8.4 | 1.57 |
| Graveyard_Child | GraveYard_KakarikoSide | -36.5 | 98.0 | 8.5 | 1.55 |
| Graveyard_Child | GraveYard_ShadowTempleSide | 72.8 | 108.5 | 2.6 | -1.57 |
| Graveyard_Child | Lear | 26.0 | 103.0 | 2.6 | -1.57 |
| Graveyard_Child | ShadowNocturne | 64.6 | 109.0 | 2.5 | 1.57 |
| HountedWasteland_Adult |  | 114.9 | 95.1 | 53.0 | -1.05 |
| HountedWasteland_Adult | EntrancePos | -105.4 | 99.1 | -55.8 | 1.57 |
| HountedWasteland_Adult | HountedWasteland_FromDesertColossus | -103.2 | 99.2 | -55.8 | 1.57 |
| HountedWasteland_Adult | HountedWasteland_FromGerudoFortress | 115.8 | 95.4 | 53.6 | -1.06 |
| HountedWasteland_Child |  | 77.2 | 93.8 | 31.3 | -0.92 |
| HountedWasteland_Child | EntrancePos | -105.4 | 99.1 | -55.8 | 1.57 |
| HountedWasteland_Child | HountedWasteland_FromDesertColossus | -103.2 | 99.2 | -55.8 | 1.57 |
| HyruleCastle |  | 13.3 | 105.3 | -13.2 | 0.09 |
| HyruleCastle | EntrancePos | 13.3 | 105.3 | -13.2 | 0.17 |
| HyruleCastle | HyruleCastle_Entrance | 13.3 | 105.2 | -13.2 | 0.18 |
| HyruleField_Adult |  | 196.9 | 163.4 | 310.5 | -1.13 |
| HyruleField_Adult | EntrancePos | -0.0 | 150.7 | 32.1 | 0.00 |
| HyruleField_Adult | HyruleField_FromLakeHylia | 0.1 | 149.7 | 98.6 | 0.06 |
| HyruleField_Adult | HyruleField_FrontOfGerudoValley | -306.9 | 137.4 | 166.4 | 1.09 |
| HyruleField_Adult | HyruleField_FrontOfKakarikoVillage | 200.4 | 159.4 | 19.3 | -0.88 |
| HyruleField_Adult | HyruleField_FrontOfLostWoodBridge | 198.2 | 163.4 | 309.6 | -1.22 |
| HyruleField_Adult | HyruleField_FrontOfMarket | -0.0 | 150.7 | 32.2 | 0.00 |
| HyruleField_Adult | HyruleField_FrontOfZoraRiver | 213.4 | 159.0 | 137.2 | -0.69 |
| HyruleField_Adult | HyruleField_FrontOfZoraRiver_UnderWater | 202.7 | 155.5 | 148.4 | -0.91 |
| HyruleField_Adult | HyruleField_FrontOfZoraRiver_UnderWater_Air | 202.7 | 156.3 | 148.4 | -0.84 |
| HyruleField_Adult | LakeHylia_FromGerudoValley | -253.5 | 134.0 | 402.2 | 0.63 |
| HyruleField_Adult | LakeHylia_FromGerudoValley_Air | -253.5 | 134.5 | 402.2 | 0.63 |
| HyruleField_Adult | MiniGame_Fishing_PlayerStart | -97.6 | 134.1 | 489.7 | 0.84 |
| HyruleField_Adult | OutsideOfWaterTemple | -183.1 | 103.5 | 496.2 | 0.73 |
| HyruleField_Adult | OutsideOfWaterTemple_Air | -183.1 | 104.5 | 496.2 | 0.73 |
| HyruleField_Adult | ReturnFromDreamWorld | -53.2 | 150.6 | 208.6 | -1.38 |
| HyruleField_Adult | StartPos_Get_Epona_Race | -84.0 | 150.6 | 227.4 | 1.31 |
| HyruleField_Adult | WaterSerenade | -202.3 | 131.7 | 509.8 | 0.73 |
| HyruleField_Adult | WaterTempleEntrancePos | -193.8 | 103.9 | 508.6 | -0.73 |
| HyruleField_Adult | ZoraDomainEntrancePos | -140.4 | 124.4 | 448.6 | -0.75 |
| HyruleField_Adult | ZoraLakeHylia_FromZoraDomain | -141.7 | 124.2 | 450.0 | -0.76 |
| HyruleField_Adult | ZoraLakeHylia_FromZoraDomain_Air | -141.7 | 124.5 | 450.0 | -0.76 |
| HyruleField_Child |  | 197.6 | 163.4 | 310.1 | -1.12 |
| HyruleField_Child | DoorOfTime_MeetImpa_EndPos | 2.6 | 150.3 | 60.2 | 0.99 |
| HyruleField_Child | EntrancePos | -0.0 | 150.7 | 32.1 | 0.00 |
| HyruleField_Child | FindCuccoStartPos | -54.9 | 150.7 | 199.0 | 1.40 |
| HyruleField_Child | HyruleField_FromLakeHylia | 0.1 | 149.7 | 98.6 | 0.06 |
| HyruleField_Child | HyruleField_FrontOfGerudoValley | -306.9 | 137.4 | 166.4 | 1.09 |
| HyruleField_Child | HyruleField_FrontOfKakarikoVillage | 200.4 | 159.4 | 19.3 | -0.88 |
| HyruleField_Child | HyruleField_FrontOfLostWoodBridge | 198.2 | 163.4 | 309.6 | -1.22 |
| HyruleField_Child | HyruleField_FrontOfMarket | -0.0 | 150.7 | 32.2 | 0.00 |
| HyruleField_Child | HyruleField_FrontOfZoraRiver | 213.4 | 159.0 | 137.2 | -0.69 |
| HyruleField_Child | HyruleField_FrontOfZoraRiver_UnderWater | 202.7 | 156.3 | 148.4 | -0.91 |
| HyruleField_Child | LakeHylia_FromGerudoValley | -253.5 | 134.0 | 402.2 | 0.63 |
| HyruleField_Child | LakeHylia_FromGerudoValley_Air | -253.5 | 134.5 | 402.2 | 0.63 |
| HyruleField_Child | MiniGame_Fishing_PlayerStart | -97.6 | 134.1 | 489.7 | 0.84 |
| HyruleField_Child | OutsideOfWaterTemple | -183.1 | 103.5 | 496.2 | 0.73 |
| HyruleField_Child | OutsideOfWaterTemple_Air | -183.1 | 104.5 | 496.2 | 0.73 |
| HyruleField_Child | ReturnFromDreamWorld | -53.2 | 150.6 | 208.6 | -1.38 |
| HyruleField_Child | StartPos_DoorOfTime | -0.1 | 150.4 | 54.2 | -0.00 |
| HyruleField_Child | WaterSerenade | -202.3 | 131.7 | 509.8 | 0.73 |
| HyruleField_Child | WaterTempleEntrancePos | -193.8 | 103.9 | 508.6 | -0.73 |
| HyruleField_Child | ZoraDomainEntrancePos | -140.4 | 124.4 | 448.6 | -0.75 |
| HyruleField_Child | ZoraLakeHylia_FromZoraDomain | -141.7 | 124.2 | 450.0 | -0.76 |
| HyruleField_Child | ZoraLakeHylia_FromZoraDomain_Air | -141.7 | 124.5 | 450.0 | -0.76 |
| IceCavern | EntrancePos | 16.7 | 102.4 | 99.5 | -0.09 |
| IceCavern | EntrancePos2 | -46.9 | 97.6 | 68.7 | -0.00 |
| IceCavern | IceCavern_FromZoraFountain | 16.7 | 102.4 | 99.5 | -0.09 |
| IceCavern | IceCavern_FromZoraFountain_Backdoor | -46.9 | 97.6 | 68.7 | -0.00 |
| IceCavern | IceCavern_FromZoraFountain_Backdoor_Air | -47.1 | 104.7 | 68.7 | -0.00 |
| IceCavern_MQ | EntrancePos | 16.7 | 102.4 | 97.3 | -0.00 |
| IceCavern_MQ | EntrancePos2 | -46.9 | 97.6 | 68.7 | -0.00 |
| IceCavern_MQ | IceCavern_FromZoraFountain | 16.7 | 102.4 | 97.3 | -0.00 |
| IceCavern_MQ | IceCavern_FromZoraFountain_Backdoor | -46.9 | 97.6 | 68.7 | -0.00 |
| IceCavern_MQ | IceCavern_FromZoraFountain_Backdoor_Air | -47.1 | 104.7 | 68.7 | -0.00 |
| InsideGanonCastle |  | 0.2 | 103.8 | 5.4 | 0.01 |
| InsideGanonCastle | Entrance | 0.0 | 110.3 | 91.6 | 0.00 |
| InsideGanonCastle | EntrancePos | 0.0 | 110.2 | 90.0 | 0.00 |
| InsideGanonCastle | StartPos_Defeat_Ganon | 0.0 | 171.1 | -11.3 | 0.00 |
| InsideGanonCastle_MQ |  | 0.2 | 103.8 | 5.4 | 0.01 |
| InsideGanonCastle_MQ | Entrance | 0.0 | 110.3 | 93.6 | 0.00 |
| InsideGanonCastle_MQ | EntrancePos | 0.0 | 110.2 | 91.9 | 0.00 |
| InsideGanonCastle_MQ | StartPos_Defeat_Ganon | 0.1 | 170.5 | -12.4 | 0.00 |
| InsideJabuJabuBelly | EntrancePos | -0.2 | 91.7 | -0.8 | 0.00 |
| InsideJabuJabuBelly | InsideJabuJabuBelly_FromZoraFountain | -0.2 | 91.7 | -0.8 | 0.00 |
| InsideJabuJabuBelly | StartPos_Get_StoneOfWater_MiddleBoss | -26.4 | 84.8 | -89.1 | -0.99 |
| InsideJabuJabuBelly | StartPos_StoneOfWater | 42.4 | 102.0 | -98.1 | -0.00 |
| InsideJabuJabuBelly_MQ | EntrancePos | -0.2 | 91.7 | -0.8 | 0.00 |
| InsideJabuJabuBelly_MQ | InsideJabuJabuBelly_FromZoraFountain | -0.2 | 91.7 | -0.8 | 0.00 |
| InsideJabuJabuBelly_MQ | StartPos_Get_StoneOfWater_MiddleBoss | -26.4 | 84.8 | -89.1 | -0.99 |
| InsideJabuJabuBelly_MQ | StartPos_StoneOfWater | 41.8 | 98.5 | -94.3 | -0.00 |
| InsideTheDekuTree |  | 0.2 | 101.0 | 14.7 | -0.00 |
| InsideTheDekuTree | DefeatBoss | 11.5 | 47.0 | 67.6 | 1.57 |
| InsideTheDekuTree | Entrance | 0.2 | 101.0 | 14.7 | -0.00 |
| InsideTheDekuTree | EntrancePos | 0.2 | 101.0 | 14.7 | -0.00 |
| InsideTheDekuTree | StartPos_Get_StoneOfForest | 6.7 | 47.0 | 67.6 | 1.57 |
| InsideTheDekuTree_MQ |  | 0.2 | 101.0 | 14.1 | -0.00 |
| InsideTheDekuTree_MQ | DefeatBoss | 11.5 | 47.0 | 67.6 | 1.57 |
| InsideTheDekuTree_MQ | Entrance | 0.2 | 101.0 | 14.7 | -0.00 |
| InsideTheDekuTree_MQ | EntrancePos | 0.2 | 101.0 | 14.7 | -0.00 |
| InsideTheDekuTree_MQ | StartPos_Get_StoneOfForest | 6.7 | 47.0 | 67.6 | 1.57 |
| IronKnuckleBlackStage | IronKnuckleBlackStage | 12.4 | 149.7 | -24.7 | -1.57 |
| IronKnuckleBlackStage | StartPos_SubEvent_AllBossBattle | 12.4 | 149.7 | -24.7 | -1.57 |
| IronKnuckleWhiteStage | IronKnuckleWhiteStage | -55.7 | 132.1 | 11.5 | -0.00 |
| IronKnuckleWhiteStage | StartPos_SubEvent_AllBossBattle | -55.7 | 132.1 | 11.5 | -0.00 |
| KakarikoVillage_Adult |  | -94.5 | 97.3 | 49.6 | 1.34 |
| KakarikoVillage_Adult | EntrancePos | -5.8 | 85.2 | 44.2 | -1.57 |
| KakarikoVillage_Adult | HitTargetStartPos | -58.5 | 91.4 | 62.6 | 1.56 |
| KakarikoVillage_Adult | KakarikoVillage_Entrance | -119.8 | 96.6 | 58.7 | 1.56 |
| KakarikoVillage_Adult | KakarikoWindmill_GraveYardSide | 12.8 | 108.0 | 44.3 | -1.57 |
| KakarikoVillage_Adult | Kakariko_GraveYardSide | -1.7 | 101.5 | 68.8 | -1.50 |
| KakarikoVillage_Adult | Kakariko_MountainTrailSide | -41.2 | 110.0 | -16.0 | -0.24 |
| KakarikoVillage_Adult | Kakariko_WellSide | -5.8 | 85.2 | 44.2 | -1.57 |
| KakarikoVillage_Adult | ReturnFromDreamWorld | -45.2 | 108.3 | 103.5 | 1.03 |
| KakarikoVillage_Adult_Alternative |  | -94.5 | 97.3 | 49.6 | 1.34 |
| KakarikoVillage_Adult_Alternative | EntrancePos | -5.8 | 85.2 | 44.2 | -1.57 |
| KakarikoVillage_Adult_Alternative | HitTargetStartPos | -58.5 | 91.4 | 62.6 | 1.56 |
| KakarikoVillage_Adult_Alternative | KakarikoVillage_Entrance | -119.8 | 96.6 | 58.7 | 1.56 |
| KakarikoVillage_Adult_Alternative | KakarikoWindmill_GraveYardSide | 12.8 | 108.0 | 44.3 | -1.57 |
| KakarikoVillage_Adult_Alternative | Kakariko_GraveYardSide | -1.7 | 101.5 | 68.8 | -1.50 |
| KakarikoVillage_Adult_Alternative | Kakariko_MountainTrailSide | -41.2 | 110.0 | -16.0 | -0.24 |
| KakarikoVillage_Adult_Alternative | Kakariko_WellSide | -5.8 | 85.2 | 44.2 | -1.57 |
| KakarikoVillage_Adult_Alternative | ReturnFromDreamWorld | -45.2 | 108.3 | 103.5 | 1.03 |
| KakarikoVillage_Child |  | -94.5 | 97.3 | 49.6 | 1.34 |
| KakarikoVillage_Child | EntrancePos | -5.8 | 85.2 | 44.2 | -1.57 |
| KakarikoVillage_Child | FromMountainTrail | -48.0 | 115.4 | 95.3 | -0.40 |
| KakarikoVillage_Child | KakarikoVillage_Entrance | -119.8 | 96.6 | 58.7 | 1.56 |
| KakarikoVillage_Child | Kakariko_GraveYardSide | -1.7 | 101.5 | 68.8 | -1.50 |
| KakarikoVillage_Child | Kakariko_MountainTrailSide | -41.2 | 110.0 | -16.0 | -0.24 |
| KakarikoVillage_Child | Kakariko_WellSide | -5.8 | 85.2 | 44.2 | -1.57 |
| KakarikoVillage_Child | ReturnFromDreamWorld | -45.2 | 108.3 | 103.5 | 1.03 |
| KokiriForest_Adult |  | -46.1 | 118.5 | 15.6 | 1.40 |
| KokiriForest_Adult | EntrancePos | -32.3 | 121.1 | -65.8 | 0.44 |
| KokiriForest_Adult | FrontDekuTree | 90.0 | 115.5 | -27.9 | -1.43 |
| KokiriForest_Adult | KokiriForest_FrontOfLostWood | -32.3 | 121.1 | -65.8 | 0.44 |
| KokiriForest_Adult | LinkBed | -46.5 | 118.6 | 15.3 | 1.44 |
| KokiriForest_Adult | LostWoodBridge_FrontOfHyruleField | -126.5 | 114.7 | -38.4 | 1.57 |
| KokiriForest_Adult | ReturnFromDreamWorld | -46.5 | 118.5 | 15.4 | 1.49 |
| KokiriForest_Adult | WarpFromForestTemple | 78.3 | 114.8 | -25.6 | 1.31 |
| KokiriForest_Child |  | -46.1 | 118.5 | 15.4 | 1.25 |
| KokiriForest_Child | After_DekuWither | 39.6 | 113.3 | -0.0 | -1.13 |
| KokiriForest_Child | EntrancePos | -32.3 | 121.1 | -65.8 | 0.44 |
| KokiriForest_Child | FrontDekuTree | 90.0 | 115.5 | -27.9 | -1.43 |
| KokiriForest_Child | KokiriForest_FrontOfLostWood | -32.3 | 121.1 | -65.8 | 0.44 |
| KokiriForest_Child | LostWoodBridge_FrontOfHyruleField | -126.5 | 114.7 | -38.4 | 1.57 |
| KokiriForest_Child | ReturnFromDreamWorld | -46.5 | 118.5 | 15.4 | 1.49 |
| KokiriForest_Child | WarpFromDekuTree | 72.2 | 113.9 | -25.5 | 1.45 |
| KokiriForest_Child | WarpFromDekuTree_2 | 65.8 | 112.7 | -24.8 | 1.41 |
| LizalfosStage | LizalfosStage | 92.5 | 99.0 | -38.0 | -0.00 |
| LizalfosStage | StartPos_SubEvent_AllBossBattle | 92.5 | 100.5 | -38.0 | -0.00 |
| LostWood_Adult |  | 0.0 | 100.0 | 5.0 | -0.00 |
| LostWood_Adult | EntrancePos | 0.0 | 100.0 | 2.5 | -0.00 |
| LostWood_Adult | LostWood_Entrance | -0.0 | 100.0 | 5.0 | -0.00 |
| LostWood_Adult | LostWood_FrontOfSacredForestMeadow | 24.0 | 100.0 | -77.1 | -0.00 |
| LostWood_Adult | LostWood_GoronCitySide_after | 24.0 | 100.1 | -29.2 | -0.00 |
| LostWood_Adult | LostWood_GoronCitySide_before | 24.0 | 100.1 | -29.2 | -0.00 |
| LostWood_Adult | LostWood_ZoraRiverSide | 64.5 | 93.0 | -25.6 | -1.57 |
| LostWood_Adult | LostWood_ZoraRiverSide_Air | 64.5 | 94.0 | -25.6 | -1.57 |
| LostWood_Child |  | 0.0 | 100.0 | 5.0 | -0.00 |
| LostWood_Child | EntrancePos | 0.0 | 100.0 | 2.5 | -0.00 |
| LostWood_Child | LostWood_Entrance | -0.0 | 100.0 | 5.0 | -0.00 |
| LostWood_Child | LostWood_FrontOfSacredForestMeadow | 24.0 | 100.0 | -77.1 | -0.00 |
| LostWood_Child | LostWood_GoronCitySide_after | 24.0 | 100.1 | -29.2 | -0.00 |
| LostWood_Child | LostWood_GoronCitySide_before | 24.0 | 100.1 | -29.2 | -0.00 |
| LostWood_Child | LostWood_ZoraRiverSide | 64.5 | 93.0 | -25.6 | -1.57 |
| LostWood_Child | LostWood_ZoraRiverSide_Air | 64.5 | 94.0 | -25.6 | -1.57 |
| Market_Adult |  | -1.9 | 102.1 | 65.2 | -0.00 |
| Market_Adult | EntrancePos | -1.8 | 100.0 | -16.1 | 0.00 |
| Market_Adult | LightPrelude | 84.8 | 104.2 | -34.0 | 1.57 |
| Market_Adult | Market_Entrance | -1.7 | 102.2 | 65.8 | -0.00 |
| Market_Adult | Market_Entrance_FromCastle | -1.8 | 100.0 | -16.1 | 0.00 |
| Market_Child |  | -1.9 | 102.1 | 65.2 | -0.00 |
| Market_Child | BombchuBowlingStartPos | -25.1 | 100.0 | 9.5 | -1.57 |
| Market_Child | EntrancePos | -2.1 | 100.1 | -16.8 | 0.00 |
| Market_Child | GameOverRespawn | -13.7 | 100.1 | 6.8 | 1.57 |
| Market_Child | HitTargetStartPos | -14.2 | 100.1 | -12.4 | -0.00 |
| Market_Child | LightPrelude | 84.8 | 104.2 | -34.0 | 1.57 |
| Market_Child | Market_Entrance | -1.7 | 102.2 | 65.8 | -0.00 |
| Market_Child | Market_FrontOfHyruleCastle | -2.0 | 100.1 | -16.1 | 0.00 |
| Market_Child | MiniGameChoiceTreasureRestartPos | -64.7 | 97.4 | 8.9 | -1.57 |
| Market_Child | ReturnFromDreamWorld | -45.4 | 98.3 | -18.3 | -1.40 |
| Market_Child | StartPos_Market_Item_Bottle_TutorialEvent | 17.6 | 100.1 | 5.8 | 1.48 |
| MegStage | MegStage | 0.0 | 100.0 | 4.4 | -0.00 |
| MegStage | StartPos_SubEvent_AllBossBattle | 0.0 | 100.0 | 4.4 | -0.08 |
| MorphaStage | MorphaStage | 0.2 | 131.4 | -87.1 | -0.76 |
| MorphaStage | StartPos_SubEvent_AllBossBattle | -4.5 | 131.2 | -73.3 | -0.03 |
| NaboruStage | NaboruStage | 0.0 | 135.1 | -80.3 | -0.00 |
| NaboruStage | StartPos_SubEvent_AllBossBattle | 0.0 | 135.1 | -80.3 | -0.00 |
| PhantomGanonStage | PhantomGanonStage | -5.6 | 74.7 | -65.8 | 1.05 |
| PhantomGanonStage | StartPos_SageOfForest | -6.0 | 74.7 | -66.0 | 1.05 |
| PhantomGanonStage | StartPos_SubEvent_AllBossBattle | -5.6 | 74.7 | -65.8 | 1.11 |
| SacredForestMeadow_Adult |  | -6.9 | 100.0 | 74.7 | -0.00 |
| SacredForestMeadow_Adult | EntrancePos | -7.0 | 100.0 | 73.9 | -0.00 |
| SacredForestMeadow_Adult | ForestMinuet | -6.9 | 114.9 | -96.0 | -0.00 |
| SacredForestMeadow_Adult | OutsideOfForestTemple | -7.0 | 119.2 | -116.9 | -0.00 |
| SacredForestMeadow_Adult | SacredForestMeadow_FrontOfLostWood | -7.0 | 100.0 | 74.0 | -0.00 |
| SacredForestMeadow_Child |  | -6.9 | 100.0 | 74.7 | -0.00 |
| SacredForestMeadow_Child | EntrancePos | -7.0 | 100.0 | 73.9 | -0.00 |
| SacredForestMeadow_Child | ForestMinuet | -6.9 | 114.9 | -96.0 | -0.00 |
| SacredForestMeadow_Child | OutsideOfForestTemple | -7.0 | 119.2 | -116.9 | -0.00 |
| SacredForestMeadow_Child | SacredForestMeadow_FrontOfLostWood | -7.0 | 100.0 | 74.0 | -0.00 |
| SageRoom |  | 0.1 | 100.2 | -0.0 | -0.00 |
| ShadowTemple | Entrance | 13.8 | 91.1 | 63.5 | -0.00 |
| ShadowTemple | EntrancePos | 13.8 | 90.3 | 28.0 | 0.00 |
| ShadowTemple | StartPos_SageOfShadow | -138.3 | -11.5 | 22.0 | -0.00 |
| ShadowTemple | StartPos_SageOfShadow_BattleOnShip | 131.2 | 46.0 | -47.7 | -0.00 |
| ShadowTemple | StartPos_SageOfShadow_BeforeBossRoom | -138.5 | 42.0 | 21.2 | -0.00 |
| ShadowTemple_MQ | Entrance | 13.8 | 91.1 | 63.5 | -0.00 |
| ShadowTemple_MQ | EntrancePos | 13.8 | 90.3 | 28.0 | 0.00 |
| ShadowTemple_MQ | StartPos_SageOfShadow | -138.7 | -11.3 | 18.3 | -0.00 |
| SpiritTemple |  | 0.0 | 100.2 | 7.7 | -0.00 |
| SpiritTemple | EntrancePos | -0.0 | 100.2 | 7.7 | -0.00 |
| SpiritTemple | SpiritTemple_Entrance | -0.0 | 100.2 | 7.7 | -0.00 |
| SpiritTemple | SpiritTemple_FromLeftHand | 55.8 | 132.1 | 39.3 | -0.00 |
| SpiritTemple | SpiritTemple_FromRightHand | -55.8 | 132.1 | 39.3 | -0.00 |
| SpiritTemple | StartPos_SageOfSpirit | 0.5 | 136.2 | -75.9 | -0.00 |
| SpiritTemple_MQ |  | 0.0 | 100.2 | 7.7 | -0.00 |
| SpiritTemple_MQ | EntrancePos | -0.0 | 100.2 | 7.7 | -0.00 |
| SpiritTemple_MQ | SpiritTemple_Entrance | -0.0 | 100.2 | 7.7 | -0.00 |
| SpiritTemple_MQ | SpiritTemple_FromLeftHand | 55.8 | 132.1 | 39.3 | -0.00 |
| SpiritTemple_MQ | SpiritTemple_FromRightHand | -55.8 | 132.1 | 39.3 | -0.00 |
| SpiritTemple_MQ | StartPos_SageOfSpirit | 0.5 | 136.2 | -75.9 | -0.00 |
| StalfosStage | StalfosStage | 70.5 | 46.3 | -62.3 | -1.57 |
| StalfosStage | StartPos_SubEvent_AllBossBattle | 70.5 | 46.2 | -62.3 | -1.57 |
| StalfosWeakStage | StalfosWeakStage | -0.0 | 105.5 | -51.5 | -0.00 |
| StalfosWeakStage | StartPos_SubEvent_AllBossBattle | -0.0 | 105.5 | -51.5 | -0.00 |
| TwinrovaStage | StartPos_SubEvent_AllBossBattle | -0.0 | 142.2 | -144.8 | 0.05 |
| TwinrovaStage | TwinrovaStage | -0.7 | 142.2 | -158.6 | 0.79 |
| VolvagiaStage | BossDefeat | -71.2 | 102.5 | 0.0 | -1.57 |
| VolvagiaStage | StartPos_SageOfFire | -64.5 | 102.5 | 0.0 | -1.57 |
| VolvagiaStage | StartPos_SubEvent_AllBossBattle | -64.5 | 102.6 | -0.0 | -1.56 |
| VolvagiaStage | VolvagiaStage | -64.5 | 102.6 | -0.0 | -1.57 |
| WaterTemple |  | -4.5 | 124.2 | 31.4 | -0.00 |
| WaterTemple | StartPos_SageOfWater | -4.5 | 131.4 | -75.3 | -0.00 |
| WaterTemple | StartPos_SageOfWater_MiddleBoss | -78.0 | 125.4 | -42.0 | -0.00 |
| WaterTemple | WaterTemple_FromLakeHylia | -4.5 | 118.6 | 43.6 | -0.00 |
| WaterTemple | WaterTemple_FromLakeHylia_Air | -4.5 | 120.0 | 43.6 | -0.00 |
| WaterTemple_MQ |  | -4.5 | 124.3 | 30.9 | -0.00 |
| WaterTemple_MQ | StartPos_SageOfWater | -4.5 | 131.4 | -74.3 | -0.00 |
| WaterTemple_MQ | StartPos_SageOfWater_MiddleBoss | -78.0 | 125.4 | -42.0 | -0.00 |
| WaterTemple_MQ | WaterTemple_FromLakeHylia | -4.5 | 120.0 | 34.3 | -0.00 |
| WaterTemple_MQ | WaterTemple_FromLakeHylia_Air | -4.5 | 122.0 | 34.3 | -0.00 |
| WolfosStage | StartPos_SubEvent_AllBossBattle | -7.1 | 100.0 | 64.7 | 0.07 |
| WolfosStage | WolfosStage | -7.1 | 100.0 | 64.7 | -0.00 |
| WolfosWhiteStage | StartPos_SubEvent_AllBossBattle | -46.5 | 109.7 | 29.5 | -0.00 |
| WolfosWhiteStage | WolfosWhiteStage | -46.5 | 109.7 | 29.5 | -0.00 |
| ZoraDomain_Adult |  | 4.0 | 103.9 | -42.0 | 0.04 |
| ZoraDomain_Adult | EntrancePos | 1.8 | 93.6 | -3.6 | 1.24 |
| ZoraDomain_Adult | ZoraDomain_FromLakeHylia | 3.3 | 93.6 | -3.7 | 1.24 |
| ZoraDomain_Adult | ZoraDomain_FromLakeHylia_Air | 3.3 | 93.9 | -3.7 | 1.24 |
| ZoraDomain_Adult | ZoraDomain_FromZoraFountain | 89.0 | 119.4 | 15.6 | -1.57 |
| ZoraDomain_Adult | ZoraDomain_FromZoraRiver | 4.5 | 103.9 | -37.0 | 0.13 |
| ZoraDomain_Adult_Alternative |  | 4.0 | 103.9 | -42.0 | 0.04 |
| ZoraDomain_Adult_Alternative | EntrancePos | 1.8 | 93.6 | -3.6 | 1.24 |
| ZoraDomain_Adult_Alternative | ZoraDomain_FromLakeHylia | 3.3 | 93.6 | -3.7 | 1.24 |
| ZoraDomain_Adult_Alternative | ZoraDomain_FromLakeHylia_Air | 3.3 | 93.9 | -3.7 | 1.24 |
| ZoraDomain_Adult_Alternative | ZoraDomain_FromZoraFountain | 89.0 | 119.4 | 15.6 | -1.57 |
| ZoraDomain_Adult_Alternative | ZoraDomain_FromZoraRiver | 4.5 | 103.9 | -37.0 | 0.13 |
| ZoraDomain_Child |  | 4.0 | 103.9 | -42.0 | 0.04 |
| ZoraDomain_Child | EntrancePos | 1.8 | 93.6 | -3.6 | 1.24 |
| ZoraDomain_Child | MiniGame_Diving_PlayerStart | 25.4 | 113.2 | -5.3 | -1.57 |
| ZoraDomain_Child | ZoraDomain_FromLakeHylia | 3.3 | 93.6 | -3.7 | 1.24 |
| ZoraDomain_Child | ZoraDomain_FromLakeHylia_Air | 3.3 | 93.9 | -3.7 | 1.24 |
| ZoraDomain_Child | ZoraDomain_FromZoraFountain | 89.0 | 119.4 | 15.6 | -1.57 |
| ZoraDomain_Child | ZoraDomain_FromZoraRiver | 4.5 | 103.9 | -37.0 | 0.13 |
| ZoraFountain_Adult |  | -11.0 | 101.6 | -24.5 | 1.57 |
| ZoraFountain_Adult | EntrancePos | -11.0 | 101.6 | -24.5 | 1.57 |
| ZoraFountain_Adult | ZoraFountain_FromIceCavern | 47.2 | 107.6 | -62.7 | -0.00 |
| ZoraFountain_Adult | ZoraFountain_FromIceCavern_Backdoor | 42.1 | 88.0 | -53.7 | -1.03 |
| ZoraFountain_Adult | ZoraFountain_FromIceCavern_Backdoor_Air | 41.3 | 89.5 | -53.9 | -1.15 |
| ZoraFountain_Adult | ZoraFountain_FromZoraDomain | -11.0 | 101.6 | -24.5 | 1.57 |
| ZoraFountain_Child |  | -11.0 | 101.6 | -24.5 | 1.57 |
| ZoraFountain_Child | ClearJabuJabu | 53.5 | 104.5 | -6.3 | -1.44 |
| ZoraFountain_Child | EntrancePos | -11.0 | 101.6 | -24.5 | 1.57 |
| ZoraFountain_Child | ZoraFountain_FromInsideJabuJabuBelly | 11.0 | 103.0 | -24.5 | -1.57 |
| ZoraFountain_Child | ZoraFountain_FromZoraDomain | -11.0 | 101.6 | -24.5 | 1.57 |
| ZoraRiver_Adult |  | -77.0 | 97.5 | 14.0 | 0.76 |
| ZoraRiver_Adult | EntrancePos | -85.1 | 97.0 | 20.8 | 0.98 |
| ZoraRiver_Adult | ZoraRiver_Entrance | -90.4 | 96.1 | 25.2 | 0.97 |
| ZoraRiver_Adult | ZoraRiver_Entrance_UnderWater | -81.4 | 94.0 | 29.6 | 0.93 |
| ZoraRiver_Adult | ZoraRiver_FromZoraDomain | 142.0 | 130.5 | -40.7 | -1.57 |
| ZoraRiver_Adult | ZoraRiver_LostWoodSide | 122.6 | 118.0 | -14.1 | -0.00 |
| ZoraRiver_Adult | ZoraRiver_LostWoodSide_Air | 122.6 | 119.0 | -14.1 | -0.00 |
| ZoraRiver_Child |  | -77.0 | 97.5 | 14.0 | 0.76 |
| ZoraRiver_Child | EntrancePos | -85.1 | 97.0 | 20.8 | 0.98 |
| ZoraRiver_Child | ZoraRiver_Entrance | -90.4 | 96.1 | 25.2 | 0.97 |
| ZoraRiver_Child | ZoraRiver_Entrance_UnderWater | -88.2 | 94.6 | 29.4 | 0.49 |
| ZoraRiver_Child | ZoraRiver_FromZoraDomain | 142.0 | 130.5 | -40.7 | -1.57 |
| ZoraRiver_Child | ZoraRiver_LostWoodSide | 122.6 | 118.0 | -14.1 | -0.00 |
| ZoraRiver_Child | ZoraRiver_LostWoodSide_Air | 122.6 | 119.0 | -14.1 | -0.00 |
