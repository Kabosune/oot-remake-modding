# Field enemy spawning: the AutoPlacementMgrParam files

Read from the romfs of build 1.1.1 (11 November 2026). **Nothing here has been tried in game**; meanings are read
from the field names. How to look inside these files: [romfs.md](romfs.md).

Stalchildren, Leevers and Guay (crows) are not placed by hand: most of them don't appear in any scene's placement
file (906 of the game's 8,363 actors in `RSDB/GameActorInfo` are never placed in `Banc/`, among them
`Enemy_Stalchild`, `Enemy_Leever`, `Enemy_Guay_Flock`, `Enemy_Peahat_Larva`). A scene's `GameBancParam` lists
`EnemyAutoPlacementParams`, files that tell a spawner what to create, how many, how often and when the stronger
version comes.

## Where

Ten loose files (uncompressed BYML, no `.zs`, no pack) in `Scene/Component/AutoPlacementMgrParam/`, named
`<Name>.game__scene__AutoPlacementMgrParam.bgyml`. Being loose, a romfs mod can replace one directly at the same
path. Several inherit through `$parent`.

| Scene (`GameBancParam`) | Files it lists |
|---|---|
| `HyruleField_Child` | `Enemy_Stalchild` |
| `HyruleField_Adult` | `Enemy_Stalchild_Adult`, `Enemy_Stalchild_Big_Adult`, `Enemy_Guey_HyruleField_Adult`, `Enemy_Guey_LakeHylia_Adult` |
| `DesertColossus_Adult` | `Enemy_Leever_DesertColossus`, `Enemy_Guay_DesertColossus_Adult` |
| `DesertColossus_Child` | `Enemy_Leever_DesertColossus`, `Enemy_Guay_DesertColossus_Child` |
| `HountedWasteland_Adult` / `_Child` | `Enemy_Leever_HountedWasteland` |
| `BarinadeStage` | lists one too (not read) |

Placed by an area actor in the scene: `StalchildAutoPlacementArea`, and `ForbidAutoPlacementAreaBox / Cylinder / Sphere`
(areas where nothing spawns).

## Fields

Common (counts and times; the unit of the intervals is presumably frames, not checked):

| Field | Meaning (from the name) | Values seen |
|---|---|---|
| `ActorName`, `StrongActorName` | the enemy and its stronger version (`Enemy_Stalchild_Big`, `Enemy_Leever_Big`, `Enemy_Guay_Boss`) | |
| `CreateActorCountMinAtOnce` / `MaxAtOnce` | how many per spawn | Stalchild child max 3; Leever 3 to 5; Guay flock 15 |
| `MinExistActorCountToCreate` | spawn again when fewer than this are alive | Stalchild 1, Leever 4 (0 in the desert), Guay 14 |
| `IntervalToCreateFrame` + `IntervalRandomToCreateFrame` | time between spawns, plus random | Stalchild 180 + 360; Leever 360 + 120, desert 300 + 180 |
| `CreateDistance`, `CreateDistanceRandom`, `CreateHeight` | where from the player | Stalchild 6 ± 2; Leever 6 (desert 10 ± 2); Guay flocks 0 and 6 m up |
| `StrongActorCreatingDefeatCount` | defeats before the strong version comes | Stalchild 10, Leever 10 (desert 20), Guay 0 |
| `IntervalAfterStrongFrame`, `IntervalStrongOnlyFrame` | pause after the strong one | Stalchild 18000, Leever 1800 / 10800, Guay 18000 |
| `StartIntervalMinExistActorCount`, `IsRandomizeMinExistActorCount` | flags | |
| `VelMultiplierForAppearOffset` | spawn farther ahead when the player moves fast | Stalchild 2.5, Leever 2 |
| `CreateType` | a hash (enum value; see [tuning.md](tuning.md) for the hashing) | |

Stalchild only: `CreateMaxAngleToCameraFront` 25 (spawns in the camera's view), `DistanceFromPrevPosToCreate` 80,
`MaxCreateStalchildByFixedSpawn` 5 (adult 6), `IntervalToCreateOnLowSpdFrame` 0.2, `StalchildBigCreate*`, and for
the adult field a line spawn (`StalchildLineSpawn*`: gap 2 to 3, near distance 60, `StalchildOnlyBigSpawn` in the
`_Big_Adult` file). The adult file sets the simple counts to 0 and spawns in lines instead.

Leever only: `LeeverBigSquadModeCreateInfos`, a list of 12 positions around the player (direction 0 to 330 degrees,
distance 3, 5 or 7, `PreparePopUpTime` 28 to 82) for the big squad, `LeeverAppearFovx` 35,
`PreparePopupMinIntervalTime`, `LeeverIntervalToCreateStrong` 30.

Guay only: `GuayFlockLocationType` (a hash; Hyrule Field and Lake Hylia have their own).

## A test

A child Hyrule Field mod that sets `Enemy_Stalchild`'s `CreateActorCountMaxAtOnce` 3 → 12, `IntervalToCreateFrame`
180 → 30 and `MinExistActorCountToCreate` 1 → 6 is one file; [`tools/zsmod.py`](../tools/zsmod.py) edits loose files too:

```
python tools/zsmod.py set Scene/Component/AutoPlacementMgrParam/Enemy_Stalchild.game__scene__AutoPlacementMgrParam.bgyml mod/romfs/Scene/Component/AutoPlacementMgrParam/Enemy_Stalchild.game__scene__AutoPlacementMgrParam.bgyml CreateActorCountMaxAtOnce=12 IntervalToCreateFrame=30 MinExistActorCountToCreate=6
```

(four bytes differ from the original). **Not tried in game.**
