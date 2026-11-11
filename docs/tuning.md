# Tuning data: what the game's own files let a mod change

Read from the romfs of build 1.1.1 (11 November 2026). **Nothing here has been tried in game yet**, and
what a field does is inferred from its name unless said otherwise. How to look inside these files:
[romfs.md](romfs.md).

## 1. Link's movement is a data file

`Pack/Actor/Player_Base.pack.zs` → `Player/PlayerGameParam/Player.game__player__PlayerGameParam.bgyml`
(246 lines). `Player_Adult` carries the same file. `Player_Child` adds
`Player_Child.game__player__PlayerGameParam.bgyml`, which starts with
`$parent: Work/Player/PlayerGameParam/Player...gyml` and overrides about 70 fields. So **bgyml files
inherit through `$parent`**, and a child-only change goes in the child file.

Fields by theme (adult / base values):

| Theme | Fields |
|---|---|
| Jumping | `JumpHeight` 0.7, `JumpGravityScale` 0.55, `StepJumpForwardSpeedMaxMps` 1.7, `LargeLandHeight` 5 |
| Dodges | `BackFlipHeight` 0.35 / `Speed` 6.8 / `GravityScale` 0.8; `SideStep*` 0.4 / 6.6 / 0.7; `FrontStep*`, `BackStep*` |
| Rolling | `RollingMaxSpeed` 6.75 (child 5.625), `RollingMaxSpeedHeavy` 3.375, `RollingTurnStep` 50 |
| Ground | `GroundSpeedScale` 1 (looks like a global speed multiplier: untested), `PlayerStepHeight` 0.45 (child 0.35), `PermitWallAngleMin` 74.9, `MovingOnIceFrame` 60 |
| Ledges | `StartJumpCliffHoldHeight` 2.19, `CliffHoldHeightMaxInAirFirst` 2.13, `DelayClamberFrame` 22 |
| Swimming | `SwimDashSpeedMps` 5, `SwimDashTime` 53, `SwimDiveSpeedMaxMps` 3, `SwimMaxUpSppedMps` 1.8, `SwimVerticalDashSpeed` 2.75 |
| Items | `HoverBootsFloatingTime` 84 (`AfterJump` 42), `HoverBootsAccel` 0.1, `NayruLoveTime` 34, `MPUsePerSecGlassTruth` 2, `ChargeTimeLevel2to3` 90, `HookshotMoveFinishDistanceEnemy` 1.5 |
| Cucco glide | `CuccoGlideGravityScale` 0.25, `MaxFallSpeedMps` 1.7, `MaxSpeedMps` 5.5 |
| Shield aiming | `MoveShieldMaxSpeedNormal` 115, `MoveShieldLimitAngle*` 50, `ControlShieldSensitivity` 5 steps, `GuardBeam*` |
| Camera feel | `SensitivityLat` [1.2, 1.6, 2, 2.4, 3], `SensitivityLat2LngRatio` 1.78 |
| Body | `PlayerHeight` 1.68 (child 1.17), `PlayerShoulderHeight` 1.48 (1.02), `CctRadius` 0.35 (0.23), `AttentionNormalOffsetY` 1.43 (0.91) |

Plain walk / run speed is not a field here (the walk action is one node, `ExecutePlayerMove`, with no
inputs); it is either in code or comes from the animation. `GroundSpeedScale` is the first thing to try.

Checked further on 11 November: `AI/Player.action.walk.module.ainb` (1,169 bytes) holds only the node
`ExecutePlayerMove` (plus the shared `Player.action.common.module` it includes), with no parameter names in it,
so walk speed is not set in the graph either. `AI/Player.scheduler.walk.module.ainb` is the top-level selector,
`SelectorPlayerSchedulerWalk`, with one `ExecuteBSASetActionVerb` branch per action: Walk, Wait, Jump, Fall,
LockOnMove, LockOnWait, BasicAttackCharge, Clamber, CliffHoldJump, PreLift, ThrowObject, PutObject, Slide, Climb,
SideStep, Swim, ChargeAttack, ClimbLadder, WaterDive, Ride, OpenDoor, BackFlip, Rolling, Crawl, PlayMusic,
BasicAttack, RangedAttack, GrabPushPull, UseItem, HookshotShoot, ShowItem, UseDinFire, BootsChange, UseWarpItem,
UseNayruLove, Fishing, UseScrubBusinessSeed, CliffHold, StepOn, UseEmptyBottle, WalkBeforeRide. So the speed is in
`main` (what `ExecutePlayerMove` does) or in the walk / run animation's root motion; reading the code is the way to
tell (needs `main.bin`).

Other files in the same pack:

- `Life/DamageParameters/Player...bgyml`: fall damage (`FallDamageStartHeight` 10, `FallDamagePerMeter`
  0.2, `FallDamageMin` 2, `FallDamageInstaKillHeight` -1), burn / lava / frozen / underwater damage,
  guard angle 120°.
- `Life/LifeParameters`: `MaxLife` 12.
- `GameParameter/BottleHeal`: `RedPotion` 20, `BluePotion` 20, `Fairy` 5, `Milk` 4, `PoeHeal` 3,
  `PoeDamageBig` -3.
- `GameBalance/AttackParam/Player`: one entry per attack type (damage multiplier, impulse 1000, hit
  stop, knockback), enum fields stored as hashes.
- `Phive/CharacterControllerParam/Player`: `GravityScale` 1, `MaxSlopeAngle` 74.9, slope slip settings.
- `Game/PlayerLifterParam`: throw speeds for carried things. `Component/ShooterParam`: pools (20 arrows,
  5 deku nuts, 1 hook).
- `GameParameter/CctComponentPlayerClimbParam`, `CctComponentPlayerRagdollParam`, 32 ragdoll operation
  files, hand / foot / look IK.

## 2. A debug fly mode is still wired into Link's AI

`Player_Base.pack` (and Child) contain `AI/Player.action.debugmove.module.ainb` (node
`ExecutePlayerDebugMove`), plus `sp.` and `sub.` versions, and the main scheduler
`AI/Player.scheduler.module.ainb` has a `SelectorPlayerSchedulerDebug` node with a `DebugMove` branch.
The code exists too: [`symbols/e0f3ccfa-commands.csv`](../symbols/e0f3ccfa-commands.csv) lists
`ExecutePlayerDebugMove` (vtable `0x849e2de8`, binder `0x827f4520`, update slots `0x827f3e60` /
`0x827f4250` / `0x827f4270`) and `ExecutePlayerSubDebugMove`.

Unknown: what makes the selector pick the branch (most likely a debug flag or button the retail build
never sets), and whether the node's body survived. That needs reading the code. If it works, it is a
ready-made noclip.

Other leftovers: `System/GameRomConfig/NormalProduct.game__RomConfig.bgyml` is
`BootupScene: .../FormalScene`, **`UseSceneSelector: False`**; sequence nodes
`SeqExecuteResetGameDataAllForDebug`, `SeqExecuteWaitLoadDebugSave`, `SeqOneShotSetDebugBancParam`,
`SeqOneshotSetVisibleDebugTelop`; `HorseGlobalParam` has `OwnedHorseCreatePosForDebug`
(-87.58, 150.6, 228.79 in `HyruleField`); 55 commands have `Debug` in the name.

## 3. Every script node, with its inputs and defaults

`AI/NodeDefinition/Node.Product.111.aidefn.byml.zs` (5,531 nodes: 1,755 Query, 1,295 Event, 1,158
Execute, about 1,070 OneShot, 229 Selector), `Logic/NodeDefinition/...` (329) and
`Sequence/NodeDefinition/...` (433). Each entry has `Inputs` by type (name → default) and `Tags`.
Example: `OneShotASPlayByPlug` takes `IsIgnoreSameCommand` (True), `PlayRate` (1), `Slot` (0),
`ASCommand`. This complements the commands table (see [script-commands.md](script-commands.md)), which
has the code addresses: together they say which code runs with which arguments. Player warps exist as
event nodes: `EventPlayerWarpToTargetPosAndRot`, `...ToWarpPoint`, `...ToDungeonEntrance`, `...SafePos`,
`...ToTargetActor`.

## 4. Enum values in data files are MurmurHash3 of the name

Checked: MurmurHash3_32, seed 0. `A` = 1423767502, `B` = 3433458314, `None` = 3069107721
(`0xb6eede09`), `Normal` = 957022509 (`0x390b012d`), `Epona` = `0x33394d17`, `EponaSong` = 1578183671,
`SariaSong` = 1714634223. So hashed fields and hashed dictionary keys can be decoded by guessing names,
and written by hashing the name wanted. (The same hash sloperinaGZ found for GameData field names.)

`GameParameter/MelodyScoreBook`: each song is a list of note hashes named after buttons (`A`, `B`, ...),
with `MelodyType` and `NoteNumForNavi`. Song notes can be changed in data.

## 5. Tables

- `RSDB/GameBancInfo`: the 81 scenes. Normal areas come as `_Child` / `_Adult` pairs (plus
  `KakarikoVillage_Adult_Alternative`, `ZoraDomain_Adult_Alternative`); dungeons are single. A
  `DreamWorld` folder holds boss / enemy rematch stages (`GohmaStage`, `DodongoStage`, `BarinadeStage`,
  `PhantomGanonStage`, `VolvagiaStage`, `MorphaStage`, `BongoBongoStage`, `TwinrovaStage`,
  `GanondorfStage`, `GanonStage`, `DarkLinkStage`, `DeadHandStage`, `IronKnuckleBlackStage`,
  `IronKnuckleWhiteStage`, `FlareDancerStage`, `LizalfosStage`, `DinolfosStage`, `StalfosStage`,
  `StalfosWeakStage`, `WolfosStage`, `WolfosWhiteStage`, `GerudoThiefStage`, `MegStage`, `NaboruStage`,
  `BigOctoStage`, `BossRushIntervalRoom`). Also `EnemyMuseum`, `SageRoom`, `FinalBattleField`,
  `CrumblingGanonCastle`, `Demo_ShootingLocation_Tapestry_ED`.
- `RSDB/Challenge` (45): the adventure log. Main quest (`Meet_DekuTree`, `Get_StoneOf*`, `SageOf*`,
  `Defeat_Ganon`, ...), 14 minigames, side events (`SubEvent_AllBossBattle`, `SubEvent_FindRichard`,
  `SubEvent_MaskSalesman`, `SubEvent_RunningRace`, ...). Steps have `IsBossBattle`, `IsMiniGame`,
  `SheikahCameraTarget`, `DestinationPoint`.
- `RSDB/PouchActorInfo` (395 rows): every inventory item: category, tab, child / adult equipment actor,
  bottle content.
- `RSDB/DungeonParam`: rooms per dungeon with Japanese labels and Navi hint steps / timers.
- `GameParameter/HorseGlobalParam`: five gear tables (top speed 12.91 → 22.14 m/s), jump heights.
  `DropGlobalParam`: drop lottery (area ratios, bottle weights). `EnemyGlobalParam`, `KnockBackParam`,
  `NaviMgrGlobalParam` (514 lines), `WmGlobalParam` (468), `GameOverEventList` (which game-over event
  per minigame; `Sequence_IsInDreamWorld`).
- `GameData/GameDataList`: 26 types (Bool, Bool64bitKey, BoolExp, Enum, Int, Float, Struct, Vector3,
  ...), entries of `Hash`, `DefaultValue`, `ResetTypeValue`, `SaveFileIndex`; save size 842,876 bytes.
- `Mals/USen...sarc.zs`: MSBT text. 454 `EventFlowMsg`, 40 `LayoutMsg`, 20 `ChallengeMsg`,
  `ActorMsg/{Enemy,Npc,PouchContent,Nickname}`, 16 `NpcTerrorMsg`, `StaffRollMsg`.
- `Pack/ResidentCommon.pack.zs`: NPC defaults, hit / land / water reaction tables, BGM params,
  `GameBalance/GameBalanceGlobalParam`, `Phive/Config/PhiveConfig.byml`.

## What this opens up

1. **Tuning mods with no code**: moon jump, long hover boots, fast roll, no fall damage, stronger
   potions, faster Epona, different song notes. One edited bgyml inside a repacked
   `Player_Base.pack.zs` (romfs mod). [`tools/zsmod.py`](../tools/zsmod.py) now does the editing and the
   repack ([romfs.md](romfs.md#changing-values-toolszsmodpy)). Value-only edits keep the file size, so the
   resource size table shouldn't need touching.
2. **Changing them live from a module**: the parameter structs are loaded into memory; finding the
   loaded `PlayerGameParam` would allow a settings page without repacking anything.
3. **Debug move** (section 2): find the selector's condition.
4. **Warps and scene lists**: read in [warps.md](warps.md) (how a scene change is placed, and all 465 spawn points).
   Next: try a warp from a module (`NextBancParamName` + `NextStartPosName` is the pair to request).

Suggested first test: `GroundSpeedScale` 1 → 1.5 and `JumpHeight` 0.7 → 2.0 in `Player_Base`, as a
romfs mod. It proves the edit → repack → load path for all of the above in one try. Build it with:

```
F=Player/PlayerGameParam/Player.game__player__PlayerGameParam.bgyml
python tools/zsmod.py set Pack/Actor/Player_Base.pack.zs  mod/romfs/Pack/Actor/Player_Base.pack.zs  --dict Pack/ZsDic.pack.zs "$F:GroundSpeedScale=1.5" "$F:JumpHeight=2.0"
python tools/zsmod.py set Pack/Actor/Player_Child.pack.zs mod/romfs/Pack/Actor/Player_Child.pack.zs --dict Pack/ZsDic.pack.zs "$F:GroundSpeedScale=1.5" "$F:JumpHeight=2.0" "Player/PlayerGameParam/Player_Child.game__player__PlayerGameParam.bgyml:GroundSpeedScale=1.5"
```

`Player_Adult.pack.zs` and `Player_Child.pack.zs` each carry their own copy of the base `Player...bgyml`
(byte-identical to the one in `Player_Base`, checked 11 November; the 493 files `Player_Base` and `Player_Child`
share are all identical), and the child file sets `GroundSpeedScale` itself (1.0) but not `JumpHeight`. Which copy
the game reads is not known, so the test edits every copy (add a third command like the first for
`Player_Adult.pack.zs`); each pack then differs from the original in 5–6 bytes. **Not tried in game.** If Link
doesn't change, the cause is either the field (`GroundSpeedScale` may not be the global speed) or a copy that was
left out; if only one age changes, the copies are read per age.
