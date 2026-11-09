# Camera

The gameplay camera is an actor, `PlayerCamera` (`Pack/Actor/PlayerCamera.pack.zs`). Its behaviour
is an AINB graph (`AI/PlayerCamera.root.ainb`), and its numbers are `.bgyml` parameter files, so most
camera tuning is a romfs mod and doesn't need code.

Units are metres and degrees.

## Parameter files (inside `PlayerCamera.pack.zs`)

| File / folder | What |
|---|---|
| `Component/PlayerCameraParam/PlayerCamera...bgyml` | global settings and the per-option "variations" (`NormalCameraVariation_Adult` / `_Child`, `HorseCameraVariation_*`), each with `Fovy`, `OffsetYMin`, ... |
| `GameParameter/PlayerCameraParamChase/` | the follow camera per situation: `Normal`, `Normal_Indoor`, `Normal_Swim`, `Crawl`, `Normal_UpSlope`, ... |
| `GameParameter/PlayerCameraParamLockOn/` | Z-targeting, including boss-specific ones (`SituationLockOn_ForTwinrovaBeamReflect`, ...) |
| `GameParameter/PlayerCameraParamAiming/` | first-person-ish aiming: `Bow`, `Hookshot`, `Boomerang`, `FishingRod` |
| `GameParameter/PlayerCameraParamEventTalkOverShoulder/`, `...MultiTalk/` | conversations |
| `GameParameter/PlayerCameraParamHorse/`, `...Tail/`, `...ZoomTarget/` | Epona, climbing, fishing lure |

Most of them have a `_Child` file that `$parent`s the adult one and overrides a few values.

## Numbers worth knowing

| | Adult | Child |
|---|---|---|
| Follow distance (`Normal` → `Radius`) | 4 (range 1.1–10) | 3.5 (max 6.5) |
| `Lat` in `Normal` (probably the default pitch) | 5 | 10 |
| Field of view (`Fovy`, normal camera) | 50° (variations: 50–70°) | same |
| FOV: aiming / talking / indoor / uphill | 40° / 35–37° / 55° / 70° | same |
| Camera look-at height on Link (`PlayerCameraTargetParam` → `TargetHeight`) | **1.68** | **1.17** |

`TargetHeight` comes from Link's own packs (`Component/PlayerCameraTargetParam/Player...bgyml` in
`Player_Base` / `Player_Child`), not the camera's.

## In memory

The view the camera produces each frame is documented in [structures.md](structures.md#camera-view-vtable-0x84c18a88).
`f_804e48c0` builds it, and the First Person mod hooks the end of that function.

## Ideas this enables

- **FOV mod:** raise `Fovy` in the variation and chase files. romfs only, no code.
- **First Person, automatic eye height:** use `TargetHeight` (1.68 / 1.17) and the game's own child
  check (`f_804d6db0(actor)`, see [engine.md](engine.md)) instead of measuring the camera.
- **Closer / further camera:** `Radius` / `RadiusMax` in `PlayerCameraParamChase/Normal*.bgyml`.
